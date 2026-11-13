# ModernTex 3.0 launch video plan

Files: `moderntex-3-demo.json` (16:9, 74 s cut, 77.9 s with bumpers), `moderntex-3-short.json` (9:16, 23.5 s cut, 27.4 s),
`../src/moderntex3/` (composition), `../build-moderntex3.mjs` (build), `../thumbs/ab/moderntex-3.json` (thumbnails),
`../assets/moderntex3/sample-paper/` (the capture document). Menu names and shortcuts are placeholders until the app is final.

## Pipeline

Real screen captures, not synthetic frames. Remotion adds the bumpers, tag pill, caption bar, narration and end card; each
capture plays inside the scene slot. Narration comes from `narrate.py` (voice en-GB-SoniaNeural, -4%) on the scenes that have
`narration`. Scenes marked `appAudio` carry the app's own read-aloud audio (captured clip audio, unmuted); no narration there.

Capture audio. `winrec` records no audio. Record each `appAudio` clip with an app-only audio tap (ScreenCaptureKit audio for the
ModernTex process, or a loopback device set only for the capture) merged with the `winrec` video by `ffmpeg`. Never record the
Mac's whole system output. Check that no notification sound lands in the clip.

## Capture shot list (phase 2)

Window 1600x900 points for the 16:9 clips (scaled to 1920x1080 by cover-fit); 540x960 points portrait crop for the Short, taken
from a 1080x1920 window region around the editor. Light theme, default zoom, sample document
`video/assets/moderntex3/sample-paper/paper.tex` (compiles with TinyTeX; `refs.bib` beside it). Dock hidden, no other windows.
Record at 30 fps, no cursor smoothing. Use a throwaway bundle id and support folder per the test-copy rule; do not touch the real
library. The voice is the best installed macOS voice, set once before capture and named in the video description.

| Clip | Seconds | App state at start | Action to record |
|---|---|---|---|
| c01-zen-open | 5 | paper.tex open, caret in the Introduction, zen mode off | press [ZEN_SHORTCUT]; the editor fades to zen mode |
| c02-read-from-click | 12 | zen mode, introduction paragraph visible | click mid-paragraph, press [READ_ALOUD_BUTTON]; hold while 3 sentences are read and highlighted. appAudio |
| c03-pause-skip | 9 | reading in progress | [PAUSE_SHORTCUT] (pause), [SKIP_BACK_SHORTCUT], [SKIP_FORWARD_SHORTCUT], [PAUSE_SHORTCUT] (resume) |
| c04-caption-table | 11 | scroll to the figure and the results table | read through the figure caption and into the table summary. appAudio. The table summary must use only numbers in the source |
| c05-stop-resume | 7 | reading mid-section | press [STOP_SHORTCUT]; caret rests on the stopped sentence; press [READ_ALOUD_BUTTON]; it resumes there |
| c06-catch-typo | 7 | sample paragraph with the planted "the the" | read aloud over it; the doubled word is audible. appAudio |
| c07-dictate | 11 | caret at the end of a sentence in a blank line | press [DICTATION_SHORTCUT]; say the line from the narration script; text lands with capital and spacing, percent escaped |
| c08-undo | 5 | dictated text inserted | press Cmd+Z once; the whole passage disappears |
| v01-click-read | 3.5 | portrait crop, zen mode | click a paragraph, press [READ_ALOUD_BUTTON] |
| v02-read | 9 | reading in progress | hold on 2 highlighted sentences. appAudio |
| v03-dictate | 6 | caret on a new line | [DICTATION_SHORTCUT] and say one sentence containing "percent" |

Dictation line to speak (c07 and v03): "Accuracy rose by twelve percent comma and the sample stayed small period". Expected
source: `Accuracy rose by twelve \% , and the sample stayed small.` Ben to confirm the exact output once the build exists; fix the
caption text if the app formats differently. Do not invent app behaviour in the captions: every caption maps to a claim on the
blog post.

## Narration script (demo)

1. "You have read this paragraph ten times. Listen to it instead."
2. (app audio, no narration)
3. "Pause, skip back a sentence, skip forward, and carry on."
4. (app audio)
5. "Stop, and it remembers where you were. Press again and it carries on from there."
6. (app audio)
7. "Dictation puts what you say into the source. The percent sign is escaped for you, and spoken punctuation works."
8. "One undo takes the whole passage back out."
9. "Both run on your Mac. Nothing is sent off it. ModernTex 3.0 is a free update for owners."

Check before render: "free update for owners" must match the final release terms (the blog post and changelog say the same).
Short: "Click anywhere in your LaTeX. Press one button." / "Or dictate. The characters that break a build are escaped." /
"ModernTex 3.0. Everything stays on your Mac."

## Music bed

