# Web2MD MCP Server

**Convert any URL to clean Markdown — directly from your AI agent.**

An MCP (Model Context Protocol) server that converts public webpages to clean, readable Markdown. Strips ads, navigation, and boilerplate — returns LLM-ready text perfect for RAG, research, and content extraction.

Works with **Claude Desktop, Cursor, Continue.dev, Windsurf, and any MCP-compatible client**.

## Quick Start

### From source (GitHub)

```bash
git clone https://github.com/astra-intelligence/web2md-mcp.git
cd web2md-mcp
pip install .
# or: uv sync
```

### Using pip (once published)

> ⏳ Pending PyPI publication. Until then, use the source install above.

```bash
pip install web2md-mcp
```

### Using uvx (once published)

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "web2md": {
      "command": "uvx",
      "args": ["web2md-mcp"]
    }
  }
}
```

## Usage

The server provides one tool: **`web2md_convert`**

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | The public URL to convert to Markdown |

### Example

```json
{
  "url": "https://example.com/article"
}
```

Returns clean Markdown content ready for LLM consumption.

## Requirements

- Python 3.10+
- Internet access to reach the Web2MD API at `167.233.135.161:9999`

## About Web2MD

Web2MD is a URL-to-Markdown conversion API running at **167.233.135.161:9999**. This MCP server wraps the API so AI agents can use it directly.

**Free tier:** 10 conversions/day per IP — no signup, no API key.

👉 **Get unlimited access on Gumroad: [https://grantshatz.gumroad.com/l/mpkqyq](https://grantshatz.gumroad.com/l/mpkqyq)** ($1+)

## Direct API Usage

You can also use the API directly without the MCP server:

```bash
curl "http://167.233.135.161:9999/api/convert?url=https://example.com/"
```

Free tier: 10/day/IP. Add `?license_key=YOUR_KEY` for unlimited access.

## License

MIT

---

## Support

If you find this project useful, consider [buying me a coffee](https://buymeacoffee.com/grantshatzer) or [sponsoring on GitHub](https://github.com/sponsors/astra-intelligence).

Check out more tools at [grantshatz.gumroad.com](https://grantshatz.gumroad.com).

