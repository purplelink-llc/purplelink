"""Shared fakes for the social posting tests: no network, no browser, no keychain, no real queue."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from socialpost.http import Resp


class FakeHttp:
    """Scripted HTTP. routes: list of (method, substring, response or callable). First match wins; each call is recorded."""

    def __init__(self, routes=None):
        self.routes = list(routes or [])
        self.calls: list[dict] = []

    def add(self, method, needle, resp):
        self.routes.append((method, needle, resp))

    def request(self, method, url, headers=None, json_body=None, form=None, data=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json_body, "form": form, "data": data})
        for m, needle, resp in self.routes:
            if m == method and needle in url:
                r = resp(self.calls[-1]) if callable(resp) else resp
                if isinstance(r, list):  # a sequence: pop the next one, keep the last
                    nxt = r.pop(0) if len(r) > 1 else r[0]
                    return nxt
                return r
        return Resp(404, b"{}")

    def posts_to(self, needle):
        return [c for c in self.calls if c["method"] == "POST" and needle in c["url"]]


def jresp(obj, status=200, headers=None):
    return Resp(status, json.dumps(obj).encode(), headers or {})


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def make_png(path: Path, extra: int = 0) -> Path:
    path.write_bytes(PNG + b"\1" * extra)
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Private locations redirected into tmp_path, notifications captured."""
    home = tmp_path / "social"
    cfgfile = tmp_path / "social.json"
    monkeypatch.setenv("PL_SOCIAL_HOME", str(home))
    monkeypatch.setenv("PL_SOCIAL_CONFIG", str(cfgfile))
    monkeypatch.setenv("PL_SOCIAL_LOG", str(tmp_path / "social.log"))
    outreach = tmp_path / "OUTREACH-LOG.md"
    outreach.write_text("# Outreach Log\n\n| Date | Target | Contact | Status | Note |\n|---|---|---|---|---|\n")
    monkeypatch.setenv("PL_OUTREACH_LOG", str(outreach))
    changer = tmp_path / "log_change.py"
    changer.write_text("import sys, pathlib\npathlib.Path(__file__).with_name('changes.txt').open('a').write(' '.join(sys.argv[1:]) + '\\n')\n")
    monkeypatch.setenv("PL_LOG_CHANGE", str(changer))
    from socialpost import hubtags, sysutil
    # A stand-in for the marketing hub's tagger: deterministic, and never reads the real queue or ledger.
    monkeypatch.setattr(hubtags, "tag", lambda link, asset, channel, campaign, **kw:
                        f"{asset.split(':')[-1].replace('.', '-')}-{channel}-test"[:60] if hubtags.on_site(link) else "")
    sent: list[str] = []
    monkeypatch.setattr(sysutil, "notify", lambda msg, title="x": sent.append(msg))
    monkeypatch.setattr(sysutil, "keychain_get", lambda platform, field: None)
    e = type("Env", (), {})()
    e.home, e.cfgfile, e.outreach, e.changes, e.notes, e.tmp = home, cfgfile, outreach, tmp_path / "changes.txt", sent, tmp_path
    return e
