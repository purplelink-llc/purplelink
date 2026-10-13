#!/usr/bin/env python3
"""Affiliate programs: report, check, apply.

  python3 scripts/affiliates.py report         registry status and where each live program is linked
  python3 scripts/affiliates.py check          registry sanity plus lint of every page; exit 1 on any problem
  python3 scripts/affiliates.py apply          dry run: list pages whose links would change
  python3 scripts/affiliates.py apply --write  rewrite links, add rel=sponsored and the disclosure paragraph

The registry is backend/digest/affiliates.py. Only programs with status "approved" and a tracked link change
anything. Generated digest pages (site/blog/digest/) are left alone: the digest publisher applies the same rules
when it renders each issue.
"""
import html
import re
import sys
from pathlib import Path

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


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "report"
    if cmd == "report":
        return cmd_report()
    if cmd == "check":
        return cmd_check()
    if cmd == "apply":
        return cmd_apply("--write" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
