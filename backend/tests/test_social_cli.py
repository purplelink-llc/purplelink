"""CLI: whoami never posts, post needs approval, dry-run is safe, secrets never go in argv."""
import datetime as dt
import subprocess

import pytest

from social_helpers import env, make_png  # noqa: F401
from socialpost import cli, engine, items, setup, sysutil
from socialpost.adapters.base import Adapter, Result
from socialpost.errors import Refused


class Probe(Adapter):
    name = "probe"
    calls = []

    def whoami(self):
        return {"handle": "x"}

    def check_identity(self):
        Probe.calls.append("identity")
        return {"handle": "x"}

    def post(self, item, dry_run=False):
        Probe.calls.append("dry" if dry_run else "POST")
        return Result(dry_run=dry_run, url=None if dry_run else "https://e.test/1", id="1", detail="d")

    def verify(self, url):
        return True


@pytest.fixture(autouse=True)
def probes(monkeypatch):
    Probe.calls = []
    monkeypatch.setattr(engine, "registry", lambda: {p: type(p, (Probe,), {"name": p}) for p in ("linkedin", "bluesky", "threads", "mastodon", "x")})


def make_item(tmp):
    it = items.create("cli", ["bluesky"], "https://purplelink.llc/vitae/", "vitae-140", (items.now() + dt.timedelta(hours=1)).isoformat())
    it.sections["default"] = "Hello {link}"
    it.save()
    return it


def test_new_validate_preview_approve_flow(env, capsys):
    assert cli.main(["new", "my-post", "--platforms", "bluesky,linkedin", "--link", "https://purplelink.llc/a/", "--campaign", "c1"]) == 0
    it = items.list_items()[0]
    assert it.status == "draft"
    assert cli.main(["validate", it.id]) == 0
    assert cli.main(["preview", it.id]) == 0
    out = capsys.readouterr().out
    assert "utm_source=bluesky" in out and "utm_source=linkedin" in out
    assert cli.main(["approve", it.id]) == 0
    assert items.Item.load(it.path).meta["approved_by"] == "ben"
    assert cli.main(["cancel", it.id]) == 0 and items.Item.load(it.path).status == "cancelled"


def test_post_needs_approval(env, capsys):
    it = make_item(env.tmp)
    assert cli.main(["post", it.id]) != 0
    assert "Run: social.py approve" in capsys.readouterr().out and "POST" not in Probe.calls


def test_post_dry_run_works_on_a_draft_and_posts_nothing(env):
    it = make_item(env.tmp)
    assert cli.main(["post", it.id, "--dry-run"]) == 0
    assert Probe.calls == ["dry"]


def test_post_after_approval_goes_through_and_records_results(env):
    it = make_item(env.tmp)
    assert cli.main(["approve", it.id]) == 0
    assert cli.main(["post", it.id]) == 0
    done = items.Item.load(it.path)
    assert done.status == "posted" and done.results["bluesky"]["url"] == "https://e.test/1"


def test_post_invalid_item_is_blocked(env, capsys):
    it = make_item(env.tmp)
    it.sections["default"] = "a" * 400
    it.save()
    assert cli.main(["post", it.id, "--dry-run"]) != 0
    assert Probe.calls == []


def test_post_refusal_exits_4_and_notifies(env, monkeypatch):
    class R(Probe):
        def post(self, item, dry_run=False):
            raise Refused("wrong")
    monkeypatch.setattr(engine, "registry", lambda: {p: type(p, (R,), {"name": p}) for p in ("linkedin", "bluesky", "threads", "mastodon", "x")})
    it = make_item(env.tmp)
    cli.main(["approve", it.id])
    assert cli.main(["post", it.id]) == 4
    assert any("REFUSED" in n for n in env.notes)


def test_whoami_checks_enabled_platforms_and_never_posts(env, capsys):
    assert cli.main(["whoami"]) == 0
    out = capsys.readouterr().out
    assert "linkedin" in out and "bluesky" in out and "disabled" in out
    assert "POST" not in Probe.calls and "dry" not in Probe.calls


