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

## Rotation: ending a broadcast every 11 hours, almost seamlessly

YouTube only saves a replay of a live stream shorter than 12 hours (a stream can run longer, it just is not archived), so the
stream rotates its broadcast every 11 hours and each one becomes a replay. The rotation used to go silent for ten minutes and
wait for YouTube to notice. Now `broadcast.end_current` ends the live broadcast through the API at once, the pipeline restarts
after 5 seconds, and the keeper opens the next broadcast, so the gap is about 20 seconds. If the API call fails the stream falls
back to the old ten-minute wait. `--rotate-hours 0` turns rotation off entirely (one endless broadcast, no replays);
`--rotate-gap N` forces a fixed gap.
