"""
Backward-compatible entry point: python src/web2md_mcp_http.py [port].

The packaged server lives in web2md_mcp.http_server; this file keeps the
original invocation path working for the live tunnel process.
"""
from web2md_mcp.http_server import main

if __name__ == "__main__":
    main()
