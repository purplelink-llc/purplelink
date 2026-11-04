# Studio sound for Hearthside Pixels long-form videos

Status: approved v2, 2026-11-04. Written after an EGM review of v1 and built on branch `studio-sound`. Ben listened to the
A/B clips and approved this scope.

Owner decisions so far (Ben, 2026-11-04): "These don't need to be chiptune... use any synth macOS tool or drive
GarageBand"; in a multiple-choice follow-up he chose "Also GarageBand samples" and to hold the first racer render
(nightq job 29) until this sound exists. After the A/B clips he chose "B: Silverlake kit", and "Later" for a sampled
lead in B sections.

## Problem

Every long-form video's music comes from `tools/chiptune-radio/chiptune.py`. Its composer (`plan` + `compose`) is good.
Its voice engine (`render` + `voices.py`) only makes chip-style tones, so every theme sounds like chiptune. The racer
theme ("Music to Run To") should sound produced: real bass, real drums and a string bed, with synth leads on top.

## What this Mac has (checked 2026-11-04)

- Logic/GarageBand sampled instruments (`.exs`) under `/Library/Application Support/Logic/Sampler Instruments/`:
  Steinway pianos, Vintage Strat, acoustic guitar, upright and fingerstyle bass, string ensemble, brass, woodwinds.
- GarageBand Drum Machine Designer kits under `/Library/Application Support/Logic/Ultrabeat Samples/Drum Machine
  Designer/` (10 kits, 240 one-shot `.aif` files at 44.1 kHz: kicks, snares, closed and open hats, toms, crashes).
- The acoustic Drum Kit Designer kit (SoCal) is **not usable**: `AVAudioUnitSampler` refuses its `.exs` files with
  error -10868 (format not supported); they point into large "consolidated" sample files.
- GarageBand itself is not installed; the libraries came with it (`pkgutil`: `GarageBand_AppStore`,
  `MAContent10_AssetPack_*`).

## Decision

Add a **studio** voice path inside `chiptune.render()`. The composer is unchanged. For each channel a theme maps to a
sampled instrument, `render()` asks `studio.py` for a dry stereo stem and adds it to that channel's group bus, in place
of the numpy notes. Everything after the buses (kick ducking, chorus, reverb send, lowpass, highpass, `ride_level`,
normalising) runs as before, so the studio sound sits in the same mix chain.

Rejected: driving the GarageBand app (not installed, steals focus, cannot run in nightq or with the screen locked); a
smart Swift host with buses and Apple effects (the v1 design; reviewers found it duplicated the Python mix chain and
moved logic into code CI cannot test).

## Design

### 1. `aurender` (Swift, `tools/chiptune-radio/aurender/aurender.swift`, about 50 lines)

A deliberately dumb host. Input: a JSON job `{"sr", "frames", "exs", "events": [[frame, status, data1, data2], ...]}`.
It loads one `.exs` into `AVAudioUnitSampler` with disk streaming turned off (`kMusicDeviceProperty_StreamFromDisk` = 0,
so every sample is in memory; see Measured), runs `AVAudioEngine` in offline manual rendering mode in 512-frame
blocks, schedules each MIDI event at its exact frame with `scheduleMIDIEventBlock(AUEventSampleTimeImmediate + offset)`,
and writes planar float32 stereo. No effects, no mixing, no random numbers. It exits 1 with a message on a missing
file, a load failure or a render error.

Built by `studio.ensure_binary()` with `swiftc -O` into `tools/chiptune-radio/.aurender-bin` (git-ignored) when the
binary is missing or older than its source, under an `fcntl` lock so parallel workers build it once. Needs the Xcode
command line tools, which this Mac has.

### 2. `studio.py`

- `sampled_stem(exs, notes, total, latency, transpose)`: composer notes to MIDI rows, runs `aurender` with a timeout,
  then checks the output length and that it is not silent. Any failure raises; there is no fallback to the chip voices,
  so a video never ships with the wrong sound or the wrong description.
- `midi_events()`: velocity is the note's volume relative to the channel's loudest note, mapped to 30..127, so the
  sampler's velocity layers follow the composer's accents. A note that starts while the same pitch still sounds ends the
  earlier note at that frame. At one frame, note-offs sort before note-ons. Notes start `latency` frames early to cancel
  the instrument's attack delay (measured below).
- `drum_stem(kit, channel, notes, total)`: one-shot hits mixed in numpy. A closed hat chokes a ringing open hat.
- `level(stem, rms)`: scales a stem so its loud passages sit at a set RMS. The per-channel targets were measured from
  the numpy voices on the same track, so the studio mix starts from the current balance.

Drum mapping (composer channel to kit hit):

| Channel | Hit |
|---|---|
| kick | `Kick_1` |
| snare | `Snare_1`; `Snare_3` when the note is under half the channel's loudest (ghost notes) |
| hat | `Hi-Hat_1`; `Hi-Hat_Open` when the note lasts 0.18 s or more |
| tom | by `extra["pitch"]`: 95 and up `Tom_High`, 75 and up `Tom_Mid`, else `Tom_Low` |

