FROM python:3.12-slim

WORKDIR /app

# Install the package and its runtime deps (mcp, httpx, starlette, uvicorn).
COPY pyproject.toml README.md glama.json server.json ./
COPY src ./src

RUN pip install --no-cache-dir .

# Streamable-http transport port (matches the published MCP remote).
EXPOSE 9998

# Default: run the streamable-http MCP server. Accepts an optional port arg,
# e.g. CMD ["web2md-mcp-http", "9998"].
CMD ["web2md-mcp-http"]
