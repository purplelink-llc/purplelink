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
2. **Decide the live stream's fate on the Purplelink channel.** Options: (a) leave it running until day 45 of the new channel, then decide; (b) end it now, which
   stops the VPS cost and gives up its accumulated likes and chat; (c) keep it and also point it at the new channel with a pinned link. Its watch hours may not count toward monetization
   (see policy item 4). I did not touch the stream or the server.
3. **Watch each video before it goes public.** The files are checked by instruments (duration, loudness, true peak, silence, frames), not by ears. Listen to at least the
   first ten minutes and a stretch from the middle of each one.
4. **Answer the Studio questionnaires**: made for kids: No; altered or synthetic content: Yes (see above); category per the JSON file.
5. **Upload**, set the thumbnail variants, and schedule. Upload as private first.

## What exists now (2026-10-16)

| Slug | Theme | Length | Music |
|---|---|---|---|
| campfire-2h | campfire | 2 h | yes |
| campfire-ambience-1h | campfire | 1 h | none |
| halloween-2h | halloween | 2 h | yes |
| winter-2h | winter | 2 h | yes |
| study-pomodoro-2h | study, 25/5 timer | 2 h | yes |

Each folder holds the `.mp4`, a `-thumb.jpg`, a `.json` of upload metadata, and four check frames. A pull request holds the code; the videos themselves are not in git.
