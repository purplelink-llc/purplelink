#!/usr/bin/env python3
"""Reddit desk: hand Ben the next Reddit post so posting it takes a paste and a click.

Ben posts every Reddit post himself (memory feedback_reddit-posting-manual.md). This script never posts, comments,
votes or clicks anything on Reddit, and it never calls Reddit's API. It opens one page in Chrome, puts text on the
clipboard and records what Ben reports back.

The post text lives in the approval queue (~/.purplelink/queue, scripts/queue/approval_queue.py): the first fenced
block under "## Draft", whose first line is "Title: ...". The day's order lives in a private schedule file,
Outreach/reddit-desk/desk.json in the main checkout (git-ignored, never added):

  {"posts": [{"id": "q-20261103-rd01", "sub": "MacOSApps", "flair": "Utilities", "slot": "2026-11-03T18:10",
              "kind": "post", "app": "keyfeel", "images": ["images/keyfeel-collage.png"], "note": "..."},
             {"id": "q-...", "sub": "iosapps", "kind": "comment", "thread": "https://www.reddit.com/r/...", ...},
             {"id": "acad-8-months", "queue": "q-...", "file": "replies/....md", "sub": "AskAcademia", "kind": "comment", ...}]}

"queue" names the queue item when the schedule id differs from it; "file" takes the text from a reply file instead of the
item's Draft block (a second, unlinked reply kept in one queue item). A queue item marked needs_ben: true is approved with
--by-ben when Ben records his own post, since posting it himself is his yes.

  reddit_desk.py status                    the schedule: posted, due, waiting
  reddit_desk.py next [--force] [--no-open]
                                           next due item: open its submit page (title prefilled) or thread,
                                           copy the body, print the flair and what to check
  reddit_desk.py title ID                  copy the title (when Reddit drops the prefilled one)
  reddit_desk.py done ID --url PERMALINK   record it: queue item to done (marketing hub), tally row
  reddit_desk.py copy FILE [--open URL]    copy a drafted comment reply and open the comment to reply to
  reddit_desk.py check [--days 7]          per post: archive score and comments, visits, trials and checkout
                                           clicks for its utm_content (stats function); writes checks.json

Pacing is enforced: at least MIN_GAP minutes since the last recorded post (--force overrides) and never two posts
in one subreddit on the same day (no override). Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_GAP = 15  # minutes between posts; Reddit's spam filter reacts to bursts from one account
ARCTIC = "https://arctic-shift.photon-reddit.com/api/posts/ids?ids="
PERMALINK = re.compile(r"^https://(?:www\.|old\.)?reddit\.com/r/([A-Za-z0-9_]+)/comments/([a-z0-9]+)(?:/[^\s?#]*)?", re.I)


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main_checkout() -> Path:
    """Outreach/ is git-ignored, so it exists only in the main checkout, not in a worktree this script runs from."""
    try:
        common = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
        return Path(common).parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        return HERE.parent


def desk_dir() -> Path:
    return Path(os.environ.get("REDDIT_DESK_DIR") or main_checkout() / "Outreach" / "reddit-desk")


def queue():
    return load("approval_queue", HERE / "queue" / "approval_queue.py")


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n")
    tmp.replace(path)


def schedule() -> list:
    posts = read_json(desk_dir() / "desk.json", {}).get("posts") or []
    if not posts:
        sys.exit(f"no posts in {desk_dir() / 'desk.json'}")
    return posts


def state() -> dict:
    return read_json(desk_dir() / "state.json", {"posted": {}})


def slot_time(p: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(p["slot"]).astimezone()


def text_of(item_id: str) -> tuple[str, str, dict]:
    """(title, body, queue item) from the item's first fenced Draft block."""
    q = queue()
    it = q.find_item(item_id)
    blocks = q.drafts_of(q.sections(it["body"]).get("Draft", ""))
    if not blocks:
        sys.exit(f"{item_id}: no fenced block under ## Draft")
    lines = blocks[0].strip("\n").split("\n")
    title = ""
    if lines and lines[0].lower().startswith("title:"):
        title = lines.pop(0).split(":", 1)[1].strip()
    return title, "\n".join(lines).strip() + "\n", it


