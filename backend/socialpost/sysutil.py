"""Small macOS helpers: notifications, the login keychain and a logger. All injectable in tests."""
from __future__ import annotations

import datetime as dt
import re
import subprocess

from . import paths

SECRET_RE = re.compile(r"^[A-Za-z0-9._~+/=:@-]{8,2048}$")


def log(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try:
        p = paths.log_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line)


def notify(msg: str, title: str = "Purplelink social") -> None:
    msg = msg.replace("\\", " ").replace('"', "'")[:230]
    try:
        subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{msg}" with title "{title}"'],
                       check=False, capture_output=True, timeout=15)
    except Exception:
        pass


def service(platform: str) -> str:
    return f"purplelink-social-{platform}"


def keychain_get(platform: str, field: str) -> str | None:
    """Read one secret. The value is returned to the caller and never printed or logged."""
    try:
        r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", service(platform), "-a", field, "-w"],
                           capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def keychain_set(platform: str, field: str, value: str) -> None:
    """Store one secret through `security -i` so the value is read from stdin, never put in argv."""
    if not SECRET_RE.match(value):
        raise ValueError("that value has characters or a length a token never has; check what you pasted")
    cmd = f"add-generic-password -U -s {service(platform)} -a {field} -w {value}\n"
    r = subprocess.run(["/usr/bin/security", "-i"], input=cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or "error" in (r.stdout + r.stderr).lower():
        raise RuntimeError("the keychain refused the item (is the login keychain unlocked?)")
