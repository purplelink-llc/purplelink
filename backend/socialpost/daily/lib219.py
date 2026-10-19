"""The PR 219 detection library (scripts/social/events.py and core.py), loaded as a library.

Only detection and facts are used from there: the sitemap, guide, product-page and video readers, the HTTP class, the
house-voice and wording helpers. Its poster, channels and queue do not post any more (see docs/social-posting.md).
"""
from __future__ import annotations

import sys

from .. import paths


def _load():
    d = str(paths.repo_root() / "scripts" / "social")
    if d not in sys.path:
        sys.path.insert(0, d)
    import core  # noqa: WPS433  (scripts/social/core.py)
    import events  # noqa: WPS433
    return core, events


core, events = _load()
Http = core.Http
Response = core.Response
Skip = core.Skip
plain = core.plain
voice_problems = core.voice_problems
