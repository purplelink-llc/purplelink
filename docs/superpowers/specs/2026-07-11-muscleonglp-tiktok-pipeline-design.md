# MuscleOnGLP TikTok Pipeline — Design Spec

**Date:** 2026-07-11
**Status:** Draft for review
**Author:** Ben Ampel (with Claude)

## Goal

Automatically turn each weekly MuscleOnGLP research roundup into faceless
short-form TikTok videos — **one video per paper (2–10/week) plus one weekly
roundup video** — narrated with neural TTS, captioned word-by-word over calm
gym b-roll, and auto-posted to a dedicated MuscleOnGLP TikTok account at a
roughly-daily drip. Every video funnels to `getmuscleonglp.com` (link in bio)
to build top-of-funnel traffic for the paid guides.

This is a **top-of-funnel growth channel**, reusing content the site already
produces and vets. It does not generate new research claims.

## Guiding constraints

- **Runs locally on the M4** (no Modal, no cloud vendor, no API keys). TTS is
  free (edge-tts neural voices); rendering is local ffmpeg/OpenCV; posting is
  the existing local Playwright uploader.
- **No new hallucination surface.** Scripts are templated from the roundup's
  already-vetted `summary` + `why_it_matters` text — no LLM regeneration.
- **Health-safe.** On-screen "Educational, not medical advice" disclaimer on
  every video; scripts stay descriptive ("a study found…"), never prescriptive
  ("you should take…"); the site link lives in the bio, **not** auto-commented
  (avoids spam-pattern flags on a moderation-heavy health niche).
- **Reuse the existing framework, don't rebuild it.** MuscleOnGLP becomes a new
  sibling pipeline under `/Volumes/Extreme SSD/TikTokPipeline/`, alongside
  `AITAPipeline` and `BallSimPipeline`.

## Reused from the existing framework (unchanged)

Located at `/Volumes/Extreme SSD/TikTokPipeline/`:

- **`tiktok_upload.py`** — shared Playwright uploader. Reads
  `<pipeline>/output/post_queue.json`, posts pending candidates (highest
  `score` first) to the account whose Chrome profile is at
  `$TIKTOK_PROFILE_DIR`, marks them posted via `post_helper.py`. **Key
  invariant we must respect: it ignores any queue whose `date` != today.**
- **`post_helper.py`** — queue parsing, `pending_candidates()`, mark-posted.
- **`narrate.py`** — edge-tts synthesis with word-level `WordBoundary`
  timings. We reuse the mechanism; MuscleOnGLP gets its own domain spoken-form
  map (see `script.py`).
- **`render.py` caption engine** — 1080×1920, 30fps, ≤4-word caption chunks
  with the active word highlighted, PIL RGBA overlays alpha-composited over a
  full-screen background, silent OpenCV pass → ffmpeg h264 mux with a faint
  background audio bed. We adapt assets/branding (below).
- **`run_daily.sh` pattern** — launchd runner: idempotent, active-hours guard,
  single-instance lock, session-expiry notification.

## New package: `MuscleOnGLPPipeline/`

Sibling directory to `AITAPipeline/`. Five new/adapted modules plus assets.

### 1. `fetch_roundup.py` (replaces `fetch_aita.py`)

**Responsibility:** read the newest published roundup from the local site
checkout and return per-paper items + one roundup item. No network.

- Reads `<site>/research/index.json` (manifest) → newest slug.
- Parses `<site>/research/<slug>/index.html` for per-paper `title`, `url`,
  `meta`, `summary`, `why`. The logic is a direct port of
  `monthly_guide.roundups.parse_post_html`. Because this pipeline lives in a
  separate location (`/Volumes/Extreme SSD/TikTokPipeline/`) from the backend
  package, **vendor a copy** of the ~40-line parser into `fetch_roundup.py`
  rather than cross-repo-importing — the pipeline stays self-contained. (The
  `.rr-item` HTML markup it parses is stable, produced by the site's own
  renderer.)
- `<site>` default: `/Volumes/Extreme SSD/Purplelink LLC/muscleonglp-site`
  (override via env).
