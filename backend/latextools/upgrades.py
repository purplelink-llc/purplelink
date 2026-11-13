"""Paper Review upgrades shown after a finished review (buyer revenue program, piece 5, 2026-11-05).

Two offers, both with real prices and no deadline:

1. The journal check add-on ($10 since 2026-11-13; was $2). A Standard review (single or pack) runs without a target journal. The add-on
   runs the same rule-based journal checklist the Journal tier uses (journals.check_compliance: abstract and body
   word counts, page count, required and recommended sections, reference style) on the manuscript for one journal.
   No model call, so it costs almost nothing to run.
2. The annual plan comparison. When a buyer has paid for two or more single reviews in the last 365 days, the
   report page and the ready email say what they spent and what the $79 plan costs. It states numbers only; it
   says "you would have saved" only when the spend really is above the plan price.

Spend is recorded at purchase time (register-token) in review_spend_dict, keyed by canonical email:
{"purchases": [{"session", "product", "amount_paid", "at"}]}. Only paid single reviews are recorded, amounts as
Stripe charged them (after any discount)."""

from __future__ import annotations

import html as _html
from typing import Optional

ANNUAL_PRODUCT = "paper-review-annual"
# The $79 plan stopped taking new buyers on 2026-11-13 (lab plans replace it), so the comparison is not shown.
# Set True only if checkout's PAPER_REVIEW_ANNUAL_OPEN is turned back on.
ANNUAL_OFFER_OPEN = False
ANNUAL_CENTS = 7900
ANNUAL_REVIEWS = 12
SINGLE_REVIEW_PRODUCTS = ("paper-review-standard", "paper-review-journal", "paper-review-deep")
# Reviews that ran without a journal checklist: the add-on is offered only after these.
ADDON_ELIGIBLE = ("paper-review-standard", "paper-review-pack-5", "paper-review-pack-20")
JOURNAL_ADDON_PRODUCT = "journal-check"
JOURNAL_ADDON_CENTS = 1000  # $10 since 2026-11-13 (was $2)
JOURNAL_ADDON_PAGE = "https://purplelink.llc/tools/paper-review/journal-check/"
ANNUAL_PAGE = "https://purplelink.llc/tools/paper-review/packs/"
YEAR_SECONDS = 365 * 86400
MAX_RECORDS = 60


def _dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def record_spend(store, canon_email: str, session_id: str, product_key: str, amount_paid: int, now: float) -> bool:
    """Add one paid single review to the buyer's spend record. Idempotent on session_id (Stripe retries the
    webhook). Returns True when a row was added. Never raises."""
    try:
        if not canon_email or product_key not in SINGLE_REVIEW_PRODUCTS:
            return False
        if not isinstance(amount_paid, int) or amount_paid <= 0:
            return False
        rec = store.get(canon_email) or {}
        rows = [r for r in (rec.get("purchases") or []) if isinstance(r, dict)]
        if any(r.get("session") == session_id for r in rows):
            return False
        rows = [r for r in rows if now - float(r.get("at") or 0) <= YEAR_SECONDS * 2]
        rows.append({"session": session_id, "product": product_key, "amount_paid": amount_paid, "at": now})
        store[canon_email] = {**rec, "purchases": rows[-MAX_RECORDS:]}
        return True
    except Exception:
        return False


def annual_comparison(purchases, now: float) -> Optional[dict]:
    """The comparison for a buyer with two or more paid single reviews in the last 365 days, else None."""
    rows = [r for r in (purchases or []) if isinstance(r, dict)
            and r.get("product") in SINGLE_REVIEW_PRODUCTS
            and isinstance(r.get("amount_paid"), int) and r["amount_paid"] > 0
            and now - float(r.get("at") or 0) <= YEAR_SECONDS]
    if len(rows) < 2:
        return None
    spent = sum(r["amount_paid"] for r in rows)
    out = {
        "count": len(rows),
        "spent_cents": spent,
        "plan_cents": ANNUAL_CENTS,
        "plan_reviews": ANNUAL_REVIEWS,
        "per_review_cents": round(ANNUAL_CENTS / ANNUAL_REVIEWS),
    }
    # Only a real saving is called a saving: the plan covers at most 12 reviews a year.
    if spent > ANNUAL_CENTS and len(rows) <= ANNUAL_REVIEWS:
        out["saving_cents"] = spent - ANNUAL_CENTS
    return out


