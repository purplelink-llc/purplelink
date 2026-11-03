#!/usr/bin/env python3
"""The Undershelf waitlist from Ben's Mac: counts, the one launch email, and the purge (docs/designs/undershelf-waitlist.md).

No web endpoint returns addresses or counts; this reads the "undershelf-waitlist" Blobs store with the Netlify CLI
(`netlify blobs:*`, run from the linked Purplelink checkout). Addresses are never printed.

  python3 scripts/undershelf_list.py counts                  # total, per version, per utm_content, distinct domains
  RESEND_API_KEY=... SUBSCRIBE_SECRET=... python3 scripts/undershelf_list.py send --subject S --body launch.txt
                                                             # dry run: prints the count it would send
  ... send --subject S --body launch.txt --test-to ben@purplelink.llc   # one copy to one address
  ... send --subject S --body launch.txt --send              # real send; asks you to type the count
  python3 scripts/undershelf_list.py purge                   # deletes every record; asks you to type the count

The launch email gets a per-recipient unsubscribe link (the same HMAC as the function), RFC 8058 headers and the
postal line. Unsubscribing deletes the record, so suppressed addresses are never on the list.
"""
import argparse
import hashlib
import hmac
import html
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

STORE = "undershelf-waitlist"
SITE = "https://purplelink.llc"
CHECKOUT = Path(os.environ.get("PURPLELINK_CHECKOUT", "/Volumes/Extreme SSD/Purplelink LLC"))
FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>"
REPLY_TO = "ben@purplelink.llc"
POSTAL = "Purplelink LLC, Atlanta, Georgia"


def cli(*args):
    r = subprocess.run(["netlify", *args], cwd=CHECKOUT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        sys.exit(f"netlify {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def keys():
    listing = json.loads(cli("blobs:list", STORE, "--json") or "{}")
    return [b["key"] for b in listing.get("blobs", [])]


def records():
    out = []
    for k in keys():
        try:
            out.append(json.loads(cli("blobs:get", STORE, k)))
        except json.JSONDecodeError:
            print("skipping one unreadable record", file=sys.stderr)
    return out


def unsubscribe_url(email, secret):
    token = hmac.new(secret.encode(), f"undershelf-unsub:{email.lower()}".encode(), hashlib.sha256).hexdigest()
    return f"{SITE}/.netlify/functions/undershelf-waitlist?u={token}&e={urllib.parse.quote(email)}"


def counts(_args):
    recs = records()
    print(f"confirmed: {len(recs)}")
    for name, field in (("version", "version"), ("utm_content", "utm")):
        c = Counter(r.get(field) or "(none)" for r in recs)
        print(f"by {name}: " + (", ".join(f"{k} {v}" for k, v in c.most_common()) or "-"))
    print(f"distinct email domains: {len({r['email'].split('@')[-1] for r in recs})}")


def confirm_count(n, what):
    if input(f"Type {n} to {what}: ").strip() != str(n):
        sys.exit("Not confirmed; nothing done.")


def send(args):
    key, secret = os.environ.get("RESEND_API_KEY"), os.environ.get("SUBSCRIBE_SECRET")
    if not key or not secret:
        sys.exit("Set RESEND_API_KEY and SUBSCRIBE_SECRET for this run only.")
    body = Path(args.body).read_text(encoding="utf-8").strip()
    recipients = [args.test_to] if args.test_to else [r["email"] for r in records()]
    if not (args.send or args.test_to):
        print(f"dry run: would send '{args.subject}' to {len(recipients)} addresses")
        return
    if args.send:
        confirm_count(len(recipients), "send")
    paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in body.split("\n\n") if p.strip())
    sent = 0
    for to in recipients:
        unsub = unsubscribe_url(to, secret)
        mail = {
            "from": FROM_ADDRESS, "reply_to": REPLY_TO, "to": [to], "subject": args.subject,
            "text": f"{body}\n\nUnsubscribe: {unsub}\n\n{POSTAL}",
            "html": f'{paras}<p><a href="{unsub}">Unsubscribe</a></p><p>{POSTAL}</p>',
            "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
        }
        req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(mail).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                sent += r.status == 200
        except Exception as e:  # keep going; the count at the end says how many went
            print(f"one send failed: {e}", file=sys.stderr)
    print(f"sent {sent} of {len(recipients)}")


def purge(_args):
    ks = keys()
    if not ks:
        print("the list is already empty")
        return
    confirm_count(len(ks), "delete every record")
    for k in ks:
        cli("blobs:delete", STORE, k, "--force")
    print(f"deleted {len(ks)} records; the suppression store is kept")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("counts").set_defaults(fn=counts)
    s = sub.add_parser("send")
    s.add_argument("--subject", required=True)
    s.add_argument("--body", required=True, help="plain-text file; blank lines separate paragraphs")
    s.add_argument("--test-to")
    s.add_argument("--send", action="store_true")
    s.set_defaults(fn=send)
    sub.add_parser("purge").set_defaults(fn=purge)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
