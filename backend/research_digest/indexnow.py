"""IndexNow ping for getmuscleonglp.com, called after each Modal deploy.

The site had no ping at all: scripts/indexnow_ping.py and the daily indexing job
only cover purplelink.llc, and Search Console shows every weekly roundup since
2026-08-31 as "Discovered - currently not indexed". One POST to the shared
endpoint reaches Bing, Yandex, Seznam and Naver (Google does not use IndexNow).

Best-effort like the Reddit cross-post: the site is already live when this
runs, so a failure logs and returns False instead of failing the job.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

HOST = "getmuscleonglp.com"
# Must match the key file served at the site root (muscleonglp repo, /<KEY>.txt).
KEY = "6109bfd0fb0b9381a37e6faaa1e4a689"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def build_payload(urls: list[str]) -> dict:
    """The IndexNow body for *urls*, keeping only this host's URLs, deduped in order."""
    seen: list[str] = []
    for u in urls:
        if u.startswith(f"https://{HOST}/") and u not in seen:
            seen.append(u)
    return {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": seen}


async def ping(client, urls: list[str]) -> bool:
    """Submit *urls*. Returns True when IndexNow accepted them (200 or 202)."""
    body = build_payload(urls)
    if not body["urlList"]:
        logger.info("indexnow: nothing to ping")
        return False
    try:
        resp = await client.post(ENDPOINT, json=body, timeout=20)
    except Exception as err:  # noqa: BLE001 - never let a ping break a run
        logger.warning("indexnow: ping failed (%s)", err)
        return False
    if resp.status_code in (200, 202):
        logger.info("indexnow: pinged %d url(s)", len(body["urlList"]))
        return True
    logger.warning("indexnow: ping rejected (%s)", resp.status_code)
    return False