### 3. Theme kits

A theme opts in with a `studio` dict inside `music["sound"]`; `longform.render_track` already copies `sound` onto the
track, so no signature changes. Channels not in the dict stay on the numpy voices. v1 for the racer:

| Channel | Voice |
|---|---|
| bass | Fingerstyle Electric Bass (sampled), latency 574 frames |
| pad | String Ensemble (sampled), latency 600 frames, 12 ms stereo spread |
| kick, snare, hat, tom | Drum Machine Designer kit `Silverlake GB` (Ben's pick) |
| lead, echo, harm | numpy `fm_brass` in A sections, `saw_lead` in B sections (unchanged) |
| arp | numpy `saw_pluck` / `pluck` (unchanged) |
| spark, fx risers | numpy (unchanged) |

Loud-passage RMS targets (`level`): bass 0.109, pad 0.026, kick 0.0997, snare 0.0474, hat 0.00714, tom 0.0663.

Deferred to later (Ben, 2026-11-04: "Later"): a sampled lead in B sections (Trumpets+), distorted Strat power chords, and
layering the sampled bass with the synth bass.

### 4. Metadata honesty

`longform_pub.py` says "Nothing in this video is sampled..." in the made-with paragraph and its holiday and sound
variants. For a theme with a `studio` kit that is false. The paragraph switches on whether the theme's sound has a
`studio` key:

> The music is original. A program composes every track from a random seed and plays it partly on synthesised voices
> and partly on instruments from Apple's GarageBand and Logic sound library. ... No existing music, loops or recordings
> are used.

The racer's sound line also changed from chiptune wording to "a driving octave electric bass, punchy electronic drums, a
string bed and bright brass and saw synth leads". The approved title keeps "16-Bit Racing Chiptune".

A test asserts the racer description never contains "Nothing in this video is sampled" and chip themes keep it.

### 5. Licence gate

GarageBand's licence lets its audio content be used royalty-free in your own original soundtracks for video and audio
projects, which may be broadcast and distributed; the sound files may not be distributed on their own. Monetised
YouTube videos of original compositions fit. **Gate:** before the first studio upload, re-read the current GarageBand
licence text and record the date and wording in this doc. We play notes on instruments; no Apple Loops are used.

### 6. Measured (prototype, 2026-11-04)

- Timing: three hits placed at odd frames came out with identical offsets per instrument (bass +574, trumpet
  +54 frames): zero jitter. The offset is the sample's own attack, cancelled by `latency`.
- Determinism: two renders of the same job are byte-identical, for `aurender` alone and for a whole studio track.
  This needed one fix. With the sampler's default disk streaming, the String Ensemble (long samples) came out
  differently on every run: the first notes of a fresh process lost up to 2.8 s of strings, and later notes dropped out
  at random, because the offline render outruns the streaming thread. Turning streaming off made six runs identical;
  `test_long_sampled_notes_render_the_same_every_time` fails with streaming on.
- Speed and memory: 120 s of bass renders in 2.2 s, peak RSS 99 MB. The full 82 s racer track renders in 2.3 s with
  studio voices (2.8 s all-numpy). A 2-hour video adds about two minutes per sampled channel per worker.
- Failure: a missing `.exs` exits 1 with "missing instrument"; an unsupported one exits 1 with the AV error.
- To do before rollout: one render under nightq with the screen locked, to prove `AVAudioEngine` offline mode needs no
  login-session audio.

### 7. Tests

- `test_studio.py`: `midi_events` sorting, overlap release, velocity range and latency shift; `drum_stem` hat choke and
  tom mapping; `level`. These run anywhere (no Apple library needed).
- Integration tests that call `aurender` (determinism, onset, missing-file exit) skip when `swiftc` or the Logic library
  is absent, so Linux CI stays green.
- Existing bit-identical chiptune tests prove themes without a `studio` kit are unchanged (239 pass on the prototype).
- `test_longform.py`: the racer made-with paragraph, as above.
- The stream's Docker image copies `studio.py` (the image test requires every imported module); the stream never uses
  a studio kit.

## Rollout

1. Done: Ben picked the Silverlake kit and deferred the sampled lead.
2. Finish tests and the metadata switch, add `.aurender-bin` to `.gitignore`, one locked-screen nightq test render.
3. PR, squash-merge on green.
4. Move nightq job 29 (`music-to-run-to-2h`, seed 313) from `deferred/` back to `queue/`; after verify, add it to
   `plan.json` for the next slot (about 2026-11-23 15:00 Eastern). Re-read the licence before that upload.

## Open questions

1. Content ID: factory instruments are used by many producers. Playing composed notes (never loops) keeps the risk low;
   watch the first upload's copyright check.
