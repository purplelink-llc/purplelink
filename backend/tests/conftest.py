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
