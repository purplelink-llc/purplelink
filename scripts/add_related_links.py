#!/usr/bin/env python3
"""
Spread internal links across topic clusters so every page in a cluster has
several contextual inbound links, not just one from its section index.

Search Console (2026-10-09) listed 51 pages as "Discovered, currently not
indexed" and 30 as "Crawled, currently not indexed". Most had one to three
inbound links from the body of another page; blog posts had exactly one, from
the blog index. Each cluster below is a ring: member i links to the next four
members, so each member gets four inbound links and no page is a sink.

Pages that already have a <nav class="tool-related"> block keep it; the missing
cluster links are appended (up to six items in all). Other pages get the block
inserted just before </main>. Safe to re-run: links already present are skipped.

    python3 scripts/add_related_links.py            # write changes
    python3 scripts/add_related_links.py --check    # exit 1 if anything would change
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
MAX_ITEMS = 6
RING = 4

CLUSTERS: dict[str, list[str]] = {
    "citations": [
        "/guides/bibtex/",
        "/guides/fix-bibtex-errors/",
        "/guides/doi-to-bibtex/",
        "/guides/build-bibtex-from-dois/",
        "/guides/format-citation-from-doi-arxiv-id/",
        "/guides/convert-references-bibtex-ris-endnote/",
        "/blog/where-bibtex-errors-actually-come-from/",
        "/blog/what-openalex-returns-when-you-ask-for-an-abstract/",
        "/tools/bib-builder/",
        "/tools/reference-converter/",
    ],
    "response": [
        "/guides/how-to-respond-to-reviewer-2/",
        "/guides/reviewer-says-novelty-is-limited/",
        "/guides/check-revisions-addressed-findings/",
        "/guides/check-response-letter-before-resubmitting/",
        "/blog/checking-your-response-letter-before-resubmission/",
        "/blog/the-comment-said-this-would-break/",
        "/blog/producing-a-diff-pdf-for-journal-resubmission/",
        "/tools/response-letter-template/",
        "/tools/response-review/",
        "/tools/paper-review/revision/",
    ],
    "before-submitting": [
        "/guides/get-feedback-on-a-paper-before-submitting/",
        "/guides/ai-paper-review-tools-compared/",
        "/guides/ai-policy-checking-your-own-manuscript/",
        "/guides/use-paper-review-before-submitting/",
        "/guides/methodology-problems-peer-reviewers-flag/",
        "/blog/what-your-literature-search-misses/",
        "/blog/running-your-manuscript-through-paper-review/",
        "/tools/paper-review/sample/",
        "/tools/paper-review/biomedicine/",
        "/tools/paper-review/chemistry/",
        "/tools/paper-review/machine-learning/",
    ],
    "latex-conversion": [
        "/guides/compile-latex-project-to-pdf-online/",
        "/guides/latex-to-word/",
        "/guides/word-to-latex/",
        "/guides/latex-word-count/",
        "/guides/csv-to-latex-table/",
        "/guides/latex-equation-to-png/",
        "/blog/tikz-and-tables-without-the-syntax/",
        "/blog/the-co-author-who-writes-in-word/",
        "/tools/latex-table-generator/",
        "/tools/equation-renderer/",
        "/tools/word-counter/",
    ],
    "pdf-to-text": [
        "/guides/research-paper-pdf-to-markdown/",
        "/blog/pdf-to-llm-without-losing-the-math/",
        "/tools/file-to-markdown/",
        "/tools/pdf-structure/",
        "/tools/pdf-tools/",
    ],
    "sheets": [
        "/sheets/",
        "/sheets/live/",
        "/sheets/live/citation-dashboard/",
        "/sheets/live/funding-feed/",
        "/sheets/grant-pipeline-tracker/",
        "/sheets/job-market-tracker/",
        "/sheets/review-screening-matrix/",
        "/sheets/submission-tracker/",
        "/sheets/tenure-tracker/",
        "/guides/track-academic-cv-tenure-case/",
    ],
    "templates": [
        "/templates/",
        "/templates/acm-acmart/",
        "/templates/apa7/",
        "/templates/elsevier-elsarticle/",
        "/templates/ieee-conference/",
        "/templates/neurips/",
    ],
    "mac-latex": [
        "/guides/best-mac-latex-editors/",
        "/guides/overleaf-alternative-mac/",
        "/guides/texshop-alternative-mac/",
        "/guides/install-latex-on-mac/",
        "/blog/the-latex-editor-academics-want/",
        "/blog/forward-and-inverse-search-arent-mirror-images/",
    ],
}


def label_for(path: Path) -> str:
    s = path.read_text(errors="ignore")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    text = m.group(1) if m else (re.search(r"<title>(.*?)</title>", s, re.S) or [None, ""])[1].split(" | ")[0]
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def page_path(url: str) -> Path:
    return SITE / url.strip("/") / "index.html"


def main() -> int:
    check = "--check" in sys.argv
    wanted: dict[str, list[str]] = {}
    for name, members in CLUSTERS.items():
        for u in members:
            assert page_path(u).exists(), f"{name}: {u} does not exist"
        n = len(members)
        for i, u in enumerate(members):
            for k in range(1, min(RING, n - 1) + 1):
                wanted.setdefault(u, []).append(members[(i + k) % n])

    changed = 0
    for url, targets in wanted.items():
        p = page_path(url)
        s = p.read_text()
        present = set(re.findall(r'href="(/[^"#?]*)"', s))
        new = [t for t in dict.fromkeys(targets) if t not in present and t != url]
        if not new:
            continue
        block = re.search(r'(<nav class="tool-related"[^>]*>.*?<ul>)(.*?)(</ul>\s*</nav>)', s, re.S)
        if block:
            have = len(re.findall(r"<li>", block.group(2)))
            room = max(0, MAX_ITEMS - have)
            new = new[:room]
            if not new:
                continue
            items = "".join(f'          <li><a href="{t}">{html.escape(label_for(page_path(t)))}</a></li>\n' for t in new)
            body = block.group(2).rstrip(" ")
            if not body.endswith("\n"):
                body += "\n"
            s2 = s[: block.start(2)] + body + items + "        " + s[block.start(3):]
        else:
            new = new[:MAX_ITEMS]
            items = "\n".join(f'          <li><a href="{t}">{html.escape(label_for(page_path(t)))}</a></li>' for t in new)
            nav = (
                '      <nav class="tool-related" aria-label="Related pages">\n'
                "        <h2>Related</h2>\n        <ul>\n" + items + "\n        </ul>\n      </nav>\n"
            )
            idx = s.rfind("</main>")
            assert idx != -1, f"{url}: no </main>"
            head = s[:idx]
            indent = head[len(head.rstrip(" ")):]
            s2 = head.rstrip(" ") + nav + (indent or "    ") + s[idx:]
        if s2 != s:
            changed += 1
            if not check:
                p.write_text(s2)
    print(f"related links: {changed} page(s) {'would change' if check else 'updated'}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
