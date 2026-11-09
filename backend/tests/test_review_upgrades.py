"""Paper Review upgrades (buyer revenue program piece 5): spend record, annual comparison, the $2 journal check
add-on and its submit endpoint, and the offers in the ready email. No network."""

import time
from types import SimpleNamespace

import pytest

from latextools import upgrades
from tests.test_app_paper_review_endpoints import PDF_BYTES, _FakeDict, client  # noqa: F401

DAY = 86400


def test_record_spend_is_idempotent_and_singles_only():
    store = {}
    now = 1_000_000_000.0
    assert upgrades.record_spend(store, "a@b.com", "cs_1", "paper-review-standard", 900, now)
    assert not upgrades.record_spend(store, "a@b.com", "cs_1", "paper-review-standard", 900, now)
    assert not upgrades.record_spend(store, "a@b.com", "cs_2", "paper-review-pack-5", 3800, now)
    assert not upgrades.record_spend(store, "a@b.com", "cs_3", "paper-review-standard", 0, now)
    assert not upgrades.record_spend(store, "", "cs_4", "paper-review-standard", 900, now)
    assert len(store["a@b.com"]["purchases"]) == 1


def test_record_spend_never_raises():
    class Broken:
        def get(self, k):
            raise RuntimeError("down")
    assert upgrades.record_spend(Broken(), "a@b.com", "cs_1", "paper-review-standard", 900, 1.0) is False


def _rows(*amounts, now, age_days=1, product="paper-review-journal"):
    return [{"session": f"cs_{i}", "product": product, "amount_paid": a, "at": now - age_days * DAY}
            for i, a in enumerate(amounts)]


def test_comparison_needs_two_paid_singles_in_a_year():
    now = 2_000_000_000.0
    assert upgrades.annual_comparison(_rows(1900, now=now), now) is None
    assert upgrades.annual_comparison(_rows(1900, 1900, now=now, age_days=400), now) is None
    c = upgrades.annual_comparison(_rows(1900, 1900, now=now), now)
    assert c["count"] == 2 and c["spent_cents"] == 3800 and "saving_cents" not in c
    assert c["per_review_cents"] == 658


def test_saving_only_when_spend_is_above_the_plan():
    now = 2_000_000_000.0
    c = upgrades.annual_comparison(_rows(3900, 3900, 1900, now=now), now)
    assert c["saving_cents"] == 9700 - 7900
    s = upgrades.comparison_sentence(c)
    assert "$97.00" in s and "$79.00 a year" in s and "renews each year until you cancel" in s and "$18.00 less" in s
    # 13 reviews are more than the plan covers, so no saving is claimed.
    c13 = upgrades.annual_comparison(_rows(*([900] * 13), now=now), now)
    assert "saving_cents" not in c13


def test_build_offers_eligibility():
    now = 2_000_000_000.0
    two = _rows(900, 900, now=now, product="paper-review-standard")
    o = upgrades.build_offers("paper-review-standard", False, two, now)
    assert set(o) == {"journal_addon", "annual"}
    assert o["journal_addon"]["price_cents"] == 200
    assert set(upgrades.build_offers("paper-review-standard", True, two, now)) == {"annual"}
    assert set(upgrades.build_offers("paper-review-pack-5", False, two, now)) == {"journal_addon"}
    assert upgrades.build_offers("paper-review-journal", True, [], now) == {}
    assert upgrades.build_offers("paper-review-annual", False, two, now) == {}


def test_offers_email_html_escapes_and_tags_links():
    o = upgrades.build_offers("paper-review-standard", False, [], 1.0)
    h = upgrades.offers_email_html(o, 'style="color:#000"')
    assert "utm_campaign=ready-upgrade" in h and "/tools/paper-review/journal-check/" in h and "$2.00" in h
    assert upgrades.offers_email_html({}, "") == ""


def test_compliance_markdown_orders_fixes_first():
    md = upgrades.compliance_markdown({
        "journal_name": "Nature", "summary": {"n_fail": 1, "n_warn": 1, "n_pass": 1},
        "results": [
            {"status": "pass", "label": "Page count", "current": 10, "target": 12, "note": "ok"},
            {"status": "fail", "label": "Abstract length", "current": 300, "target": 150, "note": "Cut it."},
            {"status": "warn", "label": "Data availability", "note": "Add one."},
        ],
        "notes": "Letters are shorter.", "sources": "https://example.org/guide",
    })
    assert md.startswith("# Journal check: Nature")
    assert md.index("Fix: Abstract length") < md.index("Check: Data availability") < md.index("Pass: Page count")
    assert "(found: 300; target: 150)" in md and "- https://example.org/guide" in md
    assert "could not run" in upgrades.compliance_markdown({"error": "unknown journal"})


