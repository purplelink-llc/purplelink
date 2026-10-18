"""Front-matter file format for queue items.

A queue file is Markdown. The front matter holds one `key: <JSON value>` per line (JSON is valid YAML, so any
YAML tool reads it, and no YAML library is needed here). The body holds the post text, one section per
platform:

    ## default
    text used by every platform without its own section

    ## bluesky
    text only for Bluesky

`{link}` inside a text is replaced by that platform's UTM link; with no `{link}` the link goes on its own last line.
"""
from __future__ import annotations

import json
import re

FENCE = "---"
SECTION_RE = re.compile(r"^##\s+([a-z0-9_-]+)\s*$", re.M)
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


def parse(text: str) -> tuple[dict, dict[str, str], str]:
    """Return (front matter, text sections, notes before the first section)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        raise ValueError("queue item must start with a --- front matter block")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == FENCE), None)
    if end is None:
        raise ValueError("front matter is not closed with ---")
    meta: dict = {}
    for n, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = KEY_RE.match(line)
        if not m:
            raise ValueError(f"line {n}: expected `key: value`")
        raw = m.group(2).strip()
        if raw == "":
            meta[m.group(1)] = None
            continue
        try:
            meta[m.group(1)] = json.loads(raw)
        except json.JSONDecodeError:
            # a bare word such as `draft` or an unquoted date is accepted as a string
            meta[m.group(1)] = raw
    body = "\n".join(lines[end + 1:])
    parts = SECTION_RE.split(body)
    preface = parts[0].strip()
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        sections[parts[i]] = parts[i + 1].strip("\n").strip()
    return meta, sections, preface


def dump(meta: dict, sections: dict[str, str], preface: str = "") -> str:
    out = [FENCE]
    for k, v in meta.items():
        out.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    out.append(FENCE)
    out.append("")
    if preface:
        out += [preface, ""]
    for name, text in sections.items():
        out += [f"## {name}", text.strip("\n"), ""]
    return "\n".join(out).rstrip("\n") + "\n"
