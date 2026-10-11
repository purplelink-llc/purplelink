#!/usr/bin/env python3
"""Sign in to Fine Art America in the automation Chrome using a password kept in the macOS Keychain.

Why: the Fine Art America session ends on its own after about two hours and the remember-me cookies do not start
a new one (measured 2026-10-11), so the daily photo sweep found it signed out every morning.

THE PASSWORD IS NEVER SEEN BY THE AGENT OR WRITTEN ANYWHERE. It is read from the Keychain at the moment of use,
typed into the form over the debug port, and dropped. Nothing is logged or saved except the resulting login cookies
(the same file stats-collect.py already keeps).

SETUP (once, run this yourself; -w with no value prompts, so the password stays out of shell history)
  security add-generic-password -a "ben.ampel@gmail.com" -s faa-login -w

USAGE
  python3 scripts/faa-autologin.py              # sign in now (if not already signed in)
  python3 scripts/faa-autologin.py --if-needed  # same, quiet: photostats-run.sh calls this before each sweep
  python3 scripts/faa-autologin.py --check      # report signed in / signed out; never types anything
  python3 scripts/faa-autologin.py --dry-run    # open the form and find the fields; never reads the Keychain

One attempt per run. After a failed attempt it waits 6 hours before trying again (a wrong password or a captcha
must not turn into a lockout); --force overrides.
"""
import argparse, importlib.util, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_tab import Tab  # noqa: E402

ACCOUNT = os.environ.get("FAA_LOGIN_ACCOUNT", "ben.ampel@gmail.com")
SERVICE = "faa-login"
CDP = "http://127.0.0.1:9340"
PROFILE = os.path.expanduser("~/.photo-automation-chrome")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LOGIN_URL = "https://fineartamerica.com/loginartist.php"
STATE = Path.home() / ".purplelink" / "faa-login-state.json"
RETRY_AFTER_FAIL_S = 6 * 3600

SIGNED_IN_JS = ("(async()=>{const r=await fetch('/controlpanel/main',{credentials:'include',redirect:'manual'});"
                "return r.type!=='opaqueredirect' && r.status===200})()")


def log(msg):
    print(f"faa-autologin: {msg}", flush=True)


def chrome_up():
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_chrome():
    if chrome_up():
        return
    # An ordinary Chrome with a debug port; Playwright-launched ones get fingerprinted (see stats-collect.py).
    subprocess.Popen([CHROME, "--remote-debugging-port=9340", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--no-default-browser-check", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if chrome_up():
            time.sleep(2)
            return
    sys.exit("faa-autologin: Chrome did not start on port 9340")


def keychain_password():
    try:
        return subprocess.run(["security", "find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"],
                              capture_output=True, text=True, check=True).stdout.rstrip("\n")
    except subprocess.CalledProcessError:
        return None


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d))


def click(t, selector):
    """A real mouse click at the centre of the element (counts as a user gesture, unlike el.click())."""
    r = t.eval("(()=>{const e=document.querySelector(%s);e.scrollIntoView({block:'center'});const b=e.getBoundingClientRect();"
               "return {x:b.left+b.width/2,y:b.top+b.height/2}})()" % json.dumps(selector))
    for typ in ("mousePressed", "mouseReleased"):
        t.send("Input.dispatchMouseEvent", type=typ, x=r["x"], y=r["y"], button="left", clickCount=1)
    time.sleep(0.4)


def signed_in(t):
    return bool(t.eval(SIGNED_IN_JS))


def save_cookies():
    """Reuse stats-collect.py's cookie saver so the sweep restores them like any other sign-in."""
    spec = importlib.util.spec_from_file_location("stats_collect", Path(__file__).resolve().parent / "stats-collect.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.save_session_cookies(["fineartamerica"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--if-needed", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keychain", action="store_true", help="type the Keychain password even when Chrome autofilled")
    a = ap.parse_args()

    ensure_chrome()
    t = Tab.new()
    try:
        t.goto(LOGIN_URL, settle=5)
        if signed_in(t):
            log("already signed in")
            return 0
        if a.check:
            log("signed out")
            return 1
        fields = t.eval("({u:!!document.querySelector('input[name=username]'),p:!!document.querySelector('input[type=password]'),"
                        "f:!!document.querySelector('form[action*=loginValidation]'),"
                        "c:!!document.querySelector('iframe[src*=recaptcha],.g-recaptcha,[data-sitekey],iframe[src*=hcaptcha],iframe[src*=turnstile]')})")
        if a.dry_run:
            log(f"form found: {fields}; nothing typed")
            return 0
        if not (fields["u"] and fields["p"] and fields["f"]):
            log(f"login form not found ({fields}); the page layout may have changed")
            return 3
        if fields["c"]:
            log("a captcha is on the login form; sign in by hand with: python3 scripts/stats-collect.py --login")
            return 3
        st = load_state()
        if not a.force and time.time() - st.get("last_fail", 0) < RETRY_AFTER_FAIL_S:
            log("last attempt failed less than 6 hours ago; not trying again (use --force)")
            return 3
        # Chrome's password manager in this profile has usually autofilled the form already. Prefer that and just
        # click Login with a real mouse click (a click also releases the autofilled value to the page); fall back to
        # the Keychain only when the password field is empty.
        autofilled = bool(t.eval("document.querySelector('input[type=password]').matches(':-webkit-autofill')"))
        if autofilled and not a.keychain:
            log("password autofilled by Chrome; clicking Login")
            click(t, "input[type=password]")
        else:
            pw = keychain_password()
            if not pw:
                log(f'no autofill and no Keychain entry. Add it once with:  security add-generic-password -a "{ACCOUNT}" -s {SERVICE} -w')
                return 2
            try:
                # Select the whole field first so typing replaces any existing text instead of being appended to it.
                t.eval("(()=>{const u=document.querySelector('input[name=username]');u.focus();u.select()})()")
                t.send("Input.insertText", text=ACCOUNT)
                t.eval("(()=>{const p=document.querySelector('input[type=password]');p.focus();p.select()})()")
                t.send("Input.insertText", text=pw)
            finally:
                del pw
        click(t, "form[action*=loginValidation] a.button")      # the page's own Login link
        time.sleep(8)
        seen = t.eval("(()=>({path:location.pathname,"
                      "msg:(document.body.innerText.match(/[^\\n]*(invalid|incorrect|wrong|not match|try again|locked|captcha|verify)[^\\n]*/i)||[''])[0].slice(0,140)}))()")
        log(f"after submit: {seen.get('path')} {('| page says: ' + seen['msg']) if seen.get('msg') else ''}")
        t.goto("https://fineartamerica.com/controlpanel/main", settle=6)
        if signed_in(t):
            save_state({"last_ok": time.time()})
            save_cookies()
            log("signed in")
            return 0
        save_state({"last_fail": time.time()})
        log("sign-in did not go through (wrong password, a captcha, or a changed form); not retrying for 6 hours")
        return 3
    finally:
        try:
            t.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
