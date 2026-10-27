#!/usr/bin/env python3
"""Rank LaTeX error messages by how many people hit them, to decide which one gets the next page and video.

Why not Search Console: the twelve error pages are two weeks old and only two have any impressions yet (123 in
90 days), so it cannot say which topic to pick. The proxy used instead is TeX Stack Exchange: for each error
phrase, the questions whose TITLE contains every word of the phrase, summed by view_count (lifetime views, so
it measures how many people landed on those questions, not how many asked). It is a relative index, not a search
volume: compare topics with each other, never read the number as monthly searches.

  python3 scripts/latex_error_demand.py                     # rank all candidates, print a table
  python3 scripts/latex_error_demand.py --write              # also write docs/growth-briefs/latex-error-demand-<date>.md
  python3 scripts/latex_error_demand.py --only 5             # top 5 uncovered topics only

The Stack Exchange API is public and unauthenticated (300 requests a day; this uses one per candidate and honours
the `backoff` field). A candidate that has a page in site/latex-errors/<slug>/ is marked covered.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.stackexchange.com/2.3/search"

# (slug, words that must all appear in a question title, the error as it prints)
CANDIDATES = [
    ("undefined-control-sequence", "undefined control sequence", "Undefined control sequence"),
    ("missing-dollar-inserted", "missing $ inserted", "Missing $ inserted"),
    ("file-not-found", "file not found", "File `x.sty' not found"),
    ("environment-undefined", "environment undefined", "Environment x undefined"),
    ("missing-begin-document", "missing begin document", "Missing \\begin{document}"),
    ("extra-alignment-tab", "extra alignment tab", "Extra alignment tab has been changed to \\cr"),
    ("misplaced-alignment-tab", "misplaced alignment tab", "Misplaced alignment tab character &"),
    ("overfull-hbox", "overfull hbox", "Overfull \\hbox"),
    ("paragraph-ended-before-complete", "paragraph ended before", "Paragraph ended before \\label was complete"),
    ("too-many-closing-braces", "too many }'s", "Too many }'s"),
    ("runaway-argument", "runaway argument", "Runaway argument"),
    ("citation-undefined", "citation undefined", "Citation `x' undefined"),
    ("reference-undefined", "reference undefined", "Reference `x' undefined"),
    ("undefined-references", "undefined references", "There were undefined references"),
    ("unicode-character", "unicode character", "Package inputenc Error: Unicode character not set up"),
    ("missing-number", "missing number treated as zero", "Missing number, treated as zero"),
    ("illegal-parameter-number", "illegal parameter number", "Illegal parameter number in definition"),
    ("extra-brace-or-forgotten-dollar", "extra forgotten", "Extra }, or forgotten $"),
    ("too-many-unprocessed-floats", "too many unprocessed floats", "Too many unprocessed floats"),
    ("floats-lost", "float(s) lost", "Float(s) lost"),
    ("option-clash", "option clash for package", "Option clash for package"),
    ("command-already-defined", "command already defined", "Command \\x already defined"),
    ("counter-too-large", "counter too large", "Counter too large"),
    ("missing-right-inserted", "missing right inserted", "Missing \\right. inserted"),
    ("not-in-outer-par-mode", "not in outer par mode", "Not in outer par mode"),
    ("lonely-item", "lonely item", "Lonely \\item"),
    ("emergency-stop", "emergency stop", "Emergency stop"),
    ("font-shape-undefined", "font shape undefined", "Font shape `OT1/cmr/m/n' undefined"),
    ("underfull-hbox", "underfull hbox", "Underfull \\hbox"),
    ("tex-capacity-exceeded", "tex capacity exceeded", "TeX capacity exceeded, sorry"),
    ("tfm-file-not-found", "tfm file not found", "Font x not loadable: Metric (TFM) file not found"),
    ("infinite-glue-shrinkage", "infinite glue shrinkage", "Infinite glue shrinkage found in a paragraph"),
    ("missing-brace-inserted", "missing { inserted", "Missing { inserted"),
    ("argument-has-extra-brace", "argument has an extra", "Argument of \\x has an extra }"),
    ("unknown-option-for-package", "unknown option", "Unknown option for package"),
    ("double-subscript", "double subscript", "Double subscript"),
    ("double-superscript", "double superscript", "Double superscript"),
    ("missing-control-sequence", "missing control sequence inserted", "Missing control sequence inserted"),
    ("only-in-preamble", "can be used only in preamble", "Can be used only in preamble"),
    ("begin-ended-by-end", "ended by end", "\\begin{x} ended by \\end{y}"),
    ("missing-item", "perhaps a missing item", "Something's wrong--perhaps a missing \\item"),
    ("dimension-too-large", "dimension too large", "Dimension too large"),
    ("bibtex-cant-open-file", "bibtex open file", "BibTeX: I couldn't open file name"),
    ("unknown-graphics-extension", "unknown graphics extension", "Unknown graphics extension"),
    ("hyperref-token-not-allowed", "token not allowed in a pdf string", "Token not allowed in a PDF string"),
    ("undefined-color", "undefined color", "Package xcolor Error: Undefined color"),
    ("missing-endcsname", "missing endcsname inserted", "Missing \\endcsname inserted"),
    ("misplaced-noalign", "misplaced noalign", "Misplaced \\noalign"),
    ("missing-delimiter", "missing delimiter", "Missing delimiter (. inserted)"),
    ("extra-else-or-fi", "extra else", "Extra \\else / Extra \\fi"),
    ("rerun-to-get-cross-references", "rerun to get cross-references right", "Rerun to get cross-references right"),
    ("label-multiply-defined", "label multiply defined", "Label `x' multiply defined"),
]


def search_url(words: str) -> str:
    q = {"order": "desc", "sort": "votes", "intitle": words, "site": "tex", "pagesize": 100}
    return API + "?" + urllib.parse.urlencode(q)


def _ssl_context() -> ssl.SSLContext:
    """python.org framework builds ship without CA roots: prefer certifi, fall back to the system store
    (the traffic dashboard does the same)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "purplelink-latex-demand"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def score(words: str, fetch=fetch_json, sleep=time.sleep) -> dict:
    """{"questions": n, "views": sum of view_count, "top_views": the biggest single question} for the phrase."""
    data = fetch(search_url(words))
    items = data.get("items", [])
    views = [int(i.get("view_count", 0)) for i in items]
    if data.get("backoff"):
        sleep(min(int(data["backoff"]), 60))
    return {"questions": len(items), "views": sum(views), "top_views": max(views, default=0),
            "quota_remaining": data.get("quota_remaining")}


