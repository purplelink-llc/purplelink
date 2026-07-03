# backend/listen/renderer.py
"""Render the listen agent's daily digest email.

Founder-facing only. Every draft reply here requires a human to read,
edit, and post it themselves — this module has no posting capability and
nothing downstream of it does either.
"""
from __future__ import annotations

import html

_BASE_CSS = (
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
    "line-height: 1.55; color: #1a1a1a; max-width: 640px;"
)

REPLY_THRESHOLD = 4


def render_digest_html(scored_pairs: list) -> str:
    """scored_pairs: list of (ListenItem, score_dict) tuples, any order —
    sorted here by descending score. Returns a full HTML email body."""
    ranked = sorted(scored_pairs, key=lambda pair: pair[1].get("score", 0), reverse=True)

    if not ranked:
        return f"""
<div style="{_BASE_CSS}">
  <h2 style="color: #6d28d9;">Listen agent — nothing today</h2>
  <p>No matching posts found on HN or Stack Exchange in the last day.</p>
</div>
"""

    actionable = [p for p in ranked if p[1].get("score", 0) >= REPLY_THRESHOLD]
    rest_count = len(ranked) - len(actionable)
    cards = "".join(_card(item, score) for item, score in actionable)

    return f"""
<div style="{_BASE_CSS}">
  <h2 style="color: #6d28d9;">Listen agent — {len(actionable)} worth a look</h2>
  <p style="color: #555; font-size: 0.9em;">
    Reviewed {len(ranked)} posts across HN + Stack Exchange (Academia) from
    the last day. {rest_count} scored below the reply threshold and are
    left out below. Nothing here was posted automatically — copy a draft,
    edit it, and post it yourself only if it is a genuinely good fit.
  </p>
  {cards or '<p>None scored high enough to draft a reply for today.</p>'}
</div>
"""


def _card(item, score: dict) -> str:
    title = html.escape(item.title or "(untitled)")
    url = html.escape(item.url or "#")
    reasoning = html.escape(score.get("reasoning", ""))
    draft = html.escape(score.get("draft_reply", "")).replace("\n", "<br>")
    source_label = "Hacker News" if item.source == "hn" else "Stack Exchange (Academia)"
    return f"""
  <div style="border: 1px solid #e5e5e5; border-radius: 8px; padding: 14px 16px; margin: 14px 0;">
    <p style="margin: 0 0 4px; font-size: 0.8em; color: #7c3aed; font-weight: 600; text-transform: uppercase;">
      {source_label} &middot; score {score.get('score', 0)}/5
    </p>
    <p style="margin: 0 0 6px;"><a href="{url}" style="color: #1a1a1a; font-weight: 600;">{title}</a></p>
    <p style="margin: 0 0 8px; color: #555; font-size: 0.85em;">{reasoning}</p>
    <div style="background: #f7f5fb; border-radius: 6px; padding: 10px 12px; font-size: 0.9em;">
      {draft}
    </div>
  </div>
"""
