#!/usr/bin/env python3
"""Multi-channel social poster for Purplelink LLC. See docs/social-poster.md.

  poster.py scan [--live] [--seed]     find new guides, releases and videos on the live site; write queue items
  poster.py run [--live]               standing approval for the three event kinds, then post approved items
  poster.py status                     channels, caps used, items waiting
  poster.py whoami CHANNEL [--unpinned]  read the account the config's token belongs to (prints id and handle only)
  poster.py refresh CHANNEL            renew an expiring token (threads: 60 days; x: 2 hours)

Dry run is the default: without --live nothing is written to the queue and nothing is posted.

Standing approval (Ben, 2026-10-18) covers only guide_live, video_published and release_published items this script
wrote itself and nobody edited. Such an item moves from pending/ to approved/ only when every check passes: not
expired, the page answers 200 on the live site, the facts read again from the live page match the item, every
variant is inside its channel's limits and the house voice. Each channel then also needs: the identity check (twice),
at most 1 post that day and 3 in 7 days, and no duplicate within 30 days. Anything else waits in pending/ for Ben.

Exit codes: 0 ok, 2 bad arguments, 3 an error, 4 REFUSED (an identity check failed; nothing posted on that channel,
and that channel is not tried again that day).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "queue"))

import approval_queue as aq  # noqa: E402
import channels as chs  # noqa: E402
import events  # noqa: E402
import variants as var  # noqa: E402
from core import (CHANNELS, DAY_CAP, DUP_DAYS, STANDING_KINDS, UTM_SOURCE, WEEK_CAP, Http, Refused, Skip,  # noqa: E402
                  day_of, length_of, limit_problems, load_config, load_state, log, notify, now, save_state, short_link,
                  text_hash)

JOB = "social-poster"
EXPIRY_DAYS = {"guide_live": 7, "release_published": 7, "video_published": 5}
LABEL = {"guide_live": "guide", "release_published": "release", "video_published": "video"}


# ---------------------------------------------------------------- items
def item_text(facts: dict, vs: dict, created: dt.datetime) -> tuple[dict, str]:
    kind = facts["kind"]
    fm = {
        "created": created.isoformat(timespec="seconds"), "job": JOB, "model": "template", "kind": "post",
        "target": f"social {facts['event_key']}", "executor": "poster", "risk": "low", "effort_minutes": 1,
        "expires": (created.date() + dt.timedelta(days=EXPIRY_DAYS[kind])).isoformat(),
        "expected_effect": "a few visits per channel (estimate)", "ledger": JOB, "status": "pending",
        "event_kind": kind, "event_key": facts["event_key"],
    }
    blocks = []
    for ch, v in vs.items():
        if ch == "email":
            blocks.append(f"```email\nSubject: {v['subject']}\n\n{v['text']}\n```")
        elif ch == "devto":
            blocks.append("```devto\n" + json.dumps(v, indent=1) + "\n```\n"
                          "(dev.to body: the live article converted to Markdown when it posts, canonical_url above.)")
        else:
            blocks.append(f"```{ch}\n{v}\n```")
    fact_lines = [f"- {k}: {facts[k]}" for k in events.FACT_KEYS[kind]]
    lengths = []
    for ch, v in vs.items():
        if isinstance(v, str):
            ln = length_of(ch, v)
            if ln:
                lengths.append(f"{ch} {ln[0]}/{ln[1]}")
    body = f"""## Ask
Post this {LABEL[kind]} to every enabled channel: {facts['title']}.

## Why now
- {facts['url']} answered 200 on the live site on {created.date().isoformat()}.

## Draft
{chr(10).join(blocks)}

## Verify
Facts read from the live page {facts['url']} on {created.isoformat(timespec='minutes')}:
{chr(10).join(fact_lines)}
{"- Release notes from the live changelog https://purplelink.llc/changelog/" if kind == "release_published" else ""}
- Lengths: {", ".join(lengths)}.

## If approved
`python3 scripts/social/poster.py run --live` posts each enabled channel after the identity, cap and duplicate checks.
Standing approval (2026-10-18) moves this item here by itself when every automatic check passes.

## If rejected
Reason code please: tone / wrong-target / wrong-fact / not-now / no-value / risk.

## Evidence
Live pages only (listed above). No scraped third-party text.

