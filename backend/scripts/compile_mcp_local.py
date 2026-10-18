#!/usr/bin/env python3
"""Run the LaTeX compile app's MCP server on this machine only (127.0.0.1), for testing.

  cd backend && python3 scripts/compile_mcp_local.py [port]      # MCP endpoint: http://127.0.0.1:8766/mcp

Compiles with this Mac's TeX, so latexmk must be on PATH (TinyTeX: ~/Library/TinyTeX/bin/universal-darwin).
Local TeX does not carry the Modal image's texmf.cnf hardening, so only compile your own test documents here.
Point the MCP Inspector (npx @modelcontextprotocol/inspector, transport "Streamable HTTP") or the MCP Python
client at it. No rate limit, nothing stored. Do not use `modal serve`: it publishes a temporary public URL.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TINYTEX = Path.home() / "Library/TinyTeX/bin/universal-darwin"
if TINYTEX.is_dir() and str(TINYTEX) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TINYTEX}:{os.environ.get('PATH', '')}"

import uvicorn  # noqa: E402

from latextools import compile_server  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    uvicorn.run(compile_server.create_app(rate_check=lambda ip: True), host="127.0.0.1", port=port, log_level="warning")
