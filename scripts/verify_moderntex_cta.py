#!/usr/bin/env python3
"""Verify the ModernTex CTA block is present and correct on all 19 pages."""
import sys

from cta_pages import MARKER, targets


def check(path, source):
    errors = []
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    # Exactly one CTA block.
    if html.count(MARKER) != 1:
        errors.append(f"{path}: expected 1 '{MARKER}', found {html.count(MARKER)}")
    # Exactly one CTA form posting to the shared waitlist.
    if html.count('name="waitlist-moderntex"') != 1:
        errors.append(f"{path}: expected 1 waitlist-moderntex form, found "
                      f"{html.count('name=\"waitlist-moderntex\"')}")
    # Correct, unique source value.
    needle = f'name="source" value="{source}"'
    if html.count(needle) != 1:
        errors.append(f"{path}: expected 1 '{needle}', found {html.count(needle)}")
    # CTA must appear before the related-tools nav.
    cta_i = html.find(MARKER)
    nav_i = html.find('<nav class="tool-related"')
    if cta_i == -1 or nav_i == -1 or cta_i >= nav_i:
        errors.append(f"{path}: CTA not positioned before tool-related nav "
                      f"(cta={cta_i}, nav={nav_i})")
    # Structure intact: still exactly one <main> and one footer.
    if html.count("</main>") != 1:
        errors.append(f"{path}: expected 1 '</main>', found {html.count('</main>')}")
    if html.count('<footer class="footer"') != 1:
        errors.append(f"{path}: expected 1 footer, found "
                      f"{html.count('<footer class=\"footer\"')}")
    return errors


def main():
    all_errors = []
    for path, source in targets():
        all_errors.extend(check(path, source))
    if all_errors:
        for e in all_errors:
            print("FAIL", e)
        print(f"\n{len(all_errors)} problems across pages")
        sys.exit(1)
    print("OK: all 19 pages have a correct, unique ModernTex CTA block")


if __name__ == "__main__":
    main()
