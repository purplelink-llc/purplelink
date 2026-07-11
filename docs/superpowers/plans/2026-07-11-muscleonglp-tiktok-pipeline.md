# MuscleOnGLP TikTok Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a faceless, local TikTok pipeline that turns each weekly MuscleOnGLP research roundup into per-paper + roundup videos and auto-posts them at a daily drip, reusing the existing `/Volumes/Extreme SSD/TikTokPipeline/` framework.

**Architecture:** A new sibling package `MuscleOnGLPPipeline/` next to `AITAPipeline/`. It parses the already-published roundup HTML, templates spoken scripts from vetted summaries (no LLM), narrates with edge-tts (word timings), renders captioned 9:16 video over gym b-roll with ffmpeg/OpenCV, and writes the shared `output/post_queue.json` contract consumed by the shared `tiktok_upload.py`. Because the uploader only posts a *today-dated* queue, rendering (weekly) is separated from posting (daily): the pipeline renders once per roundup into `output/` + a `backlog.json` master list, then each day promotes the next `DAILY_CAP` unposted entries into a today-dated queue.

**Tech Stack:** Python 3.12, edge-tts, OpenCV (`cv2`), Pillow, ffmpeg (installed at `/usr/local/bin/ffmpeg`), pytest. Reuses shared `tiktok_upload.py` / `post_helper.py`. launchd for scheduling.

---

## Reference facts (verified against the existing framework)

