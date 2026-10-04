"""Web2MD Backend — URL to Markdown converter with freemium API."""

import json, os, sys, re, time, socket, ipaddress
from collections import defaultdict
from datetime import date
from urllib.parse import urlparse
from io import BytesIO
import requests
import trafilatura
import html2text
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# --- Configuration ---
GUMROAD_PRODUCT_ID = "jr3lFuVibTi21nHekmjDLA=="  # Web2MD product
GUMROAD_PRODUCT_PERMALINK = "mpkqyq"              # Web2MD Gumroad permalink
GUMROAD_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "p-Uf5GJw5bzyfKFkXIq6NtKzxCD_RfcswhqZr1Hd4nI")
FREE_DAILY_LIMIT = 10  # Free tier: 10 conversions/day per IP

# Durable usage log (JSONL) so the funnel can be measured across restarts.
USAGE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.log")

def _log_usage(event: str, ip: str, url: str = "", license_key: str = "", **extra):
    """Append one line to the usage log. Never raises."""
    try:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "ip": ip,
            "url": url[:200],
            "has_license": bool(license_key),
        }
        rec.update(extra)
        with open(USAGE_LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass

# In-memory rate limit tracker
# Structure: {ip: {"date": date_obj, "count": int}}
rate_limits: dict = {}


def _get_client_ip() -> str:
    """Get the real client IP from headers (respecting proxies)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


# Private / loopback / link-local / metadata networks that a public converter
# must never fetch (SSRF protection).
_BLOCKED_NETS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def _url_blocked(url: str):
    """Return an error string if the URL targets a non-public address, else None."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return "Only http/https URLs are supported"
        host = parsed.hostname
        if not host:
            return "Invalid URL"
        # Resolve to IPs (literal IPs resolve to themselves).
        try:
            ips = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                ips = [ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(host, None)]
            except Exception:
                return "Could not resolve host"
        for ip in ips:
            for net in _BLOCKED_NETS:
                if ip in net:
                    return "URL target is not publicly reachable"
    except Exception as e:
        return f"Invalid URL: {e}"
    return None


def _is_license_valid(license_key: str) -> bool:
    """Verify a Gumroad license key against the Web2MD product."""
    if not license_key:
        return False
    try:
        resp = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={
                "product_permalink": GUMROAD_PRODUCT_PERMALINK,
                "license_key": license_key,
            },
            timeout=15,
        )
        result = resp.json()
        # Check purchase is valid and matches our product
        if result.get("success"):
            purchase = result.get("purchase", {})
            purchase_product_id = purchase.get("product_id", "")
            purchase_permalink = purchase.get("permalink", "")
            # Match by product_id (stable) or permalink
            if purchase_product_id == GUMROAD_PRODUCT_ID:
                return True
            if purchase_permalink == GUMROAD_PRODUCT_PERMALINK:
                return True
        return False
    except Exception:
        return False


def _check_rate_limit(ip: str, license_key: str = "") -> tuple[bool, int]:
    """
    Check rate limit for the given IP.
    Returns (allowed: bool, remaining_free: int).
    A valid license_key bypasses rate limits entirely.
    """
    # License holders bypass rate limiting
    if license_key and _is_license_valid(license_key):
        return True, -1  # -1 means unlimited

    today = date.today()
    entry = rate_limits.get(ip)

    if entry is None or entry["date"] != today:
        rate_limits[ip] = {"date": today, "count": 0}
        entry = rate_limits[ip]

    if entry["count"] >= FREE_DAILY_LIMIT:
        return False, 0

    entry["count"] += 1
    remaining = FREE_DAILY_LIMIT - entry["count"]
    return True, remaining


