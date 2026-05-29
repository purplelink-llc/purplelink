#!/usr/bin/env python3
"""Purge em-dashes (and prose en-dashes) from the site per the
design-taste-frontend skill's em-dash ban, without corrupting code.

Rules:
  * <style>/<code>/<pre>/<kbd> regions: never touched.
  * Em-dash (U+2014):  replaced with "-" everywhere EXCEPT the protected
    regions above. Em-dash never appears in JS/HTML syntax, only in string
    literals, comments, prose, attributes, and JSON-LD, so this is safe.
  * En-dash (U+2013):  replaced with "-" everywhere EXCEPT inside <script>
    (and the protected regions). This preserves the page-range-splitting
    regex /[-–]/ in reference-converter while still cleaning prose like
    "author-date".

A spaced em-dash " - " becomes a spaced hyphen " - " automatically because
only the dash character is swapped; surrounding spacing is preserved.

Run from the repo root.  Idempotent.
"""
import glob
import re
import sys

EM = "—"  # —
EN = "–"  # –

CODE_RE = re.compile(r"(?is)<(style|code|pre|kbd)\b[^>]*>.*?</\1>")
SCRIPT_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script>")

EXCLUDE = {"site/assets/og/_gen.html"}  # OG image generator template, not a page


def mask(text, regex, tag):
    store = []

    def repl(m):
        store.append(m.group(0))
        return f"\x00{tag}{len(store) - 1}\x00"

    return regex.sub(repl, text), store


def unmask(text, store, tag):
    for i, original in enumerate(store):
        text = text.replace(f"\x00{tag}{i}\x00", original)
    return text


def purge(html):
    # 1. Protect style/code/pre/kbd entirely.
    html, code_store = mask(html, CODE_RE, "C")
    # 2. Em-dash: safe everywhere remaining (prose, attrs, JSON-LD, JS strings).
    html = html.replace(EM, "-")
    # 3. En-dash: protect <script> first, then purge from prose/attrs only.
    html, script_store = mask(html, SCRIPT_RE, "S")
    html = html.replace(EN, "-")
    html = unmask(html, script_store, "S")
    # 4. Restore protected code regions.
    html = unmask(html, code_store, "C")
    return html


def main():
    check = "--check" in sys.argv
    files = sorted(f for f in glob.glob("site/**/*.html", recursive=True)
                   if f not in EXCLUDE)
    changed = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            before = fh.read()
        after = purge(before)
        if after != before:
            n = before.count(EM) - after.count(EM) + before.count(EN) - after.count(EN)
            changed.append((f, n))
            if not check:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(after)
    verb = "would change" if check else "changed"
    print(f"{verb} {len(changed)} files")
    for f, n in changed:
        print(f"  {n:3d} dashes  {f}")
    # Report any residual em/en dashes outside protected regions.
    residual = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            txt = fh.read()
        masked, _ = mask(txt, CODE_RE, "C")
        masked, _ = mask(masked, SCRIPT_RE, "S")
        residual += masked.count(EM) + masked.count(EN)
    print(f"residual em/en dashes in prose+attrs after run: {residual}")


if __name__ == "__main__":
    main()