## Facts
```json
{json.dumps(facts, indent=1)}
```
"""
    return fm, body


def parse_drafts(body: str) -> dict:
    sec = aq.sections(body).get("Draft", "")
    out = {}
    for ch, txt in re.findall(r"```([a-z]+)\n(.*?)\n```", sec, re.S):
        if ch == "email":
            m = re.match(r"Subject: (.*)\n\n(.*)", txt, re.S)
            out[ch] = {"subject": m.group(1).strip(), "text": m.group(2).strip()} if m else {"subject": "", "text": txt}
        elif ch == "devto":
            out[ch] = json.loads(txt)
        else:
            out[ch] = txt.strip()
    return out


def parse_facts(body: str) -> dict | None:
    m = re.search(r"```json\n(.*?)\n```", aq.sections(body).get("Facts", ""), re.S)
    try:
        return json.loads(m.group(1)) if m else None
    except ValueError:
        return None


def create_item(facts: dict, *, live: bool, offline: bool = False, at: dt.datetime | None = None) -> tuple[str, list]:
    """Write one queue item for an event. Returns (folder, problems)."""
    created = at or now()
    vs = var.build_all(facts)
    fm, body = item_text(facts, vs, created)
    probs = var.problems(vs)
    if not live:
        return ("pending" if not probs else "needs-work"), probs
    aq.ensure_root()
    fm["id"] = aq.next_id()
    others = aq.all_items()
    checks, lint_probs = aq.lint(fm, body, offline=offline, others=others, today=created.date())
    probs += lint_probs
    fm["checks"] = checks
    folder = "needs-work" if probs else "pending"
    fm["status"] = folder
    name = f"{created.date().isoformat()}-post-{aq.slugify(fm['target'])}.md"
    (aq.ROOT / folder / name).write_text(aq.join_item(fm, body))
    aq.write_index()
    aq.log_event(fm["id"], f"new:{folder}", JOB)
    aq.git_commit(f"new {fm['id']}")
    return folder, probs


def our_items(folder: str) -> list:
    return [i for i in aq.all_items() if i["folder"] == folder and i["fm"].get("job") == JOB]


def expired(fm: dict, at: dt.datetime) -> bool:
    try:
        return dt.date.fromisoformat(str(fm.get("expires"))[:10]) < day_of(at)
    except ValueError:
        return True


# ---------------------------------------------------------------- checks
def live_ok(http, url: str) -> bool:
    r = http.request("GET", url)
    return r.status == 200


def standing_problems(http, it, at: dt.datetime) -> list[str]:
    fm = it["fm"]
    if fm.get("executor") != "poster" or fm.get("event_kind") not in STANDING_KINDS:
        return ["not a standing-approval kind; Ben approves it"]
    if fm.get("status") != "pending":
        return [f"status is {fm.get('status')}; an edited or manual item needs Ben's approval"]
    if expired(fm, at):
        return ["expired"]
    facts = parse_facts(it["body"])
    if not facts or facts.get("kind") != fm.get("event_kind") or facts.get("event_key") != fm.get("event_key"):
        return ["no machine facts in the item; Ben approves it"]
    try:
        live = events.refetch(http, facts)
    except Skip as e:
        return [f"not live: {e}"]
    probs = events.fact_drift(facts, live)
    drafts = parse_drafts(it["body"])
    if set(drafts) - set(CHANNELS):
        probs.append("unknown channel in the draft")
    probs += var.problems(drafts)
    return probs


def channel_problems(st: dict, ch: str, item_id: str, event_key: str, text: str, at: dt.datetime) -> tuple[str, str]:
    """('', '') when the channel may post now; else (kind, reason). kind: refused, cap, duplicate."""
    today = day_of(at)
    if st["refused"].get(ch) == today.isoformat():
        return "refused", f"{ch}: refused earlier today; not retried until tomorrow"
    mine = [p for p in st["posts"] if p["channel"] == ch]
    real = [p for p in mine if p.get("url")]
    if sum(1 for p in real if p["date"] == today.isoformat()) >= DAY_CAP:
        return "cap", f"{ch}: already posted {DAY_CAP} today"
    week_start = (today - dt.timedelta(days=6)).isoformat()
    if sum(1 for p in real if p["date"] >= week_start) >= WEEK_CAP:
        return "cap", f"{ch}: already posted {WEEK_CAP} in the last 7 days"
    dup_start = (today - dt.timedelta(days=DUP_DAYS)).isoformat()
    h = text_hash(text)
    for p in real:
        if p["date"] >= dup_start and (p.get("event_key") == event_key or p.get("hash") == h):
            return "duplicate", f"{ch}: the same event or text was posted on {p['date']}"
    return "", ""


def done_channels(st: dict, item_id: str) -> set:
    return {p["channel"] for p in st["posts"] if p["item"] == item_id}


# ---------------------------------------------------------------- run
def run(http, *, live: bool, at: dt.datetime | None = None, out=print, **adapter_kw) -> int:
    at = at or now()
    st = load_state()
    code = 0

    # 1. standing approval
    for it in our_items("pending"):
        probs = standing_problems(http, it, at)
        iid = it["fm"].get("id")
        if probs:
            out(f"{iid} waits in pending: " + "; ".join(probs))
            if live:
                log("standing-wait", item=iid, reasons=probs)
            continue
        if not live:
            out(f"{iid} would move to approved under standing approval")
            continue
        aq.decide(it, "approved", "approved", actor="standing-approval",
                  note=f"Standing approval (Ben, 2026-10-18): checks passed {at.isoformat(timespec='minutes')} "
                       "(live 200, facts match the live page, limits, voice).")
        log("standing-approved", item=iid)
        out(f"{iid} approved under standing approval")

    # 2. post approved items, oldest first
    items = sorted(our_items("approved") if live else our_items("approved") + [
        i for i in our_items("pending") if not standing_problems(http, i, at)], key=lambda i: str(i["fm"].get("created")))
    for it in items:
        fm, iid = it["fm"], it["fm"].get("id")
        drafts, facts = parse_drafts(it["body"]), parse_facts(it["body"]) or {}
        if expired(fm, at):
            if live and it["folder"] == "approved":
                finish(it, st, "expired before every channel posted")
            out(f"{iid}: expired")
            continue
        event_key = fm.get("event_key", iid)
        for ch, draft in drafts.items():
            if ch in done_channels(st, iid):
                continue
            try:
                ad = chs.adapter(ch, http, **adapter_kw.get(ch, {}))
            except Refused as e:
                code = max(code, 4)
                refuse(st, ch, iid, str(e), live)
                out(f"{iid} {ch}: REFUSED: {e}")
                continue
            if ad is None:
                out(f"{iid} {ch}: {chs.status(ch)}")
                continue
            text = var.variant_text(draft)
            kind, why = channel_problems(st, ch, iid, event_key, text, at)
            if kind:
                out(f"{iid} {why}")
                if kind == "duplicate" and live:
                    st["posts"].append({"channel": ch, "item": iid, "event_key": event_key, "hash": text_hash(text),
                                        "date": day_of(at).isoformat(), "url": None, "duplicate": True})
                continue
            if ch not in ("devto", "email") and limit_problems(ch, text):
                out(f"{iid} {ch}: " + "; ".join(limit_problems(ch, text)))
                continue
            link = short_link(ch, facts) if facts else None
            if link and not live_ok(http, link):
                out(f"{iid} {ch}: {link} is not live yet (no 200); retry after the next build")
                continue
            if facts.get("url") and not live_ok(http, facts["url"]):
                out(f"{iid} {ch}: {facts['url']} is not live (no 200)")
                continue
            extra = {"title": facts.get("title", ""), "description": facts.get("description", ""),
                     "og_image": facts.get("og_image", ""), "idempotency_key": f"{iid}-{ch}"}
            if ch == "email":
                extra["subject"] = draft["subject"]
            if ch == "devto":
                tag = dev_tagger()
                try:
                    body = events.devto_markdown(http, facts, tag)
                except Skip as e:
                    out(f"{iid} devto: {e}")
                    continue
                body += f"\n\n---\n\n*Originally published at [purplelink.llc]({short_link('devto', facts)}).*\n"
                extra["article"] = {**draft, "body_markdown": body}
            if not live:
                out(f"{iid} {ch}: would post (dry run):\n{text}\n")
                continue
            try:
                url = ad.post(text, extra)
            except Refused as e:
                code = max(code, 4)
                refuse(st, ch, iid, str(e), live)
                out(f"{iid} {ch}: REFUSED: {e}")
                continue
            except Skip as e:
                log("skip", item=iid, channel=ch, reason=str(e))
                out(f"{iid} {ch}: not posted: {e}")
                continue
            except Exception as e:
                code = max(code, 3)
                log("error", item=iid, channel=ch, error=f"{type(e).__name__}: {e}")
                notify(f"{ch} post failed for {iid}: {type(e).__name__}")
                out(f"{iid} {ch}: error {type(e).__name__}: {e}")
                continue
            st["posts"].append({"channel": ch, "item": iid, "event_key": event_key, "hash": text_hash(text),
                                "date": day_of(at).isoformat(), "url": url})
            save_state(st)
            log("posted", item=iid, channel=ch, url=url)
            out(f"{iid} {ch}: posted {url}")
        if live and it["folder"] == "approved" and set(drafts) <= done_channels(st, iid):
            finish(it, st, "every channel posted or skipped as a duplicate")
    if live:
        save_state(st)
    return code


def dev_tagger():
    def tag(url: str) -> str:
        if url.startswith("https://purplelink.llc/") and "utm_" not in url:
            base, _, frag = url.partition("#")
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}utm_source={UTM_SOURCE['devto']}&utm_medium=social&utm_campaign=dev-guide" + (f"#{frag}" if frag else "")
        return url
    return tag


def refuse(st: dict, ch: str, iid: str, why: str, live: bool) -> None:
    if not live:
        return
    st["refused"][ch] = day_of(now()).isoformat()
    save_state(st)
    log("REFUSED", item=iid, channel=ch, reason=why)
    notify(f"{ch} post refused: {why[:120]}")


def finish(it, st: dict, why: str) -> None:
    iid = it["fm"]["id"]
    lines = [f"- {p['channel']}: {p['url'] or 'duplicate, skipped'}" for p in st["posts"] if p["item"] == iid]
    body = it["body"].rstrip() + f"\n\n## Result\n{why} ({now().isoformat(timespec='minutes')})\n" + "\n".join(lines) + "\n"
    aq.move(it, "done", {"status": "done"}, body)
    aq.log_event(iid, "done", JOB)
    aq.git_commit(f"done {iid}")


# ---------------------------------------------------------------- commands
def cmd_scan(a, http) -> int:
    st = load_state()
    found, notes = events.scan(http, st, seed=a.seed)
    for n in notes:
        print(f"note: {n}")
    if not found:
        print("no new events" + (" (baseline recorded; nothing is announced from before today)" if a.seed else ""))
    for f in found:
        folder, probs = create_item(f, live=a.live)
        verb = "wrote" if a.live else "would write"
        print(f"{verb} {f['event_key']} -> {folder}" + ("".join(f"\n  - {p}" for p in probs)))
    if a.live:
        save_state(st)
    else:
        print("dry run: queue and state unchanged (use --live)")
    return 0


def cmd_run(a, http) -> int:
    code = run(http, live=a.live)
    if not a.live:
        print("dry run: nothing approved or posted (use --live)")
    return code


def cmd_status(a, http) -> int:
    st = load_state()
    today = day_of(now())
    week = (today - dt.timedelta(days=6)).isoformat()
    for ch in CHANNELS:
        real = [p for p in st["posts"] if p["channel"] == ch and p.get("url")]
        d = sum(1 for p in real if p["date"] == today.isoformat())
        w = sum(1 for p in real if p["date"] >= week)
        ref = " REFUSED today" if st["refused"].get(ch) == today.isoformat() else ""
        print(f"{ch:<9} {chs.status(ch)}; today {d}/{DAY_CAP}, 7 days {w}/{WEEK_CAP}{ref}")
    print(f"items: {len(our_items('pending'))} pending, {len(our_items('approved'))} approved, "
          f"{len(our_items('needs-work'))} needs-work; baseline {'recorded' if st['seeded'] else 'not recorded yet'}")
    return 0


def cmd_whoami(a, http) -> int:
    ch = a.channel
    cfg = load_config(ch)
    if cfg is None:
        print(f"{ch}: no config file")
        return 2
    ad = chs.ADAPTERS[ch](http, cfg)
    if a.unpinned:
        ad.pin = {"id": cfg.get("id"), "handle": cfg.get("handle"), "instance": cfg.get("instance")}
    elif not chs.pinned(ch):
        print(f"{ch}: not pinned in code yet; use --unpinned to read the account for the pin")
        return 2
    try:
        got_id, handle = ad.whoami()
    except Refused as e:
        print(f"REFUSED: {e}")
        return 4
    print(f"{ch}: id {got_id}, handle {handle}")
    if not a.unpinned:
        try:
            ad.check_identity("whoami")
            print("matches the pinned company account")
        except Refused as e:
            print(f"REFUSED: {e}")
            return 4
    return 0


def cmd_refresh(a, http) -> int:
    ad = chs.adapter(a.channel, http)
    if ad is None or not hasattr(ad, "refresh"):
        print(f"{a.channel}: {chs.status(a.channel)} or has no token refresh")
        return 2
    print(f"{a.channel}: token renewed, expires {ad.refresh()}")
    return 0


def main(argv=None, http=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--live", action="store_true")
    p.add_argument("--seed", action="store_true", help="record everything live as seen; announce nothing")
    p = sub.add_parser("run")
    p.add_argument("--live", action="store_true")
    sub.add_parser("status")
    p = sub.add_parser("whoami")
    p.add_argument("channel", choices=CHANNELS)
    p.add_argument("--unpinned", action="store_true")
    p = sub.add_parser("refresh")
    p.add_argument("channel", choices=["threads", "x"])
    a = ap.parse_args(argv)
    http = http or Http()
    try:
        return {"scan": cmd_scan, "run": cmd_run, "status": cmd_status, "whoami": cmd_whoami,
                "refresh": cmd_refresh}[a.cmd](a, http)
    except Refused as e:
        print(f"REFUSED: {e}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
