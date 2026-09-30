#!/usr/bin/env python3
"""Resolve URLs, DOIs and citations with a script so a model never vouches for them.

Every function takes an optional `fetch(url, method, timeout)` returning
(status, final_url, body_bytes); tests inject one so no network is used.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
REACHABLE = {401, 403, 405, 429}
TITLE_THRESHOLD = 0.6


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def default_fetch(url: str, method: str = "GET", timeout: float = 12):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            body = r.read(200_000) if method == "GET" else b""
            return r.status, r.geturl(), body
    except urllib.error.HTTPError as exc:
        return exc.code, url, b""


def clean_url(url: str) -> str:
    url = url.strip().strip("<>\"'")
    url = url.split("#", 1)[0]
    return url.rstrip(".,;:!?)]}'\"")


def resolve_one(url: str, timeout: float = 12, fetch=None) -> dict:
    fetch = fetch or default_fetch
    u = clean_url(url)
    if not re.match(r"https?://", u):
        return {"ok": False, "status": 0, "final_url": u}
    status, final = 0, u
    for method in ("HEAD", "GET"):
        try:
            status, final, _ = fetch(u, method, timeout)
        except (OSError, ValueError):
            status = 0
            continue
        if status < 400 or status in REACHABLE:
            break
    ok = (0 < status < 400) or status in REACHABLE
    return {"ok": ok, "status": status, "final_url": final}


def resolve_urls(urls, timeout: float = 12, fetch=None) -> dict:
    """Map each input url to {ok, status, final_url}. Keys keep the original text."""
    return {u: resolve_one(u, timeout, fetch) for u in urls}


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def title_ratio(a: str, b: str) -> float:
    """Token overlap as |A and B| / min(|A|, |B|), on lowercased alphanumerics."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def check_doi(doi: str, claimed_title: str | None = None, fetch=None, timeout: float = 12) -> dict:
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I).rstrip(".,;")
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    out = {"doi": doi, "exists": False, "real_title": None, "ratio": None, "match": None}
    try:
        status, _, body = (fetch or default_fetch)(url, "GET", timeout)
    except (OSError, ValueError):
        out["error"] = "network"
        return out
    if status != 200:
        return out
    try:
        titles = json.loads(body)["message"].get("title") or []
    except (ValueError, KeyError, AttributeError):
        out["error"] = "bad response"
        return out
    out["exists"] = True
    out["real_title"] = titles[0] if titles else ""
    if claimed_title is not None:
        out["ratio"] = round(title_ratio(claimed_title, out["real_title"]), 3)
        out["match"] = out["ratio"] >= TITLE_THRESHOLD
    return out


def resolve_citation_list(items, fetch=None) -> list[dict]:
    """items: dicts with optional doi, title, url. Returns one verdict per item."""
    out = []
    for it in items:
        row = {"item": it}
        if it.get("doi"):
            row["doi"] = check_doi(it["doi"], it.get("title"), fetch)
        if it.get("url"):
            row["url"] = resolve_one(it["url"], fetch=fetch)
        row["verified"] = bool(
            (row.get("doi") and row["doi"]["exists"] and row["doi"]["match"] is not False)
            or (not row.get("doi") and row.get("url", {}).get("ok")))
        out.append(row)
    return out
