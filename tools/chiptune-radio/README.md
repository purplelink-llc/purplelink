# Chiptune radio

An endless 8-bit study stream: generated music plus a pixel study room, encoded by ffmpeg. No audio or image files are loaded from
anywhere, so there is nothing to license.

| File | What it does |
|---|---|
| `chiptune.py` | One seed makes one track (about 2.5 minutes). Chords by function, motifs that develop, echo, harmony, arpeggio, pad, bass, drums. |
| `radio.py` | A crossfaded mix of tracks as an MP3, plus `playlist.json`. |
| `scene.py` | The pixel room at 320x180: day and night cycle, rain, cat, lamp, steam, a focus timer that follows the clock (:00 to :25 focus, :25 to :30 break), now playing, the site name. |
| `stream.py` | The 24/7 loop: audio and video threads into ffmpeg, restart with back-off, a test mode that writes a file. |
| `qa.py`, `test_radio.py` | Checks. `python3.12 -m pytest -q test_radio.py` takes about 8 seconds. |
| `longform.py`, `longform_pub.py`, `themes/`, `ambience.py`, `sounds.py`, `keywords.py`, `seo_review.py`, `px.py` | Finished, fixed-length ambient videos for uploading (see Long-form videos below). `python3.12 -m pytest -q test_longform.py` takes a couple of minutes. |
| `ops/` | A run script and launchd and systemd service files. |

## Try it without going live

    python3.12 stream.py --out test.mp4 --seconds 60          # a 60-second file, about 6 seconds to make
    python3.12 stream.py --out hls:preview --seconds 120      # local HLS, paced in real time

## Going live (needs you)

Nothing here posts anywhere on its own. To start a real stream:

1. In YouTube Studio, create a live stream and copy its stream URL and key. Check YouTube's current rules for repetitive or automated
   content and for how to label generated music before you start; I have not verified them.
2. Put `STREAM_URL=rtmp://a.rtmp.youtube.com/live2/<your key>` in `~/.config/purplelink/stream.env` (`chmod 600`). The key is never printed.
3. Run `ops/run_stream.sh`, or install the launchd or systemd file so it starts at boot and restarts itself.
4. In the video description, link purplelink.llc with campaign tags so the dashboard can attribute visits, for example `?utm_source=youtube&utm_medium=stream&utm_campaign=chiptune-radio`.

## What it costs to run (measured on this Mac)

- Video is 1080p30 H.264 at a constant 2,500 kbps. The 320x180 scene scales by exactly 6, so every pixel is a clean square. At this bitrate the stream
  compresses essentially without loss (SSIM above 0.999 against the exact upscale).
- Encoder: about 0.65 of one CPU core and about 260 MB of memory at 1080p. The Python process adds about 6% of a core and 60 MB. Rendering a track
  peaks at a few hundred MB in a short-lived worker process that returns the memory.
- Upload: 2.5 Mbps video plus 128 kbps audio is about 1.2 GB an hour, about 29 GB a day, about 0.9 TB a month. Check a host's outbound bandwidth allowance.
- Loudness about -15.7 LUFS integrated, true peak about -3 dBFS.
- 4K: tried 3840x2160 (an exact 12x scale). YouTube refused it on this stream key ("expected resolution 1280x720" for this configuration), and
  the encoder needed about 1.3 to 2 cores and 1 to 1.7 GB. A 4K ingest needs a stream key created for 2160p in YouTube Studio, and YouTube recommends
  13 to 34 Mbps for 4K, so a warning about low bitrate is expected at 2,500 kbps. Set `VIDEO_SIZE` in `stream.py` to try it.

## Not built

A viewer chat, track requests, a second scene, sound effects from the rain, and a hook that tells the dashboard how many people are watching.

## Running it off the Mac (VPS)

The stream needs about one CPU core (ffmpeg at about 80% plus short render bursts) and under 1.5 GB of memory, so a 2 vCPU, 4 GB VPS
is enough (Hetzner CX22 or CAX11, about 4 to 5 euro a month; any 2 vCPU Linux host works). `Dockerfile` and `docker-compose.yml` run it with
`restart: always`, so Docker brings it back after a crash or a reboot. `ops/vps-setup.sh` has the one-time steps. The RTMP URL with the key
goes in `stream.env` on the server only (git-ignored, chmod 600). Only one machine may stream to a key at a time: stop the Mac agent first
(`launchctl bootout gui/$(id -u)/com.purplelink.chiptune-radio`) before starting the server.

