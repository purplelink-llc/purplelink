"""Regression test for the unbounded-upload-read defect in backend/app.py.

`_too_large()` in app.py only inspects the Content-Length header before a
request body is read. A request that omits Content-Length (chunked
transfer-encoding) or understates it bypasses that pre-check entirely, so
the handler would previously buffer the *entire* body via `UploadFile.read()`
before `core.validate_paper_upload` ever got a chance to reject it based on
`len(data)`. That's a memory-exhaustion vector independent of any header the
client sends.

The fix adds `_read_capped`, which reads an UploadFile in bounded chunks and
aborts (raising `_UploadTooLarge`) as soon as the running total exceeds the
cap -- so an oversized body is never fully buffered, regardless of what (if
anything) Content-Length claimed.

We can't import backend/app.py directly in a fast/hermetic unit test (its
routes are closures inside a `@modal.asgi_app()` function that requires a
live Modal client to construct). Instead this test reimplements the exact
`_read_capped` algorithm against a fake chunked-upload object that never
reports a size up front, and proves the cap is enforced purely from the
bytes actually read.
"""

import pytest


class _UploadTooLarge(Exception):
    pass


class _FakeChunkedUpload:
    """Mimics a streamed UploadFile: yields fixed-size chunks from a
    source buffer with no Content-Length / size hint available anywhere,
    the same shape as a chunked-transfer-encoding request body."""

    def __init__(self, data: bytes, chunk_size: int = 1024 * 1024):
        self._data = data
        self._chunk_size = chunk_size
        self._pos = 0

    async def read(self, n: int) -> bytes:
        # UploadFile.read(n) honors the requested chunk size, not our
        # internal chunk_size -- mirror that.
        end = min(self._pos + n, len(self._data))
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk


async def _read_capped(upload, max_bytes: int) -> bytes:
    """Same algorithm as app.py's `_read_capped`."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise _UploadTooLarge()
    return b"".join(chunks)


@pytest.mark.asyncio
async def test_read_capped_returns_full_body_under_cap():
    body = b"x" * 1000
    upload = _FakeChunkedUpload(body)
    data = await _read_capped(upload, max_bytes=2000)
    assert data == body


@pytest.mark.asyncio
async def test_read_capped_rejects_oversized_body_with_no_size_hint():
    """The core regression check: a body larger than the cap must be
    rejected even though the fake upload never advertises its total size
    anywhere (simulating chunked transfer-encoding / no Content-Length)."""
    max_bytes = 20 * 1024 * 1024  # matches core.MAX_PAPER_UPLOAD_BYTES
    oversized = b"y" * (max_bytes + 10 * 1024 * 1024)  # 10 MB over cap
    upload = _FakeChunkedUpload(oversized)
    with pytest.raises(_UploadTooLarge):
        await _read_capped(upload, max_bytes=max_bytes)


@pytest.mark.asyncio
async def test_read_capped_never_buffers_past_the_cap():
    """Regression for the memory-exhaustion vector itself: reading must
    stop as soon as the running total crosses max_bytes, not after the
    full oversized body has been consumed."""
    max_bytes = 5 * 1024 * 1024
    oversized = b"z" * (max_bytes * 10)
    upload = _FakeChunkedUpload(oversized, chunk_size=1024 * 1024)
    with pytest.raises(_UploadTooLarge):
        await _read_capped(upload, max_bytes=max_bytes)
    # Only a handful of 1 MB chunks should have been pulled before the
    # cap tripped -- nowhere near the full 50 MB body.
    assert upload._pos <= max_bytes + (1024 * 1024)


@pytest.mark.asyncio
async def test_read_capped_boundary_exact_size_is_allowed():
    max_bytes = 1000
    body = b"a" * max_bytes
    upload = _FakeChunkedUpload(body)
    data = await _read_capped(upload, max_bytes=max_bytes)
    assert data == body


@pytest.mark.asyncio
async def test_read_capped_boundary_one_byte_over_is_rejected():
    max_bytes = 1000
    body = b"a" * (max_bytes + 1)
    upload = _FakeChunkedUpload(body)
    with pytest.raises(_UploadTooLarge):
        await _read_capped(upload, max_bytes=max_bytes)
