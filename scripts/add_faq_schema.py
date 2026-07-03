#!/usr/bin/env python3
"""Add FAQPage JSON-LD to pages that already have visible FAQ/explainer
content but no structured schema for it yet.

Two page shapes handled:

1. Tool pages with `<details><summary>Q</summary><div class="faq-body">A</div>
   </details>` blocks (the same visible markup reference-converter's page
   already uses) — extract those Q&A pairs verbatim into a FAQPage
   `<script type="application/ld+json">` inserted before </head>.

2. why-it-matters explainer pages with a fixed "What it is / Why a
   reviewer cares / How to fix it" structure — extract those three
   paragraphs verbatim as three FAQPage questions, and fold them into
   the page's existing single-object JSON-LD (upgrading it to a @graph
   alongside the existing TechArticle entry) rather than adding a second
   <script> tag.

Every question/answer here is existing, already-published page text —
this script restructures it, it does not write new copy.

Idempotent: skips any file that already has "FAQPage" in it.

Usage: python3 scripts/add_faq_schema.py
"""
import json
import os
import re

SITE = os.path.join(os.path.dirname(__file__), "..", "site")

TOOL_PAGES = [
    "tools/anonymity-check/index.html",
    "tools/citation-gap/index.html",
    "tools/cover-letter/index.html",
    "tools/file-to-markdown/index.html",
    "tools/response-review/index.html",
]

DETAILS_RE = re.compile(
    r'<details><summary>(.*?)</summary><div class="faq-body">(.*?)</div></details>',
    re.S,
)


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def canonical_url(path):
    # site/tools/foo/index.html -> https://purplelink.llc/tools/foo/
    rel = os.path.relpath(path, SITE).replace("index.html", "")
    return f"https://purplelink.llc/{rel}"


def add_tool_faq(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    if "FAQPage" in html:
        print(f"SKIP (already has FAQPage): {path}")
        return False

    pairs = DETAILS_RE.findall(html)
    if not pairs:
        print(f"SKIP (no <details> FAQ found): {path}")
        return False

    questions = [
        {
            "@type": "Question",
            "name": strip_tags(q),
            "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)},
        }
        for q, a in pairs
    ]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": questions,
    }
    script = (
        '    <script type="application/ld+json">\n'
        f"    {json.dumps(jsonld, indent=2)}\n"
        "    </script>\n"
    )

    if "</head>" not in html:
        print(f"FAIL (no </head>): {path}")
        return False
    new_html = html.replace("</head>", script + "  </head>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_html)
    print(f"ADDED {len(questions)} Q&A to: {path}")
    return True


WIM_SECTION_RE = {
    "what": re.compile(r"<h2>What it is</h2>\s*<p>(.*?)</p>", re.S),
    "why": re.compile(r"<h2>Why a reviewer cares</h2>\s*<p>(.*?)</p>", re.S),
    "fix": re.compile(r"<h2>How to fix it</h2>\s*<p>(.*?)</p>", re.S),
}
EXISTING_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', re.S
)


def add_wim_faq(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    if "FAQPage" in html:
        print(f"SKIP (already has FAQPage): {path}")
        return False

    m_title = re.search(r"<h1>(.*?)</h1>", html)
    topic = strip_tags(m_title.group(1)) if m_title else "this issue"

    sections = {}
    for key, rx in WIM_SECTION_RE.items():
        m = rx.search(html)
        if not m:
            print(f"SKIP (missing section {key!r}): {path}")
            return False
        sections[key] = strip_tags(m.group(1))

    m_ld = EXISTING_JSONLD_RE.search(html)
    if not m_ld:
        print(f"FAIL (no existing JSON-LD to merge into): {path}")
        return False
    existing = json.loads(m_ld.group(1))

    faq = {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"What is {topic}?",
                "acceptedAnswer": {"@type": "Answer", "text": sections["what"]},
            },
            {
                "@type": "Question",
                "name": f"Why does a reviewer care about {topic}?",
                "acceptedAnswer": {"@type": "Answer", "text": sections["why"]},
            },
            {
                "@type": "Question",
                "name": f"How do I fix {topic}?",
                "acceptedAnswer": {"@type": "Answer", "text": sections["fix"]},
            },
        ],
    }

    graph = {"@context": "https://schema.org", "@graph": [existing, faq]}
    # existing already carries its own @context; drop it from the nested copy
    graph["@graph"][0] = {k: v for k, v in existing.items() if k != "@context"}

    new_script = (
        '<script type="application/ld+json">\n'
        f"    {json.dumps(graph, indent=2)}\n"
        "    </script>"
    )
    new_html = EXISTING_JSONLD_RE.sub(lambda _m: new_script, html, count=1)

    # Fix the one known pre-existing inline-style CSP violation on these
    # pages while already touching them (see .static-page .divider in
    # styles.css) — same file, same edit pass, no separate churn later.
    new_html = new_html.replace(
        '<hr style="border:none;border-top:1px solid #ffffff14;margin:2rem 0">',
        '<hr class="divider">',
    )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_html)
    print(f"ADDED FAQPage (3 Q&A) + fixed inline hr: {path}")
    return True


def main():
    changed = 0
    for rel in TOOL_PAGES:
        path = os.path.join(SITE, rel)
        if add_tool_faq(path):
            changed += 1

    wim_dir = os.path.join(SITE, "guides", "why-it-matters")
    for name in sorted(os.listdir(wim_dir)):
        page = os.path.join(wim_dir, name, "index.html")
        if not os.path.isfile(page):
            continue
        if add_wim_faq(page):
            changed += 1

    print(f"\n{changed} files changed")


if __name__ == "__main__":
    main()
