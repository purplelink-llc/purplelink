#!/usr/bin/env python3
"""Turn a muscleonglp-reddit-outreach drafts file into a one-click hand-off page.

The outreach task drafts replies and never posts (Ben's rule, 2026-10-09; the
API route closed and the browser route is blocked). This page makes the manual
step quick: per draft, one button opens the thread and one copies the reply.
Ticking "Posted" is remembered in that browser, and "Copy confirmation" puts a
line like "Posted from drafts-2026-10-12: 1x3rozr, 1x3oo9x" on the clipboard to
paste back into Claude, which is what lets the task update handled.json.

Usage:
    scripts/reddit-handoff.py                       # newest ~/.purplelink/reddit/drafts-*.md
    scripts/reddit-handoff.py path/to/drafts.md
    scripts/reddit-handoff.py --open                # also open the page in the default browser

Writes drafts-YYYY-MM-DD.html next to the .md file. Standard library only, no
network: the page is a local file and loads nothing from outside.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

DRAFTS_DIR = Path.home() / ".purplelink" / "reddit"

DRAFT_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.*)$")
SUB_TITLE = re.compile(r'^(r/\S+)\s+"(.*?)"\s*(?:\((.*)\))?\s*$')
THREAD_URL = re.compile(r"https://(?:www\.|old\.)?reddit\.com/r/[^\s)]+")
POST_ID = re.compile(r"\(post id\s+([a-z0-9]+)\)", re.I)
URL_ID = re.compile(r"/comments/([a-z0-9]+)", re.I)
# Older runs wrote "- Status: **HANDED TO BEN 2026-10-02**".
STATUS = re.compile(r"^[-\s]*status:\s*\**(.+?)\**\s*$", re.M | re.I)
FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.M | re.S)


# ---------------------------------------------------------------- parse ----

def parse(text: str) -> dict:
    """Split a drafts file into its header, the draft sections, and the rest.

    Only "## <n>. ..." sections are drafts; "## Skipped" and "## Outcome"
    are kept as plain notes. A draft with no fenced reply is still shown, so a
    BLOCKED thread is visible rather than silently dropped.
    """
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else "Drafts"

    sections: list[tuple[str, list[str]]] = []
    header: list[str] = []
    current: tuple[str, list[str]] | None = None
    for line in lines[1:]:
        if line.startswith("## "):
            current = (line, [])
            sections.append(current)
        elif current is None:
            header.append(line)
        else:
            current[1].append(line)

    drafts, notes = [], []
    for heading, body_lines in sections:
        body = "\n".join(body_lines)
        m = DRAFT_HEADING.match(heading)
        if not m:
            notes.append({"heading": heading[3:].strip(), "body": body.strip()})
            continue
        num, rest = m.groups()
        sm = SUB_TITLE.match(rest.strip())
        sub, thread_title, meta = (sm.groups() if sm else ("", rest.strip(), ""))
        fence = FENCE.search(body)
        url = THREAD_URL.search(body)
        # The Reddit post id is what handled.json stores; the URL slug is not.
        pid = POST_ID.search(body) or (URL_ID.search(url.group(0)) if url else None)
        status = STATUS.search(body)
        reply = fence.group(1).strip() if fence else ""
        # Everything except the reply itself is the drafter's working notes.
        context = (body[: fence.start()] + body[fence.end():]) if fence else body
        context = STATUS.sub("", context)
        drafts.append({
            "num": num,
            "sub": sub,
            "title": thread_title,
            "meta": (meta or "").strip(),
            "url": url.group(0) if url else "",
            "id": pid.group(1) if pid else f"draft-{num}",
            "status": status.group(1).strip() if status else "",
            "reply": reply,
            "words": len(reply.split()),
            "has_link": "getmuscleonglp.com" in reply,
            "context": context.strip(),
        })
    return {"title": title, "header": "\n".join(header).strip(), "drafts": drafts, "notes": notes}


# ----------------------------------------------------------------- render ----

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reddit Hand-off</title>
<style>
:root {
  --bg: #f6f8f7; --card: #ffffff; --ink: #1b2420; --muted: #5d6b65; --line: #dde7e3;
  --accent: #2f6f5e; --accent-ink: #ffffff; --warn: #9a5b00; --done: #e8f3ef;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #111614; --card: #1a201d; --ink: #e6ece9; --muted: #9aa8a2; --line: #2c3632;
          --accent: #5fb39a; --accent-ink: #0f1513; --warn: #e0a54a; --done: #1d2b26; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.sub { color: var(--muted); margin: 0 0 20px; }
details.head { margin-bottom: 20px; color: var(--muted); font-size: 13px; }
details pre, .ctx pre { white-space: pre-wrap; word-break: break-word; margin: 8px 0 0; font: 12px/1.45 ui-monospace, Menlo, monospace; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.card.posted { background: var(--done); }
.top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.sr { font-weight: 600; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 99px; border: 1px solid var(--line); color: var(--muted); }
.badge.link { color: var(--warn); border-color: var(--warn); }
.ttl { margin: 4px 0 10px; }
.reply { white-space: pre-wrap; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin: 0 0 12px; }
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
button, a.btn { font: inherit; font-size: 14px; padding: 8px 14px; border-radius: 99px; border: 1px solid var(--accent);
                background: transparent; color: var(--accent); cursor: pointer; text-decoration: none; }
button.primary { background: var(--accent); color: var(--accent-ink); }
button:disabled { opacity: .5; cursor: default; }
label.posted-box { margin-left: auto; color: var(--muted); display: flex; gap: 6px; align-items: center; cursor: pointer; }
.ctx { margin-top: 10px; font-size: 13px; color: var(--muted); }
.foot { position: sticky; bottom: 0; background: var(--bg); padding: 12px 0; border-top: 1px solid var(--line); }
.notes { margin-top: 28px; }
.notes h2 { font-size: 15px; margin: 16px 0 4px; }
.toast { color: var(--accent); font-size: 13px; min-width: 6em; }
</style>
</head>
<body>
<main>
<h1>__TITLE__</h1>
<p class="sub">__COUNT__ · Open the thread, paste the reply, post it yourself, then tick Posted.</p>
__HEADER__
__CARDS__
<div class="foot row">
  <button class="primary" id="confirm">Copy confirmation</button>
  <span class="toast" id="confirm-toast"></span>
  <span class="sub" id="tally" style="margin:0 0 0 auto"></span>
</div>
__NOTES__
</main>
<script>
(function () {
  var FILE = __FILE__;
  var IDS = __IDS__;
  function key(id) { return "reddit-handoff:" + id; }
  function get(id) { try { return localStorage.getItem(key(id)) === "1"; } catch (e) { return false; } }
  function set(id, v) { try { v ? localStorage.setItem(key(id), "1") : localStorage.removeItem(key(id)); } catch (e) {} }

  function copy(text, toast) {
    function done(msg) { if (toast) { toast.textContent = msg; setTimeout(function () { toast.textContent = ""; }, 1800); } }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done("Copied"); } catch (e) { done("Copy failed"); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done("Copied"); }, fallback);
    } else { fallback(); }
  }

  function tally() {
    var n = IDS.filter(get).length;
    document.getElementById("tally").textContent = n + " of " + IDS.length + " posted";
  }

  document.querySelectorAll(".card").forEach(function (card) {
    var id = card.getAttribute("data-id");
    var box = card.querySelector("input[type=checkbox]");
    var toast = card.querySelector(".toast");
    box.checked = get(id);
    card.classList.toggle("posted", box.checked);
    box.addEventListener("change", function () { set(id, box.checked); card.classList.toggle("posted", box.checked); tally(); });
    card.querySelector(".copy").addEventListener("click", function () {
      copy(card.querySelector(".reply").textContent, toast);
    });
  });

  document.getElementById("confirm").addEventListener("click", function () {
    var posted = IDS.filter(get);
    var line = "Posted from " + FILE + ": " + (posted.length ? posted.join(", ") : "none");
    copy(line, document.getElementById("confirm-toast"));
  });
  tally();
})();
</script>
</body>
</html>
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render(doc: dict, source: Path) -> str:
    cards = []
    for d in doc["drafts"]:
        badges = []
        if d["meta"]:
            badges.append(f'<span class="badge">{esc(d["meta"])}</span>')
        badges.append('<span class="badge link">has link</span>' if d["has_link"] else '<span class="badge">no link</span>')
        if d["status"]:
            badges.append(f'<span class="badge">{esc(d["status"])}</span>')
        if d["reply"]:
            reply = f'<p class="reply">{esc(d["reply"])}</p>'
            copy_btn = '<button class="copy primary">Copy reply</button>'
            badges.append(f'<span class="badge">{d["words"]} words</span>')
        else:
            reply = '<p class="reply">(The drafts file has no reply text for this thread, only notes about it. Open the notes below.)</p>'
            copy_btn = '<button class="copy" disabled>Copy reply</button>'
        open_btn = (f'<a class="btn" href="{esc(d["url"])}" target="_blank" rel="noopener noreferrer">Open thread</a>'
                    if d["url"] else "")
        cards.append(f"""<section class="card" data-id="{esc(d['id'])}">
  <div class="top"><span class="sr">{d['num']}. {esc(d['sub'])}</span>{''.join(badges)}</div>
  <p class="ttl">{esc(d['title'])}</p>
  {reply}
  <div class="row">{open_btn}{copy_btn}<span class="toast"></span>
    <label class="posted-box"><input type="checkbox"> Posted</label></div>
  <details class="ctx"><summary>Drafter's notes (post {esc(d['id'])})</summary><pre>{esc(d['context'])}</pre></details>
