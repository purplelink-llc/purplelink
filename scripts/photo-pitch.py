#!/usr/bin/env python3
"""Direct licensing pitches to hotels, tour operators and publishers.

Nothing here sends on its own. `queue` turns verified targets into items in
the approval queue (scripts/queue/approval_queue.py); Ben approves them in
the queue digest; `send` mails only the approved ones, with watermarked
previews attached, and logs each send in Outreach/OUTREACH-LOG.md under
"Photo licensing pitches".

  python3 scripts/photo-pitch.py queue [--n 15] [--dry-run]   # next verified, unpitched targets -> pending/
  python3 scripts/photo-pitch.py followup                     # the Hotel d'Angleterre follow-up -> pending/
  python3 scripts/photo-pitch.py send [--dry-run]             # mail every approved photo-pitch item, mark done, log
  python3 scripts/photo-pitch.py status

Targets: docs/photo-licensing/direct-pitch-targets.csv. A row is queued only
when its notes carry "VERIFIED <date>": someone opened every file named in
it and confirmed it shows what the pitch says (2026-09-25: a caption claimed
a hotel facade and the frame was a street with ornaments). The weekly
scheduled task does that check by viewing the files, then adds the marker.

Prices are the public ones on /photography/license/ ($79 commercial, $199
extended), so a prospect who opens the page finds the same number.
"""
import argparse, csv, datetime as dt, html, importlib.util, io, json, re, subprocess, sys, tempfile
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "docs" / "photo-licensing" / "direct-pitch-targets.csv"
LOG = ROOT / "Outreach" / "OUTREACH-LOG.md"
QUEUE = ROOT / "scripts" / "queue" / "approval_queue.py"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
_WS = ROOT / "photo-licensing-workspace"
WS = _WS if _WS.exists() else Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
SECTION = "Photo licensing pitches"
JOB = "photo-pitch"
LICENSE_URL = "https://purplelink.llc/photography/license/"
PRICE_ONE, PRICE_EXT = 79, 199
SIGN = "Benjamin Ampel\nPurplelink LLC, Atlanta\nben@purplelink.llc"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def titles():
    out = {}
    p = WS / "batch-001-metadata.csv"
    if p.exists():
        for r in csv.DictReader(open(p, newline="", encoding="utf-8")):
            out[r["filename"]] = r["title"].strip()
    return out


def targets():
    return list(csv.DictReader(open(TARGETS, newline="", encoding="utf-8")))


JOBS = {JOB: SECTION, "photo-credit": "Photo-for-credit offers"}


def queue_items(jobs=(JOB,)):
    aq = load("approval_queue", QUEUE)
    return [i for i in aq.all_items() if i["fm"].get("job") in jobs]


def logged_targets():
    out = {}
    if not LOG.exists():
        return out
    in_sec = False
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_sec = line[3:].strip().lower().startswith(SECTION.lower()); continue
        if in_sec and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0][:2] == "20":
                out[cells[1].lower()] = cells[3]
    return out


def ensure_log_section(section=SECTION):
    txt = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
    if f"## {section}" in txt:
        return
    txt = txt.rstrip("\n") + f"\n\n## {section}\n\nSent by scripts/photo-pitch.py from approved queue items.\n\n| Date | Target | Contact | Status | Note |\n|---|---|---|---|---|\n|  |  |  |  |  |\n"
    LOG.write_text(txt, encoding="utf-8")


def bundle_price(n):
    if n <= 1:
        return PRICE_ONE
    return int(round(PRICE_ONE * n * 0.75 / 10.0)) * 10


def pitch_body(t, names):
    files = [f.strip() for f in t["filenames"].split(";") if f.strip()]
    n = len(files)
    short = t["target"].split("(")[0].strip()
    descr = [names.get(f, f[:-5]) for f in files][:4]
    lines = ["Hello,", "",
             f"I'm a photographer based in Atlanta. I photographed {short} and would like to offer the images to your marketing team.",
             "", f"There are {n} images (previews attached):"]
    lines += [f"- {d}" for d in descr]
    if n > len(descr):
        lines.append(f"- and {n - len(descr)} more")
    lines += ["",
              f"A commercial license (web, social, newsletters, print marketing) is ${PRICE_ONE} per image, or ${bundle_price(n)} for all {n}, with no expiry. "
              f"Single images can be licensed by card at {LICENSE_URL}; for the set, reply and I will send a payment link.",
              "", "Please forward this if someone else handles imagery.", "", SIGN]
    return "\n".join(lines)


