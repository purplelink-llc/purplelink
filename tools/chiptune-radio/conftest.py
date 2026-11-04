"""Every test draws the themes from code unless it asks for a loop: the racer's Blender loop lives on the SSD, not in the repo, so tests that need
one build a small synthetic loop in a temporary folder (test_bgloop.py)."""
import pytest


@pytest.fixture(autouse=True)
def _code_background(monkeypatch):
    monkeypatch.setenv("AMBIENT_BG", "code")