</section>""")

    header = (f'<details class="head"><summary>Run summary</summary><pre>{esc(doc["header"])}</pre></details>'
              if doc["header"] else "")
    notes = "".join(f'<h2>{esc(n["heading"])}</h2><details class="ctx" open><pre>{esc(n["body"])}</pre></details>'
                    for n in doc["notes"])
    n = len(doc["drafts"])
    page = PAGE
    for k, v in {
        "__TITLE__": esc(doc["title"]),
        "__COUNT__": f"{n} draft{'s' if n != 1 else ''}",
        "__HEADER__": header,
        "__CARDS__": "\n".join(cards) or '<p class="sub">No drafts in this run.</p>',
        "__NOTES__": f'<div class="notes">{notes}</div>' if notes else "",
        # json.dumps output is safe inside <script> once "</" cannot close the tag.
        "__FILE__": json.dumps(source.stem).replace("</", "<\\/"),
        "__IDS__": json.dumps([d["id"] for d in doc["drafts"]]).replace("</", "<\\/"),
    }.items():
        page = page.replace(k, v)
    return page


# ------------------------------------------------------------------- main ----

def newest_drafts() -> Path:
    files = sorted(DRAFTS_DIR.glob("drafts-*.md"))
    if not files:
        sys.exit(f"no drafts-*.md in {DRAFTS_DIR}")
    return files[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("drafts", nargs="?", type=Path, help="drafts .md file (default: newest in ~/.purplelink/reddit)")
    ap.add_argument("--out", type=Path, help="where to write the page (default: next to the .md)")
    ap.add_argument("--open", action="store_true", help="open the page after writing it")
    args = ap.parse_args()

    src = args.drafts or newest_drafts()
    if not src.is_file():
        sys.exit(f"not a file: {src}")
    doc = parse(src.read_text(encoding="utf-8"))
    out = args.out or src.with_suffix(".html")
    out.write_text(render(doc, src), encoding="utf-8")
    print(f"{out}  ({len(doc['drafts'])} drafts)")
    if args.open:
        subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
