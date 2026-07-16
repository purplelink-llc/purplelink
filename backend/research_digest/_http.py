"""Anthropic API helper for the research-digest package (self-contained)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-6"


async def anthropic_message(
    client, *, system: str, user_content: list[dict],
    max_tokens: int, model: str = MODEL, temperature: float = 0.1,
) -> str:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
            "system": system, "messages": [{"role": "user", "content": user_content}]}
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION,
               "content-type": "application/json"}
    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            resp = await client.post(ANTHROPIC_API_URL, json=body, headers=headers,
                timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=5.0))
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_exc = e
            if attempt < 3:
                await asyncio.sleep((attempt ** 2) * 2.0); continue
            raise
        if resp.status_code in (429, 529):
            await asyncio.sleep(float(resp.headers.get("retry-after", attempt * 2)))
            continue
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    raise RuntimeError("anthropic_message: exhausted retries") from last_exc


def parse_json(raw: str) -> Any:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)
    return json.loads(m.group(1) if m else raw)
