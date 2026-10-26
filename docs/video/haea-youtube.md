# haea YouTube uploads: text and status

Script: `haea-howto-script.md`. Both uploads are PRIVATE on the Purplelink channel (UCUv28P5SUzT4RLQOmi3EK8w), made with
`scripts/yt-api-upload.py --channel purplelink --kind product|howto-short --privacy private`. They are published by
`scripts/app-release-watch.py` when the App Store lists haea (ascAppId 6761912624) as READY_FOR_SALE; the watcher reads
`video/out/haea/release.json` in the shared checkout (git-ignored).

| Cut | YouTube ID | Privacy | Length |
|-----|-----------|---------|--------|
| Long, 1920x1080 | `k_aluYUOxoU` | private | 2:37 |
| Short, 1080x1920 | `1hbbv-rRzmg` | private | 0:45 |

Thumbnails A/B/C: `video/thumbs/ab/haea.json` (A readiness screen, B numbered promise, C route planner); A is set.
Caption tracks: `video/write-stills-srt.mjs`; the watcher uploads them at release.

## Long description

Title: How haea works: readiness, strength, running and insights on iPhone

---
haea reads Apple Health and gives you a daily readiness briefing. This video goes through the app tab by tab: Today, Strength, Running, Insights and Coach. All of the analysis runs on the iPhone. Everything shown is demo data.

0:00 What haea is
0:17 The Today briefing
0:28 Warnings and Today's health
0:52 Strength log
1:12 Running
1:22 Route planning
1:33 Insights
1:52 Coach
2:01 Private by design
2:09 General wellness, not medical advice
2:18 Free, with optional Premium

haea is for general wellness. It is not medical advice and does not diagnose or treat any condition. Talk to a doctor about medical questions.

haea is free to download. The daily briefing, strength log and running work without a subscription. Optional Premium adds deeper analysis: $1.99 a month, $14.99 a year, or $49.99 once (lifetime).

App Store link: ADD BEFORE PUBLISHING
More about haea: https://purplelink.llc/haea/?utm_source=youtube&utm_medium=video&utm_campaign=hub-haea-promo&utm_content=haea-promo-youtube-261025
Privacy: https://purplelink.llc/privacy

#applehealth #iphoneapps #fitnessapp #strengthtraining
---

## Short description

Title: haea in 45 seconds: a daily readiness briefing on iPhone

---
A daily readiness briefing from Apple Health, a strength log, run route planning and Insights, all analyzed on your iPhone. Demo data shown. General wellness, not medical advice.

Full video: LINK THE LONG VIDEO WHEN BOTH ARE PUBLIC

App Store link: ADD BEFORE PUBLISHING
More about haea: https://purplelink.llc/haea/?utm_source=youtube&utm_medium=video&utm_campaign=hub-haea-short&utm_content=haea-short-youtube-261025

#applehealth #iphoneapps #fitnessapp #shorts
---