- Returns `{slug, week_label, date, papers: [RoundupPaper...], dek}`.

**Interface:** `fetch_latest_roundup(site_dir) -> Roundup | None`
(None when the manifest is missing or empty).

### 2. `script.py`

**Responsibility:** turn one paper (or the roundup) into a spoken script +
on-screen title, deterministically.

- **Per-paper script (~25–40s):** hook → finding (`summary`) → why it matters
  (`why`) → CTA + disclaimer. Example shape:
  > "New research on [drug/topic]. [summary]. Why it matters: [why].
  >  This is educational, not medical advice. Full breakdown at
  >  getmuscleonglp dot com — link in bio."
- **Roundup script (~50–70s):** dek intro → one line per paper (title + a
  one-clause takeaway drawn from `why`) → CTA + disclaimer.
- **Spoken-form map** (on-screen text keeps the originals): `GLP-1` →
  "G L P one", `GIP` → "gip", `PYY` → "P Y Y", `DXA` → "dexa", drug-name
  pronunciations (retatrutide, tirzepatide, survodutide, cagrilintide, …), `%`
  → "percent", `vs` → "versus". Extend as needed.
- Pure functions, no I/O → unit-testable.

**Interface:**
`paper_script(paper) -> (spoken_text, on_screen_title)`;
`roundup_script(roundup) -> (spoken_text, on_screen_title)`;
`spoken_form(text) -> text`.

### 3. `render.py` (adapted from AITA)

Same caption engine; MuscleOnGLP branding:

- **Highlight color** = brand green (`#34A07F` bright on the current white base;
  AITA already highlights green, so this is a constant swap).
- **Title banner** = the paper title (roundup: "This week in GLP-1 research").
- **Persistent disclaimer footer** every frame: "Educational, not medical
  advice" (small, bottom-safe area).
- **End card** (last ~2s): "getmuscleonglp.com · link in bio".
- **Background** = calm gym/fitness b-roll from `backgrounds/*.mp4` (one clip
  per video, random), faint audio bed at the existing low volume.

**Interface (unchanged from AITA):**
`render_video(title, words, mp3_path, bg_path, out_path, rng) -> duration`.

### 4. `pipeline.py` (orchestrator — render-once-weekly, promote-N-daily)

This is the one genuinely new piece of logic, needed because the shared
uploader only posts a **today-dated** queue. We therefore separate *rendering*
(weekly) from *posting* (daily drip):

- **State files** (in `output/`):
  - `backlog.json` — every rendered-but-unposted video for the current week:
    `[{id, title, score, video, description, hashtags, duration, posted:false}]`.
  - `rendered_state.json` — `{last_rendered_slug}` so we render each roundup
    exactly once.
  - `post_queue.json` — the shared uploader's today-dated working queue.

- **Daily `main()` (called by `run_daily.sh`):**
  1. `roundup = fetch_latest_roundup(site)`.
  2. **If** `roundup.slug != rendered_state.last_rendered_slug`: render all
     papers + the roundup video into `backlog/`, append entries to
     `backlog.json` (fresh week supersedes any still-unposted leftovers — they
     drop, mirroring AITA's "new day supersedes" so stale research never
     posts), set `last_rendered_slug = roundup.slug`.
  3. **Promote today's drip:** move the next `DAILY_CAP` unposted backlog
     entries into `post_queue.json` with `date = today`, `posted = false`.
     - `DAILY_CAP = max(1, ceil(remaining_unposted / days_until_next_monday))`,
       clamped to ≤ 3. This drains the week's backlog *before* the next roundup
       refills it, at a roughly-daily cadence. Light weeks (2 papers) → 1/day
       with quiet days at week's end, which is acceptable ("quiet weeks are
       quieter"; no padding, no evergreen filler in v1).
  4. The shared `tiktok_upload.py` (invoked next by `run_daily.sh`) posts the
     queue; on success, `pipeline.py` marks those backlog entries `posted`.

