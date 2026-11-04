"""Weekly studio note: a first-person, unnamed "from the studio" story post for the company LinkedIn page, Bluesky
and Mastodon (Ben's voice, the `benampel` skill's rules).

It is a kind of post the standing approvals do NOT cover (docs/social-posting.md, "Studio notes"). So this module only
ever writes DRAFTS: a `social.py` queue item with status draft, and an approval-queue item with `needs_ben: true` that
the daily auto-approver cannot pass. Ben's yes in chat is what lets `social.py approve` run, unless `queue --auto` is used: since 2026-11-03 Ben's standing
approval ("Standing approval for notes") covers a note that passes this gate, on LinkedIn company page, Bluesky and
Mastodon only. `--auto` approves it under that approval, checks the link answers 200, and notifies Ben with the text so
he can cancel before it goes out (it is scheduled for the next day at 10:30 ET).

  material   what happened this week (merged PRs, logged changes), written to a private brief
  queue      validate a drafted note file, tag its links through the marketing hub, write both queue items
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from . import config, hubtags, items, paths
from .daily import vet

PLATFORMS = ["linkedin", "bluesky", "mastodon"]
CAMPAIGN = "studio-note"
HARD_CTA = re.compile(r"\b(buy now|buy it|download now|sign up|start (your|a) (free )?trial|limited time|don't miss|"
                      r"get it (now|today)|order now|act now)\b", re.I)
NAMED = re.compile(r"\b(Ben|Ampel|Benjamin)\b")


class NoteError(Exception):
    pass


def parse_note(text: str) -> tuple[dict, dict[str, str]]:
    """Front matter (`key: value` lines between ---) and `## platform` sections."""
    m = re.match(r"---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not m:
        raise NoteError("the note needs front matter between --- lines (slug, link, asset)")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    sections: dict[str, str] = {}
    cur = None
    for line in m.group(2).splitlines():
        h = re.match(r"##\s+(\w+)\s*$", line)
        if h:
            cur = h.group(1).lower()
            sections[cur] = ""
        elif cur:
            sections[cur] += line + "\n"
    return meta, {k: v.strip() for k, v in sections.items()}


def problems(meta: dict, sections: dict[str, str]) -> list[str]:
    out = []
    for p in PLATFORMS:
        if not sections.get(p):
            out.append(f"missing a ## {p} section")
    for p, text in sections.items():
        if p not in PLATFORMS:
            out.append(f"unknown section ## {p}")
            continue
        out += [f"{p}: {x}" for x in vet.voice_problems(text)]
        if p != "mastodon" and NAMED.search(vet.strip_urls(text)):
            out.append(f"{p}: the note is unnamed; it does not say who writes it")
        if meta.get("cta", "none") != "hard" and HARD_CTA.search(text):
            out.append(f"{p}: hard call to action (set `cta: hard` only if Ben asked for one this week)")
    if sections.get("mastodon"):
        out += [f"mastodon: {x}" for x in vet.ben_voice_problems(sections["mastodon"])]
    link = meta.get("link", "")
    if link and not hubtags.on_site(link):
        out.append("link must be on purplelink.llc (it gets a hub tag)")
    if not link:
        for p, text in sections.items():
            if "{link}" in text:
                out.append(f"{p}: has {{link}} but the note has no link")
    return out


def _week_scheduled(meta: dict) -> str:
    if meta.get("at"):
        return meta["at"]
    t = dt.datetime.now().astimezone()
    t = (t + dt.timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0)
    return items.iso(t)


def make_items(meta: dict, sections: dict[str, str], auto: bool = False) -> items.Item:
    bad = problems(meta, sections)
    if bad:
        raise NoteError("not queued:\n  " + "\n  ".join(bad))
    link = meta.get("link", "")
    stamp = dt.date.today().strftime("%y%m%d")
    it = items.create(f"studio-note-{meta['slug']}", platforms=list(PLATFORMS), link=link, campaign=CAMPAIGN,
                      when=_week_scheduled(meta))
    it.sections = {p: sections[p] for p in PLATFORMS}
    it.preface = ("Studio note. NOT covered by any standing approval: Ben's own yes in chat, then `social.py approve`. "
                  "Replaces that day's automated post on these platforms only if approved before the daily pick (09:30 ET).")
    it.meta["experiment_note"] = "studio note against the automated daily posts of the same week (clicks per post, replies)"
    it.meta["source"] = items.STUDIO_STANDING_SOURCE
    if not auto:
        it.meta["needs_ben"] = True
    if link:
        it.meta["utm_contents"] = {p: hubtags.tag(link, meta.get("asset", "studio"), p, CAMPAIGN,
                                                  preferred=f"studio-note-{stamp}-{p}") for p in PLATFORMS}
    it.save()
    errs, _warn = items.validate(it, config.load())
    if errs:
        items.cancel(it)
        raise NoteError("social.py validate failed:\n  " + "\n  ".join(errs))
    return it


def auto_approve(it: items.Item, meta: dict, http=None) -> None:
    """Approve under the standing approval after one more check: the note's link answers 200 and stays on its page."""
    link = meta.get("link", "")
    if link:
        if http is None:
            from .daily import lib219
            http = lib219.Http()
        bad = vet.link_problems(http, link)
        if bad:
            raise NoteError("not auto-approved (left as a draft for Ben): " + "; ".join(bad))
    items.approve_studio_standing(it, config.load())


