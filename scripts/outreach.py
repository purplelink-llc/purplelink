#!/usr/bin/env python3
"""Run the Outreach/WEEKLY-PLAN.md cadence without a browser session.

The plan docs stay the source of truth; this script reads them, does the next
unit of work per channel, and writes the row to Outreach/OUTREACH-LOG.md.

    scripts/outreach.py status                    # what's next on each channel
    scripts/outreach.py email --next [--dry-run]  # next LibGuide email not yet sent
    scripts/outreach.py email --target rmit
    scripts/outreach.py linkedin --next [--dry-run]   # next Week-N template post
    scripts/outreach.py bluesky  --next [--dry-run]   # next Post-N template post
    scripts/outreach.py texse [--days 60] [--max-views 10000]   # candidate scan
    scripts/outreach.py weekly [--dry-run]        # what launchd runs Tue-Thu 09:30

CHANNELS
  email     Gmail SMTP with the same Keychain app password mail-collect.py uses
            (service gmail-imap, account ben.ampel@gmail.com). If a Keychain item
            for service `icloud-smtp` / account ben@purplelink.llc exists it is
            preferred, so the studio address wins once you add one:
                security add-generic-password -a ben@purplelink.llc -s icloud-smtp -w
  linkedin  Delegates to backend/scripts/linkedin_post.py --text-file (the saved
            Playwright session that already posts the daily digest).
  bluesky   atproto createRecord with an app password from Keychain:
                security add-generic-password -a purplelink.llc -s bluesky-app -w
            (make one at bsky.app -> Settings -> Privacy and security -> App
            passwords). Skipped with a notice until that item exists.
  texse     Read-only. Ranks fresh, low-view, unanswered tex.stackexchange.com
            questions against the four answer templates and writes
            Outreach/02-community/texse-candidates.md. It never posts: Stack
            Exchange sites prohibit AI-written answers, and answers there only
            carry weight under a human account writing in its own words.

Nothing here stores a credential. Everything is read from Keychain at runtime.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import smtplib
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Outreach"
LOG = OUT / "OUTREACH-LOG.md"
LIBGUIDE_DOC = OUT / "04-outreach" / "libguide-outreach.md"
LINKEDIN_DOC = OUT / "01-identity" / "linkedin-company-page.md"
BLUESKY_DOC = OUT / "01-identity" / "bluesky-setup.md"
TEXSE_OUT = OUT / "02-community" / "texse-candidates.md"
LINKEDIN_POSTER = ROOT / "backend" / "scripts" / "linkedin_post.py"

PYTHON = sys.executable
SENDER_NAME = "Benjamin Ampel"
SENDERS = [  # first one whose Keychain item exists wins
    ("ben@purplelink.llc", "icloud-smtp", "smtp.mail.me.com", 587),
    ("ben.ampel@gmail.com", "gmail-imap", "smtp.gmail.com", 465),
]
BSKY_HANDLE = "purplelink.llc"
BSKY_KEYCHAIN = "bluesky-app"
BSKY_API = "https://bsky.social/xrpc"
SE_API = "https://api.stackexchange.com/2.3"
UA = "purplelink-outreach/1.0 (+https://purplelink.llc)"

# Only the named-contact LibGuide targets are auto-queued. The Ask-form ones
# (MIT, Yale, UMass) need a web form and stay manual.
LIBGUIDE_KEYS = {"uva": 1, "rmit": 2, "montclair": 3, "tsu": 4, "fresno": 5}

# TeX SE search queries -> template in 02-community/answer-templates.md
TEXSE_QUERIES = [
    ("T1 BibTeX errors", ["bibtex error", "bibtex unbalanced braces", "citation undefined bibliography missing"]),
    ("T2 DOI to BibTeX", ["doi to bibtex", "bibtex from doi", "arxiv bibtex entry"]),
    ("T3 LaTeX to Word", ["convert tex to docx", "latex to word", "pandoc docx latex"]),
    ("T4 latexdiff", ["latexdiff", "track changes latex two versions"]),
]


# ── helpers ──────────────────────────────────────────────────────────────────

def today() -> str:
    return dt.date.today().isoformat()


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def keychain(account: str, service: str) -> str | None:
    r = subprocess.run(["security", "find-generic-password", "-a", account, "-s", service, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def notify(msg: str) -> None:
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Purplelink outreach"'],
                   capture_output=True)


def http_json(url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    h = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw) if raw else {}


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = text.replace("·", "-")  # middle-dot bullets -> plain hyphen in mail
    return text


def blockquote_block(lines: list[str], start: int) -> tuple[str, int]:
    """Collect the first `> ` block at or after `start`. Returns (text, next_index)."""
    i = start
    while i < len(lines) and not lines[i].startswith(">"):
        if lines[i].startswith("#"):
            return "", i
        i += 1
    buf = []
    while i < len(lines) and lines[i].startswith(">"):
        buf.append(lines[i][1:].lstrip(" "))
        i += 1
    return "\n".join(buf).strip(), i


# ── log ──────────────────────────────────────────────────────────────────────

def log_text() -> str:
    return LOG.read_text(encoding="utf-8")


def log_table_rows(section: str) -> list[list[str]]:
    """Rows (as cell lists) of the table under `## <section>`; skips header and placeholder rows."""
    rows = []
    in_sec = False
    for line in log_text().splitlines():
        if line.startswith("## "):
            in_sec = line[3:].strip().lower().startswith(section.lower())
            continue
        if in_sec and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= {"-"} or not any(cells):
                continue
            rows.append(cells)
    return rows[1:] if rows else []  # drop header


def log_write_row(section: str, cells: list[str], replace_match: str | None = None) -> None:
    """Append a row to the section's table, or replace the row containing `replace_match`.
    A placeholder row of empty cells is replaced by the first real row."""
    lines = log_text().splitlines()
    row = "| " + " | ".join(cells) + " |"
    in_sec = False
    last_table_line = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if in_sec and last_table_line is not None:
                break
            in_sec = line[3:].strip().lower().startswith(section.lower())
            continue
        if not in_sec or not line.startswith("|"):
            continue
        if replace_match and replace_match in line:
            lines[i] = row
            LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
        last_table_line = i
    if last_table_line is None:
        sys.exit(f"OUTREACH-LOG.md: no table under '## {section}'")
    cells_there = [c.strip() for c in lines[last_table_line].strip().strip("|").split("|")]
    if not any(cells_there):
        lines[last_table_line] = row
    else:
        lines.insert(last_table_line + 1, row)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── LibGuide email ───────────────────────────────────────────────────────────

def libguide_targets() -> dict[int, dict]:
    lines = LIBGUIDE_DOC.read_text(encoding="utf-8").splitlines()
    targets: dict[int, dict] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^## Target (\d+) — (.+)$", lines[i])
        if not m:
            i += 1
            continue
        n, title = int(m.group(1)), m.group(2).strip()
        t = {"n": n, "title": title, "contact": "", "email": "", "subject": "", "guide": ""}
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            line = lines[j]
            if line.startswith("**LibGuide:**"):
                t["guide"] = line.split("**LibGuide:**", 1)[1].strip()
            elif line.startswith("**Contact:**"):
                c = line.split("**Contact:**", 1)[1].strip()
                em = re.search(r"[\w.+-]+@[\w.-]+\.\w+", c)
                t["email"] = em.group(0) if em else ""
                t["contact"] = c.split("—")[0].strip()
            elif line.startswith("**Subject:**"):
                t["subject"] = line.split("**Subject:**", 1)[1].strip()
                t["body"], j = blockquote_block(lines, j + 1)
                continue
            j += 1
        if t["email"]:
            targets[n] = t
        i = j
    return targets


def libguide_sent_titles() -> set[str]:
    return {r[1] for r in log_table_rows("LibGuide outreach") if r[0]}


def next_libguide() -> dict | None:
    sent = libguide_sent_titles()
    for n, t in sorted(libguide_targets().items()):
        short = t["title"].split("·")[0].strip()
        if not any(short.split(" ")[0] in s for s in sent):
            return t
    return None


def pick_sender() -> tuple[str, str, str, int]:
    for addr, service, host, port in SENDERS:
        pw = keychain(addr, service)
        if pw:
            return addr, pw, host, port
    sys.exit("No SMTP credential in Keychain. Run scripts/setup-gmail.command "
             "or add: security add-generic-password -a ben@purplelink.llc -s icloud-smtp -w")


def send_email(t: dict, dry_run: bool, to_override: str | None) -> int:
    addr, pw, host, port = pick_sender()
    to = to_override or t["email"]
    body = strip_md(t["body"])
    msg = EmailMessage()
    msg["From"] = formataddr((SENDER_NAME, addr))
    msg["To"] = to
    msg["Subject"] = t["subject"]
    msg.set_content(body)
    print(f"From:    {msg['From']}\nTo:      {to}\nSubject: {t['subject']}\n\n{body}\n")
    if dry_run:
        print("[dry-run] not sent")
        return 0
    ctx = ssl_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30, context=ctx) as s:
            s.login(addr, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(addr, pw)
            s.send_message(msg)
    short = t["title"].split("·")[0].strip()
    log_write_row("LibGuide outreach",
                  [today(), short, f"{t['contact']} ({t['email']})", "sent",
                   f"Target {t['n']} template, via {addr}" + (f" (to override {to})" if to_override else "")],
                  replace_match=t["email"])
    print(f"sent -> {to}; logged")
    return 0


def cmd_email(a) -> int:
    targets = libguide_targets()
    if a.target:
        n = LIBGUIDE_KEYS.get(a.target.lower())
        t = targets.get(n) if n else None
        if not t:
            sys.exit(f"unknown target {a.target!r}; one of {', '.join(LIBGUIDE_KEYS)}")
    else:
        t = next_libguide()
        if not t:
            print("All named LibGuide targets already sent. MIT/Yale/UMass are Ask-form only (manual).")
            return 1
    return send_email(t, a.dry_run, a.to)


# ── LinkedIn / Bluesky template posts ────────────────────────────────────────

def template_posts(doc: Path, heading_re: str) -> dict[int, tuple[str, str]]:
    """{n: (topic, text)} for '### Week N — topic' / '### Post N — topic' blocks."""
    lines = doc.read_text(encoding="utf-8").splitlines()
    posts = {}
    for i, line in enumerate(lines):
        m = re.match(heading_re, line)
        if m:
            text, _ = blockquote_block(lines, i + 1)
            if text:
                posts[int(m.group(1))] = (m.group(2).strip(), text)
    return posts


def posted_numbers(platform: str) -> set[int]:
    nums = set()
    for r in log_table_rows("LinkedIn / Bluesky posts"):
        if len(r) >= 3 and r[1].lower() == platform.lower():
            m = re.search(r"Post (\d+)", r[2])
            if m:
                nums.add(int(m.group(1)))
    return nums


def next_post(platform: str) -> tuple[int, str, str] | None:
    if platform == "LinkedIn":
        posts = template_posts(LINKEDIN_DOC, r"^### Week (\d+) — (.+)$")
    else:
        posts = template_posts(BLUESKY_DOC, r"^### Post (\d+) — (.+)$")
    done = posted_numbers(platform)
    for n in sorted(posts):
        if n not in done:
            return n, *posts[n]
    return None


def cmd_linkedin(a) -> int:
    nxt = next_post("LinkedIn")
    if not nxt:
        print("LinkedIn: all template posts done.")
        return 1
    n, topic, text = nxt
    print(f"LinkedIn post {n} ({topic}):\n\n{text}\n")
    tmp = Path.home() / ".purplelink" / f"linkedin-outreach-{n}.txt"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(text + "\n", encoding="utf-8")
    cmd = [PYTHON, str(LINKEDIN_POSTER), "--text-file", str(tmp)] + (["--dry-run"] if a.dry_run else [])
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        print(f"linkedin_post.py exit {rc}" + (" (session expired: run backend/scripts/linkedin_login.py)" if rc == 2 else ""))
        return rc
    if a.dry_run:
        print("[dry-run] not posted")
        return 0
    log_write_row("LinkedIn / Bluesky posts",
                  [today(), "LinkedIn", f"Post {n} ({topic.lower()})", "TBD", "company page, via outreach.py"])
    print("posted; logged")
    return 0


URL_RE = re.compile(r"(?:https?://)?(?:[\w-]+\.)+(?:llc|com|org|net|edu|io|app|dev)(?:/[^\s),.]*[^\s),.])?")


def bsky_facets(text: str) -> list[dict]:
    facets = []
    b = text.encode("utf-8")
    for m in URL_RE.finditer(text):
        raw = m.group(0)
        uri = raw if raw.startswith("http") else "https://" + raw
        start = len(text[:m.start()].encode("utf-8"))
        facets.append({"index": {"byteStart": start, "byteEnd": start + len(raw.encode("utf-8"))},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
    assert all(f["index"]["byteEnd"] <= len(b) for f in facets)
    return facets


def cmd_bluesky(a) -> int:
    nxt = next_post("Bluesky")
    if not nxt:
        print("Bluesky: all template posts done.")
        return 1
    n, topic, text = nxt
    print(f"Bluesky post {n} ({topic}):\n\n{text}\n")
    if len(text) > 300:
        sys.exit(f"Bluesky post {n} is {len(text)} chars (>300). Shorten it in {BLUESKY_DOC.name}.")
    facets = bsky_facets(text)
    print(f"links: {[f['features'][0]['uri'] for f in facets]}")
    pw = keychain(BSKY_HANDLE, BSKY_KEYCHAIN)
    if not pw:
        print(f"SKIP: no Keychain item (service {BSKY_KEYCHAIN}, account {BSKY_HANDLE}). "
              f"Create an app password at bsky.app and run:\n"
              f"  security add-generic-password -a {BSKY_HANDLE} -s {BSKY_KEYCHAIN} -w")
        return 4
    if a.dry_run:
        print("[dry-run] not posted")
        return 0
    sess = http_json(f"{BSKY_API}/com.atproto.server.createSession",
                     {"identifier": BSKY_HANDLE, "password": pw})
    record = {"$type": "app.bsky.feed.post", "text": text,
              "createdAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "langs": ["en"]}
    if facets:
        record["facets"] = facets
    res = http_json(f"{BSKY_API}/com.atproto.repo.createRecord",
                    {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record},
                    {"Authorization": f"Bearer {sess['accessJwt']}"})
    rkey = res["uri"].rsplit("/", 1)[-1]
    url = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{rkey}"
    log_write_row("LinkedIn / Bluesky posts",
                  [today(), "Bluesky", f"Post {n} ({topic.lower()})", "TBD", url])
    print(f"posted {url}; logged")
    return 0


# ── TeX SE candidate scan ────────────────────────────────────────────────────

def cmd_texse(a) -> int:
    since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)).timestamp())
    logged = {r[1] for r in log_table_rows("TeX StackExchange answers")}
    seen: dict[int, dict] = {}
    quota = None
    for template, queries in TEXSE_QUERIES:
        for q in queries:
            params = urllib.parse.urlencode({
                "site": "tex", "order": "desc", "sort": "creation", "q": q,
                "fromdate": since, "accepted": "False", "pagesize": 30,
            })
            try:
                d = http_json(f"{SE_API}/search/advanced?{params}")
            except urllib.error.HTTPError as e:
                print(f"SE API {e.code} for {q!r}: {e.read()[:200]!r}")
                continue
            quota = d.get("quota_remaining", quota)
            for it in d.get("items", []):
                if it["view_count"] > a.max_views or it["link"] in logged:
                    continue
                if it["question_id"] in seen:
                    continue
                it["_template"] = template
                it["_query"] = q
                seen[it["question_id"]] = it
    def rank(it):  # unanswered first, then newest
        return (it["answer_count"] > 0, -it["creation_date"])
    items = sorted(seen.values(), key=rank)
    rows = ["| Asked | Views | Answers | Score | Template | Question |", "|---|---|---|---|---|---|"]
    for it in items:
        asked = dt.datetime.fromtimestamp(it["creation_date"], dt.timezone.utc).date().isoformat()
        title = re.sub(r"\|", "\\|", urllib.parse.unquote(it["title"]))
        rows.append(f"| {asked} | {it['view_count']} | {it['answer_count']} | {it['score']} | {it['_template']} | [{title}]({it['link']}) |")
    header = (f"# TeX SE candidates — {today()}\n\n"
              f"Generated by `scripts/outreach.py texse` (last {a.days} days, < {a.max_views} views, "
              f"no accepted answer, {len(items)} candidates, API quota left {quota}).\n\n"
              "Pick one, read the whole thread, and write the answer yourself in your own words, "
              "using the matching template in `answer-templates.md` only as a checklist of points. "
              "Do not paste generated text: Stack Exchange bans AI-written answers.\n\n"
              "Unanswered questions sort first. Log the one you answer in `OUTREACH-LOG.md`.\n\n")
    TEXSE_OUT.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"{len(items)} candidates -> {TEXSE_OUT.relative_to(ROOT)}  (quota left {quota})\n")
    for it in items[:a.show]:
        flag = "UNANSWERED" if it["answer_count"] == 0 else f"{it['answer_count']} ans"
        print(f"  [{it['_template'][:2]}] {flag:>10} {it['view_count']:>5}v  {it['title'][:70]}\n"
              f"        {it['link']}")
    return 0


# ── status / weekly ──────────────────────────────────────────────────────────

def cmd_status(a) -> int:
    lg = [r for r in log_table_rows("LibGuide outreach") if r[0]]
    tx = log_table_rows("TeX StackExchange answers")
    week = max(len(lg), len(tx)) + 3  # weeks 1-2 are identity + first posts
    print(f"Plan week: ~{week}  (LibGuide sent {len(lg)}/5 named, TeX SE answers {len(tx)})")
    t = next_libguide()
    print(f"Next email:    {t['title'] + ' <' + t['email'] + '>' if t else 'none (named targets done)'}")
    for p in ("LinkedIn", "Bluesky"):
        n = next_post(p)
        print(f"Next {p:9} {'Post %d (%s)' % (n[0], n[1]) if n else 'template posts done'}")
    print(f"Bluesky cred:  {'ok' if keychain(BSKY_HANDLE, BSKY_KEYCHAIN) else 'MISSING (see --help)'}")
    print(f"SMTP cred:     {pick_sender()[0]}")
    return 0


def cmd_weekly(a) -> int:
    """One pass of the weekly plan. Each step is idempotent through the log."""
    results = {}
    for name, fn in (("email", cmd_email), ("linkedin", cmd_linkedin), ("bluesky", cmd_bluesky), ("texse", cmd_texse)):
        print(f"\n== {name} ==")
        try:
            results[name] = fn(a)
        except SystemExit as e:
            print(e)
            results[name] = 5
        except Exception as e:  # keep going; one channel failing must not block the others
            print(f"{name} failed: {e!r}")
            results[name] = 6
    summary = ", ".join(f"{k}={'ok' if v == 0 else v}" for k, v in results.items())
    print(f"\nweekly: {summary}")
    if not a.dry_run:
        notify(f"Weekly outreach ran: {summary}. Candidates in texse-candidates.md")
    return 0 if all(v in (0, 1, 4) for v in results.values()) else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    e = sub.add_parser("email")
    e.add_argument("--next", action="store_true")
    e.add_argument("--target", help="|".join(LIBGUIDE_KEYS))
    e.add_argument("--to", help="override recipient (send a test to yourself)")
    sub.add_parser("linkedin").add_argument("--next", action="store_true")
    sub.add_parser("bluesky").add_argument("--next", action="store_true")
    t = sub.add_parser("texse")
    t.add_argument("--days", type=int, default=60)
    t.add_argument("--max-views", type=int, default=10000)
    t.add_argument("--show", type=int, default=8)
    sub.add_parser("weekly")
    a = ap.parse_args()
    for k, v in (("target", None), ("to", None), ("days", 60), ("max_views", 10000), ("show", 8)):
        if not hasattr(a, k):
            setattr(a, k, v)
    sys.exit({"status": cmd_status, "email": cmd_email, "linkedin": cmd_linkedin,
              "bluesky": cmd_bluesky, "texse": cmd_texse, "weekly": cmd_weekly}[a.cmd](a))


if __name__ == "__main__":
    main()