- **Caption/hashtag builder** (MuscleOnGLP `build_caption`, mirrors AITA's):
  HOOK (paper title / "This week in GLP-1 research") + keyword-rich DESCRIPTION
  (names the drug + muscle/lean-mass angle for SEO/GEO) + CTA ("Full breakdown
  at getmuscleonglp.com — link in bio") + tiered hashtags (broad: #Ozempic
  #Wegovy #Mounjaro #Zepbound; niche: #GLP1 #musclepreservation #leanmass
  #tirzepatide #retatrutide; rotating mid-tier). Disclaimer line included in
  the caption text too.

### 5. `run_daily.sh` + launchd plist (cloned)

- Clone AITA's `run_daily.sh`: new `PROJECT`, `TIKTOK_PROFILE_DIR=
  $HOME/.tiktok_pipeline/chrome-profile-muscleonglp`, active hours, headless.
- New launchd plist on a short `StartInterval` (matches the other pipelines),
  guarded by SSD-mounted and active-hours checks.

### Assets: `backgrounds/`

A handful of royalty-free **vertical** gym/fitness loops (training, weights,
meal prep) from CC0 sources (Pexels / Pixabay / Mixkit). Claude helps source
and organize; **Ben confirms licensing** before use. One clip chosen per video.

## Voice

Default edge-tts voice: a calm, credible neutral voice (e.g.
`en-US-EricNeural` or `en-US-JennyNeural`) at a slightly measured rate
(≈ +0–5%, calmer than AITA's +8%). Trivially swappable; final pick during the
build after an ear test.

## One-time manual setup (Ben)

1. **Create the MuscleOnGLP TikTok account** (Claude cannot create accounts).
2. **Log in once:** `TIKTOK_PROFILE_DIR="$HOME/.tiktok_pipeline/chrome-profile-muscleonglp" python3 ../tiktok_login.py`.
3. Set the bio link to `getmuscleonglp.com`.
4. Load the launchd plist.

## Data flow (summary)

```
muscleonglp-site/research/<slug>/index.html
  → fetch_roundup.parse → papers[]
  → (weekly) script.py + narrate + render → backlog/*.mp4 + backlog.json
  → (daily) promote DAILY_CAP → output/post_queue.json (date=today)
  → tiktok_upload.py (shared) → MuscleOnGLP TikTok account
  → mark posted in backlog.json
```

## Error handling

- Missing manifest/post → no-op (nothing to render), logged.
- A paper whose script is empty → skipped, others continue.
- Missing ffmpeg / no backgrounds → fail loudly with a clear message.
- Render exception for one video → skip it, continue the rest.
- Uploader session expired → existing notify path ("run tiktok_login.py").
- Re-runs are idempotent: same roundup slug never re-renders; a today-dated
  queue is not rebuilt within the same day.

## Testing

- **Unit (pure functions):** `spoken_form`, `paper_script`, `roundup_script`,
  caption chunking, `build_caption`, and the `DAILY_CAP` drain math (table of
  (backlog size, days-to-Monday) → expected cap).
- **Smoke:** render one video from a fixed fixture (short script + a tiny
  background clip) and assert a valid non-empty MP4 with an audio stream.
- **Manual A/V:** eyeball one paper video + the roundup video (voice quality,
  caption sync, disclaimer legibility, end card) before first live post.

## Out of scope (v1)

- Avatar / talking-head video (faceless only; revisit if the funnel converts).
- Auto-commenting the link (bio link only).
- Evergreen `/learn`-article backfill for quiet days.
- Cross-post to other platforms (the framework has a dormant FB path; not now).
- Any change to the shared `tiktok_upload.py` / `post_helper.py`.

## Open risks

- **Health-niche moderation:** medical content is scrutinized more than AITA.
  Mitigations: on-screen + in-caption disclaimer, descriptive-only scripts, no
  auto-comment links, calm non-sensational framing. Monitor for takedowns after
  launch; if flagged, revisit framing before scaling cadence.
- **New-account cold start:** a fresh account posting daily may see low initial
  reach; expected, not a bug.
```
