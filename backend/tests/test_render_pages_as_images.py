"""Regression test for backend/latextools/papercheck.py::render_pages_as_images.

Confirms the L1 vision layer's PDF-to-disk staging (required because
poppler's pdftoppm/pdftocairo only accept a file path) is cleaned up
deterministically: no temp file/dir left behind after a normal render,
and none left behind if poppler raises mid-conversion.

Run via: pytest backend/tests/test_render_pages_as_images.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

pytest.importorskip("pdf2image")
PIL_Image = pytest.importorskip("PIL.Image")

from latextools import papercheck  # noqa: E402


def _tmp_entries(prefix: str) -> list[str]:
    tmp_root = tempfile.gettempdir()
    return [
        name
        for name in os.listdir(tmp_root)
        if name.startswith(prefix)
    ]


def test_render_pages_as_images_leaves_no_temp_file_on_success():
    """convert_from_path is called on a path the function owns, and that
    path (plus its parent TemporaryDirectory) is gone once the call returns.
    """
    fake_page = PIL_Image.new("RGB", (10, 10))
    seen_path = {}

    def fake_convert_from_path(path, **kwargs):
        seen_path["path"] = path
        assert os.path.exists(path), "PDF must exist on disk while poppler runs"
        # Confirm restrictive permissions (owner read/write only).
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600
        return [fake_page]

    with mock.patch("pdf2image.convert_from_path", side_effect=fake_convert_from_path):
        before = set(_tmp_entries("papercheck-vision-"))
        images = papercheck.render_pages_as_images(b"%PDF-1.4 fake", max_pages=1)
        after = set(_tmp_entries("papercheck-vision-"))

    assert len(images) == 1
    assert isinstance(images[0], bytes)
    # The path poppler was given must no longer exist post-call.
    assert not os.path.exists(seen_path["path"])
    # No stray papercheck-vision-* directories left in the temp root.
    assert after == before


def test_render_pages_as_images_caps_pixel_size_and_timeout():
    """Guards against a decompression-bomb-style PDF: a crafted MediaBox
    (PDF spec allows up to 200x200in) combined with dpi could otherwise ask
    poppler to rasterize an unbounded number of pixels per page, with no
    wall-clock limit on the call. convert_from_path must always be called
    with a `size=` cap (bounds pixel area independent of dpi/MediaBox) and a
    finite `timeout=`.
    """
    fake_page = PIL_Image.new("RGB", (10, 10))
    seen_kwargs = {}

    def fake_convert_from_path(path, **kwargs):
        seen_kwargs.update(kwargs)
        return [fake_page]

    with mock.patch("pdf2image.convert_from_path", side_effect=fake_convert_from_path):
        images = papercheck.render_pages_as_images(b"%PDF-1.4 fake", max_pages=1)

    assert len(images) == 1
    assert seen_kwargs.get("size") == papercheck.MAX_VISION_PAGE_PX
    assert seen_kwargs.get("timeout") == papercheck.VISION_RENDER_TIMEOUT_SECONDS
    assert isinstance(seen_kwargs.get("timeout"), int) and seen_kwargs["timeout"] > 0


def test_render_pages_as_images_leaves_no_temp_file_on_poppler_failure():
    """If poppler raises mid-conversion, the staged PDF must still be
    cleaned up (the failure path treats this as 'vision skipped').
    """
    seen_path = {}

    def failing_convert_from_path(path, **kwargs):
        seen_path["path"] = path
        assert os.path.exists(path)
        raise RuntimeError("simulated poppler crash")

    with mock.patch("pdf2image.convert_from_path", side_effect=failing_convert_from_path):
        before = set(_tmp_entries("papercheck-vision-"))
        images = papercheck.render_pages_as_images(b"%PDF-1.4 fake", max_pages=1)
        after = set(_tmp_entries("papercheck-vision-"))

    assert images == []
    assert not os.path.exists(seen_path["path"])
    assert after == before