def queue_markdown(it: items.Item, meta: dict, why: list[str], auto: bool = False) -> str:
    today = dt.date.today()
    qid = f"q-{today:%Y%m%d}-studio-{meta['slug']}"[:60]
    expires = (today + dt.timedelta(days=5)).isoformat()
    when = it.meta["scheduled_at"]
    drafts = it.raw_text("linkedin")   # {link} stays literal: the tag lives on the social item, and a tag may appear once.  # the queue lint caps a post draft at 220 words; the other two go under Verify
    others = "\n".join(f"  {p.capitalize()}: {it.raw_text(p)}" for p in PLATFORMS if p != "linkedin")
    why_lines = "\n".join(f"- {w}" for w in why) or "- Weekly studio note (Ben's 2026-11-03 yes to the Adam Robinson recommendations 3, 4 and 6)."
    approve_note = (f"Nothing to do: already approved under the standing approval. To stop it, `social.py cancel {it.id}` before the time above." if auto else f"In chat, say yes. A session then runs `approval_queue.py approve {qid} --by-ben` and `social.py approve {it.id}`.")
    needs = "" if auto else "needs_ben: true\n"
    ask_lead = "FYI, approved under your 2026-11-03 standing approval:" if auto else "Approve"
    ask_tail = ("It goes out at the time below unless you cancel it first (`social.py cancel`)." if auto else
                "Drafted, not scheduled to go until you say yes. It is outside the standing approvals, so the daily auto-approver cannot pass it.")
    return f"""---
id: {qid}
created: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}
job: weekly-studio-note
model: "hosted:claude"
kind: post
target: "Studio note {today.isoformat()}: LinkedIn company page, Bluesky, Mastodon"
executor: ben
risk: low
effort_minutes: 3
expires: {expires}
expected_effect: "A few clicks per post (estimate); the test is tone against the automated daily posts"
ledger: proposed
status: pending
assets: {meta.get('asset', 'studio')}
channel: social
{needs}---

## Ask
{ask_lead} this week's studio note for the company LinkedIn page, Bluesky and Mastodon (Mastodon text is in your voice; the three texts are in Draft and Verify). {ask_tail}

## Why now
{why_lines}

## Draft
```
{drafts}
```

## Verify
- Every fact comes from the sources listed under Evidence; the link answers 200 (checked when queued).
- Social draft item: `{it.id}`, scheduled {when}, status {'approved' if auto else 'draft'}. `social.py preview {it.id}` shows the exact text.
- The Draft above is the LinkedIn text. The same note on the other platforms ({{link}} is replaced at posting by the research page with that platform's own hub tag; see the social item):
{others}

## If approved
{approve_note} `social.py run-due` posts it at {when}; because it is approved before the 09:30 ET daily pick that day, the pick skips these platforms. Never from Ben's personal LinkedIn.

## If rejected
Give one reason code (tone, wrong-target, wrong-fact, not-now, no-value, risk). A session cancels `{it.id}` with `social.py cancel`.

## Evidence
{meta.get('evidence', 'See the private material brief under docs/growth-briefs/studio-notes/.')}
"""


def merged_prs(days: int = 7) -> list[dict]:
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    r = subprocess.run(["gh", "pr", "list", "--repo", "purplelink-llc/purplelink", "--state", "merged", "--search",
                        f"merged:>={since}", "--limit", "100", "--json", "number,title,mergedAt,body"],
                       capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise NoteError(f"gh pr list failed: {r.stderr[:200]}")
    return sorted(json.loads(r.stdout), key=lambda p: p["mergedAt"])


def logged_changes(days: int = 7) -> list[dict]:
    f = paths.change_logger().with_name("changes.jsonl")
    if not f.exists():
        return []
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = []
    for line in f.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("date", "") >= since:
            rows.append(row)
    return rows


def material(days: int = 7) -> str:
    """Markdown brief the drafter reads. Private: written under docs/growth-briefs/, which is git-ignored."""
    prs, changes = merged_prs(days), logged_changes(days)
    out = [f"# Studio note material, week to {dt.date.today().isoformat()}", "",
           "Pick ONE real thing: a bug, a user request, a number, a decision. Story first, no hard call to action. "
           "First person, unnamed. Check each fact against the PR or log row it came from.", "",
           f"## Merged PRs ({len(prs)})"]
    for p in prs:
        out.append(f"- #{p['number']} {p['mergedAt'][:10]} {p['title']}")
    out += ["", f"## Logged changes ({len(changes)})"]
    for c in changes:
        out.append(f"- {c.get('date')} [{c.get('area')}] {c.get('what', '')[:220]}")
    return "\n".join(out) + "\n"


def run_new(path: str) -> str:
    """Run approval_queue.py new on a rendered markdown file. Returns the tool's output."""
    r = subprocess.run([sys.executable, str(paths.repo_root() / "scripts" / "queue" / "approval_queue.py"), "new", path],
                       capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()


def approve_queue_item(run_new_output: str) -> None:
    """Record the standing approval on the approval-queue item (first `q-...` id in the output of `new`)."""
    m = re.search(r"\b(q-\d{8}-[\w-]+)\s+->\s+pending", run_new_output)
    if not m:
        return
    subprocess.run([sys.executable, str(paths.repo_root() / "scripts" / "queue" / "approval_queue.py"), "approve", m.group(1),
                    "--note", "standing approval (Ben, 2026-11-03, studio notes); socialpost.studio gate passed"],
                   capture_output=True, text=True, timeout=120)
