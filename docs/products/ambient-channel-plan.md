# Ambient channel plan: uploaded long-form videos

Status: draft for Ben's decision, written 2026-10-16. Nothing here has been uploaded, posted or created. No channel exists yet.

## What this is

The 24/7 chiptune study stream becomes a second, separate YouTube channel of finished, fixed-length ambient videos (1 to 2 hours each) across themes: campfire,
Halloween, winter cabin, study room with a Pomodoro timer, and more later (rain, autumn, ocean, space). Every video is made by code in
`tools/chiptune-radio/`: the music is composed from a seed, the sounds (fire, wind, crickets, rain) are synthesised, and the pixel-art scene is drawn by the
same program. Nothing is recorded, sampled or downloaded, so there is nothing to license and nothing for Content ID to match.

Renderer: `tools/chiptune-radio/longform.py`. Thumbnails, upload metadata and the finished-file check: `longform_pub.py`. Themes are one small file each in
`tools/chiptune-radio/themes/`. See the README section "Long-form videos". Rendered files live outside the repo in
`/Volumes/Extreme SSD/PurplelinkVideos/ambient/<slug>/`.

## Channel name options

I checked with web search only. The search engine does not index YouTube handles well, so **none of this proves a name is free**. Ben should type each name
into YouTube search and into the handle box when the channel is created.

| Name | Handle to try | What the search showed (2026-10-16) |
|---|---|---|
| Pixel Hearth | @pixelhearth | No channel of that name found. Results were unrelated pixel-art channels. |
| Ember Hours | @emberhours | No channel found. |
| Lantern Hours | @lanternhours | No channel found. |
| Quiet Pixels | @quietpixels | No channel found. |
| Cozy Pixel Hours | @cozypixelhours | No channel found; a different channel called "Cozy Hours" (watercolor music videos) exists, so this one is close to it. |

Notes: "Cozy" is crowded and the closest name above is the one most likely to be confused. A name with "Pixel" says what the pictures are; a name with "Hearth"
or "Ember" works for fire and winter videos but not for rain or space. Whichever name is chosen, search it for a trademark conflict before ordering anything
with it; I did not do that.

## YouTube policy check (read 2026-10-16)

I read the pages below through a summarising fetch tool, so the short quotes are from that reading. Ben, or the next session, should open each page once and
confirm the wording before the channel is built around it.

1. **Repetitive or "inauthentic" content (monetization).** On 2025-07-15 YouTube renamed "repetitious content" to "inauthentic content" in the Partner Program
   policies and said it includes content that is "repetitive or mass-produced". The page says this "has always been ineligible for monetization" and that
   "the substance of each video should be materially varied", and that channels whose videos feel "interchangeable" cannot monetize.
   Source: https://support.google.com/youtube/answer/1311392. Press coverage (TechCrunch, 2025-07-09:
   https://techcrunch.com/2025/07/09/youtube-prepares-crackdown-on-mass-produced-and-repetitive-videos-as-concern-over-ai-slop-grows) calls it a clarification
   of an existing rule, and I found no source that names AI or generated music specifically.
2. **Is generated music over a near-static picture at risk?** Yes, this is the exact shape of content the rule is aimed at, and the risk is to monetization
   (the channel can still upload and grow). Being original (no sampled material) helps with copyright, not with this rule. What the policy rewards is real difference
   between videos. This pipeline has genuine ones: a different scene and palette per theme, scene events (owl, bats, ghost, sleigh, rain, visitors), a
   day-and-night or dusk-to-dawn sky across each video, different composed music in every video (about 38 tracks of 3 minutes each, no repeats), and a different
   key, tempo and mood drift. Things that keep a channel safer: a modest cadence (not daily batches), each video's title, thumbnail and description specific to its
   theme, real variety in themes across the calendar, a few themes with more happening on screen (the study room has a working timer and a whole day cycle),
   and Shorts that are cut from real moments. Things that raise the risk: the same scene re-rendered with a new seed and a new title, large batch uploads,
   and descriptions that read as templates. Treat monetization as unproven until YouTube reviews the channel.
