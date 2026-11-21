"""Log who calls a public MCP endpoint: one line per POST /mcp with the JSON-RPC method, the client name from
`initialize`, and a truncated User-Agent. No IP, no tool arguments, no reference or LaTeX text.

The line exists so steady idle traffic (registry crawlers, connector refreshes) can be told apart from real use.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("mcp.caller")

_UA_MAX = 80
_NAME_MAX = 40


def _summary(body: bytes) -> tuple[str, str]:
    """(method, client name) from the first body chunk; '?' when it is not a JSON-RPC object."""
    try:
        msg = json.loads(body)
    except Exception:
        return "?", ""
    if isinstance(msg, list):
        return f"batch[{len(msg)}]", ""
    if not isinstance(msg, dict):
        return "?", ""
    method = str(msg.get("method") or "?")[:_NAME_MAX]
    client = ""
    if method == "initialize":
        info = (msg.get("params") or {}).get("clientInfo") or {}
        if isinstance(info, dict):
            client = f"{str(info.get('name', ''))[:_NAME_MAX]}/{str(info.get('version', ''))[:16]}"
    return method, client


class CallerLog:
    """Pure ASGI middleware; passes every message through unchanged."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST" or not scope.get("path", "").startswith("/mcp"):
            return await self.app(scope, receive, send)

        ua = ""
        for k, v in scope.get("headers") or []:
            if k == b"user-agent":
                ua = v.decode("latin-1")[:_UA_MAX]
                break
        logged = False

        async def tap():
            nonlocal logged
            message = await receive()
            if not logged and message.get("type") == "http.request":
                logged = True
                method, client = _summary(message.get("body", b""))
                log.info("mcp call method=%s client=%s ua=%r", method, client or "-", ua)
            return message

        return await self.app(scope, tap, send)
