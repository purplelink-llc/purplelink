#!/usr/bin/env python3
"""Send one RubbleFront news email to the confirmed list. Nothing here runs by itself.

    RUBBLEFRONT_BROADCAST_SECRET=... python3 scripts/rubblefront-broadcast.py \
        --subject "The demo is out" --body news.md                 # dry run (default): prints a count only
    ... --test-to ben@purplelink.llc                                # one copy to one address
    ... --send                                                      # real send, asks you to type the count

The message file is plain text or light markdown (paragraphs, # headings, - lists, **bold**, *italic*,
[text](https://link)). The server adds a per-recipient unsubscribe link, the List-Unsubscribe headers and
the postal line. The server sends through Resend, so RESEND_API_KEY is never needed on this machine.
Addresses are never printed. A run is split into batches of 50 and is resumable: if it stops, rerun with
the printed --resume <id> and recipients already sent are skipped.

Env: RUBBLEFRONT_BROADCAST_SECRET (required), RUBBLEFRONT_BASE_URL (default https://purplelink.llc),
SSL_CERT_FILE (optional CA bundle; otherwise /etc/ssl/cert.pem is used if the default store has none).
"""
import argparse
import html
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("RUBBLEFRONT_BASE_URL", "https://purplelink.llc").rstrip("/")
ENDPOINT = f"{BASE}/.netlify/functions/rubblefront-broadcast"


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render(markdown):
    """Return (plain text, html) for a small markdown subset."""
    blocks = [b for b in re.split(r"\n\s*\n", markdown.strip()) if b.strip()]
    out = []
    for block in blocks:
        lines = block.splitlines()
        if all(re.match(r"\s*[-*] ", l) for l in lines):
            items = "".join(f"<li>{inline(re.sub(r'^\s*[-*] ', '', l))}</li>" for l in lines)
            out.append(f"<ul>{items}</ul>")
        elif re.match(r"#{1,3} ", lines[0]) and len(lines) == 1:
            out.append(f"<h2>{inline(re.sub(r'^#+ ', '', lines[0]))}</h2>")
        else:
            out.append(f"<p>{inline(' '.join(l.strip() for l in lines))}</p>")
    plain = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", markdown.strip())
    plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
    return plain, "\n".join(out)


SYSTEM_CA_FILE = "/etc/ssl/cert.pem"


def ssl_contexts():
    """TLS contexts to try, in order. Verification is never turned off.

    The python.org build of Python ships with no CA roots, so the default context can fail with
    CERTIFICATE_VERIFY_FAILED. The fallback is the system bundle (macOS: /etc/ssl/cert.pem), or the file
    named by SSL_CERT_FILE when that is set."""
    default = ssl.create_default_context()
    contexts = [default]
    cafile = os.environ.get("SSL_CERT_FILE") or SYSTEM_CA_FILE
    if os.path.isfile(cafile):
        # An empty default store means the first context cannot verify anything: start with the file.
        empty = not default.get_ca_certs() and not os.environ.get("SSL_CERT_FILE")
        fallback = ssl.create_default_context(cafile=cafile)
        contexts = [fallback, default] if empty else [default, fallback]
    return contexts


def is_verify_error(exc):
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason)


def open_url(req):
    last = None
    for ctx in ssl_contexts():
        try:
            return urllib.request.urlopen(req, timeout=60, context=ctx)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ssl.SSLError) as e:
            if not is_verify_error(e):
                raise
            last = e
    raise last


def call(secret, payload):
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"},
    )
    try:
        with open_url(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", required=True, help="markdown or text file")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="default: print the recipient count only")
    mode.add_argument("--test-to", metavar="ADDRESS", help="send one copy to this address only")
    mode.add_argument("--send", action="store_true", help="send to every confirmed subscriber")
    ap.add_argument("--resume", metavar="ID", help="continue an interrupted --send")
    args = ap.parse_args()

    secret = os.environ.get("RUBBLEFRONT_BROADCAST_SECRET", "")
    if not secret:
        sys.exit("RUBBLEFRONT_BROADCAST_SECRET is not set.")
    with open(args.body, encoding="utf-8") as fh:
        text, body_html = render(fh.read())
    if not text:
        sys.exit("The body file is empty.")
    message = {"subject": args.subject, "text": text, "html": body_html}

    status, data = call(secret, {"action": "count"})
    if status != 200:
        sys.exit(f"Could not read the count (HTTP {status}).")
    count = data["count"]
    print(f"Confirmed recipients: {count}")

    if args.test_to:
        status, data = call(secret, {"action": "test", "to": args.test_to, **message})
        print("Test copy sent." if status == 200 else f"Test failed (HTTP {status}).")
        return 0 if status == 200 else 1

    if not args.send:
        print(f"Dry run. Subject: {args.subject!r}. Message: {len(text)} characters. Nothing was sent.")
        return 0

    if count == 0:
        print("Nobody to send to.")
        return 0
    if not sys.stdin.isatty():
        sys.exit("--send needs an interactive terminal for the confirmation.")
    typed = input(f"Type the recipient count ({count}) to send this email to all of them: ").strip()
    if typed != str(count):
        sys.exit("Count did not match. Nothing was sent.")

    broadcast_id = args.resume or str(uuid.uuid4())
    print(f"Broadcast id {broadcast_id} (use --resume {broadcast_id} if this stops).")
    expect = None if args.resume else count
    total_sent = 0
    while True:
        payload = {"action": "send", "broadcastId": broadcast_id, **message}
        if expect is not None:
            payload["expect"] = expect
        status, data = call(secret, payload)
        expect = None
        if status != 200:
            print(f"Stopped (HTTP {status} {data.get('error', '')}). Sent so far this run: {total_sent}.")
            return 1
        total_sent += data["sent"]
        print(f"Sent {total_sent}, remaining {data['remaining']}")
        if data["remaining"] == 0:
            break
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
