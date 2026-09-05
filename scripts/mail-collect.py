#!/usr/bin/env python3
"""Collect platform stats from notification email instead of browser sessions.

WHY THIS EXISTS
Six live browser logins is a fragile foundation -- FAA, Shutterstock and Getty
sessions all died within hours on 2026-08-08/09, and Dreamstime now serves a
human-check to the collector entirely. Email is durable: the platforms push
sale and review notifications, and a mailbox doesn't log itself out.

CREDENTIALS ARE NEVER STORED HERE AND NEVER SEEN BY THE AGENT.
Uses an app-specific password held in the macOS Keychain, read at runtime only,
exactly like the FTP uploaders:

    security add-generic-password -a "ben.ampel@gmail.com" -s gmail-imap -w

(Create the app password at https://myaccount.google.com/apppasswords -- it is
scoped to mail and revocable, unlike your account password.)

SCOPE
Reads ONLY messages from the sender list below, only their subject/plain body,
and only within --days. It does not touch the rest of the mailbox, never
deletes, never sends, and never marks anything read (uses BODY.PEEK).

USAGE
  scripts/mail-collect.py --discover --days 30   # what's actually arriving
  scripts/mail-collect.py --dump adobe --days 30 # show bodies, to write parsers
  scripts/mail-collect.py --days 1               # parse into snapshots.csv
"""
import argparse, csv, datetime, email, imaplib, json, os, re, subprocess, sys
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
AN = WS / "analytics"
SNAPSHOTS = AN / "snapshots.csv"
RAW = AN / "mail-samples"

IMAP_HOST = "imap.gmail.com"
KEYCHAIN_SERVICE = "gmail-imap"

# Only these senders are ever fetched. Narrow on purpose.
SENDERS = {
    "adobe_stock":  ["@stock.adobe.com", "@adobe.com"],
    "shutterstock": ["@shutterstock.com"],
    "alamy":        ["@alamy.com"],
    "dreamstime":   ["@dreamstime.com"],
    "getty":        ["@gettyimages.com", "@istockphoto.com"],
    "fineartamerica": ["@fineartamerica.com", "@pixels.com"],
}


def password(account):
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", account,
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit(
            f"No Keychain entry for {account} / {KEYCHAIN_SERVICE}.\n"
            f'Add one (it prompts, so it stays out of shell history):\n'
            f'  security add-generic-password -a "{account}" -s {KEYCHAIN_SERVICE} -w\n'
            f"Use a Google APP PASSWORD, not your account password:\n"
            f"  https://myaccount.google.com/apppasswords")


def decode(s):
    if not s:
        return ""
    out = []
    for part, enc in decode_header(s):
        out.append(part.decode(enc or "utf-8", "ignore") if isinstance(part, bytes) else part)
    return "".join(out)


def body_text(msg):
    """Plain-text body only. HTML is stripped to text rather than parsed."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", "ignore")
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    html = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", "ignore")
                    return re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    continue
        return ""
    try:
        raw = msg.get_payload(decode=True)
        txt = raw.decode(msg.get_content_charset() or "utf-8", "ignore") if raw else ""
        return re.sub(r"<[^>]+>", " ", txt) if "<html" in txt.lower() else txt
    except Exception:
        return ""


SEEN = AN / "mail-seen.json"


def load_seen():
    import json as _j
    return set(_j.loads(SEEN.read_text())) if SEEN.exists() else set()


def save_seen(ids):
    import json as _j
    SEEN.write_text(_j.dumps(sorted(ids), indent=0))


def fetch(account, days, only=None):
    """Return [(platform, date, subject, body, msgid)] for the configured senders.

    NOTE ON DOUBLE-COUNTING: IMAP's SINCE is date-inclusive, so `--days 1`
    returns yesterday's mail as well as today's. Event metrics are summed, so a
    single "2 rejected" email was being counted again every run and read as two
    fresh rejections each day. Messages are now identified by Message-ID and
    counted once, ever.
    """
    pw = password(account)
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    out = []
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        M.login(account, pw)
        # "[Gmail]/All Mail" rather than INBOX: Gmail files plenty of platform
        # mail straight to a label or the archive, and an INBOX-only search
        # reports those as "never sent". All Mail covers everything except
        # Spam and Trash. readonly so nothing is ever marked as read.
        if M.select('"[Gmail]/All Mail"', readonly=True)[0] != "OK":
            M.select("INBOX", readonly=True)
        for platform, domains in SENDERS.items():
            if only and platform != only:
                continue
            for dom in domains:
                typ, ids = M.search(None, f'(SINCE {since} FROM "{dom}")')
                if typ != "OK":
                    continue
                for num in ids[0].split():
                    typ, dat = M.fetch(num, "(BODY.PEEK[])")
                    if typ != "OK" or not dat or not dat[0]:
                        continue
                    msg = email.message_from_bytes(dat[0][1])
                    mid = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
                    out.append((platform,
                                decode(msg.get("Date", "")),
                                decode(msg.get("Subject", "")),
                                body_text(msg),
                                mid or f"{platform}:{decode(msg.get('Subject',''))[:60]}"))
    finally:
        try:
            M.logout()
        except Exception:
            pass
    # DEDUPE WITHIN THE FETCH. Several platforms are listed under more than one
    # sender domain (Adobe under both @stock.adobe.com and @adobe.com), so the
    # same message is returned once per matching domain -- 11 rows for 7 real
    # messages. The persisted seen-list only guards across RUNS, so a message
    # duplicated inside a single run was counted once per copy, and the ADDITIVE
    # metrics ("16 accepted") would have doubled.
    seen_ids, uniq = set(), []
    for m in out:
        if m[4] in seen_ids:
            continue
        seen_ids.add(m[4])
        uniq.append(m)
    return uniq


# --- per-platform parsers -----------------------------------------------------
# Written against REAL messages only. Until a sample has been seen for a
# platform, its parser stays None so the collector reports "no parser yet"
# rather than silently inventing a zero -- the same failure that let a broken
# scraper report success all week.

def _clean(body):
    """HTML-stripped, whitespace-collapsed text. These are marketing templates,
    so structure is unreliable -- match on wording, not markup."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def parse_adobe(subject, body):
    """Review summary. The template prints the three NUMBERS first and their
    LABELS after, e.g. "SUMMARY 43 0 0 Accepted Pending Reminders Weren't
    accepted" -- so position, not proximity, is what identifies them.
    """
    out = {}
    t = _clean(body)
    if "Updates from your Adobe Stock submission" in subject or "SUMMARY" in t:
        m = re.search(r"SUMMARY\s+(\d+)\s+(\d+)\s+(\d+)\s+Accepted", t, re.I)
        if m:
            out["email_accepted"] = int(m.group(1))
            out["email_pending_reminders"] = int(m.group(2))
            out["email_not_accepted"] = int(m.group(3))
    m = re.search(r"\$\s*([\d,]+\.\d{2})", t)
    if m:
        out["email_earnings"] = float(m.group(1).replace(",", ""))
    return out