Each broadcast is pinned to one era so its replay can carry an honest title: 16-bit, 8-bit, synth, then an all-era mix, repeating. The counter
lives in `/state/era` (a Docker volume) so a deploy does not repeat an era. `--era mix` (or any single era) overrides the cycle.

## Keeping a broadcast open (`broadcast.py`)

The stream goes silent for ten minutes every 11 hours so YouTube ends and archives the broadcast, then resumes.
It used to rely on YouTube to open the next broadcast on its own. On 2026-10-06 YouTube did not: the key stayed `active`
and `good` for hours with no live video. `broadcast.py` now makes sure one broadcast is open on the stream key: right after
each broadcast starts, again at 2 and 10 minutes, then hourly, it creates and binds a new one (cloned from the newest finished
broadcast, with the era in the title) if none is open.

It needs a token for the channel that owns the stream, scope `youtube.force-ssl`, as the JSON text on one line in `stream.env`:
`YT_LIVE_TOKEN_JSON={...}`. Without it the stream runs as before and the log says "broadcast keeper off". Both lines are secrets.
`python3.12 -m pytest -q test_broadcast.py` checks the logic against a fake service.

## Rotation: off by default, one endless broadcast

The stream runs as a single YouTube broadcast with no scheduled end (decided 2026-10-07): one permanent video address, likes and
chat that keep building, and nobody dropped mid-session. The cost is no replays: YouTube only saves a replay of a live stream shorter
than 12 hours, and says a longer one "might not be captured at all". A restart (a deploy, a crash) that reconnects within about
half a minute keeps the same broadcast; a longer gap makes YouTube end it, and `broadcast.py` opens a fresh one within seconds.

Rotation is still built in and tested if you want it back, set in `stream.env` or on the command line:

| Setting | What it does |
|---|---|
| `STREAM_ROTATE_AT=03:00` (`--rotate-at`), `STREAM_TZ=America/New_York` | end the broadcast every day at that local time (daylight saving handled); no replays |
| `STREAM_ROTATE_HOURS=11` (`--rotate-hours`) | end it every 11 hours so each becomes a replay |
| `docker compose kill -s USR1 radio` | rotate right now, once |

A rotation ends the old broadcast through the API (`broadcast.end_current`), restarts the pipeline 5 seconds later and has the keeper
open the next one, so the gap is about 40 seconds (a rehearsal on 2026-10-07 measured 42 s); if that API call fails it falls back to
waiting 10 minutes for YouTube to end it. A minute before a scheduled rotation the stream posts one chat message with the channel's
permanent link, `https://www.youtube.com/channel/UCUv28P5SUzT4RLQOmi3EK8w/live`, which is the address to share: it always opens
whatever is live.

## The room: HUD and events

- **Sharp text.** `Scene.frame_hd` enlarges the 320x180 scene exactly 6x in Python and draws the world clocks (LA, NYC, London,
  Delhi, Tokyo, Sydney, with a sun or moon for day or night there), the Pomodoro timer, now-playing, the link and the like /
  subscribe nudge at 1920x1080 with `pixfont.py`, a 5x7 pixel font made in code. The pipe to ffmpeg carries 1080p frames.
- **Events.** `critters.py` cuts the wall clock into 4 minute slots and picks one event (or none) per slot from a seeded
  generator, so the same minute shows the same event after any restart: the cat wakes, stretches, washes, yawns, watches the
  window and goes back to sleep; a blonde English Labrador walks in, sits, lies down and leaves (about two minutes); a robin
  lands on the sill by day; the robot vacuum crosses the floor; a shooting star at night; a hot-air balloon by day; lightning in
  the rain. At the start of every break the person stretches their arms up. Weights and lengths are the `EVENTS` table.
- Cost: about 11% more CPU than the old 320x180 pipe at the same bitrate (measured on a 30 s render).

## Staying connected

- **Auto-stop is off.** YouTube's `enableAutoStop` ends a broadcast by itself when the encoder goes quiet for a while; on 2026-10-09 a
  network stall of about two minutes did that and the next broadcast got a new link. `broadcast.py` creates broadcasts with it off and
  turns it off on any open broadcast it finds, so a dropped connection pauses the picture and nothing more. The broadcast still has
  to be ended by hand, or by `end_current`.
- **Network record.** `netwatch.py` probes YouTube's ingest host once a minute (DNS, TCP connect, and the container's TCP
  retransmit counters), logs only failed or slow probes plus an hourly summary, and prints the last five minutes the moment the pipeline stops
  ("network before the stop: ..."). That line is how to tell a network problem from YouTube closing the connection.
