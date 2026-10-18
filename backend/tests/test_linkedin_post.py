"""Tests for backend/scripts/linkedin_post.py: argument parsing and the company-only identity checks.

No live LinkedIn: sync_playwright is replaced by a fake that records what the script does.
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("playwright")
import linkedin_post as lp  # noqa: E402

COMPANY_URL = "https://www.linkedin.com/company/120183926/admin/page-posts/published/"


class FakeLocator:
    def __init__(self, page, name):
        self.page, self.name = page, name
        self.first = self
        self.last = self

    def click(self, **kw):
        self.page.clicks.append(self.name)

    def wait_for(self, **kw):
        pass

    def fill(self, *a, **kw):
        pass

    def inner_text(self, **kw):
        return f"Dialog content start.\n{self.page.identity}\nWhat do you want to talk about?"

    def get_by_text(self, *a, **kw):
        return FakeLocator(self.page, "text")

    def get_by_role(self, role, name=None, **kw):
        return FakeLocator(self.page, f"{role}:{name}")

    def get_by_label(self, *a, **kw):
        return FakeLocator(self.page, "label")

    def locator(self, sel, **kw):
        return FakeLocator(self.page, sel)


class FakeKeyboard:
    def press(self, *a):
        pass

    def insert_text(self, t):
        pass


class FakePage(FakeLocator):
    def __init__(self, identity, url=COMPANY_URL):
        self.page = self
        self.name = "page"
        self.first = self.last = self
        self.identity, self.url = identity, url
        self.clicks, self.shots = [], []
        self.keyboard = FakeKeyboard()

    def goto(self, *a, **kw):
        pass

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self, path=None, **kw):
        self.shots.append(path)

    def expect_file_chooser(self, **kw):
        raise AssertionError("upload must not be reached in these tests")


def _run(page, monkeypatch, tmp_path, **kw):
    ctx = mock.MagicMock()
    ctx.pages = [page]
    pw = mock.MagicMock()
    pw.chromium.launch_persistent_context.return_value = ctx
    cm = mock.MagicMock()
    cm.__enter__.return_value = pw
    monkeypatch.setattr(lp, "sync_playwright", lambda: cm)
    monkeypatch.setattr(lp, "PROFILE_DIR", tmp_path)
    monkeypatch.setattr(lp, "_notify", lambda m: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return lp.post_to_linkedin("hello", **kw), pw


def test_refuses_when_composer_identity_is_a_person(monkeypatch, tmp_path):
    page = FakePage("Ben Ampel")
    code, _ = _run(page, monkeypatch, tmp_path, dry_run=False,
                   document=tmp_path / "d.pdf", document_title="T")
    assert code == 4
    assert "button:Post" not in page.clicks
    assert not any("add a document" in c.lower() or "Add a document" in c for c in page.clicks)


def test_refuses_when_not_on_company_admin_page(monkeypatch, tmp_path):
    page = FakePage("Purplelink LLC", url="https://www.linkedin.com/feed/")
    code, _ = _run(page, monkeypatch, tmp_path, dry_run=False)
    assert code == 4
    assert "button:Post" not in page.clicks


def test_headless_flag_reaches_browser_launch(monkeypatch, tmp_path):
    page = FakePage("Ben Ampel")
    _, pw = _run(page, monkeypatch, tmp_path, dry_run=True, headless=True)
    assert pw.chromium.launch_persistent_context.call_args.kwargs["headless"] is True


def _main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["linkedin_post.py", *argv])
    called = {}

    def fake_post(text, dry_run, **kw):
        called.update(text=text, dry_run=dry_run, **kw)
        return 0

    monkeypatch.setattr(lp, "post_to_linkedin", fake_post)
    with pytest.raises(SystemExit) as e:
        lp.main()
    return e.value.code, called


def test_main_passes_document_arguments(monkeypatch, tmp_path):
    txt = tmp_path / "p.txt"
    txt.write_text("body\n")
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    code, called = _main(monkeypatch, ["--text-file", str(txt), "--document", str(pdf),
                                       "--document-title", "Five ways", "--dry-run", "--headless"])
    assert code == 0
    assert called["text"] == "body"
    assert called["document"] == pdf.resolve()
    assert called["document_title"] == "Five ways"
    assert called["dry_run"] is True and called["headless"] is True


def test_main_without_document_keeps_old_behaviour(monkeypatch, tmp_path):
    txt = tmp_path / "p.txt"
    txt.write_text("body")
    code, called = _main(monkeypatch, ["--text-file", str(txt)])
    assert code == 0 and called["document"] is None and called["headless"] is False


@pytest.mark.parametrize("extra", [["--document", "x.pdf"], ["--document-title", "T"]])
def test_main_document_needs_title_and_text(monkeypatch, tmp_path, extra):
    txt = tmp_path / "p.txt"
    txt.write_text("body")
    monkeypatch.setattr(sys, "argv", ["linkedin_post.py", "--text-file", str(txt), *extra])
    with pytest.raises(SystemExit) as e:
        lp.main()
    assert e.value.code == 2


def test_main_rejects_non_pdf(monkeypatch, tmp_path):
    txt = tmp_path / "p.txt"
    txt.write_text("body")
    img = tmp_path / "d.png"
    img.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["linkedin_post.py", "--text-file", str(txt),
                                      "--document", str(img), "--document-title", "T"])
    with pytest.raises(SystemExit) as e:
        lp.main()
    assert e.value.code == 2
