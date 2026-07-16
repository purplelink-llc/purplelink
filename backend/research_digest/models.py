"""Shared data models for the weekly research roundup."""
from __future__ import annotations

from dataclasses import dataclass, field

from .harvester import Paper


@dataclass
class DigestItem:
    """One selected paper plus its conservative, abstract-derived summary."""
    paper: Paper
    relevance: int            # 0-3, from the curator
    summary: str              # 2-4 sentence plain-language summary of the abstract
    why_it_matters: str       # 1-2 sentences tying it to muscle-on-GLP-1 readers
    action: str = ""          # optional: 1 sentence pointing to a general, already-
                               # published, non-prescriptive next step (protein target,
                               # resistance training, monitoring, or talking to a
                               # clinician). Empty when the paper doesn't cleanly map
                               # to one of those — never forced, never paper-specific
                               # medical advice. See curator.py ACTION_CATEGORIES.


@dataclass
class WeeklyDigest:
    date: str                 # YYYY-MM-DD (publish date, a Monday)
    week_label: str           # e.g. "July 4-10, 2026"
    slug: str                 # e.g. "2026-07-10"
    intro: str                # 2-3 sentence editor's note for the week
    items: list[DigestItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def has_preprints(self) -> bool:
        return any(it.paper.is_preprint for it in self.items)