3. **Altered or synthetic content disclosure.** The disclosure page (https://support.google.com/youtube/answer/14328491) lists music made with generative tools
   as something creators must disclose, says a label may appear in the player or the expanded description, and says non-realistic animated content needs no disclosure.
   Our music is written by a program we wrote, not a trained model, and nothing imitates a real recording, so a strict reading says disclosure is not required.
   **Recommendation: answer Yes** on every upload. The cost is a small label; the benefit is that nobody can later say generated audio went undisclosed.
   Each `<slug>.json` carries this decision and the reasoning. Ben can change it.
4. **Do long uploaded videos count toward the 4,000 public watch hours?** Yes. YouTube counts qualified watch hours from public long-form videos
   (https://support.google.com/youtube/answer/72851). Eligibility is 1,000 subscribers plus 4,000 public watch hours in the last 12 months, or 10 million Shorts
   views in 90 days. Watch hours from the Shorts feed do not count toward the 4,000. Live streams count only if they are public and converted to a video on demand;
   the page excludes streams that are unlisted, deleted, or not converted. The existing 24/7 stream runs as one endless broadcast, so its hours may not count
   at all, which is a reason to move the watch-hours effort to uploads.
5. **Copyright.** No audio or image file is loaded anywhere. The winter music is composed from a seed, with no carol or existing tune used (not even public-domain
   ones, because a recording of those can still match in Content ID).

## Cadence and calendar

Two long videos a week, Monday and Thursday at 15:00 US Eastern to start, then adjust from the data. Each long video gets two Shorts (20 to 40 seconds, cut from
a real moment such as the fire catching, the owl landing or the sleigh crossing), posted the next two days, with the long video linked in the description and in the pinned comment.
Shorts do not add to the 4,000 hours, so their job is only to send people to the long video.

Thumbnail test: upload each long video with three thumbnail variants (A the title text over the scene as made by `longform_pub.py thumb`; B the scene with no
text; C a different moment or crop) and use YouTube's Test & Compare. Keep the winner, and note which style wins per theme.

| Week of | Monday | Thursday | Theme status |
|---|---|---|---|
| Oct 19 | Halloween Porch, 2 h (first upload, Halloween is Oct 31) | Cozy Campfire with music, 2 h | built |
| Oct 26 | Halloween Study (study room, Halloween decor, 25/5 timer), 2 h | Campfire ambience, no music, 1 h | built (`--season halloween`) |
| Nov 2 | Autumn Rain, 2 h | Study With Me, 25/5 timer, 2 h | rain theme: new, small |
| Nov 9 | Foggy Forest Morning, 2 h | Rainy Study Room, 2 h | forest: new; study exists |
| Nov 16 | Autumn Cabin, 2 h | Campfire ambience, 1 h | cabin: reuse winter scene with autumn palette |
| Nov 23 | Thanksgiving Evening (warm kitchen window, rain), 2 h (Thanksgiving is Nov 26) | Cozy Campfire 2, new seed and sky, 2 h | evening scene: new |
| Nov 30 | Winter Cabin, 2 h | Snowfall, no music, 1 h | built |
| Dec 7 | Winter Study, 25/5 timer (study room, holiday decor), 2 h | Winter Cabin 2 | built (`--season christmas`) |
| Dec 14 | Christmas Eve Fireplace, 2 h | Winter Night Ambience, no music, 1 h | built (`winter` plus a long variant) |
| Dec 21 | Winter Solstice Night (longest night, aurora), 2 h | New Year Fireworks Ambience, 2 h | aurora and fireworks: new |

Ten weeks is twenty long videos and about forty Shorts. Rendering is cheap in labor (one command each) but slow on a busy machine, so queue the next
week's renders on Friday.

## Stop rule

Day 0 is the first public upload. At **day 45, if the channel has under 100 public watch hours in total, stop** and archive the channel (no more uploads, no more renders).
Checks before that: at day 14, if the average click-through rate on the thumbnails is under 2 percent, change the thumbnail style before making more videos; at day 30,
if no video has passed 10 hours of watch time, change the theme mix once. The stop rule is not extended by a single viral Short, since Shorts hours do not count.
Cost to compare against: about 5 euro a month for the VPS if the live stream stays on, plus the time to queue renders.

## What Ben has to do himself

1. **Create the channel.** In YouTube Studio under his Google login, create a new channel as a **Brand Account** (not a new Google login), so the existing automation
   Chrome on port 9340 can switch to it from the account menu. Pick the name, handle and avatar. Do not give the new channel's login or any token to a script.
2. **The live stream (decided 2026-10-16):** it stops once the first uploads are live on the new channel, and its final broadcast is then unlisted. The six
   earlier stream recordings on the Purplelink channel were unlisted on 2026-10-16.
3. **Watch each video before it goes public.** The files are checked by instruments (duration, loudness, true peak, silence, frames), not by ears. Listen to at least the
   first ten minutes and a stretch from the middle of each one.
4. **Answer the Studio questionnaires**: made for kids: No; altered or synthetic content: Yes (see above); category per the JSON file.
5. **Upload**, set the thumbnail variants, and schedule. Upload as private first.

## Render status (2026-10-17)

Videos are made from one seamless loop of picture and music (`--loop-min`, 10 to 20 minutes, Ben's call on 2026-10-17). The loop's end crossfades into its
start, so it repeats with no click or jump. The full-length file repeats it by stream copy, with one audio encode. Each folder also holds the bare loop
(`<slug>-loop<L>min.mp4`), and each description says plainly that the video is one repeating loop.

| Slug | Theme | Length | Music | Status |
|---|---|---|---|---|
| halloween-2h | halloween | 2 h | yes | finished 2026-10-17 (rendered before loop mode: 2 h of unique music over a 20 minute picture), verified, thumbnail and metadata done |
| campfire-2h | campfire | 2 h from a 20 min loop | yes | queued |
| campfire-ambience-1h | campfire | 1 h from a 15 min loop | none | queued |
| winter-2h | winter | 2 h from a 20 min loop | yes | queued |
| study-pomodoro-2h | study, 25/5 timer | 2 h | yes | not queued: the Pomodoro counter cannot repeat |

The videos themselves are not in git.


## Sound variants, keywords and review loop (added 2026-10-17)

Ben asked for each video type in several sound versions (the things people put on and forget), and for the videos to be keyword, SEO and GEO optimised over time.
Everything below is code in `tools/chiptune-radio/`; nothing has been uploaded or changed on YouTube.

### Sound modes (`longform.py --sound NAME`)

`--sound` defaults to `chiptune`, which is exactly what the renderer did before. Every other mode is synthesised in `sounds.py` from random numbers and sine
waves (nothing sampled or downloaded), mixed with the theme's own ambience bed at a low level unless `--no-bed` is given. Each mode has its own loudness target
(`sounds.SOUNDS[name].lufs`); the mux masters to it, and `longform_pub.py verify --sound NAME` (render_batch.sh passes it) checks the file against it.

| Sound | What it is | LUFS | Theme bed under it |
|---|---|---|---|
| chiptune | the existing composed chiptune music | -14 | as before |
| lofi | the chiptune engine slowed to about 62 to 68 BPM with a softened top end, warm electric-piano lead and vinyl crackle | -16 | as for music |
| brown | -6 dB per octave (leaky integrator plus DC blocker), independent in each ear | -20 | 0.7 |
| pink | -3 dB per octave (ladder of pole and zero pairs, pre-warped), DC-free | -20 | 0.7 |
| white | flat spectrum | -20 | 0.6 |
| binaural-alpha / theta / delta | 200 Hz in the left ear, 200 plus 10 / 6 / 2 Hz in the right, under a soft pad and quiet pink noise; the description says to use headphones | -20 | 0.25 |
| synth | slow ambient pads: a chord of pure partials that each swell on their own 60 to 220 s cycle; no beat, no melody, no key change | -18 | 0.3 |
| rain | layered hiss, body and single drops, with distant thunder about every 9 minutes | -20 | 0.4, the theme's own rain dropped |
| thunderstorm | heavier rain with a rumble about every 2 minutes | -20 | 0.3 |
| fireplace | crackle and low roar, louder than the bed | -18 | 0.2, the theme's own fire dropped |
| ocean | two drifting wave trains, rumble, wash and crest foam | -20 | 0.2 |
| wind, fan, airplane | wind with gusts; fan whoosh with motor hum; airplane cabin roar with two beating engine tones | -20 | 0.2 |

Why these extras: the autocomplete research (below) surfaces fan, airplane (cabin, "airplane white noise", "airplane noise 10 hours"), wind, ocean and
thunderstorm next to brown, white and rain for the bare seeds, and all are cheap to synthesise. A web search found no ranking of YouTube sleep sounds by
views (only blog lists naming white noise, brown noise, rain, fan, airplane and train sounds, and 8 to 10 hour lengths), so the autocomplete data is the evidence
used. Left out: train, vacuum, heartbeat, river, waterfall (more work to make convincing), and any claim that a sound improves sleep, focus or anything else.

How the loop stays seamless: the random part (noise, rain, crackle) is crossfaded at the seam with equal power, which keeps noise level. Tones and slow swells are
built to repeat exactly once per loop (every frequency is a whole number of cycles per loop) and are added after the crossfade, so a binaural beat is exactly
its beat everywhere, including at the join. Tests check: the pink and brown slopes, DC, the L/R beat difference after the AAC mux (stereo stays separate),
the loop seam, and each loudness target.

`--dark SECONDS` dims the picture to near black (RGB 4,4,4) over 20 seconds starting at that time and keeps the sound going. Only the first part of the picture
is drawn; a black clip is repeated by stream copy, so a 10 hour dark video costs the 10 hour AAC encode (about 8 minutes) and little more. "Black screen" is one of
the most typed modifiers in the research, so titles for dark videos say it (the title builder picks "Black Screen" or "Dark Screen" from the research). The
description says the screen dims to near black.

### Keyword method (`keywords.py`)

Source: YouTube's public search suggest endpoint (`suggestqueries.google.com/complete/search?client=firefox&ds=yt`). Autocomplete is what people type, in popularity
order; it is a demand signal, not a view count, and it says nothing about competition. 390 queries (each seed phrase for each sound and theme, bare and with
modifiers: 10 hours, 8 hours, for sleep, for studying, black screen, dark screen, no ads, 1 hour, 3 hours), two a second at most, cached with their dates for 7 days in
`/Volumes/Extreme SSD/PurplelinkVideos/ambient/keywords/` (`cache.json`, `ranked-DATE.json`, `latest.json`). A phrase scores (10 minus position) / 10 per query that returns it;
a bare seed counts three times a seed with a modifier we added ourselves, because added modifiers are echoed back.

Top phrases per sound on 2026-10-17 (full lists: `keywords.py --show NAME`):

| Sound | Top 5 ranked phrases |
|---|---|
| brown | brown noise no ads; brown noise for studying; brown noise; brown noise black screen no ads; brown noise sleep |
| pink | pink noise black screen; pink noise no ads; pink noise; pink noise for studying; pink noise 10 hours |
| white | white noise black screen; white noise no ads; white noise for studying; white noise; white noise for sleep |
| binaural-alpha | 10 hz binaural beats; 10 hertz binaural beats; 10 hz binaural beats pure; 10 hz binaural beats for focus; alpha binaural beats 10 hz |
| binaural-theta | 6hz theta waves no ads; 6 hz binaural beats; 6 hertz binaural beats; 6 hz binaural beats cortisol; theta binaural beats |
| binaural-delta | 2 hz binaural beats; 2 hz binaural beats sleep; 2 hz binaural beats black screen; 2 hz binaural beats no ads; delta binaural beats |
| synth | synth pads ambient; ambient synth music; synth pad backing track; ambient synth music no copyright; ambient music no ads |
| lofi | lofi chiptune; lofi chiptune music; lofi music 8 bit; lofi music for studying; lofi study music no ads |
| rain | rain sounds for sleeping; rain sounds for sleeping no ads; rain sounds for sleeping live; rain sounds for sleeping thunder; rain sounds no ads |
| thunderstorm | rain and thunder sounds for sleeping; thunderstorm sounds for sleeping no ads; rain and thunder sounds for sleeping no ads; thunderstorm sounds for sleeping; rain and thunder sounds no ads |
| fireplace | crackling fire sounds 1 hour; crackling fire sounds for sleeping; crackling fire sounds black screen; crackling fire sounds for studying; fireplace sounds 10 hours |
| ocean | ocean waves sounds no ads; ocean waves sounds; ocean waves sounds for deep sleep; ocean waves sounds for sleeping dark screen; ocean waves sounds for sleep |
| wind | wind sounds for sleeping; wind sounds for sleeping no ads; wind sounds; wind sounds 10 hours; wind sounds black screen |
| fan | fan noise for sleeping black screen; fan sounds for sleeping; fan noise for sleeping; fan noise for sleeping no ads; fan sounds for sleeping no ads |
| airplane | airplane cabin sounds for sleeping; airplane white noise for sleeping; airplane noise 10 hours; airplane noise no ads; airplane noise black screen |

Modifier popularity from the bare seeds: for sleep (34), no ads (27), black screen (9), no music (7), pomodoro (7), 10 hours (6), 1 hour (5), for studying (5),
dark screen (0.6). Notes: "no ads" cannot be promised on a monetised channel, so it is not used. "Black screen" beats "dark screen" about 15 to 1, so dark videos are titled
"Black Screen". Some binaural phrases carry health words (cortisol, meditation, focus, sleep); they are not used in titles, tags or descriptions.

### How the research feeds the metadata (`longform_pub.py`)

- Title: the searched phrase first, then the scene, the length, then the screen: "Brown Noise with Crackling Campfire, 10 Hours, Black Screen" (the lead is the
  highest-ranked of a few candidates per sound, for example "10 Hz Binaural Beats" over "Alpha Binaural Beats 10 Hz"). 100 characters at most.
- Description: the first sentence is at most 150 characters and says plainly what it is ("Brown Noise, 10 Hours. Deep, smooth brown noise with quiet fire crackle, wind and
  crickets, over a pixel-art campfire at night."). That is what search results and answer engines show.
- GEO block, headed "About this video": what it is, length (and loop), what else is in the mix, the picture, how it was made, loudness, headphones where
  relevant, and one line about the channel. Short labelled facts a language model can quote without guessing. Honesty rule: only what is in the video.
- Tags: the lead phrase, then the ranked phrases for the sound (10) and the theme (4), then the theme's own tags; at most 15, under 470 characters, no duplicates.
- Three hashtags: the sound's, the theme's, and #sleepsounds or #ambience.
- Chiptune videos keep their existing descriptions; only their tags pick up the ranked phrases.
- Proposed, not built: a public page on purplelink.llc listing each video with the same fact block as plain HTML and a VideoObject schema.org block, so answer engines
  that read the web (not YouTube) can cite the channel. Cost is a page per video or one index page; do it only if the channel passes the day-14 check.

### Review loop (`seo_review.py`, `keywords.py` weekly)

Weekly (Monday): refresh keywords. Weekly (Friday, before queueing the next week's renders): export per-video stats and run
`python3.12 seo_review.py stats.csv`. It flags, per video: too few impressions to judge; click-through under 2 percent with at least 300 impressions
(change the thumbnail first, with Test & Compare, then the title); searched terms the video earns but its title and tags lack (add to tags, re-lead the title);
early drop-off on long videos. Per sound and per theme it totals views, click-through and watch hours, and it ranks every theme x sound pair not yet made by search
demand times how the theme and sound have done, shrunk toward the channel average so one lucky video does not decide (and by demand alone until three videos have
300 impressions). The calendar below is a starting order; the review reorders it. Re-title a video at most once, no sooner than 14 days after upload, and record every
change with `log_change.py` so a later rise or fall can be traced.

### What Ben must do for Analytics access

Until then `seo_review.py` works on a CSV exported by hand from Studio (Analytics, Advanced mode, Content, metrics views, impressions, impressions click-through rate,
average view duration, watch time; add each video's top search terms from its Reach tab).

1. In the Google Cloud project that owns `~/.tiktok_pipeline/youtube_client_secret.json`, enable both **YouTube Analytics API** and **YouTube Data API v3**. If the OAuth consent
   screen is in "Testing", refresh tokens expire after 7 days: set it to "In production" (read-only scopes need no review for your own account) or expect to redo step 2 weekly.
2. In his own terminal (it opens a browser), following `TikTokPipeline/youtube_analytics_login.py`:

       YOUTUBE_CLIENT_SECRET=~/.tiktok_pipeline/youtube_client_secret.json \
       YOUTUBE_ANALYTICS_TOKEN=~/.tiktok_pipeline/youtube_analytics_pixelhearth.json \
       python3 "/Volumes/Extreme SSD/TikTokPipeline/youtube_analytics_login.py"

   At Google's chooser pick the **Pixel Hearth** brand account (not the Purplelink channel). Scopes requested: `yt-analytics.readonly` and `youtube.readonly`. The token
   can read statistics only; it cannot upload, edit or delete.
3. Tell the next session the file `~/.tiktok_pipeline/youtube_analytics_pixelhearth.json` exists. A small fetcher (not written yet, no OAuth was attempted) would call
   `reports.query` per video for views, estimatedMinutesWatched and averageViewDuration, and for search terms use dimension `insightTrafficSourceDetail` filtered to
   `insightTrafficSourceType==YT_SEARCH`. As far as I know the Analytics API does not return impressions or click-through rate for channels, so that one column
   stays a manual Studio export; check the API reference before relying on this.

### Weekly keyword job (launchd text, not installed)

Save as `~/Library/LaunchAgents/com.purplelink.ambient-keywords.plist` and `launchctl bootstrap gui/$(id -u)` it when Ben agrees. It uses the checkout path of whichever
branch holds `keywords.py` (update the path after PR 168 merges). The job only reads the suggest endpoint and writes files under `PurplelinkVideos/ambient/keywords/`.

    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0"><dict>
      <key>Label</key><string>com.purplelink.ambient-keywords</string>
      <key>ProgramArguments</key><array>
        <string>/Library/Frameworks/Python.framework/Versions/3.12/bin/python3</string>
        <string>/Volumes/Extreme SSD/Purplelink LLC/tools/chiptune-radio/keywords.py</string>
        <string>--refresh</string>
      </array>
      <key>WorkingDirectory</key><string>/Volumes/Extreme SSD/Purplelink LLC/tools/chiptune-radio</string>
      <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>30</integer></dict>
      <key>StandardOutPath</key><string>/Users/benampel/Library/Logs/ambient-keywords.log</string>
      <key>StandardErrorPath</key><string>/Users/benampel/Library/Logs/ambient-keywords.log</string>
      <key>LowPriorityIO</key><true/><key>ProcessType</key><string>Background</string>
    </dict></plist>

### Revised calendar: scenes mixed with sounds

Rule of thumb from YouTube's policy reading above: vary the substance, not only the title. Alternate a music video, a noise or nature-sound video and a scene-led video;
never the same scene and sound twice in a month; dark-screen versions only for the sound videos people sleep to. Length follows the search data (10 hours for noise,
fan and airplane; 2 to 3 hours for scenes). The first batch is queued in `~/.purplelink/nightq/deferred/` (prefix 20 to 24) until Ben decides.

| Week of | Monday | Thursday |
|---|---|---|
| Oct 19 | Halloween Porch with chiptune music, 2 h (first upload) | Campfire + Brown Noise, 10 h, black screen (job 20) |
| Oct 26 | Halloween Porch + Ambient Synth, 2 h (job 23) | Campfire ambience, no music, 1 h |
| Nov 2 | Winter Cabin + Rain Sounds, 3 h (job 21) | Study With Me, 25/5 timer, chiptune, 2 h |
| Nov 9 | Study Room + 10 Hz Binaural Beats, 2 h (job 22) | Campfire + Pink Noise, 8 h (job 24) |
| Nov 16 | Winter Cabin + Fireplace Sounds, 3 h, black screen | Halloween Porch + Thunderstorm, 3 h |
| Nov 23 | Study Room + Brown Noise, 10 h, black screen | Cozy Campfire with lofi music, 2 h |
| Nov 30 | Winter Cabin + Wind Sounds, 3 h | Winter Cabin with chiptune music, 2 h |
| Dec 7 | Campfire + Ocean Waves, 3 h | Study Room + Airplane Cabin Sounds, 10 h, black screen |

After week 3 the review reorders this: keep the pairs the data favours, drop the sounds with the lowest watch hours per video. The stop rule above still applies.