def item_md(target_name, email, subject, body, files, why, verify, expires_days=14, risk="medium"):
    exp = (dt.date.today() + dt.timedelta(days=expires_days)).isoformat()
    tgt = target_name.replace('"', "'")
    return f"""---
job: {JOB}
model: "hosted:claude"
kind: email
target: "{tgt}"
executor: claude-code
risk: {risk}
effort_minutes: 2
expires: {exp}
expected_effect: one reply per 40 to 60 sends; a license is $79 to $199 per image (estimate)
ledger: proposed
status: pending
photos: "{';'.join(files)}"
---

## Ask
Send this licensing pitch to {tgt} with watermarked previews of {len(files)} photograph(s) attached.

## Why now
- {why}

## Draft
```
To: {email}
Subject: {subject}

{body}
```

## Verify
- {verify}
- Prices match /photography/license/ (site/photography/license/index.html) and netlify/functions/checkout.mjs.

## If approved
scripts/photo-pitch.py send mails it from ben@purplelink.llc (or the Gmail fallback) with the previews attached and logs the row in Outreach/OUTREACH-LOG.md.

## If rejected
Reason code; wrong-target drops the row from the targets CSV, wrong-fact sends it back for a re-check of the files.

## Evidence
- Files: {', '.join(files)} in /Volumes/Extreme SSD/Nikon Photos. Previews are generated at send time from those files with the site watermark.
- Target row: docs/photo-licensing/direct-pitch-targets.csv (rank {{rank}}).
"""


