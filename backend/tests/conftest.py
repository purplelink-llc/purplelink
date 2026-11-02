from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate_usage_ledger(monkeypatch):
    """Keep `.local()` pipeline tests out of the production cost ledger.

    app.usage_ledger_dict is a real modal.Dict handle, and the pipeline tests
    stub the job/token dicts but not this one, so every run used to write
    zero-token records into paper-review-usage-ledger and made real per-job
    Anthropic cost look like $0.00 in the profit view.
    """
    try:
        import app as backend_app
    except Exception:
        return
    monkeypatch.setattr(backend_app, "usage_ledger_dict", {})


class MemVolume:
    """In-memory stand-in for the modal.Volume calls DurableDict makes."""

    class _Entry:
        def __init__(self, path):
            self.path = path

    class _Batch:
        def __init__(self, files):
            self._files = files

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def put_file(self, fileobj, path):
            self._files[path] = fileobj.read()

    def __init__(self):
        self.files = {}

    def read_file(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        yield self.files[path]

    def listdir(self, prefix):
        return [self._Entry(p) for p in sorted(self.files) if p.startswith(prefix + "/")]

    def remove_file(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        del self.files[path]

    def batch_upload(self, force=False):
        return self._Batch(self.files)


@pytest.fixture(autouse=True)
def _isolate_durable_volume(monkeypatch):
    """Keep tests off the production paper-review-durable Volume: give each
    DurableDict store in app.py an in-memory volume. Tests that swap a whole
    store for a fake dict are unaffected."""
    try:
        import app as backend_app
    except Exception:
        return
    for name in ("paper_tokens_dict", "lifecycle_optout_dict", "referral_dict"):
        store = getattr(backend_app, name, None)
        if hasattr(store, "_volume"):
            monkeypatch.setattr(store, "_volume", MemVolume())
