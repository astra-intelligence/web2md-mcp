# Web2MD MCP Server

**Convert any URL to clean Markdown — directly from your AI agent.**

An MCP (Model Context Protocol) server that converts public webpages to clean, readable Markdown. Strips ads, navigation, and boilerplate — returns LLM-ready text perfect for RAG, research, and content extraction.

Works with **Claude Desktop, Cursor, Continue.dev, Windsurf, and any MCP-compatible client**.

## Quick Start

### Using uvx (recommended)

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

### Using pip

```bash
pip install web2md-mcp
```

Then configure your MCP client to use the `web2md-mcp` command.

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

Web2MD is a URL-to-Markdown conversion API. This MCP server wraps the API so AI agents can use it directly.

👉 **Get Web2MD on Gumroad: [https://grantshatz.gumroad.com/l/mpkqyq](https://grantshatz.gumroad.com/l/mpkqyq)** ($1)

The Web2MD API runs 24/7, requires no authentication, and is backed by robust readability extraction.

## License

MIT