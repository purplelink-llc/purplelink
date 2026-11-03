"""utm_content tags from the marketing hub (scripts/hub/hub.py make_utm), one per post per platform.

The hub keeps every tag unique across all placements (approval queue, outreach log, video ledger, social queue), so a
post's clicks can be told apart from every other placement's. Tags are made when an item is built, before approval, and
stored on it as `utm_contents: {platform: tag}`; Item.render puts the platform's tag on the link. A link that is not on
purplelink.llc (a YouTube video) is not tagged.
"""
from __future__ import annotations

import importlib.util
import re

from . import paths

_hub = None


class TagError(Exception):
    """The hub could not make a tag (missing, or it refused the link)."""


def hub():
    global _hub
    if _hub is None:
        spec = importlib.util.spec_from_file_location("purplelink_hub", paths.repo_root() / "scripts" / "hub" / "hub.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _hub = mod
    return _hub


def on_site(link: str) -> bool:
    return bool(re.match(r"https://(www\.)?purplelink\.llc(/|$)", link or ""))


def tag(link: str, asset: str, channel: str, campaign: str, source: str = "", medium: str = "social",
        preferred: str = "") -> str:
    """A utm_content no placement uses yet for `link` on `channel`; "" for a link not on purplelink.llc."""
    if not on_site(link):
        return ""
    try:
        h = hub()
        url = h.make_utm(h.paths(), link, asset, channel, source=source or channel, campaign=campaign, medium=medium,
                         content=preferred)
    except (Exception, SystemExit) as e:
        raise TagError(f"the marketing hub could not tag {link} ({type(e).__name__}: {str(e)[:120]})")
    m = re.search(r"utm_content=([\w.\-]+)", url)
    if not m:
        raise TagError(f"the marketing hub returned no utm_content for {link}")
    return m.group(1)
