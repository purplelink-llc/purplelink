"""Static consistency checks for the Paper Review volume packs page.

No server / network required — just parses the shipped HTML and JS.
Guards against the checkout button's no-JS fallback text drifting out of
sync with whichever pack radio is pre-checked (packs.js overwrites the
text on load, but crawlers / pre-hydration paints see the raw HTML).
"""
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[2] / "site"
PACKS_HTML = SITE / "tools" / "paper-review" / "packs" / "index.html"
PACKS_JS = SITE / "tools" / "paper-review" / "packs.js"


def test_checkout_button_matches_checked_radio_price():
    html = PACKS_HTML.read_text()

    # Find the checked radio's value and its displayed price.
    radio_match = re.search(
        r'<input type="radio" name="pack" value="([^"]+)" checked>', html
    )
    assert radio_match, "no pre-checked pack radio found"
    checked_value = radio_match.group(1)

    # The price shown in that option's pr-tier-head, e.g. <em>$12</em>.
    option_block_match = re.search(
        rf'value="{re.escape(checked_value)}" checked>.*?<em>\$(\d+)</em>',
        html,
        re.S,
    )
    assert option_block_match, f"could not find price for checked option {checked_value}"
    checked_price = option_block_match.group(1)

    # The static fallback button text.
    button_match = re.search(
        r'id="checkout-btn">Buy pack — \$(\d+)</button>', html
    )
    assert button_match, "checkout button not found or in unexpected format"
    button_price = button_match.group(1)

    assert button_price == checked_price, (
        f"checkout button shows ${button_price} but the pre-checked radio "
        f"({checked_value}) is ${checked_price}"
    )

    # Cross-check against packs.js LABELS map too, if present.
    js = PACKS_JS.read_text()
    label_match = re.search(
        rf'"{re.escape(checked_value)}":\s*"Buy pack — \$(\d+)"', js
    )
    if label_match:
        assert label_match.group(1) == checked_price