Per the music-bed rule: an ACE-Step SFT take, cover re-render at shift 3, cut to the action, -22 LUFS under the voice, ducked
under narration and under app audio. ACE-Step uses about 15 GB per run, so run one at a time and check `memory_pressure`.
Prompt: calm piano and soft pad, 84 bpm, no vocals, no build or drop; keep the read-aloud voice intelligible. Fallback if ACE-Step
is unavailable: `addTrendBed` (the build script calls it unless `--no-bed`). Mix with `mixbed.py` for a custom bed.

## YouTube

Channel `purplelink` (kinds `product`, `howto-short` are allowed by `scripts/yt-channels.json`).

Title (demo): `ModernTex 3.0: hear your LaTeX read aloud, and dictate into it`
Title (Short): `Proofread your LaTeX by ear (ModernTex 3.0) #shorts`

Descriptions are files: `moderntex-3-desc-demo.txt` and `moderntex-3-desc-short.txt` (utm links made with `hub.py utm`,
assets `moderntex-3-demo-16x9` and `moderntex-3-short-9x16`, channel `youtube`; the content suffix carries the make date 261112,
regenerate if that matters). Chapter stamps assume the 1.8 s opening bumper and the current scene durations; re-check them against the
rendered cut (each chapter is over 10 s, YouTube's minimum). `[VOICE_NAME]` in the demo description must be filled before upload.

Tags: ModernTex, LaTeX editor, LaTeX Mac, read aloud, text to speech, proofreading, dictation, speech to text, academic writing,
Overleaf alternative, manuscript, PhD, thesis writing. Category 28. The dry run shows `containsSyntheticMedia: False` by default. The narration is TTS; Ben decides whether to declare it before the flip.

## Thumbnails (A/B for Test & Compare, 3 variants, `thumbs/ab/moderntex-3.json`)

- A, product: existing editor screenshot (`site/assets/moderntex-screens/01-editor-clean.webp`) as an interim, headline
  "Click. Listen. Fix." Phase 2 should swap in a crop of c02 (zen mode, one sentence highlighted) once it exists.
- B, text: "Proofread LaTeX by ear", "2 new tools: read aloud and dictation". No capture needed.
- C, text: "Dictate into LaTeX", "5 symbols, escaped for you: % & _ $ #". No capture needed.

Render: `node video/build-thumbs.mjs --spec thumbs/ab/moderntex-3.json` (rendered once as a check; looks right). Upload A first; `yt-abtest.py start` after the
video is public.

## Phase 2 run order

Work from the worktree (or the merged branch): the build script is not on `main` until the PR merges. `video/node_modules` is a
symlink to the main checkout's, git-ignored.

```
set -u
cd "/Volumes/Extreme SSD/_worktrees/Purplelink LLC/moderntex-3-launch/video"
export ELEVENLABS_DISABLE=1          # local Kokoro narration, no spend
# 1. capture the 11 clips into $MT3_CLIPS (default /Volumes/Extreme SSD/PurplelinkVideos/moderntex-3/clips)
# 2. check, then render with --no-bed and mix the real bed afterwards (see Music bed); omit --no-bed to take the trend bed instead
node build-moderntex3.mjs moderntex-3-demo --check
node build-moderntex3.mjs moderntex-3-demo --no-bed
node build-moderntex3.mjs moderntex-3-short --no-bed
# 3. mix the bed (mixbed.py), watch both files once with sound; confirm read-aloud level and no notification sounds
# 4. upload PRIVATE (the Purplelink token exists; add --dry-run first)
```

Use this form for the uploads (run from the main checkout `/Volumes/Extreme SSD/Purplelink LLC`, `V` = the worktree's `video`):

```
set -u
V="/Volumes/Extreme SSD/_worktrees/Purplelink LLC/moderntex-3-launch/video"
python3 scripts/yt-api-upload.py --channel purplelink --kind product "$V/out/moderntex3/moderntex-3-demo.mp4" \
  --title "ModernTex 3.0: hear your LaTeX read aloud, and dictate into it" --description-file "$V/storyboards/moderntex-3-desc-demo.txt" \
  --tags "ModernTex,LaTeX editor,LaTeX Mac,read aloud,text to speech,proofreading,dictation,speech to text,academic writing,Overleaf alternative,manuscript,PhD,thesis writing" \
  --category 28 --privacy private
python3 scripts/yt-api-upload.py --channel purplelink --kind howto-short "$V/out/moderntex3/moderntex-3-short.mp4" \
  --title "Proofread your LaTeX by ear (ModernTex 3.0) #shorts" --description-file "$V/storyboards/moderntex-3-desc-short.txt" \
  --tags "ModernTex,LaTeX,read aloud,dictation,proofreading" --category 28 --privacy private
```
`yt-visibility.py` and `yt-abtest.py` drive the automation Chrome on port 9340 (signed in to Studio); start it first.
