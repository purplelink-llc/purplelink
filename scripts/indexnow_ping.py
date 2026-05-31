#!/usr/bin/env python3
"""IndexNow ping for purplelink.llc.

Reads the sitemap, optionally diffs against the last ping, and pings the
IndexNow shared endpoint (https://api.indexnow.org/IndexNow) with the URLs
that changed. Bing, Yandex, Seznam, and Naver subscribe to the shared
endpoint, so a single POST covers all of them.

Usage:
    # Ping all URLs in the sitemap (use sparingly — limit ~10,000/day):
    python scripts/indexnow_ping.py --all

    # Ping only URLs whose lastmod is today (default behaviour):
    python scripts/indexnow_ping.py

    # Ping a specific URL list:
    python scripts/indexnow_ping.py https://purplelink.llc/guides/latex/ ...

Run after a netlify deploy. The IndexNow key file already lives at
site/<key>.txt; the constant below matches.
"""
import datetime
import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# macOS Python ships without a CA bundle by default; use certifi if available
# to avoid SSL verify failures. Falls back to system default if certifi is
# missing (Linux + Modal container both have one wired up correctly).
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

HOST = "purplelink.llc"
KEY = "7c6ea98702bc415eccb029b334bc63fef6905e06458c01f93ea762fa140019cf"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/IndexNow"
SITEMAP_PATH = Path(__file__).parent.parent / "site" / "sitemap.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def urls_from_sitemap(only_today=True):
    """Return URLs from sitemap.xml. If only_today, filter to those with
    lastmod == today's date (the typical post-deploy pattern)."""
    today = datetime.date.today().isoformat()
    tree = ET.parse(SITEMAP_PATH)
    urls = []
    for url in tree.getroot().findall("sm:url", NS):
        loc = url.findtext("sm:loc", default="", namespaces=NS)
        lastmod = url.findtext("sm:lastmod", default="", namespaces=NS)
        if not loc:
            continue
        if only_today and lastmod != today:
            continue
        urls.append(loc)
    return urls


def ping(urls):
    if not urls:
        print("No URLs to ping.")
        return
    body = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    import json
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as resp:
            print(f"IndexNow {resp.status} {resp.reason}: pinged {len(urls)} URL(s)")
            for u in urls:
                print(f"  · {u}")
    except urllib.error.HTTPError as e:
        # IndexNow returns 200 on success, 202 accepted, 400 bad-request, 422 unprocessable, 429 too-many.
        body = e.read().decode("utf-8", errors="replace")[:400]
        print(f"IndexNow {e.code}: {body}")
    except urllib.error.URLError as e:
        print(f"IndexNow network error: {e}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        urls = urls_from_sitemap(only_today=False)
    elif args and args[0].startswith("http"):
        urls = args
    else:
        urls = urls_from_sitemap(only_today=True)
    ping(urls)


if __name__ == "__main__":
    main()