def fetch_as_markdown(url):
    """Fetch a URL and convert its content to clean markdown."""
    try:
        # First try trafilatura for clean content extraction
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                output_format="markdown",
                include_links=True,
                include_images=False,
            )
            if text and len(text) > 50:
                return {
                    "success": True,
                    "markdown": text,
                    "title": extract_title(downloaded),
                    "url": url,
                    "char_count": len(text),
                }

        # Fallback: use requests + html2text
        resp = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Web2MD/1.0; +https://github.com/astra-intelligence/saas-landing-page-template)"
            },
        )
        resp.raise_for_status()
        html = resp.text

        converter = html2text.HTML2Text()
        converter.body_width = 0
        converter.ignore_links = False
        converter.ignore_images = True
        converter.ignore_emphasis = False
        converter.protect_links = True
        converter.unicode_snob = True
        converter.skip_internal_links = True
        converter.inline_links = True
        md = converter.handle(html)

        if not md or len(md.strip()) < 50:
            from html import unescape

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", unescape(text))
            md = text.strip()[:10000]

        title = extract_title(html)

        return {
            "success": True,
            "markdown": md.strip(),
            "title": title,
            "url": url,
            "char_count": len(md.strip()),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def extract_title(html):
    """Extract the <title> from HTML."""
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return match.group(1).strip() if match else ""


# ============================================================
# Routes
# ============================================================


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/convert")
def convert():
    url = request.args.get("url", "")
    license_key = request.args.get("license_key", "")

    if not url:
        return jsonify({"success": False, "message": "No URL provided. Usage: /api/convert?url=https://example.com/"}), 400

    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return jsonify({"success": False, "message": "Invalid URL"}), 400

    # SSRF guard: never fetch internal/private targets
    blocked = _url_blocked(url)
    if blocked:
        return jsonify({"success": False, "message": blocked}), 400

    # Rate limiting
    ip = _get_client_ip()
    allowed, remaining = _check_rate_limit(ip, license_key)

    if not allowed:
        _log_usage("limit_reached", ip, url, license_key, remaining=0)
        return jsonify(
            {
                "success": False,
                "message": f"Free tier limit reached ({FREE_DAILY_LIMIT}/day). "
                f"Get unlimited access: https://grantshatz.gumroad.com/l/mpkqyq",
                "limit_reached": True,
                "limit": FREE_DAILY_LIMIT,
                "remaining": 0,
                "upgrade_url": "https://grantshatz.gumroad.com/l/mpkqyq",
            }
        )

    result = fetch_as_markdown(url)
    _log_usage("convert", ip, url, license_key, remaining=remaining, char_count=result.get("char_count", 0))
    result["remaining_free"] = remaining
    result["limit"] = FREE_DAILY_LIMIT
    result["upgrade_url"] = "https://grantshatz.gumroad.com/l/mpkqyq"
    return jsonify(result)


@app.route("/api/verify-license", methods=["POST"])
def verify_license():
    data = request.get_json()
    license_key = data.get("license_key", "")
    product_permalink = data.get("product_permalink", GUMROAD_PRODUCT_PERMALINK)

    if not license_key:
        return jsonify({"success": False, "valid": False, "message": "No license key provided"})

    try:
        resp = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={
                "product_permalink": product_permalink,
                "license_key": license_key,
            },
            timeout=15,
        )
        result = resp.json()
        purchase = result.get("purchase", {})
        pid = purchase.get("product_id", "")
        perm = purchase.get("permalink", "")

        if result.get("success") and (pid == GUMROAD_PRODUCT_ID or perm == GUMROAD_PRODUCT_PERMALINK):
            return jsonify({"success": True, "valid": True, "purchase": {"email": purchase.get("email", "")}})
        else:
            return jsonify({"success": True, "valid": False, "message": "Invalid license key"})
    except Exception as e:
        return jsonify({"success": False, "valid": False, "message": str(e)})


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json()
    license_key = data.get("license_key", "")
    markdown = data.get("markdown", "")
    product_permalink = data.get("product_permalink", GUMROAD_PRODUCT_PERMALINK)

    if not _is_license_valid(license_key):
        return jsonify({"success": False, "message": "Invalid license"})

    buf = BytesIO(markdown.encode("utf-8"))
    return send_file(
        buf,
        as_attachment=True,
        download_name="converted.md",
        mimetype="text/markdown",
    )


@app.route("/api/status")
def status():
    """Public status endpoint showing the API health."""
    ip = _get_client_ip()
    entry = rate_limits.get(ip, {"date": None, "count": 0})
    is_same_day = entry["date"] == date.today()
    return jsonify(
        {
            "status": "ok",
            "version": "2.0",
            "free_daily_limit": FREE_DAILY_LIMIT,
            "used_today": entry["count"] if is_same_day else 0,
            "upgrade_url": "https://grantshatz.gumroad.com/l/mpkqyq",
        }
    )


@app.route("/api")
@app.route("/api/")
def api_docs():
    return jsonify(
        {
            "name": "Web2MD API",
            "version": "2.0",
            "free_daily_limit": FREE_DAILY_LIMIT,
            "upgrade_url": "https://grantshatz.gumroad.com/l/mpkqyq",
            "endpoints": {
                "convert": {
                    "method": "GET",
                    "path": "/api/convert",
                    "params": {
                        "url": "URL to convert (required)",
                        "license_key": "Optional — bypass rate limit with Gumroad license",
                    },
                    "example": "/api/convert?url=https://example.com/",
                },
                "verify-license": {
                    "method": "POST",
                    "path": "/api/verify-license",
                    "body": '{"license_key": "xxx", "product_permalink": "mpkqyq"}',
                },
                "status": {
                    "method": "GET",
                    "path": "/api/status",
                    "description": "Check API health and your usage",
                },
            },
        }
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Web2MD v2.0 running on http://0.0.0.0:{port}")
    print(f"Free tier: {FREE_DAILY_LIMIT} conversions/day/IP")
    print(f"Upgrade: https://grantshatz.gumroad.com/l/mpkqyq")
    app.run(host="0.0.0.0", port=port, debug=False)