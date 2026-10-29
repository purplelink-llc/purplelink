#!/usr/bin/env python3
"""Affiliate programs: report, check, apply.

  python3 scripts/affiliates.py report         registry status and where each live program is linked
  python3 scripts/affiliates.py check          registry sanity plus lint of every page; exit 1 on any problem
  python3 scripts/affiliates.py apply          dry run: list pages whose links would change
  python3 scripts/affiliates.py apply --write  rewrite links, add rel=sponsored and the disclosure paragraph
  python3 scripts/affiliates.py health         fetch each paid link's destination (never a tracking URL); exit 1 on a dead one

The registry is backend/digest/affiliates.py. Only programs with status "approved" and a tracked link change
anything. Generated digest pages (site/blog/digest/) are left alone: the digest publisher applies the same rules
when it renders each issue.
"""
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from digest import affiliates as aff  # noqa: E402

SITE = ROOT / "site"
SCAN = ("guides", "blog", "tools", "desk")


def pages():
    for top in SCAN:
        for page in sorted((SITE / top).rglob("*.html")):
            if page.relative_to(SITE).as_posix().startswith("blog/digest/"):
                continue
            yield page


def _hrefs(text: str):
    return [html.unescape(h) for h in re.findall(r'href="([^"]+)"', text)]


def cmd_report() -> int:
    for p in aff.REGISTRY:
        print(f"{p.id:10} {p.status:10} {p.network:18} terms read {p.terms_checked}  {p.commission}")
    for k, v in aff.CLOSED.items():
        print(f"{k:10} closed      {v}")
    print()
    for prog in aff.live_programs():
        where = []
        for page in pages():
            text = page.read_text(encoding="utf-8", errors="replace")
            if any(aff.program_for(h, [prog]) for h in _hrefs(text)):
                where.append(page.relative_to(SITE).as_posix())
        print(f"live: {prog.id}: {len(where)} page(s)")
        for w in where:
            print("   ", w)
    return 0


def cmd_check() -> int:
    problems = [f"registry: {p}" for p in aff.check_registry()]
    for page in pages():
        text = page.read_text(encoding="utf-8", errors="replace")
        for p in aff.lint_html(text):
            problems.append(f"{page.relative_to(SITE).as_posix()}: {p}")
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_apply(write: bool) -> int:
    n_pages = 0
    for page in pages():
        text = page.read_text(encoding="utf-8")
        new, changed = aff.rewrite_html(text)
        if new != text:
            n_pages += 1
            print(f"{'rewrote' if write else 'would rewrite'} {page.relative_to(SITE).as_posix()} ({changed} change(s))")
            if write:
                page.write_text(new, encoding="utf-8")
    print(f"{n_pages} page(s) {'changed' if write else 'would change'}")
    return 0


# A request to a network tracking URL is recorded as a click, so health fetches only what sits behind it.
TRACKING_HOSTS = ("kqzyfj.com", "tkqlhce.com", "jdoqocy.com", "anrdoezrs.com", "dpbolvw.net", "sjv.io")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def health_target(href: str):
    """(URL safe to fetch, what it is), or (None, why it is skipped)."""
    parts = urlsplit(href)
    host = parts.netloc.lower()
    if host.endswith("amazon.com"):
        m = re.match(r"/dp/(\w{10})", parts.path)
        if not m:
            return None, "amazon search link, not a product"
        return f"https://www.amazon.com/dp/{m.group(1)}", "amazon product"
    if any(host == h or host.endswith("." + h) for h in TRACKING_HOSTS):
        dest = parse_qs(parts.query).get("url")
        if dest:
            return dest[0], "deep link destination"
        return None, "fixed tracking link, not fetched: a request counts as a click (check it in the network dashboard)"
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", "")), "referral link, query dropped"


def _paid_links(text: str):
    for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", text, re.S | re.I):
        tag = m.group(0)[: m.group(0).index(">") + 1]
        h = re.search(r'\bhref="([^"]+)"', tag)
        rel = re.search(r'\brel="([^"]*)"', tag)
        if not h:
            continue
        href = html.unescape(h.group(1))
        if (rel and "sponsored" in rel.group(1).split()) or aff.is_tracked(href):
            yield href, " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split())[:60]


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(600_000).decode("utf-8", "replace")
            return r.status, r.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception as e:  # noqa: BLE001 - a network failure is a result here
        return 0, url, type(e).__name__


def cmd_health() -> int:
    rows = []
    for page in sorted(SITE.rglob("*.html")):
        rel = page.relative_to(SITE).as_posix()
        if rel.startswith("blog/digest/"):
            continue
        for href, label in _paid_links(page.read_text(encoding="utf-8", errors="replace")):
            rows.append((rel, href, label))
    seen, dead = {}, 0
    for rel, href, label in rows:
        url, what = health_target(href)
        if url is None:
            print(f"SKIP  {rel}  {label!r}  {what}")
            continue
        if url not in seen:
            status, final, body = _fetch(url)
            title = re.search(r'id="productTitle"[^>]*>\s*([^<]+)', body) or re.search(r"<title[^>]*>([^<]+)", body)
            seen[url] = (status, final, " ".join(html.unescape(title.group(1)).split())[:70] if title else "")
            time.sleep(2)
        status, final, title = seen[url]
        ok = 200 <= status < 300
        flag = "OK  " if ok else ("BLOCK" if status in (403, 429, 503) else "DEAD")
        dead += flag == "DEAD"
        moved = "" if final.rstrip("/") == url.rstrip("/") else f" -> {final}"
        print(f"{flag}  {status}  {rel}  {label!r}  {url}{moved}  [{title}]")
    print(f"{len(rows)} paid link(s), {len(seen)} destination(s) fetched, {dead} dead. "
          "BLOCK means the site refuses scripts; open that one by hand.")
    return 1 if dead else 0


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "report"
    if cmd == "report":
        return cmd_report()
    if cmd == "check":
        return cmd_check()
    if cmd == "apply":
        return cmd_apply("--write" in argv)
    if cmd == "health":
        return cmd_health()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
