"""End-to-end: serve site/ locally, drive the PDF tool against the live Modal endpoint.

Requires: pip install playwright && playwright install chromium
Run only when explicitly enabled (hits the live endpoint):
    RUN_E2E=1 pytest backend/tests/test_frontend_e2e.py -q
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_E2E") != "1", reason="set RUN_E2E=1")

SITE = Path(__file__).resolve().parents[2] / "site"


@pytest.fixture
def server():
    proc = subprocess.Popen(
        ["python", "-m", "http.server", "4200", "--directory", str(SITE)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    yield "http://localhost:4200"
    proc.terminate()


def test_compile_pdf_end_to_end(server, tmp_path):
    from playwright.sync_api import sync_playwright

    tex = tmp_path / "h.tex"
    tex.write_text(r"\documentclass{article}\begin{document}Hello e2e\end{document}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{server}/tools/latex-to-pdf/")
        page.set_input_files("#file", str(tex))
        page.click("#run")
        page.wait_for_selector("a[download='compiled.pdf'], .tool-error", timeout=90000)
        assert page.query_selector("a[download='compiled.pdf']") is not None
        browser.close()
