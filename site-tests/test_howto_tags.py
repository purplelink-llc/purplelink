"""Hashtags on the daily how-to videos (scripts/howto-publish.py): content tag per app,
YouTube order (first three shown above the title), #shorts last on the Short only."""
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("howto_publish", ROOT / "scripts" / "howto-publish.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)


def _fake(out, calls=None):
    def run(cmd, **kw):
        if calls is not None:
            calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
    return run


def test_content_tags_per_app_and_overleaf():
    assert H.content_tags({"app": "moderntex", "scenes": []}) == ["latex"]
    assert H.content_tags({"app": "moderntex", "scenes": ["Overleaf"]}) == ["latex", "overleaf"]
    assert H.content_tags({"app": "legroom"}) == ["macstorage"]
    assert H.content_tags({"app": "unknown"}) == []
    # every rotation app has a content tag
    import json
    apps = [a["app"] for a in json.loads((ROOT / "video/howto/rotation.json").read_text())["apps"]]
    assert all(H.APP_TAGS.get(a) for a in apps), [a for a in apps if not H.APP_TAGS.get(a)]


def test_assemble_is_called_with_the_content_tags(monkeypatch):
    calls = []
    monkeypatch.setattr(H.subprocess, "run", _fake("mac macos macstorage storagetips mactips", calls))
    out = H.trend_tags({"app": "legroom", "scenes": []}, short=True)
    assert "assemble" in calls[0] and "macstorage" in calls[0]
    assert out == "#mac #macos #macstorage #shorts"


def test_long_video_has_four_tags_and_no_shorts(monkeypatch):
    monkeypatch.setattr(H.subprocess, "run", _fake("mac macos latex overleaf mactips", None))
    out = H.trend_tags({"app": "moderntex", "scenes": ["latex"]}, short=False)
    assert out == "#mac #macos #latex #overleaf" and "shorts" not in out


def test_latex_tags_dropped_when_not_about_latex(monkeypatch):
    monkeypatch.setattr(H.subprocess, "run", _fake("mac macos latex mactips", None))
    out = H.trend_tags({"app": "legroom", "scenes": []}, short=False)
    assert "latex" not in out


def test_fallback_when_the_cli_fails(monkeypatch):
    def boom(*a, **k):
        raise OSError("no trends checkout")
    monkeypatch.setattr(H.subprocess, "run", boom)
    assert H.trend_tags({"app": "legroom", "scenes": []}, short=False).startswith("#macos")