- **Shared uploader** `/Volumes/Extreme SSD/TikTokPipeline/tiktok_upload.py` reads `<ROOT>/output/post_queue.json` where `ROOT = $TIKTOK_PIPELINE_ROOT`. It calls `post_helper.pending_candidates(q)` and maps each to `{"id", "file": OUTPUT_DIR / c["split_screen"], "caption": c["description"], "title": c["title"]}`. It **ignores any queue whose `date` != today**.
- **`post_helper.pending_candidates(q)`** returns candidates where `c["id"] not in q["posted_ids"]` and `(OUTPUT_DIR / c["split_screen"]).exists()`, highest `score` first. `q["posted"]==True` short-circuits to `[]`.
- **Queue schema:** `{date, generated, posted, posted_ids, candidates:[{id, title, score, split_screen, description, hashtags, duration, ...}]}`.
- **Cleanup** (`post_helper cleanup` / AITA's `run_daily.sh`) globs `output/<id>_*` to delete posted files, so every output filename for clip `<id>` MUST start with `<id>_`.
- **Per-pipeline files:** each pipeline owns its `fetch_*.py`, `narrate.py`, `render.py`, `pipeline.py`. Only `tiktok_upload.py` + `post_helper.py` live in the parent.
- **`run_daily.sh`** sets `TIKTOK_PIPELINE_ROOT` and `TIKTOK_PROFILE_DIR` (per-account Chrome profile), then runs `pipeline.py` (render/promote) and `../tiktok_upload.py` (post).

Absolute paths used throughout:
- Pipeline dir: `/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline`
- Parent (shared): `/Volumes/Extreme SSD/TikTokPipeline`
- Site checkout (roundup source): `/Volumes/Extreme SSD/Purplelink LLC/muscleonglp-site`
- Python: `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`

## File structure

```
/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/
  fetch_roundup.py      # vendored roundup HTML parser → Roundup/RoundupPaper
  script.py             # spoken_form + paper_script + roundup_script (pure)
  captions.py           # build_caption + hashtag pools (pure)
  narrate.py            # edge-tts synth + word timings (generic copy of AITA's)
  render.py             # 9:16 captioned render over gym b-roll (adapted)
  pipeline.py           # render-once-weekly + promote-DAILY_CAP-daily; main()
  run_daily.sh          # launchd runner (clone of AITA's, MuscleOnGLP profile)
  com.purplelink.muscleonglp-tiktok.plist   # launchd job
  backgrounds/          # CC0 vertical gym b-roll *.mp4 (Ben sources)
  output/               # rendered mp4s + backlog.json + post_queue.json
  tests/
    conftest.py
    fixtures/roundup_sample.html
    test_fetch_roundup.py
    test_script.py
    test_captions.py
    test_pipeline_logic.py
    test_render_smoke.py
```

Test runner: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" -m pytest tests -v`

Throughout, `PY` denotes `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`.

---

## Task 1: Package skeleton + test harness

**Files:**
- Create: `MuscleOnGLPPipeline/tests/conftest.py`
- Create: `MuscleOnGLPPipeline/.gitignore`

- [ ] **Step 1: Create the directories**

```bash
cd "/Volumes/Extreme SSD/TikTokPipeline"
mkdir -p MuscleOnGLPPipeline/tests/fixtures MuscleOnGLPPipeline/backgrounds MuscleOnGLPPipeline/output
```

- [ ] **Step 2: Write `tests/conftest.py`** so tests import the pipeline modules by adding the package dir to `sys.path`.

```python
import sys
from pathlib import Path

# The pipeline modules are top-level scripts in the package dir, not an
# installed package; put that dir on sys.path so `import script` etc. work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 3: Write `.gitignore`** (keep rendered media + queue state out of git).

```gitignore
output/
backgrounds/*.mp4
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 4: Verify pytest collects nothing yet (harness works)**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" -m pytest tests -q`
Expected: `no tests ran` (exit code 5), no import errors.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline"
git add -A 2>/dev/null || true
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline 2>/dev/null || true
# If the parent is not a git repo, initialize one so the new pipeline is tracked:
git -C "/Volumes/Extreme SSD/TikTokPipeline" rev-parse --git-dir >/dev/null 2>&1 || git -C "/Volumes/Extreme SSD/TikTokPipeline" init
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): package skeleton + test harness"
```

---

## Task 2: `fetch_roundup.py` — vendored roundup parser

**Files:**
- Create: `MuscleOnGLPPipeline/fetch_roundup.py`
- Create: `MuscleOnGLPPipeline/tests/fixtures/roundup_sample.html`
- Test: `MuscleOnGLPPipeline/tests/test_fetch_roundup.py`

The parser is a direct port of `backend/research_digest`-published markup, matching `monthly_guide.roundups.parse_post_html`. The site renders each paper as `<article class="rr-item">` with `<h2><a href>`, `<p class="rr-meta">`, a following `<p>` summary, and `<p class="rr-why"><strong>…</strong> …</p>`.

- [ ] **Step 1: Write the fixture** `tests/fixtures/roundup_sample.html`

```html
<html><head><title>Weekly research</title></head><body>
<article class="research-roundup">
<h1>This week in GLP-1 research</h1>
<p class="article-dek">Two new papers on lean mass during incretin therapy.</p>
<article class="rr-item">
  <h2><a href="https://doi.org/10.1/abc" rel="noopener">Tirzepatide and lean mass in a 72-week trial</a></h2>
  <p class="rr-meta">JAMA &middot; 2026-07-08 &middot; Smith J et al.</p>
  <p>Participants on tirzepatide lost more total weight, and about 25% of that loss was lean mass.</p>
  <p class="rr-why"><strong>Why it matters:</strong> Resistance training and protein may blunt the lean-mass share of loss.</p>
</article>
<article class="rr-item">
  <h2><a href="https://europepmc.org/article/PPR/xyz">Retatrutide body-composition preprint</a></h2>
  <p class="rr-meta">medRxiv preprint &middot; 2026-07-05 &middot; Doe A et al.</p>
  <p>A triple agonist produced large fat-mass reductions; lean-mass effects were not yet peer-reviewed.</p>
  <p class="rr-why"><strong>Why it matters:</strong> Early signal that next-gen agonists follow the same lean-mass pattern.</p>
</article>
</article>
</body></html>
```

- [ ] **Step 2: Write the failing test** `tests/test_fetch_roundup.py`

```python
import json
from pathlib import Path

import fetch_roundup as F

FIX = Path(__file__).parent / "fixtures" / "roundup_sample.html"


def test_parse_post_html_extracts_papers():
    dek, papers = F.parse_post_html(FIX.read_text())
    assert dek == "Two new papers on lean mass during incretin therapy."
    assert len(papers) == 2
    p0 = papers[0]
    assert p0.title == "Tirzepatide and lean mass in a 72-week trial"
    assert p0.url == "https://doi.org/10.1/abc"
    assert "JAMA" in p0.meta and "Smith J" in p0.meta
    assert "25%" in p0.summary
    assert p0.why.startswith("Resistance training")


def test_fetch_latest_roundup_reads_manifest(tmp_path):
    site = tmp_path / "site"
    (site / "research" / "2026-07-13").mkdir(parents=True)
    (site / "research" / "index.json").write_text(json.dumps([
        {"slug": "2026-07-06", "date": "2026-07-06", "week_label": "Jun 30-Jul 6"},
        {"slug": "2026-07-13", "date": "2026-07-13", "week_label": "Jul 7-13"},
    ]))
    (site / "research" / "2026-07-13" / "index.html").write_text(FIX.read_text())
    r = F.fetch_latest_roundup(str(site))
    assert r is not None
    assert r.slug == "2026-07-13"          # newest by date
    assert r.week_label == "Jul 7-13"
    assert len(r.papers) == 2


def test_fetch_latest_roundup_missing_manifest(tmp_path):
    assert F.fetch_latest_roundup(str(tmp_path / "nope")) is None
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_fetch_roundup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fetch_roundup'`.

- [ ] **Step 4: Implement** `fetch_roundup.py`

```python
#!/usr/bin/env python3
"""Read the newest published MuscleOnGLP research roundup out of the local site
checkout and return its per-paper items. Pure filesystem + HTML parsing — no
network. The markup (`rr-item`, `rr-meta`, `rr-why`, `article-dek`) is produced
by the site's own research_digest renderer; this parser is a vendored copy of
`backend/monthly_guide/roundups.parse_post_html` so the pipeline stays
self-contained in its separate location.
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field

MANIFEST_REL = "research/index.json"
DEFAULT_SITE = "/Volumes/Extreme SSD/Purplelink LLC/muscleonglp-site"


@dataclass
class RoundupPaper:
    title: str
    url: str
    meta: str
    summary: str
    why: str


@dataclass
class Roundup:
    slug: str
    week_label: str
    date: str
    dek: str = ""
    papers: list[RoundupPaper] = field(default_factory=list)


def _clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


_ITEM_RE = re.compile(r'<article class="rr-item">(.*?)</article>', re.S)
_TITLE_RE = re.compile(r'<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>', re.S)
_META_RE = re.compile(r'<p class="rr-meta">(.*?)</p>', re.S)
_SUMMARY_RE = re.compile(r'</p>\s*<p>(.*?)</p>', re.S)
_WHY_RE = re.compile(r'<p class="rr-why">.*?</strong>\s*(.*?)</p>', re.S)
_DEK_RE = re.compile(r'<p class="article-dek">(.*?)</p>', re.S)


def parse_post_html(post_html: str) -> tuple[str, list[RoundupPaper]]:
    dek_m = _DEK_RE.search(post_html)
    dek = _clean(dek_m.group(1)) if dek_m else ""
    papers: list[RoundupPaper] = []
    for block in _ITEM_RE.findall(post_html):
        title_m = _TITLE_RE.search(block)
        if not title_m:
            continue
        url, title = title_m.group(1).strip(), _clean(title_m.group(2))
        meta_m = _META_RE.search(block)
        summary_m = _SUMMARY_RE.search(block)
        why_m = _WHY_RE.search(block)
        papers.append(RoundupPaper(
            title=title,
            url=url,
            meta=_clean(meta_m.group(1)) if meta_m else "",
            summary=_clean(summary_m.group(1)) if summary_m else "",
            why=_clean(why_m.group(1)) if why_m else "",
        ))
    return dek, papers


def fetch_latest_roundup(site_dir: str | None = None) -> Roundup | None:
    """Newest roundup (by manifest `date`) as a Roundup, or None if the manifest
    is missing/empty or its post HTML is absent."""
    site_dir = site_dir or os.environ.get("MUSCLEONGLP_SITE_DIR") or DEFAULT_SITE
    mpath = os.path.join(site_dir, MANIFEST_REL)
    if not os.path.exists(mpath):
        return None
    with open(mpath) as f:
        manifest = json.load(f)
    if not manifest:
        return None
    newest = max(manifest, key=lambda m: m.get("date", ""))
    slug = newest["slug"]
    post_path = os.path.join(site_dir, "research", slug, "index.html")
    dek, papers = ("", [])
    if os.path.exists(post_path):
        with open(post_path) as f:
            dek, papers = parse_post_html(f.read())
    return Roundup(
        slug=slug,
        week_label=newest.get("week_label", slug),
        date=newest["date"],
        dek=dek,
        papers=papers,
    )


if __name__ == "__main__":
    r = fetch_latest_roundup()
    if not r:
        print("no roundup found")
    else:
        print(f"{r.slug} ({r.week_label}): {len(r.papers)} paper(s)")
        for p in r.papers:
            print(f"  - {p.title[:70]}")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_fetch_roundup.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): fetch_roundup parser + tests"
```

---

## Task 3: `script.py` — spoken-form + templated scripts

**Files:**
- Create: `MuscleOnGLPPipeline/script.py`
- Test: `MuscleOnGLPPipeline/tests/test_script.py`

- [ ] **Step 1: Write the failing test** `tests/test_script.py`

```python
import script
from fetch_roundup import RoundupPaper, Roundup


def test_spoken_form_expands_domain_terms():
    out = script.spoken_form("GLP-1 and GIP cut fat by 25% vs placebo; PYY too.")
    assert "G L P one" in out
    assert "gip" in out.lower()
    assert "percent" in out
    assert "versus" in out
    assert "P Y Y" in out
    assert "%" not in out


def test_paper_script_is_descriptive_and_has_disclaimer():
    p = RoundupPaper(
        title="Tirzepatide and lean mass",
        url="https://doi.org/10.1/abc",
        meta="JAMA 2026",
        summary="About 25% of weight lost was lean mass.",
        why="Training may protect lean mass.",
    )
    spoken, title = script.paper_script(p)
    assert title == "Tirzepatide and lean mass"
    assert "lean mass" in spoken.lower()
    assert "not medical advice" in spoken.lower()
    assert "getmuscleonglp" in spoken.lower()
    # descriptive, not prescriptive: no second-person command
    assert "you should" not in spoken.lower()


def test_roundup_script_covers_each_paper():
    r = Roundup(
        slug="2026-07-13", week_label="Jul 7-13", date="2026-07-13",
        dek="Two papers on lean mass.",
        papers=[
            RoundupPaper("Paper A", "u1", "m", "s", "A protects muscle."),
            RoundupPaper("Paper B", "u2", "m", "s", "B affects strength."),
        ],
    )
    spoken, title = script.roundup_script(r)
    assert "this week" in title.lower()
    assert "Paper A" in spoken and "Paper B" in spoken
    assert "not medical advice" in spoken.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_script.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'script'`.

- [ ] **Step 3: Implement** `script.py`

```python
#!/usr/bin/env python3
"""Turn a roundup paper (or the whole roundup) into a spoken narration script
and an on-screen title. Deterministic and LLM-free: the narration is composed
from the roundup's already-vetted `summary` + `why` text, so it adds no new
claims and stays descriptive. `spoken_form` rewrites domain jargon so the TTS
pronounces it correctly (the on-screen captions keep the originals).
"""
from __future__ import annotations

import re

from fetch_roundup import Roundup, RoundupPaper

DISCLAIMER_SPOKEN = "This is educational, not medical advice."
CTA_SPOKEN = "Full breakdown at get muscle on G L P dot com. Link in bio."

# (pattern, replacement). Order matters: do multi-token drug names before the
# bare acronym expansions. On-screen text keeps the originals.
_SPOKEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bGLP-?1\b", re.I), "G L P one"),
    (re.compile(r"\bGIP\b"), "gip"),
    (re.compile(r"\bPYY\b"), "P Y Y"),
    (re.compile(r"\bDXA\b", re.I), "dexa"),
    (re.compile(r"\bBMI\b"), "B M I"),
    (re.compile(r"\bretatrutide\b", re.I), "reta-TROO-tide"),
    (re.compile(r"\btirzepatide\b", re.I), "tur-ZEP-a-tide"),
    (re.compile(r"\bsemaglutide\b", re.I), "SEM-a-gloo-tide"),
    (re.compile(r"\bsurvodutide\b", re.I), "sur-VOD-you-tide"),
    (re.compile(r"\bcagrilintide\b", re.I), "ka-GRIL-in-tide"),
    (re.compile(r"\bvs\.?\b", re.I), "versus"),
    (re.compile(r"%"), " percent"),
    (re.compile(r"\s*&\s*"), " and "),
]


def spoken_form(text: str) -> str:
    for pat, rep in _SPOKEN:
        text = pat.sub(rep, text)
    return re.sub(r"\s+", " ", text).strip()


def _clip(text: str) -> str:
    """Trim to a sentence-safe length so a single paper video stays ~25-40s."""
    text = text.strip()
    if len(text) <= 320:
        return text
    cut = text[:320]
    dot = cut.rfind(". ")
    return (cut[:dot + 1] if dot > 120 else cut).strip()


def paper_script(paper: RoundupPaper) -> tuple[str, str]:
    """(spoken_text, on_screen_title). Spoken text has spoken_form applied;
    the title keeps the original wording for the caption banner."""
    lead = "New research on muscle and GLP-1 medications."
    summary = _clip(paper.summary) or paper.title
    why = _clip(paper.why)
    parts = [lead, summary]
    if why:
        parts.append("Why it matters: " + why)
    parts.append(DISCLAIMER_SPOKEN)
    parts.append(CTA_SPOKEN)
    spoken = spoken_form(" ".join(parts))
    return spoken, paper.title


def roundup_script(roundup: Roundup) -> tuple[str, str]:
    """(spoken_text, on_screen_title) for the weekly wrap video."""
    title = "This week in GLP-1 research"
    lead = roundup.dek.strip() or "Here is this week in GLP-1 and muscle research."
    lines = [lead]
    for p in roundup.papers:
        takeaway = _clip(p.why) or _clip(p.summary)
        lines.append(f"{p.title}. {takeaway}")
    lines.append(DISCLAIMER_SPOKEN)
    lines.append(CTA_SPOKEN)
    spoken = spoken_form(" ".join(lines))
    return spoken, title
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_script.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): script templating + spoken-form + tests"
```

---

## Task 4: `captions.py` — TikTok caption + hashtags

**Files:**
- Create: `MuscleOnGLPPipeline/captions.py`
- Test: `MuscleOnGLPPipeline/tests/test_captions.py`

- [ ] **Step 1: Write the failing test** `tests/test_captions.py`

```python
import random

import captions


def test_paper_caption_structure_and_hashtags():
    cap, tags = captions.build_caption(
        kind="paper",
        title="Tirzepatide and lean mass in a 72-week trial",
        rng=random.Random(1),
    )
    # hook line is the title
    assert cap.splitlines()[0].startswith("Tirzepatide and lean mass")
    # disclaimer + link present
    assert "not medical advice" in cap.lower()
    assert "getmuscleonglp.com" in cap.lower()
    # hashtags: deduped, all start with '#', niche tags present
    assert cap.strip().endswith(" ".join(f"#{t}" for t in tags))
    assert len(tags) == len(set(tags))
    assert "glp1" in [t.lower() for t in tags]


def test_roundup_caption_uses_wrap_hook():
    cap, tags = captions.build_caption(
        kind="roundup", title="This week in GLP-1 research", rng=random.Random(2))
    assert cap.splitlines()[0] == "This week in GLP-1 research"
    assert tags  # non-empty
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_captions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'captions'`.

- [ ] **Step 3: Implement** `captions.py`

```python
#!/usr/bin/env python3
"""SEO/GEO-minded TikTok caption + hashtag builder for MuscleOnGLP videos.
Mirrors AITAPipeline.build_caption's shape: HOOK (title) + keyword-rich
DESCRIPTION + CTA + tiered, deduped hashtags. Descriptions name the drug/topic
so search and AI engines understand the clip; every caption carries the
disclaimer and the bio-link CTA.
"""
from __future__ import annotations

import random

DESC_POOL = [
    "New peer-reviewed research on preserving muscle and lean mass while on "
    "GLP-1 medications like Ozempic, Wegovy, Mounjaro and Zepbound.",
    "What the latest GLP-1 and incretin studies say about lean mass, protein "
    "intake and resistance training during weight loss.",
    "Breaking down this week's muscle-and-GLP-1 research in plain language.",
]

CTA_POOL = [
    "Full breakdown at getmuscleonglp.com — link in bio.",
    "Read the full research review at getmuscleonglp.com (link in bio).",
]

DISCLAIMER = "Educational, not medical advice."

NICHE_TAGS = ["GLP1", "musclepreservation", "leanmass", "ozempic", "wegovy"]
BROAD_TAGS = ["weightloss", "fitness", "health", "gym", "nutrition"]
MID_TAGS = ["mounjaro", "zepbound", "tirzepatide", "retatrutide", "protein",
            "sarcopenia", "resistancetraining", "bodycomposition"]


def build_caption(kind: str, title: str,
                  rng: random.Random | None = None) -> tuple[str, list[str]]:
    """Return (caption_text, hashtags). `kind` is "paper" or "roundup"."""
    rng = rng or random.Random()
    desc = rng.choice(DESC_POOL)
    cta = rng.choice(CTA_POOL)
    tags = NICHE_TAGS + rng.sample(BROAD_TAGS, 3) + rng.sample(MID_TAGS, 4)
    seen, ordered = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            ordered.append(t)
    caption = (f"{title}\n\n{desc}\n\n{cta}\n{DISCLAIMER}\n\n"
               + " ".join(f"#{t}" for t in ordered))
    return caption, ordered
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_captions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): caption + hashtag builder + tests"
```

---

## Task 5: `narrate.py` — edge-tts synthesis (vendored, generic)

**Files:**
- Create: `MuscleOnGLPPipeline/narrate.py`

This is AITA's `narrate.py` with the AITA-specific `_SPOKEN` map removed (spoken-form now lives in `script.py`, applied before narration) and a calmer default voice. No unit test (edge-tts hits the network); a guarded manual smoke is the check.

- [ ] **Step 1: Implement** `narrate.py`

```python
#!/usr/bin/env python3
"""TTS narration via edge-tts (free Microsoft neural voices) with word-level
timestamps. WordBoundary events (100-ns ticks) arrive alongside the audio, so
caption sync needs no separate alignment pass.

    narrate(text, voice, mp3_path) -> [{"word", "start", "end"}, ...]

Text should already be in spoken form (see script.spoken_form); this module
does not rewrite it. CLI:  python3 narrate.py "some text" out.mp3
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

DEFAULT_VOICE = "en-US-JennyNeural"   # calm, credible; swap to taste
RATE = "+3%"                          # measured — calmer than AITA's +8%


async def _run(text: str, voice: str, mp3_path: Path) -> list[dict]:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=RATE, boundary="WordBoundary")
    words: list[dict] = []
    with open(mp3_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append({"word": chunk["text"],
                              "start": round(start, 3),
                              "end": round(start + chunk["duration"] / 1e7, 3)})
    return words


def narrate(text: str, voice: str, mp3_path: Path) -> list[dict]:
    mp3_path = Path(mp3_path)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    words = asyncio.run(_run(text, voice or DEFAULT_VOICE, mp3_path))
    if not words or mp3_path.stat().st_size == 0:
        raise RuntimeError("edge-tts produced no audio/word events")
    return words


if __name__ == "__main__":
    txt = sys.argv[1] if len(sys.argv) > 1 else "New research on muscle and G L P one medications."
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "output/narrate_test.mp3")
    w = narrate(txt, DEFAULT_VOICE, out)
    print(json.dumps(w[:8], indent=1))
    print(f"{len(w)} words, {w[-1]['end']:.1f}s -> {out}")
```

- [ ] **Step 2: Install edge-tts and run the manual smoke**

```bash
"$PY" -m pip install --quiet edge_tts
cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline"
"$PY" narrate.py "New research on muscle and G L P one medications." output/narrate_test.mp3
```
Expected: prints word timings and a non-zero-length `output/narrate_test.mp3`. (Requires network.)

- [ ] **Step 3: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): vendored edge-tts narrate (calm voice)"
```

---

## Task 6: `render.py` — captioned 9:16 render (adapted from AITA)

**Files:**
- Create: `MuscleOnGLPPipeline/render.py`
- Test: `MuscleOnGLPPipeline/tests/test_render_smoke.py`

Start from AITA's `render.py` (`/Volumes/Extreme SSD/TikTokPipeline/AITAPipeline/render.py`) and apply the MuscleOnGLP changes below: brand-green highlight, a persistent disclaimer footer, and a branded end card. The caption/word-sync machinery (`chunk_words`, `render_chunk_overlay`, `render_title_banner`, `_alpha_blit`, the cv2→ffmpeg mux) is unchanged.

- [ ] **Step 1: Copy AITA's render.py as the starting point**

```bash
cp "/Volumes/Extreme SSD/TikTokPipeline/AITAPipeline/render.py" \
   "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/render.py"
```

- [ ] **Step 2: Change the brand constants** — replace the constants block (the lines from `W, H = 1080, 1920` through `BED_VOLUME = 0.06`) with:

```python
W, H = 1080, 1920
FPS = 30
CHUNK_WORDS = 4
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
CAPTION_SIZE = 78
TITLE_SIZE = 54
TITLE_SECONDS = 6.0
HIGHLIGHT = (52, 160, 127)     # MuscleOnGLP brand green #34A07F (RGB)
BASE_COLOR = (255, 255, 255)
BED_VOLUME = 0.05
DISCLAIMER_TEXT = "Educational, not medical advice"
DISCLAIMER_SIZE = 34
ENDCARD_SECONDS = 2.2
ENDCARD_LINES = ["getmuscleonglp.com", "link in bio"]
ENDCARD_SIZE = 66
BRAND_GREEN_BGR = (127, 160, 52)   # #34A07F as BGR for cv2 fills
```

- [ ] **Step 3: Add a disclaimer-footer overlay builder** — insert this function immediately after `render_title_banner`:

```python
def render_disclaimer_footer() -> np.ndarray:
    """Small persistent 'Educational, not medical advice' strip (RGBA)."""
    font = _font(DISCLAIMER_SIZE)
    img = Image.new("RGBA", (W, DISCLAIMER_SIZE + 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    tw = draw.textlength(DISCLAIMER_TEXT, font=font)
    x = (W - tw) / 2
    draw.text((x, 8), DISCLAIMER_TEXT, font=font, fill=(255, 255, 255, 235),
              stroke_width=5, stroke_fill=(0, 0, 0, 255))
    return np.array(img)


def render_end_card() -> np.ndarray:
    """Full-frame brand-green end card (RGBA) with the CTA lines."""
    img = Image.new("RGBA", (W, H), BRAND_GREEN_BGR[::-1] + (255,))  # RGB green, opaque
    draw = ImageDraw.Draw(img)
    font = _font(ENDCARD_SIZE)
    total_h = (ENDCARD_SIZE + 24) * len(ENDCARD_LINES)
    y = (H - total_h) / 2
    for ln in ENDCARD_LINES:
        tw = draw.textlength(ln, font=font)
        draw.text(((W - tw) / 2, y), ln, font=font, fill=(255, 255, 255, 255),
                  stroke_width=4, stroke_fill=(20, 60, 48, 255))
        y += ENDCARD_SIZE + 24
    return np.array(img)
```

- [ ] **Step 4: Composite the footer every frame + the end card at the tail** — in `render_video`, after the line `title_banner = render_title_banner(title)`, add:

```python
    footer = render_disclaimer_footer()
    end_card = render_end_card()
    endcard_start = duration - ENDCARD_SECONDS
```

Then, inside the per-frame loop, immediately BEFORE `vw.write(frame)`, add:

```python
        # persistent disclaimer footer (kept clear of the caption band)
        _alpha_blit(frame, footer, H - 150)
        # brand-green CTA end card over the final seconds
        if t >= endcard_start:
            _alpha_blit(frame, end_card, 0)
```

- [ ] **Step 5: Point the smoke `__main__` at MuscleOnGLP text** — replace the `if __name__ == "__main__":` block at the bottom of `render.py` with:

```python
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from narrate import narrate
    text = ("New research on muscle and G L P one medications. About twenty five "
            "percent of weight lost was lean mass. Why it matters: training may "
            "protect lean mass. This is educational, not medical advice.")
    out = Path("output"); out.mkdir(exist_ok=True)
    w = narrate(text, "en-US-JennyNeural", out / "smoke.mp3")
    bgs = sorted(Path("backgrounds").glob("*.mp4"))
    if not bgs:
        raise SystemExit("put a vertical .mp4 in backgrounds/ first")
    d = render_video("Tirzepatide and lean mass in a 72-week trial",
                     w, out / "smoke.mp3", bgs[0], out / "smoke.mp4",
                     random.Random(42))
    print(f"rendered {d:.1f}s -> output/smoke.mp4")
```

- [ ] **Step 6: Write the smoke test** `tests/test_render_smoke.py` (generates a tiny background with ffmpeg and fake word timings, so it needs no edge-tts/network — only ffmpeg + cv2 + Pillow).

```python
import subprocess
import wave
import struct
import math
from pathlib import Path

import pytest

import render


def _make_bg(path: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=1080x1920:d=3",
         "-r", "30", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True)


def _make_silent_mp3(path: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", "2", "-q:a", "9", str(path)],
        check=True, capture_output=True)


def test_render_video_produces_valid_mp4(tmp_path):
    bg = tmp_path / "bg.mp4"; _make_bg(bg)
    mp3 = tmp_path / "n.mp3"; _make_silent_mp3(mp3)
    out = tmp_path / "clip.mp4"
    words = [
        {"word": "New", "start": 0.0, "end": 0.4},
        {"word": "research", "start": 0.4, "end": 0.9},
        {"word": "on", "start": 0.9, "end": 1.1},
        {"word": "muscle.", "start": 1.1, "end": 1.6},
    ]
    dur = render.render_video("Test title for a paper", words, mp3, bg, out)
    assert out.exists() and out.stat().st_size > 0
    assert dur >= 1.6
    # the output has a video stream
    codec = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_name", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True).stdout.strip()
    assert codec == "h264"
```

Note: `render_video`'s signature has `rng` optional (`rng=None` → `random.Random()`), so the test omits it. Confirm AITA's default is `rng: random.Random | None = None`; it is.

- [ ] **Step 7: Install render deps and run the smoke test**

```bash
"$PY" -m pip install --quiet opencv-python-headless numpy pillow
cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_render_smoke.py -v
```
Expected: 1 passed. (If `cv2` import fails under headless, install `opencv-python` instead.)

- [ ] **Step 8: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): branded render (green highlight, disclaimer, end card) + smoke test"
```

---

## Task 7: `pipeline.py` — render-once-weekly, promote-daily drip

**Files:**
- Create: `MuscleOnGLPPipeline/pipeline.py`
- Test: `MuscleOnGLPPipeline/tests/test_pipeline_logic.py`

The two pure pieces — `daily_cap` and the promote/reconcile logic — are unit-tested with tmp dirs and a monkeypatched renderer. `main()` wires them to `fetch_roundup` + `narrate` + `render`.

- [ ] **Step 1: Write the failing test** `tests/test_pipeline_logic.py`

```python
import datetime
import json
from pathlib import Path

import pipeline


def test_daily_cap_drains_before_next_monday():
    # Monday 2026-07-13: 7 post-days until next Monday; 11 videos -> ceil(11/7)=2
    monday = datetime.date(2026, 7, 13)
    assert pipeline.daily_cap(11, monday) == 2
    # Saturday: 2 post-days left (Sat, Sun); 3 videos -> ceil(3/2)=2
    saturday = datetime.date(2026, 7, 18)
    assert pipeline.daily_cap(3, saturday) == 2
    # light week: 2 videos on Monday -> 1/day
    assert pipeline.daily_cap(2, monday) == 1
    # never zero, never more than the cap
    assert pipeline.daily_cap(0, monday) == 0
    assert pipeline.daily_cap(100, monday) == pipeline.DAILY_CAP_MAX


def test_promote_builds_today_dated_queue(tmp_path, monkeypatch):
    out = tmp_path / "output"; out.mkdir()
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", out)
    monkeypatch.setattr(pipeline, "BACKLOG", out / "backlog.json")
    monkeypatch.setattr(pipeline, "QUEUE", out / "post_queue.json")
    # a backlog of 4 unposted entries whose files exist
    entries = []
    for i in range(4):
        (out / f"mus_x_p{i}_split_screen.mp4").write_bytes(b"x")
        entries.append({"id": f"mus_x_p{i}", "title": f"P{i}", "score": 10 - i,
                        "split_screen": f"mus_x_p{i}_split_screen.mp4",
                        "description": "cap", "hashtags": ["glp1"],
                        "duration": 30.0, "posted": False})
    (out / "backlog.json").write_text(json.dumps(
        {"slug": "2026-07-13", "entries": entries}))
    today = datetime.date(2026, 7, 13)
    n = pipeline.promote_today(today, cap=2)
    assert n == 2
    q = json.loads((out / "post_queue.json").read_text())
    assert q["date"] == today.isoformat()
    assert q["posted"] is False and q["posted_ids"] == []
    # highest score first
    assert [c["id"] for c in q["candidates"]] == ["mus_x_p0", "mus_x_p1"]


def test_reconcile_marks_posted_from_queue(tmp_path, monkeypatch):
    out = tmp_path / "output"; out.mkdir()
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", out)
    monkeypatch.setattr(pipeline, "BACKLOG", out / "backlog.json")
    monkeypatch.setattr(pipeline, "QUEUE", out / "post_queue.json")
    entries = [{"id": "mus_x_p0", "posted": False, "split_screen": "a.mp4",
                "title": "t", "score": 1, "description": "c", "hashtags": [],
                "duration": 1.0}]
    (out / "backlog.json").write_text(json.dumps(
        {"slug": "s", "entries": entries}))
    (out / "post_queue.json").write_text(json.dumps(
        {"date": "2026-07-13", "posted": True,
         "posted_ids": ["mus_x_p0"], "candidates": [{"id": "mus_x_p0"}]}))
    pipeline.reconcile_backlog()
    bl = json.loads((out / "backlog.json").read_text())
    assert bl["entries"][0]["posted"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_pipeline_logic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline'`.

- [ ] **Step 3: Implement** `pipeline.py`

```python
#!/usr/bin/env python3
"""MuscleOnGLP TikTok orchestrator: render-once-weekly + promote-daily.

The shared uploader only posts a queue dated today, so rendering (once per
roundup) is separated from posting (a daily drip):

  main():
    roundup = fetch_latest_roundup()
    if roundup.slug is new  -> render every paper + the roundup video into
                               output/ and write backlog.json (fresh week
                               supersedes any still-unposted leftovers)
    reconcile_backlog()     -> fold yesterday's posted queue into backlog.json
    if today's queue exists -> stop (idempotent)
    else promote_today()    -> write next DAILY_CAP unposted entries into a
                               today-dated post_queue.json for the uploader
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import random
from math import ceil
from pathlib import Path

ROOT = Path(os.environ.get("TIKTOK_PIPELINE_ROOT") or Path(__file__).parent)
OUTPUT_DIR = ROOT / "output"
BACKLOG = OUTPUT_DIR / "backlog.json"
QUEUE = OUTPUT_DIR / "post_queue.json"
BG_DIR = ROOT / "backgrounds"
VOICE = os.environ.get("MUSCLEONGLP_VOICE", "en-US-JennyNeural")

DAILY_CAP_MAX = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("muscleonglp").info


def daily_cap(n_unposted: int, today: datetime.date) -> int:
    """How many to post today so the backlog drains before next Monday's
    roundup. 0 when nothing is unposted; capped at DAILY_CAP_MAX."""
    if n_unposted <= 0:
        return 0
    days_until_monday = (7 - today.weekday()) % 7 or 7  # today..(next Mon - 1)
    return min(DAILY_CAP_MAX, max(1, ceil(n_unposted / days_until_monday)))


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def reconcile_backlog() -> None:
    """Mark backlog entries posted using the current queue's posted_ids."""
    bl = _load(BACKLOG)
    q = _load(QUEUE)
    if not bl or not q:
        return
    posted = set(q.get("posted_ids", []))
    if q.get("posted"):
        posted |= {c.get("id") for c in q.get("candidates", [])}
    changed = False
    for e in bl["entries"]:
        if e["id"] in posted and not e["posted"]:
            e["posted"] = True
            changed = True
    if changed:
        BACKLOG.write_text(json.dumps(bl, indent=2))


def promote_today(today: datetime.date, cap: int | None = None) -> int:
    """Write the next `cap` unposted backlog entries into a today-dated queue.
    Returns the number promoted."""
    bl = _load(BACKLOG)
    if not bl:
        return 0
    unposted = [e for e in bl["entries"]
                if not e["posted"] and (OUTPUT_DIR / e["split_screen"]).exists()]
    if cap is None:
        cap = daily_cap(len(unposted), today)
    if cap <= 0 or not unposted:
        return 0
    chosen = sorted(unposted, key=lambda e: e["score"], reverse=True)[:cap]
    queue = {
        "date": today.isoformat(),
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "posted": False,
        "posted_ids": [],
        "candidates": [{k: e[k] for k in
                        ("id", "title", "score", "split_screen",
                         "description", "hashtags", "duration")} for e in chosen],
    }
    QUEUE.write_text(json.dumps(queue, indent=2))
    return len(chosen)


def _render_entry(clip_id: str, spoken: str, banner: str, rng) -> dict:
    """Narrate + render one clip into OUTPUT_DIR; return a backlog entry."""
    from narrate import narrate
    from render import render_video
    import captions

    bgs = sorted(BG_DIR.glob("*.mp4"))
    if not bgs:
        raise RuntimeError(f"no backgrounds in {BG_DIR}")
    bg = bgs[rng.randrange(len(bgs))]
    mp3 = OUTPUT_DIR / f"{clip_id}_narration.mp3"
    mp4 = OUTPUT_DIR / f"{clip_id}_split_screen.mp4"
    words = narrate(spoken, VOICE, mp3)
    dur = render_video(banner, words, mp3, bg, mp4, rng)
    mp3.unlink(missing_ok=True)
    kind = "roundup" if clip_id.endswith("_roundup") else "paper"
    caption, tags = captions.build_caption(kind=kind, title=banner, rng=rng)
    return {"id": clip_id, "title": banner, "score": 0,
            "split_screen": mp4.name, "description": caption,
            "hashtags": tags, "duration": round(dur, 1), "posted": False}


def render_roundup(roundup, rng: random.Random) -> list[dict]:
    """Render every paper + the weekly roundup video; return backlog entries.
    Papers score highest→first in document order; the roundup posts last."""
    import script
    entries: list[dict] = []
    n = len(roundup.papers)
    for i, paper in enumerate(roundup.papers, start=1):
        spoken, banner = script.paper_script(paper)
        try:
            e = _render_entry(f"mus_{roundup.slug}_p{i}", spoken, banner, rng)
        except Exception as exc:                       # skip one bad paper
            log(f"  render failed for paper {i}: {exc}")
            continue
        e["score"] = (n - i) + 1                        # p1 highest, then p2...
        entries.append(e)
    spoken, banner = script.roundup_script(roundup)
    try:
        e = _render_entry(f"mus_{roundup.slug}_roundup", spoken, banner, rng)
        e["score"] = 0                                  # roundup posts last
        entries.append(e)
    except Exception as exc:
        log(f"  render failed for roundup video: {exc}")
    return entries


def main() -> int:
    from fetch_roundup import fetch_latest_roundup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()

    roundup = fetch_latest_roundup()
    if roundup is None or not roundup.papers:
        log("no roundup available — nothing to do")
        return 0

    bl = _load(BACKLOG)
    # 1. New roundup? render once (superseding last week's leftovers).
    if not bl or bl.get("slug") != roundup.slug:
        for f in OUTPUT_DIR.glob("mus_*"):
            f.unlink(missing_ok=True)
        rng = random.Random()
        entries = render_roundup(roundup, rng)
        if not entries:
            log("render produced no videos")
            return 1
        BACKLOG.write_text(json.dumps(
            {"slug": roundup.slug,
             "generated": datetime.datetime.now().isoformat(timespec="seconds"),
             "entries": entries}, indent=2))
        # a brand-new week starts a fresh queue; drop the stale one
        QUEUE.unlink(missing_ok=True)
        log(f"rendered {len(entries)} video(s) for {roundup.slug}")

    # 2. Fold yesterday's posted results into the backlog.
    reconcile_backlog()

    # 3. Idempotent: today's queue already built?
    q = _load(QUEUE)
    if q and q.get("date") == today.isoformat():
        log("today's queue already exists — nothing to promote")
        return 0

    # 4. Promote today's drip.
    n = promote_today(today)
    log(f"promoted {n} video(s) into today's queue" if n
        else "backlog drained — quiet until next roundup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify the logic tests pass**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests/test_pipeline_logic.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full test suite**

Run: `cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline" && "$PY" -m pytest tests -v`
Expected: all tests pass (fetch_roundup 3, script 3, captions 2, pipeline 3, render smoke 1).

- [ ] **Step 6: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): drip orchestrator (render-weekly, promote-daily) + tests"
```

---

## Task 8: `run_daily.sh` + launchd job

**Files:**
- Create: `MuscleOnGLPPipeline/run_daily.sh`
- Create: `MuscleOnGLPPipeline/com.purplelink.muscleonglp-tiktok.plist`

Clone of AITA's runner, pointed at this pipeline + its own Chrome profile. Only differences from AITA: `PROJECT`, `TIKTOK_PROFILE_DIR`, and no Reddit/FB env.

- [ ] **Step 1: Write `run_daily.sh`**

```bash
#!/bin/bash
# MuscleOnGLP TikTok runner — idempotent (mirrors AITAPipeline/run_daily.sh).
# launchd runs this on a short interval; pipeline.py decides what (if anything)
# needs rendering/promoting today, then tiktok_upload.py posts the day's queue.
PARENT="/Volumes/Extreme SSD/TikTokPipeline"
PROJECT="$PARENT/MuscleOnGLPPipeline"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$PROJECT/pipeline_launchd.log"
ACTIVE_START=${PIPELINE_START_HOUR:-9}
ACTIVE_END=${PIPELINE_END_HOUR:-21}

export TIKTOK_PIPELINE_ROOT="$PROJECT"
export TIKTOK_PROFILE_DIR="$HOME/.tiktok_pipeline/chrome-profile-muscleonglp"
export TIKTOK_HEADLESS=1

notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"MuscleOnGLP Pipeline\"" 2>/dev/null; }

[ -d "$PROJECT" ] && [ -f "$PROJECT/pipeline.py" ] || exit 0

HOUR=$((10#$(/bin/date +%H)))
if [ "$HOUR" -lt "$ACTIVE_START" ] || [ "$HOUR" -ge "$ACTIVE_END" ]; then exit 0; fi

LOCK="$PROJECT/.run_daily.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then exit 0; fi
    rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
fi
echo $$ > "$LOCK/pid"; trap 'rm -rf "$LOCK"' EXIT
cd "$PROJECT" || exit 0

echo "" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] MuscleOnGLP run" >> "$LOG"
"$PYTHON" "$PROJECT/pipeline.py" >> "$LOG" 2>&1 || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] render/promote failed — retry next wake" >> "$LOG"; exit 0; }

"$PYTHON" "$PARENT/tiktok_upload.py" >> "$LOG" 2>&1
case $? in
  0) notify "Posted a MuscleOnGLP video to TikTok"; echo "[$(date '+%Y-%m-%d %H:%M:%S')] upload OK" >> "$LOG" ;;
  1) echo "[$(date '+%Y-%m-%d %H:%M:%S')] upload: nothing pending" >> "$LOG" ;;
  2) notify "MuscleOnGLP TikTok session expired — run tiktok_login.py"; echo "[$(date '+%Y-%m-%d %H:%M:%S')] upload: SESSION EXPIRED" >> "$LOG" ;;
  *) echo "[$(date '+%Y-%m-%d %H:%M:%S')] upload: some failed — retry next wake" >> "$LOG" ;;
esac

for dir in "Default/IndexedDB" "Default/Cache" "Default/Code Cache" "Default/GPUCache"; do
    rm -rf "$TIKTOK_PROFILE_DIR/$dir" 2>/dev/null
done
exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/run_daily.sh"
```

- [ ] **Step 3: Write the launchd plist** `com.purplelink.muscleonglp-tiktok.plist` (runs every 30 min; the script's own active-hours + idempotency guards handle the rest).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.purplelink.muscleonglp-tiktok</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/run_daily.sh</string>
    </array>
    <key>StartInterval</key><integer>1800</integer>
    <key>StandardOutPath</key><string>/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/launchd.out.log</string>
    <key>StandardErrorPath</key><string>/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/launchd.err.log</string>
  </dict>
</plist>
```

- [ ] **Step 4: Verify the runner is a no-op outside active hours / with no roundup** (dry check — does not post):

```bash
cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline"
TIKTOK_PIPELINE_ROOT="$PWD" "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" pipeline.py
```
Expected: logs either "no roundup available" or a render/promote line; exits 0; writes no `post_queue.json` unless a real roundup + backgrounds exist.

- [ ] **Step 5: Commit**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "feat(muscleonglp-tiktok): launchd runner + plist"
```

> **Manual load step (Ben, once, NOT part of automated execution):**
> `cp "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/com.purplelink.muscleonglp-tiktok.plist" ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.purplelink.muscleonglp-tiktok.plist`

---

## Task 9: Backgrounds + README (manual asset step)

**Files:**
- Create: `MuscleOnGLPPipeline/README.md`
- Add: `MuscleOnGLPPipeline/backgrounds/*.mp4` (Ben sources)

- [ ] **Step 1: Write `README.md`**

````markdown
# MuscleOnGLP TikTok Pipeline

Faceless TikTok pipeline: weekly research roundup → per-paper + roundup videos,
auto-posted at a daily drip. Local-only (edge-tts + ffmpeg + Playwright uploader).

## One-time setup
1. Create the MuscleOnGLP TikTok account (manual).
2. Log in once:
   `TIKTOK_PROFILE_DIR="$HOME/.tiktok_pipeline/chrome-profile-muscleonglp" python3 ../tiktok_login.py`
3. Set the account bio link to `getmuscleonglp.com`.
4. Put 3-6 vertical (1080x1920) CC0 gym/fitness clips in `backgrounds/`.
   Sources: pexels.com/videos, pixabay.com/videos, mixkit.co — verify each
   licence permits commercial use with no attribution before adding.
5. `cp com.purplelink.muscleonglp-tiktok.plist ~/Library/LaunchAgents/ &&
    launchctl load ~/Library/LaunchAgents/com.purplelink.muscleonglp-tiktok.plist`

## Manual run
`TIKTOK_PIPELINE_ROOT="$PWD" python3 pipeline.py`   # render/promote today
`TIKTOK_PIPELINE_ROOT="$PWD" python3 ../tiktok_upload.py`  # post today's queue

## Deps
`python3 -m pip install edge_tts opencv-python numpy pillow`  (+ ffmpeg on PATH)
````

- [ ] **Step 2: Verify backgrounds presence is enforced** (the code already raises "no backgrounds in …"); document that Task 10 needs at least one clip.

- [ ] **Step 3: Commit the README**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline/README.md
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "docs(muscleonglp-tiktok): setup README"
```

---

## Task 10: End-to-end dry run (manual verification, no posting)

**Files:** none (verification only)

- [ ] **Step 1: Ensure at least one background clip exists** in `backgrounds/` (from Task 9). If none, add a placeholder solid-green clip to prove the pipeline:

```bash
cd "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline"
ffmpeg -y -f lavfi -i color=c=0x1B2420:s=1080x1920:d=15 -r 30 -pix_fmt yuv420p backgrounds/placeholder.mp4
```

- [ ] **Step 2: Run the pipeline against the real latest roundup** (renders; does NOT post — posting is a separate uploader call):

```bash
TIKTOK_PIPELINE_ROOT="$PWD" "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" pipeline.py
```
Expected: `rendered N video(s) for <slug>` then `promoted K video(s) into today's queue`; `output/backlog.json` and `output/post_queue.json` exist; `output/mus_*_split_screen.mp4` files exist.

- [ ] **Step 3: Eyeball one paper video and the roundup video**

```bash
open "/Volumes/Extreme SSD/TikTokPipeline/MuscleOnGLPPipeline/output/"
```
Check: captions sync to the voice, active word is brand-green, title banner correct, disclaimer footer legible throughout, brand-green end card with "getmuscleonglp.com / link in bio" on the last ~2s, drug names pronounced acceptably.

- [ ] **Step 4: Validate the queue matches the uploader contract**

```bash
TIKTOK_PIPELINE_ROOT="$PWD" "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" ../post_helper.py status
```
Expected: `PENDING: K/… clip(s) to post → …` (exit 0), proving `post_helper` reads the queue and finds the files.

- [ ] **Step 5: (Ben, when ready) first real post** — with the account logged in (Task 8 manual step), run the uploader once headed to watch it work:

```bash
cd "/Volumes/Extreme SSD/TikTokPipeline"
TIKTOK_PIPELINE_ROOT="$PWD/MuscleOnGLPPipeline" \
TIKTOK_PROFILE_DIR="$HOME/.tiktok_pipeline/chrome-profile-muscleonglp" \
TIKTOK_HEADLESS=0 "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" tiktok_upload.py
```
Expected: the top-scored clip uploads to the MuscleOnGLP account. After confirming, the launchd job handles subsequent days headless.

- [ ] **Step 6: Commit any fixture/asset updates**

```bash
git -C "/Volumes/Extreme SSD/TikTokPipeline" add MuscleOnGLPPipeline
git -C "/Volumes/Extreme SSD/TikTokPipeline" commit -m "chore(muscleonglp-tiktok): end-to-end dry run verified" || true
```

---

## Self-review notes

- **Spec coverage:** fetch_roundup (Task 2), script + spoken-form (Task 3), captions (Task 4), narrate edge-tts (Task 5), branded render — green highlight/disclaimer/end card/gym b-roll (Task 6), render-once-weekly + promote-daily drip with `DAILY_CAP` + fresh-week-supersedes (Task 7), run_daily.sh + launchd + new Chrome profile (Task 8), b-roll sourcing + one-time manual setup (Task 9), end-to-end + first post (Task 10). All spec sections map to a task.
- **Queue contract:** candidates use `split_screen` (video filename), `description` (caption), `title`, `score`, `id`; files live in `output/` and are named `<id>_*` for cleanup — matches the verified shared-uploader/post_helper contract.
- **Health-safety:** disclaimer is baked into both the spoken script (Task 3), the on-screen footer (Task 6), and the caption text (Task 4); link stays in bio (no auto-comment).
- **Out of scope (unchanged):** no edits to shared `tiktok_upload.py`/`post_helper.py`; no avatar; no evergreen backfill; no cross-post.
```