def queue_new(md, dry_run):
    if dry_run:
        print(md); print("[dry-run] not queued\n"); return 0
    r = subprocess.run([sys.executable, str(QUEUE), "new", "-"], input=md, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def cmd_queue(a):
    names = titles()
    already = {str(i["fm"].get("target", "")).lower() for i in queue_items()} | set(logged_targets())
    n = 0
    for t in targets():
        if n >= a.n:
            break
        key = t["target"].lower()
        if key in already or not t.get("contact_email") or not re.search(r"VERIFIED \d{4}-\d{2}-\d{2}", t.get("notes", "")):
            continue
        files = [f.strip() for f in t["filenames"].split(";") if f.strip()]
        if not files or not all((SRC / f).exists() for f in files):
            print(f"skip {t['target']}: a file is missing locally"); continue
        subject = f"Photos of {t['target'].split('(')[0].strip()}, available to license"
        ver = re.search(r"VERIFIED \d{4}-\d{2}-\d{2}[^.;]*", t["notes"]).group(0)
        md = item_md(t["target"], t["contact_email"], subject, pitch_body(t, names), files,
                     f"{t['type']} in {t['country']} with its own marketing contact ({t.get('contact_url') or 'see CSV'}); no image bank of its own.",
                     f"{ver}: every file opened and matched to the pitch text (notes column of docs/photo-licensing/direct-pitch-targets.csv).")
        md = md.replace("{rank}", t.get("rank", "?"))
        queue_new(md, a.dry_run); n += 1
    print(f"queued {n}")
    return 0


def cmd_followup(a):
    body = ("Hello Caroline,\n\n"
            "Thank you for looking at the two Christmas previews of Hotel d'Angleterre last week. I wanted to make the next step easy.\n\n"
            f"A commercial license for one image is ${PRICE_ONE} and never expires: your website, social accounts, newsletters and printed marketing. "
            f"Both images together are $129. You can license either one by card at {LICENSE_URL} and the clean full-resolution file arrives within a minute, "
            "with a written license. For both, reply and I will send a single payment link.\n\n"
            "If the timing is wrong for this season, I am happy to hold them for next year's campaign.\n\n" + SIGN)
    md = item_md("Hotel d'Angleterre (follow-up)", "pr@dangleterre.com",
                 "Hotel d'Angleterre Christmas photos: license and next step", body, ["DSC_7189.jpeg", "DSC_7206.jpeg"],
                 "Caroline Danielsen (PR and Marketing) asked for previews on 2026-09-25 and received them the same day; no reply since. One follow-up at day 5 to 7 is normal.",
                 "VERIFIED 2026-09-25: DSC_7189 and DSC_7206 opened and confirmed as the hotel's Christmas facade (docs/photo-licensing/direct-pitch-targets.csv, rank 2 notes).",
                 risk="low")
    md = md.replace("{rank}", "2")
    return queue_new(md, a.dry_run)


def preview(fname, hubs):
    """Watermarked 1200px JPEG of an original, as bytes."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(SRC / fname) as im:
        im = im.convert("RGB"); im.thumbnail((1200, 1200), Image.LANCZOS)
        out = io.BytesIO(); hubs.watermark(im).save(out, "JPEG", quality=80)
        return out.getvalue()


def parse_draft(body):
    m = re.search(r"## Draft\s*```\s*\n(.*?)```", body, re.S)
    if not m:
        return None
    block = m.group(1)
    to = re.search(r"^To:\s*(.+)$", block, re.M); sub = re.search(r"^Subject:\s*(.+)$", block, re.M)
    text = block.split("\n\n", 1)[1] if "\n\n" in block else ""
    return (to.group(1).strip() if to else "", sub.group(1).strip() if sub else "", text.strip() + "\n")


def cmd_send(a):
    outreach = load("outreach", ROOT / "scripts" / "outreach.py")
    hubs = load("hubs", ROOT / "scripts" / "gen_photo_hubs.py")
    for sec in JOBS.values():
        ensure_log_section(sec)
    sent = 0
    for it in queue_items(tuple(JOBS)):
        fm = it["fm"]
        if it["folder"] != "approved":
            continue
        text = it["body"] if it.get("body") else Path(it["path"]).read_text(encoding="utf-8")
        d = parse_draft(text)
        if not d or not d[0]:
            print(f"{fm.get('id')}: no To/Subject/body in Draft; skipped"); continue
        to, subject, body = d
        files = [f for f in str(fm.get("photos", "")).split(";") if f]
        addr, pw, host, port = outreach.pick_sender()
        msg = EmailMessage()
        msg["From"] = formataddr((outreach.SENDER_NAME, addr)); msg["To"] = to; msg["Subject"] = subject
        msg.set_content(body)
        for f in files:
            try:
                msg.add_attachment(preview(f, hubs), maintype="image", subtype="jpeg", filename=f"preview-{f[:-5]}.jpg")
            except Exception as e:
                print(f"  preview {f} failed: {type(e).__name__}: {e}")
        print(f"To: {to}\nSubject: {subject}\n{body}\n[{len(files)} preview(s)]")
        if a.dry_run:
            print("[dry-run] not sent\n"); continue
        import smtplib
        ctx = outreach.ssl_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=ctx) as s:
                s.login(addr, pw); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ctx); s.login(addr, pw); s.send_message(msg)
        outreach.log_write_row(JOBS[fm.get("job")], [dt.date.today().isoformat(), str(fm.get("target")), to, "sent", f"queue {fm.get('id')}, {len(files)} previews, via {addr}"])
        subprocess.run([sys.executable, str(QUEUE), "done", str(fm.get("id")), "--result", f"sent {dt.date.today().isoformat()} to {to}"], capture_output=True, text=True)
        sent += 1
        print(f"sent -> {to}; logged\n")
    print(f"sent {sent}")
    return 0


def cmd_status(a):
    by = {}
    for i in queue_items(tuple(JOBS)):
        k = f"{i['fm'].get('job')}/{i['folder']}"
        by[k] = by.get(k, 0) + 1
    rows = targets()
    verified = sum(1 for t in rows if re.search(r"VERIFIED \d{4}-\d{2}-\d{2}", t.get("notes", "")))
    print(f"targets {len(rows)} ({verified} verified); queue {by or 'empty'}; logged {len(logged_targets())}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue"); q.add_argument("--n", type=int, default=15)
    sub.add_parser("followup"); sub.add_parser("send"); sub.add_parser("status")
    a = ap.parse_args()
    return {"queue": cmd_queue, "followup": cmd_followup, "send": cmd_send, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