def test_compliance_markdown_on_real_specs():
    from latextools import journals
    key = next(iter(journals.JOURNAL_SPECS))
    struct = SimpleNamespace(abstract="word " * 400, body="word " * 5000, page_count=30)
    md = upgrades.compliance_markdown(journals.check_compliance(struct, key))
    assert md.startswith("# Journal check:")


def test_journal_check_is_a_two_dollar_product(client):  # noqa: F811
    _, backend_app = client
    cfg = backend_app.PAID_PRODUCTS["journal-check"]
    assert cfg["amount"] == 200 and cfg["category"] == "journal-check" and cfg["qty"] == 1
    assert backend_app.PURCHASE_UPLOAD_PATHS["journal-check"].endswith("/journal-check/upload/")


def _seed(backend_app, product_key, session_id):
    cfg = backend_app.PAID_PRODUCTS[product_key]
    token = "tok-" + session_id
    backend_app.paper_tokens_dict[session_id] = {
        "tokens": [token], "product_key": product_key, "product_cfg": cfg, "email": "buyer@example.com",
        "amount_paid": cfg.get("amount", 0), "redeemed": False, "consumed_tokens": [],
        "created_at": time.time(), "expires_at": time.time() + 7 * DAY,
    }
    return token


def test_journal_check_submit_spawns_with_journal(client):  # noqa: F811
    http, backend_app = client
    from latextools import journals
    key = next(iter(journals.JOURNAL_SPECS))
    token = _seed(backend_app, "journal-check", "s-jc-1")
    r = http.post("/journal-check/submit", data={"token": token, "journal_key": key},
                  files={"file": ("m.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 200, r.text
    args, kwargs = backend_app.adjacent_tool_pipeline.calls[0]
    assert "journal-check" in args and kwargs["journal_key"] == key


def test_journal_check_submit_rejects_bad_journal_and_wrong_token(client):  # noqa: F811
    http, backend_app = client
    from latextools import journals
    token = _seed(backend_app, "journal-check", "s-jc-2")
    r = http.post("/journal-check/submit", data={"token": token, "journal_key": "nope"},
                  files={"file": ("m.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 400
    other = _seed(backend_app, "anonymity-check", "s-jc-3")
    r = http.post("/journal-check/submit", data={"token": other, "journal_key": next(iter(journals.JOURNAL_SPECS))},
                  files={"file": ("m.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code in (400, 403)
    assert backend_app.adjacent_tool_pipeline.calls == []


def test_journal_check_pipeline_writes_a_checklist(monkeypatch):
    import app as backend_app
    from latextools import journals, papercheck
    monkeypatch.setattr(backend_app, "paper_jobs_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_tokens_dict", _FakeDict())
    monkeypatch.setattr(backend_app, "paper_token_index_dict", _FakeDict())
    key = next(iter(journals.JOURNAL_SPECS))
    monkeypatch.setattr(papercheck, "extract_paper",
                        lambda b: SimpleNamespace(abstract="word " * 100, body="word " * 3000, page_count=9))
    _seed(backend_app, "journal-check", "s-jc-4")
    backend_app.adjacent_tool_pipeline.local("tok-s-jc-4", "journal-check", pdf_bytes=PDF_BYTES, journal_key=key)
    job = backend_app.paper_jobs_dict["tok-s-jc-4"]
    assert job["status"] == "done" and job["result_md"].startswith("# Journal check:")


def test_register_token_records_single_review_spend(client, monkeypatch):  # noqa: F811
    http, backend_app = client
    monkeypatch.setenv("BACKEND_WEBHOOK_SECRET", "s")
    amt = backend_app.PAID_PRODUCTS["paper-review-standard"]["amount"]
    for sid in ("cs_x1", "cs_x2"):
        r = http.post("/paper-review/register-token", headers={"x-webhook-secret": "s"}, json={
            "session_id": sid, "product": "paper-review-standard", "email": "Buyer@Uni.edu", "amount_paid": amt})
        assert r.status_code == 200
    recs = [v for _, v in backend_app.review_spend_dict.items()]
    assert len(recs) == 1 and len(recs[0]["purchases"]) == 2
    entry = backend_app.paper_tokens_dict["cs_x2"]
    offers = backend_app._upgrade_offers_for(entry, False)
    assert "annual" in offers and "journal_addon" in offers


def test_ready_email_carries_offers():
    from latextools import delivery
    o = upgrades.build_offers("paper-review-standard", False, [], 1.0)
    h = delivery.html_review_ready(status_url="https://x/s", amount_cents=900, offers=o)
    assert "Journal check" in h and "ready-upgrade" in h
    assert "ready-upgrade" not in delivery.html_review_ready(status_url="https://x/s", amount_cents=900)
    assert "journal-check" in delivery._READY_NAMES
