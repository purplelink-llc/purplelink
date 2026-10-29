# Site tests

Regression tests for shipped roadmap items. They read the checked-in files under `site/` and `scripts/`; nothing here
touches the network, a date or a third-party service. Stdlib only (Python 3.11+); the modules are `unittest` classes, so
pytest collects them too.

    python3 -m pytest site-tests -q        # if pytest is installed
    python3 -m unittest discover -s site-tests -t site-tests -v   # no dependencies

One module per item: `test_m1_*` (latex-errors and templates link the editors guide), `test_m2_*` (ModernTex seats),
`test_m5_*` (noindex and the sitemap), `test_m6_*` (Outbound Veil proof line), `test_guides_m6_m8` (the two new guides),
`test_w8_*`, `test_social_cards`, `test_digest_links`, `test_photography_text`, `test_asset_fingerprints`,
`test_facts_consistency`, `test_intl_moderntex` (hreflang across the four ModernTex pages, no Google on /zh-cn/, sitemap alternates).

`scripts/verify_roadmap_live.py` is the live counterpart (needs the network and Ben's Mac); it is not run in CI.
The Node tests run with `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`.
