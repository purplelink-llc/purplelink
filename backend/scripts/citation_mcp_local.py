#!/usr/bin/env python3
"""Run the citation app's MCP server on this machine only (127.0.0.1), for testing.

  cd backend && python3 scripts/citation_mcp_local.py [port]      # MCP endpoint: http://127.0.0.1:8765/mcp

Then point the MCP Inspector (npx @modelcontextprotocol/inspector, transport "Streamable HTTP") or the MCP
Python client at it. Lookups go to the real Crossref and Semantic Scholar APIs. No rate limit, no storage.
Do not use `modal serve` for this: it publishes a temporary public URL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from latextools import citation_server  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run(citation_server.create_app(rate_check=lambda ip: True), host="127.0.0.1", port=port, log_level="warning")