def parse_dreamstime(subject, body):
    out = {}
    t = _clean(body)
    if "Selected images" in subject:
        m = re.search(r"(\d+)\s+images?\s+(?:were|was)\s+approved", t, re.I)
        if m:
            out["email_approved"] = int(m.group(1))
    if "not selected" in subject.lower():
        m = re.search(r"(\d+)\s+images?\s+(?:were|was)\s+refused", t, re.I)
        if m:
            out["email_refused"] = int(m.group(1))
    if "transferred to editorial" in subject.lower():
        # one email per image; counted by the caller summing across messages
        out["email_rf_to_editorial"] = 1
    return out


def parse_alamy(subject, body):
    out = {}
    s = subject.lower()
    if "passed qc" in s:
        out["email_qc_passed"] = 1
    elif "failed qc" in s or "did not pass" in s:
        out["email_qc_failed"] = 1
    return out


def parse_getty(subject, body):
    """Contributor onboarding, plus the batch verdicts.

    "Submission Batch Summary" is the ONLY place Getty reports review outcomes
    per batch; ESP shows live counts but not the decision email, and the ESP
    session expires far more often than the mailbox does. The table renders as
    a flat run of numbers once tags are stripped:

        <batch name> <batch id> <total> <accepted> <rejected> <to revise>

    so rows are anchored on the 8-digit batch id followed by exactly four
    integers, rather than on column headers that only exist in the HTML.
    """
    out = {}
    s = subject.lower()
    if "invitation" in s or "welcome to the getty" in s:
        out["email_accepted_contributor"] = 1
    if "submission batch summary" in s:
        t = _clean(body)
        rows = re.findall(r"\b(\d{8})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\b", t)
        if rows:
            out["email_batch_total"] = sum(int(r[1]) for r in rows)
            out["email_accepted"] = sum(int(r[2]) for r in rows)
            out["email_rejected"] = sum(int(r[3]) for r in rows)
            out["email_to_revise"] = sum(int(r[4]) for r in rows)
    return out