def text_for(p: dict) -> tuple[str, str, dict]:
    """(title, body, queue item) for a schedule entry: its reply file, or its queue item's Draft block."""
    qid = p.get("queue", p["id"])
    if not p.get("file"):
        return text_of(qid)
    path = desk_dir() / p["file"]
    if not path.is_file():
        sys.exit(f"missing reply file: {path}")
    return "", path.read_text().strip() + "\n", queue().find_item(qid)


def utm_content(body: str) -> str:
    m = re.search(r"utm_content=([\w.\-]+)", body)
    return m.group(1) if m else ""


def pbcopy(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def open_in_chrome(url: str) -> None:
    # One tab, the one Ben is about to use. No other window is touched.
    subprocess.run(["open", "-a", "Google Chrome", url], check=True)


def submit_url(sub: str, title: str, images: bool = False) -> str:
    # An image post shows the picture in the feed; its body text field takes the same markdown as a text post.
    q = {"type": "IMAGE", "title": title} if images else {"type": "TEXT", "selftext": "true", "title": title}
    return f"https://www.reddit.com/r/{sub}/submit?" + urllib.parse.urlencode(q)


def image_paths(p: dict) -> list[Path]:
    """Screenshots and collages for the post, relative to the desk folder. Every post should have one (Ben, 2026-11-03)."""
    paths = [desk_dir() / x for x in p.get("images") or []]
    missing = [str(x) for x in paths if not x.is_file()]
    if missing:
        sys.exit("missing image: " + ", ".join(missing))
    return paths


def last_post_time(st: dict) -> dt.datetime | None:
    times = [dt.datetime.fromisoformat(v["at"]) for v in st["posted"].values() if v.get("at")]
    return max(times) if times else None


def posted_today_in(st: dict, sub: str, day: dt.date) -> str | None:
    """A linked (promotional) post or reply already made in this subreddit today. Unlinked replies do not count."""
    for pid, v in st["posted"].items():
        if (v.get("utm_content") and v.get("sub", "").lower() == sub.lower()
                and dt.datetime.fromisoformat(v["at"]).date() == day):
            return pid
    return None


def due(posts: list, st: dict, t: dt.datetime) -> tuple[dict | None, dict | None]:
    """(first post due now, first post still waiting) among those not posted yet, in schedule order."""
    open_posts = [p for p in posts if p["id"] not in st["posted"] and not p.get("skip")]
    for p in open_posts:
        if slot_time(p) <= t:
            return p, None
    return None, (open_posts[0] if open_posts else None)


def cmd_status(a) -> None:
    st, t = state(), now()
    for p in schedule():
        v = st["posted"].get(p["id"])
        if v:
            mark = f"posted {v['at'][11:16]}  {v['url']}"
        elif p.get("skip"):
            mark = "skipped: " + p["skip"]
        else:
            mark = "due" if slot_time(p) <= t else "waiting"
        print(f"{p['slot'][5:16]}  r/{p['sub']:<18} {p['id']:<20} {mark}")
    last = last_post_time(st)
    if last:
        gap = MIN_GAP - (t - last).total_seconds() / 60
        print(f"\nlast post {last:%H:%M}; " + (f"next allowed in {gap:.0f} min" if gap > 0 else "next allowed now"))


def cmd_next(a) -> None:
    st, t = state(), now()
    p, waiting = due(schedule(), st, t)
    if not p:
        if waiting and a.force:
            p = waiting
        else:
            sys.exit("nothing left" if not waiting else f"next is r/{waiting['sub']} at {waiting['slot'][11:16]} (--force to take it now)")
    last = last_post_time(st)
    if last and (t - last).total_seconds() < MIN_GAP * 60 and not a.force:
        sys.exit(f"last post was {last:%H:%M}; wait until {(last + dt.timedelta(minutes=MIN_GAP)):%H:%M} (--force overrides)")
    title, body, it = text_for(p)
    clash = posted_today_in(st, p["sub"], t.date()) if utm_content(body) else None
    if clash:
        sys.exit(f"r/{p['sub']} already had {clash} today; move {p['id']} to another day in desk.json")
    ok = ("pending", "approved", "done") if p.get("file") else ("pending", "approved")
    if it["folder"] not in ok:
        sys.exit(f"{it['fm'].get('id')} is in {it['folder']}/, not {' or '.join(ok)}")
    kind = p.get("kind", "post")
    images = image_paths(p)
    url = p["thread"] if kind == "comment" else submit_url(p["sub"], title, bool(images))
    pbcopy(body)
    if not a.no_open:
        open_in_chrome(url)
        if images:
            subprocess.run(["open", "-R", str(images[0])], check=True)  # Finder, file selected, ready to drag
    print(f"{p['id']}  r/{p['sub']}  ({kind})")
    if kind == "post":
        print(f"\nTitle (prefilled; if it is empty, run: python3 scripts/reddit_desk.py title {p['id']}):\n  {title}")
        print(f"Flair: {p.get('flair') or 'none needed'}")
    else:
        print(f"\nThread: {url}\nPaste it as a top-level comment.")
    if images:
        print("Images (shown in Finder; drag them onto the page" + (" first, then paste the body into the body text box):" if kind == "post" else "):"))
        for x in images:
            print(f"  {x}")
    elif kind == "post":
        print("No image for this post yet: every post should carry a screenshot or collage (add 'images' in desk.json).")
    print(f"Body: on the clipboard ({len(body.split())} words). utm_content={utm_content(body) or 'none'}")
    if str(it["fm"].get("needs_ben", "")).lower() in ("true", "yes", "1"):
        print("This item is outside every standing approval: post it only if you want it out (your post is the yes).")
    if p.get("note"):
        print(f"Check first: {p['note']}")
    print("Read the rules panel on the page before posting. Paste, pick the flair, click Post yourself.")
    print(f"Then: python3 scripts/reddit_desk.py done {p['id']} --url <permalink>")


def cmd_title(a) -> None:
    p = {x["id"]: x for x in schedule()}.get(a.id) or {"id": a.id}
    title, _, _ = text_for(p)
    pbcopy(title)
    print(f"title on the clipboard: {title}")


TALLY_HEAD = ("# Reddit desk tally\n\nOne row per post Ben made by hand. Private: never git-add this folder.\n\n"
              "| Date | Subreddit | App | Title | Permalink | utm_content |\n|---|---|---|---|---|---|\n")


def tally_row(day: str, p: dict, title: str, url: str, tag: str) -> str:
    def cell(s) -> str:
        return str(s).replace("|", "/")
    return f"| {day} | r/{p['sub']} | {cell(p.get('app', ''))} | {cell(title)} | {url} | {tag} |"


def add_tally_row(path: Path, row: str) -> None:
    """Insert after the table's last row, so notes kept below the table stay below it."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TALLY_HEAD)
    lines = path.read_text().split("\n")
    last = max((i for i, ln in enumerate(lines) if ln.startswith("|")), default=len(lines) - 1)
    lines.insert(last + 1, row)
    path.write_text("\n".join(lines))


def cmd_done(a) -> None:
    p = {x["id"]: x for x in schedule()}.get(a.id)
    if not p:
        sys.exit(f"{a.id} is not in desk.json")
    m = PERMALINK.match(a.url)
    if not m:
        sys.exit("--url must be the reddit.com/r/<sub>/comments/<id>/... permalink of the post or comment")
    if m.group(1).lower() != p["sub"].lower():
        sys.exit(f"that permalink is in r/{m.group(1)}, but {a.id} is for r/{p['sub']}")
    st = state()
    if a.id in st["posted"]:
        sys.exit(f"{a.id} is already recorded: {st['posted'][a.id]['url']}")
    title, body, it = text_for(p)
    qid = it["fm"].get("id")
    aq = [sys.executable, str(HERE / "queue" / "approval_queue.py")]
    if it["folder"] == "pending":
        by_ben = ["--by-ben"] if str(it["fm"].get("needs_ben", "")).lower() in ("true", "yes", "1") else []
        subprocess.run(aq + ["approve", qid, "--note", "Ben posted it by hand from the Reddit desk; his post is the approval"]
                       + by_ben, check=True)
    if it["folder"] != "done":  # a second reply from an item already done adds a tally row only
        subprocess.run(aq + ["done", qid, "--url", a.url, "--result", f"posted by Ben in r/{p['sub']}"], check=True)
    t = now()
    tag = utm_content(body)
    if not title:
        title = "(comment) " + " ".join(body.split())[:70]
    st["posted"][a.id] = {"at": t.isoformat(timespec="minutes"), "sub": p["sub"], "url": a.url, "reddit_id": m.group(2),
                          "utm_content": tag, "title": title}
    write_json(desk_dir() / "state.json", st)
    add_tally_row(desk_dir() / "tally.md", tally_row(t.date().isoformat(), p, title, a.url, tag))
    n_today = sum(1 for v in st["posted"].values() if v["at"][:10] == t.date().isoformat())
    print(f"recorded {a.id}: {n_today} post(s) today. Next allowed at {(t + dt.timedelta(minutes=MIN_GAP)):%H:%M}.")


def cmd_copy(a) -> None:
    text = Path(a.file).read_text().strip() + "\n"
    if "—" in text:
        sys.exit("the reply has an em dash; fix it first")
    if a.open and not PERMALINK.match(a.open):
        sys.exit("--open must be a reddit.com permalink")
    pbcopy(text)
    if a.open:
        open_in_chrome(a.open)
    print(f"reply on the clipboard ({len(text.split())} words). Paste it under the comment and click Reply yourself.")


def fetch_json(url: str, headers: dict | None = None, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "purplelink-reddit-desk", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def cmd_check(a) -> None:
    """Read-only: the public archive's snapshot of each post, and the site's own per-link counts."""
    st = state()
    if not st["posted"]:
        sys.exit("nothing posted yet")
    reddit = {}
    try:
        ids = ",".join(v["reddit_id"] for v in st["posted"].values())
        reddit = {d["id"]: d for d in fetch_json(ARCTIC + ids).get("data") or []}
    except Exception as e:  # the archive rate-limits; the site counts still matter
        print(f"(archive not read: {e})")
    hub = load("hub", HERE / "hub" / "hub.py")
    tok, content = hub.stats_token(hub.paths()), {}
    if tok:
        try:
            content = fetch_json(f"{hub.STATS_URL}?days={a.days}", {"x-stats-token": tok}, 60).get("funnelByContent") or {}
        except Exception as e:
            print(f"(stats function not read: {e})")
    else:
        print("(no stats token; site counts skipped)")
    t = now()
    out = read_json(desk_dir() / "checks.json", {})
    for pid, v in st["posted"].items():
        r = reddit.get(v["reddit_id"], {})
        c = content.get(v["utm_content"], {})
        trial = c.get("trial")
        row = {"at": t.isoformat(timespec="minutes"),
               "hours": round((t - dt.datetime.fromisoformat(v["at"])).total_seconds() / 3600, 1),
               "score": r.get("score"), "comments": r.get("num_comments"), "removed": r.get("removed_by_category"),
               "visits": c.get("pageviews", 0),
               "trials": sum(trial.values()) if isinstance(trial, dict) else (trial or 0),
               "checkouts": sum((c.get("checkout") or {}).values())}
        out.setdefault(pid, []).append(row)
        removed = f"  REMOVED ({row['removed']})" if row["removed"] else ""
        print(f"r/{v['sub']:<18} +{row['hours']:>5}h  score {row['score']}  comments {row['comments']}{removed}"
              f"  visits {row['visits']}  trials {row['trials']}  checkout clicks {row['checkouts']}")
    write_json(desk_dir() / "checks.json", out)
    print("\nScores are the archive's snapshot when it ingested the post and can lag Reddit.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    n = sub.add_parser("next")
    n.add_argument("--force", action="store_true", help="take the next post before its slot or the gap")
    n.add_argument("--no-open", action="store_true", help="copy and print only")
    n.set_defaults(fn=cmd_next)
    s = sub.add_parser("title")
    s.add_argument("id")
    s.set_defaults(fn=cmd_title)
    d = sub.add_parser("done")
    d.add_argument("id")
    d.add_argument("--url", required=True)
    d.set_defaults(fn=cmd_done)
    c = sub.add_parser("copy")
    c.add_argument("file")
    c.add_argument("--open")
    c.set_defaults(fn=cmd_copy)
    k = sub.add_parser("check")
    k.add_argument("--days", type=int, default=7)
    k.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