def covered(slug: str, root: Path = ROOT) -> bool:
    return (root / "site" / "latex-errors" / slug / "index.html").exists()


def rank(fetch=fetch_json, sleep=time.sleep, root: Path = ROOT, candidates=CANDIDATES) -> list[dict]:
    rows = []
    for slug, words, shown in candidates:
        try:
            s = score(words, fetch, sleep)
        except Exception as e:                               # one failed lookup must not lose the rest
            s = {"questions": 0, "views": 0, "top_views": 0, "error_lookup": str(e)[:80]}
        rows.append({"slug": slug, "error": shown, "covered": covered(slug, root), **s})
        sleep(0.4)
    rows.sort(key=lambda r: r["views"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def table(rows: list[dict]) -> str:
    out = [f"{'#':>3}  {'views':>9}  {'qs':>3}  {'covered':7}  error"]
    for r in rows:
        flag = "yes" if r["covered"] else ""
        note = "   (no title matched: reword the phrase before trusting this row)" if r["questions"] == 0 else ""
        out.append(f"{r['rank']:>3}  {r['views']:>9,}  {r['questions']:>3}  {flag:7}  {r['error']}{note}")
    return "\n".join(out)


def brief(rows: list[dict], today: str) -> str:
    unc = [r for r in rows if not r["covered"]]
    cov = [r for r in rows if r["covered"]]
    lines = [f"# LaTeX error demand ranking, {today}", "",
             "Index: summed TeX Stack Exchange view counts of questions whose title contains the error's words. A relative",
             "measure of how many people hit the error, not a search volume. Compare rows with each other only.", "",
             "## Next topics (not yet covered), highest first", "", table(unc[:15]), "",
             "## Already covered, for comparison", "", table(cov), ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="write docs/growth-briefs/latex-error-demand-<date>.md")
    ap.add_argument("--only", type=int, help="print only the top N uncovered topics")
    a = ap.parse_args()
    rows = rank()
    failed = [r for r in rows if r.get("error_lookup")]
    if len(failed) > len(rows) // 2:
        print(f"{len(failed)} of {len(rows)} lookups failed (first: {failed[0]['error_lookup']}); not ranking.", file=sys.stderr)
        return 1
    shown = [r for r in rows if not r["covered"]][:a.only] if a.only else rows
    print(table(shown))
    if failed:
        print(f"\nNote: {len(failed)} lookup(s) failed and are ranked as zero: " + ", ".join(r["slug"] for r in failed), file=sys.stderr)
    if a.write:
        p = ROOT / "docs" / "growth-briefs" / f"latex-error-demand-{dt.date.today().isoformat()}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(brief(rows, dt.date.today().isoformat()), encoding="utf-8")
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
