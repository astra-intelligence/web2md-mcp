"""
Web2MD MCP Server — Convert URLs to clean Markdown for AI agents.

Free tier: 10 conversions/day.
Unlimited: Set WEB2MD_LICENSE_KEY env var with Gumroad license key.
           Purchase at https://grantshatz.gumroad.com/l/mpkqyq ($1+)

Usage via Claude Desktop config:
{
  "mcpServers": {
    "web2md": {
      "command": "uvx",
      "args": ["web2md-mcp"]
    }
  }
}

With license key:
{
  "mcpServers": {
    "web2md": {
      "command": "uvx",
      "args": ["web2md-mcp"],
      "env": {
        "WEB2MD_LICENSE_KEY": "YOUR_LICENSE_KEY"
      }
    }
  }
}
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

__version__ = "0.3.0"

# Web2MD API endpoint
WEB2MD_API = "http://167.233.135.161:9999/api/convert"
# Gumroad license verification
GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
WEB2MD_PRODUCT_ID = "jr3lFuVibTi21nHekmjDLA=="
# Rate limit: 10 conversions/day for free tier
FREE_TIER_DAILY_LIMIT = 10
# State file for tracking daily usage
STATE_DIR = Path.home() / ".web2md-mcp"
STATE_FILE = STATE_DIR / "usage.json"


def load_state() -> dict:
    """Load usage state from disk."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {"daily_count": 0, "date": time.strftime("%Y-%m-%d")}


def save_state(state: dict):
    """Save usage state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def check_rate_limit() -> tuple[bool, int]:
    """Check if the free tier rate limit has been exceeded.
    Returns (allowed: bool, remaining: int)."""
    state = load_state()
    today = time.strftime("%Y-%m-%d")

    # Reset counter if new day
    if state.get("date") != today:
        state = {"daily_count": 0, "date": today}

    remaining = FREE_TIER_DAILY_LIMIT - state["daily_count"]
    if remaining <= 0:
        return False, 0

    return True, remaining


def increment_usage():
    """Increment the daily usage counter."""
    state = load_state()
    today = time.strftime("%Y-%m-%d")

    if state.get("date") != today:
        state = {"daily_count": 0, "date": today}

    state["daily_count"] += 1
    save_state(state)


def verify_license_key(license_key: str) -> bool:
    """Verify a Gumroad license key via the API."""
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
    """Check if a valid license key is configured."""
    key = os.environ.get("WEB2MD_LICENSE_KEY", "")
    if not key:
        return False
    return verify_license_key(key)


def fetch_url_as_markdown(url: str) -> dict[str, Any]:
    """Convert a URL to clean Markdown via Web2MD API."""
    full_url = f"{WEB2MD_API}?url={urllib.parse.quote(url, safe='')}"
    try:
        req = urllib.request.Request(full_url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return {
                "content": [{"type": "text", "text": data.get("markdown", data.get("content", ""))}],
                "isError": False,
            }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error converting URL: {str(e)}"}],
            "isError": True,
        }


def handle_message(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2026-03-26",
                "capabilities": {
                    "tools": {
                        "web2md_convert": {
                            "name": "web2md_convert",
                            "description": "Convert any public URL to clean, readable Markdown. "
                            "Strips ads, navigation, and boilerplate. "
                            "Returns LLM-ready text perfect for RAG, research, and content extraction. "
                            "Free: 10/day. Unlimited: set WEB2MD_LICENSE_KEY env var.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": {
                                        "type": "string",
                                        "description": "The URL to convert to Markdown"
                                    }
                                },
                                "required": ["url"],
                            },
                        }
                    }
                },
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "web2md_convert",
                        "description": "Convert any public URL to clean, readable Markdown. "
                        "Free: 10 conversions/day. "
                        "Unlimited: set WEB2MD_LICENSE_KEY env var. "
                        "Buy: https://grantshatz.gumroad.com/l/mpkqyq ($1+)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "The URL to convert to Markdown",
                                }
                            },
                            "required": ["url"],
                        },
                    }
                ]
            },
        }

    if method == "tools/call":
        tool_name = req.get("params", {}).get("name", "")
        arguments = req.get("params", {}).get("arguments", {})

        if tool_name == "web2md_convert":
            url = arguments.get("url", "")
            if not url:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": "Error: url parameter is required"}],
                        "isError": True,
                    },
                }

            # Check license key first
            licensed = has_valid_license()

            if not licensed:
                # Check rate limit for free tier
                allowed, remaining = check_rate_limit()
                if not allowed:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": "Free tier limit reached (10 conversions/day). "
                                        "Purchase a license key for unlimited access: "
                                        "https://grantshatz.gumroad.com/l/mpkqyq ($1+) "
                                        "Then set WEB2MD_LICENSE_KEY environment variable."
                            }],
                            "isError": True,
                        },
                    }

            result = fetch_url_as_markdown(url)

            # Only increment usage counter if successful and not licensed
            if not result.get("isError") and not licensed:
                increment_usage()

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return None


def main():
    """MCP server entry point — reads JSON-RPC from stdin, writes to stdout."""
    # Send initial server info
    init = {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {
            "protocolVersion": "2026-03-26",
            "serverInfo": {"name": "web2md-mcp", "version": __version__},
            "capabilities": {
                "tools": {
                    "web2md_convert": {
                        "name": "web2md_convert",
                        "description": "Convert any public URL to clean, readable Markdown. "
                        "Free: 10/day. Unlimited: set WEB2MD_LICENSE_KEY env var.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "The URL to convert to Markdown",
                                }
                            },
                            "required": ["url"],
                        },
                    }
                }
            },
        },
    }
    print(json.dumps(init))
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_message(req)
            if resp:
                print(json.dumps(resp))
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    main()