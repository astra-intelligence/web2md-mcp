"""
Web2MD MCP Server — streamable-http transport (mcp 2.x).

Wraps the Web2MD REST API (http://167.233.135.161:9999/api/convert) as an MCP
server so AI agents can convert URLs to clean Markdown. Free tier 10/day/IP;
unlimited via Gumroad license key (WEB2MD_LICENSE_KEY env var).

Run:  web2md-mcp-http [port]
"""
import json
import os
import sys
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

WEB2MD_API = "http://167.233.135.161:9999/api/convert"
GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
WEB2MD_PRODUCT_ID = "jr3lFuVibTi21nHekmjDLA=="
UPGRADE_URL = "https://grantshatz.gumroad.com/l/mpkqyq"


def verify_license_key(license_key: str) -> bool:
    try:
        data = urllib.parse.urlencode({
            "product_id": WEB2MD_PRODUCT_ID,
            "license_key": license_key,
            "increment_uses_count": True,
        }).encode()
        req = urllib.request.Request(GUMROAD_VERIFY_URL, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get("success", False)
    except Exception:
        return False


def has_valid_license() -> bool:
    key = os.environ.get("WEB2MD_LICENSE_KEY", "")
    if not key:
        return False
    return verify_license_key(key)


def fetch_url_as_markdown(url: str) -> str:
    full_url = f"{WEB2MD_API}?url={urllib.parse.quote(url, safe='')}"
    try:
        req = urllib.request.Request(full_url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            md = data.get("markdown", data.get("content", ""))
            # Surface the freemium wall to agents instead of silently
            # returning empty text: free tier exhausted -> upgrade prompt.
            if data.get("limit_reached"):
                return (
                    data.get("message", "Free tier limit reached.")
                    + " --- Upgrade for unlimited access (one-click, $1): "
                    + data.get("upgrade_url", UPGRADE_URL)
                )
            # Show remaining free quota on success so agents can pace usage.
            remaining = data.get("remaining_free")
            if remaining is not None:
                try:
                    remaining = int(remaining)
                    if remaining <= 3:
                        md = md.rstrip() + f"\n\n[Web2MD: {remaining} free conversions left today. Unlimited: {UPGRADE_URL} ($1)]"
                except (TypeError, ValueError):
                    pass
            return md or "(empty conversion)"
    except Exception as e:
        return f"Error converting URL: {str(e)}"


server = MCPServer(
    name="web2md-mcp",
    version="0.3.5",
    instructions=(
        "Convert any public URL to clean Markdown. Free tier: 10/day. "
        f"Unlimited via Gumroad license: {UPGRADE_URL}"
    ),
)


@server.tool(
    name="web2md_convert",
    description=(
        "Convert any public URL to clean, readable Markdown. Strips ads, "
        "navigation, and boilerplate. Returns LLM-ready text for RAG, "
        "research, and content extraction. Free: 10/day. Unlimited: set "
        f"WEB2MD_LICENSE_KEY env var. Buy: {UPGRADE_URL} ($1+)"
    ),
)
async def web2md_convert(url: str) -> str:
    """Convert a public URL to clean Markdown."""
    return fetch_url_as_markdown(url)


@server.tool(
    name="web2md_convert_batch",
    description=(
        "Convert multiple public URLs to clean Markdown in one call (Web2MD Pro). "
        "Requires a WEB2MD_LICENSE_KEY env var (buy: " + UPGRADE_URL + " $1). "
        "Returns a list of {url, success, markdown} results. Free tier is single-URL only."
    ),
)
async def web2md_convert_batch(urls: list) -> str:
    """Convert a list of URLs to clean Markdown (Pro feature, needs license key)."""
    if not has_valid_license():
        return ("Batch processing is a Web2MD Pro feature. Set WEB2MD_LICENSE_KEY "
                "to your $1 Gumroad license key to unlock unlimited conversions + batch. "
                f"Buy: {UPGRADE_URL}")
    if not urls:
        return "No URLs provided."
    out = []
    for u in urls[:50]:
        out.append(f"## {u}\n\n" + fetch_url_as_markdown(u))
    return "\n\n".join(out)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9998
    print(f"Web2MD MCP streamable-http starting on port {port}", flush=True)
    server.run(transport="streamable-http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
