#!/usr/bin/env python3
"""
Render every customer email in backend/latextools/delivery.py with sample
data into one page, docs/email-previews.html, for reading before a deploy.

Each email is shown with its subject line, when it is sent, and its HTML as
the recipient sees it (inside an iframe, so its inline styles stay its own).
Nothing is sent. The output is a local file under docs/, never deployed.

Usage:
    python3 scripts/preview_emails.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from latextools import delivery as d  # noqa: E402

UNSUB = "https://purplelink.llc/paper-review/lifecycle/unsubscribe?email=you%40example.edu&token=SAMPLE"
TITLE = "Attention Sinks in Small Vision Transformers"

EMAILS = [
    ("Your Paper Review is ready", "When a paid review finishes", d.html_review_ready,
     dict(status_url="https://purplelink.llc/tools/paper-review/status/?token=SAMPLE", manuscript_title=TITLE)),
    ("Your Citation Gap report is ready", "When a Citation Gap Analysis finishes", d.html_review_ready,
     dict(status_url="https://purplelink.llc/tools/paper-review/status/?token=SAMPLE", manuscript_title=TITLE, amount_cents=300, product="citation-gap")),
    ("Your Paper Review: link to start", "At purchase, single purchases", d.html_purchase_link,
     dict(product_name="Paper Review", link="https://purplelink.llc/tools/paper-review/upload/?direct_token=SAMPLE")),
    ("Your Paper Review is still waiting", "Two days after purchase, if unused", d.html_purchase_waiting,
     dict(product_name="Paper Review", link="https://purplelink.llc/tools/paper-review/upload/?direct_token=SAMPLE", ends="Thursday 1 October")),
    ("Your 5-pack of Paper Reviews", "At purchase, volume packs", d.html_volume_pack_tokens,
     dict(tokens=["pr_SAMPLE1", "pr_SAMPLE2", "pr_SAMPLE3", "pr_SAMPLE4", "pr_SAMPLE5"], pack_size=5)),
    ("Getting the most out of your review", "Paper Review, 3 days after purchase", d.html_lifecycle_tips,
     dict(manuscript_title=TITLE, unsubscribe_url=UNSUB)),
    ("How did the review hold up?", "Paper Review, 14 days after purchase", d.html_lifecycle_review_request,
     dict(manuscript_title=TITLE, unsubscribe_url=UNSUB, feedback_url="https://purplelink.llc/feedback/?p=paper-review&s=cs_SAMPLE&k=SIG")),
    ("Still writing?", "Paper Review, 90 days after purchase, if no purchase since", d.html_lifecycle_winback,
     dict(unsubscribe_url=UNSUB)),
    ("When the reviews come back", "Around the decision date the buyer chose at upload", d.html_lifecycle_decision_reminder,
     dict(manuscript_title=TITLE, unsubscribe_url=UNSUB)),
    ("A few things in ModernTex worth knowing", "ModernTex, 3 days after purchase", d.html_lifecycle_mtx_tips,
     dict(unsubscribe_url=UNSUB)),
    ("Before you submit", "ModernTex, 21 days after purchase", d.html_lifecycle_mtx_before_submit,
     dict(unsubscribe_url=UNSUB)),
    ("Setting up the ModernTex trial", "Trial sign-up, straight away", d.html_lifecycle_trial_setup,
     dict(unsubscribe_url=UNSUB)),
    ("Four things to try in ModernTex", "Trial sign-up, day 4", d.html_lifecycle_trial_features,
     dict(unsubscribe_url=UNSUB)),
    ("Your ModernTex trial ends soon", "Trial sign-up, day 6", d.html_lifecycle_trial_ending,
     dict(unsubscribe_url=UNSUB)),
    ("A week before your submission deadline", "Deadline reminder, 7 days before the date entered", d.html_lifecycle_deadline_week,
     dict(venue="NeurIPS", deadline="Friday 16 October", unsubscribe_url=UNSUB)),
    ("A week before your resubmission deadline", "Resubmission reminder, from the response letter template", d.html_lifecycle_deadline_week,
     dict(venue="PLOS ONE", deadline="Monday 2 November", kind="resubmission", unsubscribe_url=UNSUB)),
    ("You've got a referral credit", "After a .edu purchase through a referral link", d.html_referral_credit,
     dict(promo_code="REF-SAMPLE", reason="A colleague you referred bought a Paper Review with a .edu email.")),
    ("Your invoice", "When a buyer asks for an invoice on the status page", d.html_invoice_ready,
     dict(invoice_url="https://invoice.stripe.com/i/SAMPLE", amount_cents=900)),
]


def main() -> int:
    covered = {fn.__name__ for _s, _w, fn, _k in EMAILS}
    missing = sorted(n for n in dir(d) if n.startswith("html_") and n not in covered)
    parts = []
    for subject, when, fn, kwargs in EMAILS:
        body = fn(**kwargs)
        parts.append(
            '<section><h2>%s</h2><p class="when">%s &middot; <code>%s</code></p>'
            '<iframe title="%s" srcdoc="%s"></iframe></section>'
            % (html.escape(subject), html.escape(when), fn.__name__, html.escape(subject), html.escape(body, quote=True))
        )
    note = ""
    if missing:
        note = '<p class="missing">Templates not shown here: %s</p>' % ", ".join(missing)
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Purplelink customer emails</title>
<style>
body { font: 15px/1.5 system-ui, sans-serif; margin: 32px auto; max-width: 820px; padding: 0 16px; color: #1c1326; background: #faf8fc; }
h1 { margin-bottom: 4px; } h2 { margin: 36px 0 2px; font-size: 1.15rem; }
.when { margin: 0 0 8px; color: #5b5266; font-size: 0.9rem; }
iframe { width: 100%%; height: 560px; border: 1px solid #ddd3ea; border-radius: 10px; background: #fff; }
.missing { color: #8a1c1c; }
</style></head><body>
<h1>Customer emails</h1>
<p>Every email the site and backend send to customers, with sample data. Generated by <code>scripts/preview_emails.py</code>; nothing is sent.</p>
%s
%s
</body></html>
""" % (note, "\n".join(parts))
    out = ROOT / "docs" / "email-previews.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(EMAILS)} emails){'; missing: ' + ', '.join(missing) if missing else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