def parse_fineartamerica(subject, body):
    """FAA's "Weekly Update" — the only session-free view of FAA activity.

    It carries per-image VISITOR counts, which the control panel only shows as
    one aggregate. It carries NO money: no balance, no earnings, no sale rows.
    So this supplements the FAA collector rather than replacing it, and the
    balance still needs either a login or the Excel export from
    Behind the Scenes -> Accounting -> Balance.

    Format (verified against the 2026-08-09 update):
        Recent Visitors to Your Artwork ...
        Visitors: 57  Last Visitor: Albany, KY
        Visitors: 54  Last Visitor: , United Kingdom
    Fifteen images, descending. The body opens with a large CSS block, so tags
    are stripped before matching rather than after.

    `email_faa_visitors_nocity` counts "Last Visitor" entries with a country but
    NO city. Real traffic usually resolves to a city; a run of bare country
    entries is the signature of the bot traffic that makes FAA's headline
    visitor count read as demand when nothing else on the account moves.
    """
    t = _clean(re.sub(r"(?is)<style.*?</style>", " ", body)).replace("&nbsp;", " ")
    if "Recent Visitors to Your Artwork" not in t:
        return {}
    vis = [int(x) for x in re.findall(r"Visitors:\s*(\d+)", t)]
    if not vis:
        return {}
    locs = re.findall(r"Last Visitor:\s*([^V]{0,40}?)\s*(?:Visitors:|$)", t)
    nocity = sum(1 for l in locs if l.strip().startswith(","))
    return {"email_faa_visitors_top": sum(vis),
            "email_faa_images_listed": len(vis),
            "email_faa_best_image_visitors": max(vis),
            "email_faa_visitors_nocity": nocity}


PARSERS = {
    "adobe_stock": parse_adobe,
    "dreamstime": parse_dreamstime,
    "alamy": parse_alamy,
    "getty": parse_getty,
    # Nothing but onboarding/marketing has arrived from these two yet, so there
    # is no format to parse. Left None deliberately: a parser written against
    # imagined wording would report zeros that look like real data.
    "shutterstock": None,
    "fineartamerica": parse_fineartamerica,
}
# Metrics that are per-message events and should be summed across the day,
# rather than last-value-wins like a balance reading.
ADDITIVE = {"email_rf_to_editorial", "email_qc_passed", "email_qc_failed",
            "email_approved", "email_refused", "email_accepted_contributor"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="ben.ampel@gmail.com")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--discover", action="store_true",
                    help="list what each platform actually sends")
    ap.add_argument("--dump", help="print bodies for one platform, to write a parser")
    ap.add_argument("--reparse", action="store_true",
                    help="ignore the seen-list and re-read every message in the "
                         "window. Needed whenever a parser is ADDED: dedup is by "
                         "Message-ID regardless of whether a parser existed at "
                         "the time, so mail read before the parser was written "
                         "is otherwise skipped forever.")
    a = ap.parse_args()

    msgs = fetch(a.account, a.days, only=a.dump)

    if a.discover:
        seen = {}
        for platform, date, subj, _b, _id in msgs:
            seen.setdefault(platform, []).append((date[:16], subj[:70]))
        for platform in SENDERS:
            got = seen.get(platform, [])
            state = "parser ready" if PARSERS.get(platform) else "NO PARSER YET"
            print(f"\n{platform}  ({len(got)} message(s) in {a.days}d)  [{state}]")
            for d, s in got[:8]:
                print(f"    {d}  {s}")
        return

    if a.dump:
        RAW.mkdir(parents=True, exist_ok=True)
        for i, (platform, date, subj, body, _id) in enumerate(msgs, 1):
            p = RAW / f"{platform}-{i:02d}.txt"
            p.write_text(f"DATE: {date}\nSUBJECT: {subj}\n\n{body[:4000]}")
            print(f"  wrote {p.name}  ({subj[:60]})")
        print(f"\n{len(msgs)} sample(s) in {RAW}")
        return

    # parse into the same tidy CSV the browser collector writes
    today = datetime.date.today().isoformat()
    rows = []
    if SNAPSHOTS.exists():
        rows = [r for r in csv.DictReader(open(SNAPSHOTS))
                if not (r["snapshot_date"] == today and r["metric"].startswith("email_"))]
    # Aggregate first: several messages can describe the same day (Dreamstime
    # sends one mail per transferred image), so event counts sum and readings
    # take the latest value.
    seen = set() if a.reparse else load_seen()
    fresh = [m for m in msgs if m[4] not in seen]
    print(f"{len(msgs)} message(s) matched, {len(fresh)} not yet counted")
    agg = {}
    for platform, _date, subj, body, mid in fresh:
        fn = PARSERS.get(platform)
        if not fn:
            continue
        for k, v in fn(subj, body).items():
            key = (platform, k)
            if k in ADDITIVE:
                agg[key] = agg.get(key, 0) + v
            else:
                agg[key] = v
    added = 0
    for (platform, k), v in sorted(agg.items()):
        rows.append({"snapshot_date": today, "platform": platform,
                     "metric": k, "value": v, "note": "from email"})
        added += 1
    save_seen(seen | {m[4] for m in fresh})
    rows.sort(key=lambda r: (r["snapshot_date"], r["platform"], r["metric"]))
    AN.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOTS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["snapshot_date", "platform", "metric", "value", "note"])
        w.writeheader(); w.writerows(rows)
    print(f"parsed {len(msgs)} message(s); wrote {added} metric row(s) to {SNAPSHOTS.name}")
    missing = [p for p, f in PARSERS.items() if not f]
    if missing:
        print("no parser yet for: " + ", ".join(missing))
        print("run --discover, then --dump <platform> to see real samples")


if __name__ == "__main__":
    main()