- **Image contents.** Every module `stream.py` imports must be on the Dockerfile's COPY line; a test checks it, because a missing
  file crash-loops the container.

## Long-form videos (uploaded, not live)

The same generators make finished videos of 1 to 2 hours in several themes. Nothing is uploaded by this code.

    python3.12 longform.py --theme campfire --hours 2 --out campfire-2h.mp4
    python3.12 longform.py --theme campfire --hours 1 --no-music --out campfire-ambience-1h.mp4     # fire, wind and crickets only
    python3.12 longform.py --theme study --hours 2 --pomodoro 25/5 --out study-2h.mp4               # study theme only
    python3.12 longform.py --theme winter --preview-frame 1800 --out frame.png                       # one 1080p frame
    python3.12 longform_pub.py thumb --theme winter --hours 2 --out winter-thumb.jpg                 # 1280x720 JPEG
    python3.12 longform_pub.py meta  --theme winter --hours 2 --slug winter-2h --out winter-2h.json  # title, description, tags, disclosure
    python3.12 longform_pub.py verify --video winter-2h.mp4 --frames-dir frames/                    # ffprobe, LUFS, true peak, silence, 4 frames

    python3.12 longform.py --theme campfire --hours 10 --loop-min 20 --sound brown --dark 300 --out campfire-brown-10h.mp4   # brown noise, dims to black after 5 min
    python3.12 keywords.py --refresh                                     # YouTube autocomplete research, cached weekly; --show brown lists the ranked phrases
    python3.12 seo_review.py stats.csv                                   # what to retitle and which theme x sound to make next, from exported stats

Sounds (`--sound`, default `chiptune`): `lofi`, `brown`, `pink`, `white`, `binaural-alpha` (10 Hz), `binaural-theta` (6 Hz), `binaural-delta` (2 Hz), `synth`, `rain`,
`thunderstorm`, `fireplace`, `ocean`, `wind`, `fan`, `airplane`. They live in `sounds.py`, are synthesised in code, are mixed with the theme's bed unless `--no-bed`, and
each masters to its own loudness (noise and binaural -20 LUFS, synth -18, lofi -16, chiptune -14); `verify --sound NAME` checks against it. Tones repeat exactly once per
loop and are added after the loop crossfade, so a binaural beat is exact across the seam. `--dark SECONDS` dims the picture to near black and repeats a black clip. See
docs/products/ambient-channel-plan.md for the keyword method, the metadata rules and the review loop.

Output is 1920x1080, 30 fps H.264, AAC 192 kbps, -14 LUFS integrated, true peak under -1 dBTP, faststart. Themes: `campfire`, `halloween`, `winter`, `study`.
Run long renders with `nice -n 10`, at most two at once; a 2 hour video takes a few hours on a busy Mac (about 40 CPU-minutes of drawing and 100 of x264, plus
about 12 CPU-minutes of music). Work files go in `<out>.work/` and are removed at the end; put the output outside the repo (the videos are gigabytes).

- **Music.** `plan_tracks` picks seeds one after another. A track is skipped if it repeats the previous key or jumps tempo by more than 8 BPM, the mood
  wanders slowly between the theme's low and high settings (about 45 minutes a wave), and tracks overlap by a 6 second crossfade, so there is no seam. A theme
  chooses the modes (`chiptune.plan(..., mode_weights=)`), the eras and the instruments. The last 8 seconds fade out; the picture fades 5 seconds.
- **Ambience.** `ambience.py` makes fire crackle, wind, rain, crickets, an owl and sleigh bells from noise and sine waves, in blocks that carry filter state, so there are no seams.
  The events the picture draws (an owl landing, a log settling, a gust, a sleigh) come from one list, so the sound arrives when the thing is seen.
- **Loudness.** Everything is mixed, soft-clipped and set to about -14 LUFS, then ffmpeg's `loudnorm` is run twice (measure, then linear apply) with a -2 dBTP ceiling.
- **A new theme** is one file in `themes/`: subclass `Theme`, set `name`, `label`, `thumb_lines`, `music`, `bed`, write `frame(t)` (a 320x180 image, a pure function of `t`
  apart from the flame in `px.Fire`), list its events with `schedule(...)`, and decorate it with `@register`. Add its words to `COPY` in `longform_pub.py` for the metadata.
- **Frames** are drawn in worker processes in 30 second chunks. The flame is stepped frame to frame, so a chunk starts it fresh once every 30 seconds, which looks like
  ordinary flicker. The video runs at 10 fps and every frame is shown three times, so the cadence is even.
