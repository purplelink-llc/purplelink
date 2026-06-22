# backend/digest/_http.py
"""Anthropic API call helper for the digest package.

Self-contained so `digest` has no dependency on `latextools`. Retries
transient failures (429, 529, timeouts) with exponential backoff.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DIGEST_MODEL = "claude-sonnet-4-6"


async def anthropic_message(
    client,
    *,
    system: str,
    user_content: list[dict],
    max_tokens: int,
    model: str = DIGEST_MODEL,
    temperature: float = 0.2,
) -> str:
    """Call Anthropic /v1/messages and return assistant text.

    client: httpx.AsyncClient managed by caller.
    """
    import asyncio
    import httpx

    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    max_attempts = 3
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.post(
                ANTHROPIC_API_URL, json=body, headers=headers,
                timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=5.0),
            )
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_exc = e
            if attempt < max_attempts:
                await asyncio.sleep((attempt ** 2) * 2.0)
                continue
            raise
        if resp.status_code in (429, 529):
            retry_after = float(resp.headers.get("retry-after", attempt * 2))
            logger.warning("Anthropic rate-limited, retrying in %.0fs", retry_after)
            if attempt < max_attempts:
                await asyncio.sleep(retry_after)
                continue
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    raise RuntimeError("anthropic_message: exhausted retries") from last_exc


def parse_json(raw: str) -> Any:
    """Extract JSON from a string that may have surrounding prose."""
    import re
    # Strip markdown code fences.
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    return json.loads(raw)