def comparison_sentence(c: dict) -> str:
    """Plain-text sentence for the report page and email."""
    s = (f"You have bought {c['count']} single reviews in the last 12 months, for {_dollars(c['spent_cents'])} in all. "
         f"The annual plan is {_dollars(c['plan_cents'])} a year for {c['plan_reviews']} Journal reviews "
         f"({_dollars(c['per_review_cents'])} each), and it renews each year until you cancel.")
    if c.get("saving_cents"):
        s += f" On the plan, these reviews would have cost {_dollars(c['saving_cents'])} less."
    return s


def build_offers(sold_as: str, journal_used: bool, purchases, now: float) -> dict:
    """The offers for one finished review. `sold_as` is the product the token was bought as."""
    offers: dict = {}
    if sold_as in ADDON_ELIGIBLE and not journal_used:
        offers["journal_addon"] = {
            "price_cents": JOURNAL_ADDON_CENTS,
            "url": JOURNAL_ADDON_PAGE,
            "text": ("Check this manuscript against one journal's stated rules (abstract and word limits, page "
                     f"count, required sections, reference style) for {_dollars(JOURNAL_ADDON_CENTS)}. "
                     "It is a rule-based checklist; the reviewers do not run again."),
        }
    if ANNUAL_OFFER_OPEN and sold_as in SINGLE_REVIEW_PRODUCTS:
        c = annual_comparison(purchases, now)
        if c:
            offers["annual"] = {**c, "url": ANNUAL_PAGE, "text": comparison_sentence(c)}
    return offers


def offers_email_html(offers: dict, link_style: str) -> str:
    """Paragraphs for the ready email. Text is escaped; URLs are our own constants."""
    parts = []
    for key, label in (("journal_addon", "Journal check"), ("annual", "Annual plan")):
        o = (offers or {}).get(key)
        if not o:
            continue
        url = _html.escape(o["url"] + "?utm_source=email&utm_campaign=ready-upgrade", quote=True)
        parts.append(f'<p style="color: #555; font-size: 0.9em;">{_html.escape(o["text"])} '
                     f'<a href="{url}" {link_style}>{label}</a></p>')
    return "\n  ".join(parts)


_STATUS_WORD = {"pass": "Pass", "fail": "Fix", "warn": "Check", "info": "Note"}


def compliance_markdown(res: Optional[dict]) -> str:
    """Render journals.check_compliance output as the add-on's report."""
    if not res:
        return ""
    if res.get("error"):
        return f"# Journal check\n\nThe check could not run: {res['error']}\n"
    name = res.get("journal_name") or res.get("journal_key") or "the journal"
    lines = [f"# Journal check: {name}", ""]
    summ = res.get("summary") or {}
    lines.append(f"{summ.get('n_fail', 0)} to fix, {summ.get('n_warn', 0)} to check, "
                 f"{summ.get('n_pass', 0)} passed.")
    lines.append("")
    lines.append("This checklist compares what was extracted from your PDF with the journal's stated rules. "
                 "Counts from a PDF are approximate, so confirm any near-limit number in your own editor, and "
                 "check the journal's current author guidelines before you submit.")
    lines.append("")
    order = {"fail": 0, "warn": 1, "info": 2, "pass": 3}
    for r in sorted(res.get("results") or [], key=lambda r: order.get(r.get("status"), 4)):
        word = _STATUS_WORD.get(r.get("status"), "Note")
        cur, tgt = r.get("current"), r.get("target")
        detail = ""
        if cur not in (None, "") or tgt not in (None, ""):
            detail = f" (found: {cur}; target: {tgt})"
        lines.append(f"- **{word}: {r.get('label', r.get('rule', ''))}**{detail}. {r.get('note', '')}".rstrip())
    notes = res.get("notes")
    if notes:
        lines += ["", "## Notes on this journal", "", str(notes)]
    sources = res.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    if sources:
        lines += ["", "## Source for these rules", ""] + [f"- {s}" for s in sources]
    return "\n".join(lines) + "\n"
