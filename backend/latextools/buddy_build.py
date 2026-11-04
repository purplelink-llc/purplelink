"""Writes latextools/buddy_facts.py, Buddy's facts block, from site/llms.txt (docs/designs/buddy-chat.md, section 4).

The file is build output and is not in git (docs/designs/generated-files-at-build.md): app.py writes it whenever it
runs on this machine, which is every `modal deploy` and every test run, so Modal's upload of `latextools` always
carries facts made from the llms.txt being deployed. The Modal image bundles Python sources only, which is why the
facts ship as a module.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LLMS = REPO / "site" / "llms.txt"
FACTS_PY = Path(__file__).with_name("buddy_facts.py")


def facts_source(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return (
        '"""Generated from site/llms.txt by latextools/buddy_build.py at deploy and test time. Not in git."""\n'
        f"SOURCE_SHA256 = {digest!r}\n"
        f"FACTS = {text!r}\n"
    )


def write_facts() -> Path:
    """Write the facts module from site/llms.txt (only when it changed). Raises if llms.txt is missing, so a deploy
    from a tree without it fails instead of shipping a chat with no facts."""
    if not LLMS.is_file():
        raise RuntimeError(f"Buddy's facts need {LLMS}; deploy from a full checkout of the purplelink repo")
    src = facts_source(LLMS.read_text(encoding="utf-8"))
    if not FACTS_PY.is_file() or FACTS_PY.read_text(encoding="utf-8") != src:
        FACTS_PY.write_text(src, encoding="utf-8")
    return FACTS_PY
