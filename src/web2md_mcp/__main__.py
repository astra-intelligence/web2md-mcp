"""
Web2MD MCP Server — Convert URLs to clean Markdown for AI agents.

Model Context Protocol (MCP) server that wraps the Web2MD API.
Works with Claude Desktop, Cursor, Continue.dev, and any MCP-compatible client.

Usage via Claude Desktop config:
{
  "mcpServers": {
    "web2md": {
      "command": "uvx",
      "args": ["web2md-mcp"]
    }
  }
}

Get Web2MD: https://grantshatz.gumroad.com/l/mpkqyq ($1)
"""

__version__ = "0.1.0"

import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Any


# Web2MD API endpoint
WEB2MD_API = "http://167.233.135.161:9999/api/convert"


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
                            "Returns LLM-ready text perfect for RAG, research, and content extraction.",
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
                        "Strips ads, navigation, and boilerplate. Returns LLM-ready text.",
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
            result = fetch_url_as_markdown(url)
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
                        "description": "Convert any public URL to clean, readable Markdown.",
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