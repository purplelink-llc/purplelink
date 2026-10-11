#!/usr/bin/env python3
"""Read-only live check of the shipped roadmap items. Stdlib only. Not run in CI: it needs the network and Ben's Mac.

  python3 scripts/verify_roadmap_live.py

Prints a PASS / FAIL / SKIP table and exits 1 if anything FAILed (SKIP never fails). It creates no Stripe session
(the only POSTs are two invalid checkout requests that are refused before Stripe is called), sends no email, and
never prints a secret: the Keychain entry is only looked up (no -w), and Netlify env values other than
POST_PURCHASE_FOLLOWUP are discarded unread.
"""
import json
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://purplelink.llc"
HOME = Path.home()
UA = {"User-Agent": "purplelink-roadmap-verify/1.0"}
rows = []


def _ssl_context():
    """The default context, or the macOS system bundle when this Python ships without root certificates."""
    for cafile in (None, "/etc/ssl/cert.pem"):
        if cafile and not Path(cafile).exists():
            continue
        ctx = ssl.create_default_context(cafile=cafile)
        if cafile or ctx.cert_store_stats().get("x509_ca", 0) > 0:
            return ctx
    return ssl.create_default_context()


CTX = _ssl_context()


def record(name, status, detail=""):
    rows.append((name, status, detail))


def http(url, data=None, headers=None, timeout=20):
    h = dict(UA, **(headers or {}))
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def check(name, fn):
    try:
        res = fn()
    except Exception as e:  # network down, missing tool, etc.
        record(name, "FAIL", f"{type(e).__name__}: {e}"[:120])
        return
    if isinstance(res, tuple):
        record(name, *res)
    else:
        record(name, "PASS" if res else "FAIL")


def page_200(path):
    def run():
        code, _ = http(BASE + path)
        return ("PASS" if code == 200 else "FAIL", f"HTTP {code}")
    return run


def checkout_error(payload, want, want_status=None):
    def run():
        code, body = http(BASE + "/.netlify/functions/checkout", data=payload)
        try:
            err = json.loads(body).get("error")
        except ValueError:
            err = None
        ok = err == want and (want_status is None or code == want_status)
        return ("PASS" if ok else "FAIL", f"HTTP {code}, error={err}")
    return run


def unsubscribe_bad():
    code, _ = http(BASE + "/.netlify/functions/followup-unsubscribe?u=bad")
    return ("PASS" if code == 200 else "FAIL", f"HTTP {code}")


def dmarc():
    q = urllib.parse.urlencode({"name": "_dmarc.purplelink.llc", "type": "TXT"})
    code, body = http("https://cloudflare-dns.com/dns-query?" + q, headers={"accept": "application/dns-json"})
    answers = [a.get("data", "") for a in json.loads(body).get("Answer", [])]
    ok = any("rua=mailto:ben@purplelink.llc" in a for a in answers)
    return ("PASS" if ok else "FAIL", f"{len(answers)} TXT record(s)")


def task_file(name):
    def run():
        p = HOME / ".claude" / "scheduled-tasks" / name / "SKILL.md"
        if not p.exists():
            return ("SKIP", "file absent")
        return ("PASS", "exists")
    return run


def checkpoint150():
    p = HOME / ".claude" / "scheduled-tasks" / "outbound-veil-org-outreach" / "SKILL.md"
    if not p.exists():
        return ("SKIP", "file absent")
    ok = "NO-REPLY CHECKPOINT AT 150" in p.read_text(encoding="utf-8", errors="ignore")
    return ("PASS" if ok else "FAIL", "")


def faa_probe_absent():
    p = HOME / "Library" / "LaunchAgents" / "com.benampel.faa-probe.plist"
    return ("FAIL", "plist still installed") if p.exists() else ("PASS", "absent")


def chrome_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:9340/json/version", timeout=3).close()
        return True
    except Exception:
        return False


def faa_check():
    if not chrome_up():
        return ("SKIP", "Chrome on port 9340 is down")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "faa-autologin.py"), "--check"], capture_output=True, text=True, timeout=90)
    return ("PASS" if r.returncode in (0, 1) else "FAIL", f"exit {r.returncode}")


def keychain():
    if not shutil.which("security"):
        return ("SKIP", "security CLI missing")
    r = subprocess.run(["security", "find-generic-password", "-a", "ben.ampel@gmail.com", "-s", "faa-login"], capture_output=True, text=True, timeout=20)
    return ("PASS" if r.returncode == 0 else "FAIL", "entry found" if r.returncode == 0 else "entry not found")


def followup_env():
    if not shutil.which("netlify"):
        return ("SKIP", "netlify CLI missing")
    r = subprocess.run(["netlify", "env:list", "--context", "production", "--json"], capture_output=True, text=True, timeout=90, cwd=ROOT)
    if r.returncode != 0:
        return ("SKIP", "netlify env:list failed (not logged in or not linked)")
    out = r.stdout
    starts = [i for i in (out.find("{"), out.find("[")) if i >= 0]
    if not starts:
        return ("SKIP", "netlify env:list gave no JSON (not linked to the site?)")
    data = json.loads(out[min(starts):])
    value = data.get("POST_PURCHASE_FOLLOWUP") if isinstance(data, dict) else None
    if value is None and isinstance(data, list):
        value = next((e.get("value") for e in data if e.get("key") == "POST_PURCHASE_FOLLOWUP"), None)
    return ("PASS" if value == "on" else "FAIL", "set to on" if value == "on" else "not on")


def repo_private(repo):
    def run():
        if not shutil.which("gh"):
            return ("SKIP", "gh missing")
        r = subprocess.run(["gh", "repo", "view", f"purplelink-llc/{repo}", "--json", "visibility", "-q", ".visibility"], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return ("SKIP", "gh could not read the repo (not logged in?)")
        v = r.stdout.strip()
        return ("PASS" if v == "PRIVATE" else "FAIL", v)
    return run


def main():
    for path in ("/guides/before-you-paste-client-notes-into-chatgpt/", "/guides/what-ai-tools-leave-on-your-mac/", "/moderntex/", "/outbound-veil/", "/tapefolio/"):
        check(f"GET {path} is 200", page_200(path))
    check("checkout: unknown product refused", checkout_error({"product": "nope"}, "unknown_product"))
    check("checkout: 3 seats refused (invalid_seats, 400)", checkout_error({"product": "moderntex-seats", "seats": 3}, "invalid_seats", 400))
    check("followup-unsubscribe bad token is 200", unsubscribe_bad)
    check("DMARC rua=mailto:ben@purplelink.llc", dmarc)
    check("task moderntex-price-checkpoint exists", task_file("moderntex-price-checkpoint"))
    check("task gsc-thin-page-recheck exists", task_file("gsc-thin-page-recheck"))
    check("outbound-veil-org-outreach has NO-REPLY CHECKPOINT AT 150", checkpoint150)
    check("faa-probe LaunchAgent is not installed", faa_probe_absent)
    check("faa-autologin.py --check does not crash", faa_check)
    check("Keychain entry faa-login exists", keychain)
    check("Netlify POST_PURCHASE_FOLLOWUP is on", followup_env)
    for repo in ("tapefolio", "keyfeel", "legroom", "outbound-veil", "moderntex", "frontlink"):
        check(f"GitHub purplelink-llc/{repo} is PRIVATE", repo_private(repo))

    w = max(len(r[0]) for r in rows)
    for name, status, detail in rows:
        print(f"{status:<5} {name:<{w}}  {detail}")
    counts = {s: sum(1 for r in rows if r[1] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{counts['PASS']} pass, {counts['FAIL']} fail, {counts['SKIP']} skip")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