def test_whoami_reports_a_mismatch_with_exit_4(env, monkeypatch, capsys):
    class Bad(Probe):
        def check_identity(self):
            raise Refused("signed in as 'ben'")
    monkeypatch.setattr(engine, "registry", lambda: {p: type(p, (Bad,), {"name": p}) for p in ("linkedin", "bluesky", "threads", "mastodon", "x")})
    assert cli.main(["whoami"]) == 4
    assert "REFUSED" in capsys.readouterr().out and env.notes


def test_pause_and_resume(env):
    cli.main(["pause"])
    assert (env.home / "PAUSE").exists()
    cli.main(["resume"])
    assert not (env.home / "PAUSE").exists()


def test_run_due_via_cli_posts_nothing_without_approved_items(env):
    make_item(env.tmp)
    assert cli.main(["run-due"]) == 0 and Probe.calls == []


def test_status_lists_items(env, capsys):
    it = make_item(env.tmp)
    assert cli.main(["status"]) == 0
    assert it.id in capsys.readouterr().out


# ---- secrets
def test_keychain_set_never_puts_the_secret_in_argv(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw.get("input")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sysutil.subprocess, "run", fake_run)
    sysutil.keychain_set("threads", "access_token", "SECRET-VALUE-12345")
    assert "SECRET-VALUE-12345" not in " ".join(seen["cmd"])
    assert seen["cmd"] == ["/usr/bin/security", "-i"]
    assert "purplelink-social-threads" in seen["input"] and "SECRET-VALUE-12345" in seen["input"]


def test_keychain_set_rejects_odd_values(monkeypatch):
    monkeypatch.setattr(sysutil.subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    for bad in ("short", "has space in it", "quote'inject; rm -rf", "x" * 3000, "line\nbreak12345"):
        with pytest.raises(ValueError):
            sysutil.keychain_set("x", "access_token", bad)


def test_keychain_get_reads_service_names(monkeypatch):
    monkeypatch.undo()
    seen = {}
    monkeypatch.setattr(sysutil.subprocess, "run", lambda cmd, **kw: (seen.update(cmd=cmd), subprocess.CompletedProcess(cmd, 0, "tok\n", ""))[1])
    assert sysutil.keychain_get("mastodon", "access_token") == "tok"
    assert "purplelink-social-mastodon" in seen["cmd"]


def test_pkce_and_x_authorize_url():
    v, c = setup.pkce_pair()
    assert len(v) >= 43 and len(c) == 43 and "=" not in c
    u = setup.x_authorize_url("cid", "st", c)
    assert "code_challenge_method=S256" in u and "media.write" in u and "client_id=cid" in u


def test_setup_threads_stores_token_via_keychain_and_pins_only_on_yes(env, monkeypatch):
    stored = {}
    monkeypatch.setattr(sysutil, "keychain_set", lambda p, f, v: stored.update({(p, f): v}))
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt="": "LONG-LIVED-TOKEN-1234" if "access token" in prompt else "")
    monkeypatch.setattr(setup, "_confirm_identity", lambda *a, **k: False)
    monkeypatch.setattr(setup, "build_adapter", lambda *a, **k: None)
    assert setup.setup.__name__ == "setup"
    from socialpost import config
    assert setup._setup_threads(config.load()) == 1
    assert stored[("threads", "access_token")] == "LONG-LIVED-TOKEN-1234"


def test_confirm_identity_pins_expected_values_in_private_config(env, monkeypatch):
    class A:
        def whoami(self):
            return {"id": "77", "username": "purplelink"}
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    assert setup._confirm_identity("threads", A(), {"user_id": "id", "username": "username"})
    from socialpost import config
    cfg = config.load()
    assert cfg["platforms"]["threads"]["enabled"] and cfg["platforms"]["threads"]["expected"] == {"user_id": "77", "username": "purplelink"}
    assert oct(env.cfgfile.stat().st_mode)[-3:] == "600"
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert not setup._confirm_identity("x", A(), {"user_id": "id"})
    assert not config.load()["platforms"]["x"]["enabled"]
