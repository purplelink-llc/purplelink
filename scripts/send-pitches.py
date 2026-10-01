#!/usr/bin/env python3
"""Send approved direct-licensing pitches through Mail.app from ben@purplelink.llc.

Reads photo-licensing-workspace/pitches/pitches.json (parsed from
docs/photo-licensing/direct-pitch-drafts.md) and sends each pitch that has an
email address, skipping ranks in --skip and anything already in the sent log.
Contact-form targets are not handled here. Every send is appended to
photo-licensing-workspace/pitches/sent-log.json with a timestamp so nothing
goes out twice.

  python3 scripts/send-pitches.py --test ben@purplelink.llc --rank 1   # one test copy
  python3 scripts/send-pitches.py --skip 7                            # send the rest
"""
import argparse, datetime, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "photo-licensing-workspace" / "pitches"
SENDER = "Benjamin Ampel <ben@purplelink.llc>"


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send(to, subject, body):
    script = f'''
tell application "Mail"
    set m to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:false}}
    set sender of m to "{esc(SENDER)}"
    tell m to make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}
    send m
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", help="send to this address instead, tagged [TEST]")
    ap.add_argument("--rank", type=int, nargs="*")
    ap.add_argument("--skip", type=int, nargs="*", default=[])
    a = ap.parse_args()
    pitches = json.loads((P / "pitches.json").read_text())
    logf = P / "sent-log.json"
    log = json.loads(logf.read_text()) if logf.exists() else []
    sent = {e["rank"] for e in log if not e.get("test")}
    for x in pitches:
        if a.rank and x["rank"] not in a.rank:
            continue
        if x["rank"] in a.skip or not x["email"] or (x["rank"] in sent and not a.test):
            continue
        to = a.test or x["email"]
        subj = ("[TEST] " if a.test else "") + x["subject"]
        send(to, subj, x["body"])
        log.append({"rank": x["rank"], "name": x["name"], "to": to, "subject": subj,
                    "test": bool(a.test), "at": datetime.datetime.now().isoformat(timespec="seconds")})
        logf.write_text(json.dumps(log, indent=1, ensure_ascii=False))
        print(f"  sent #{x['rank']} {x['name']} -> {to}")


if __name__ == "__main__":
    main()
