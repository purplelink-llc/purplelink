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
3. Run `ops/run_stream.sh`, or install the launchd or systemd file so it starts at boot and restarts itself. On macOS, launchd agents are not allowed to run files on an external volume (the job fails with "Operation not permitted"), so run it from a copy in the home folder: `rsync -a --exclude out --exclude out2 tools/chiptune-radio/ ~/chiptune-radio/` and point the plist at `~/chiptune-radio/ops/run_stream.sh`. After changing code, rsync again and `launchctl kickstart -k gui/$(id -u)/com.purplelink.chiptune-radio`.
4. In the video description, link purplelink.llc with campaign tags so the dashboard can attribute visits, for example `?utm_source=youtube&utm_medium=stream&utm_campaign=chiptune-radio`.

## What it costs to run (measured on this Mac, file mode)

- About a third of one CPU core on average over 12 minutes of stream, including rendering the next track. A 2 vCPU, 2 GB virtual server is enough.
- Rendering a track peaks at a few hundred MB, so it runs in a short-lived worker process that returns the memory; the main process stays small.
- Video averaged about 0.6 Mbps (pixel art compresses well), so roughly 270 MB an hour, about 200 GB a month, plus the audio.
- Loudness about -15.7 LUFS integrated, true peak about -3 dBFS.

## Not built

A viewer chat, track requests, a second scene, sound effects from the rain, and a hook that tells the dashboard how many people are watching.
