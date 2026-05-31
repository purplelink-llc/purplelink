# Outreach toolkit — Purplelink LLC

A do-it-yourself kit for the four off-site authority tiers. Everything that can be drafted in advance is already drafted; what's left is the actual posting / sending, which only you can do under your own identity.

## The 1-hour-a-week deal

- **You** read `WEEKLY-PLAN.md` each Sunday (auto-surfaced by a scheduled task)
- **You** spend ~1 hour Monday–Friday executing what it says
- **You** update `OUTREACH-LOG.md` with what you did
- **I** refresh the toolkit quarterly + react when you ship a launch

## Folder map

```
Outreach/
├── README.md                       # this file
├── WEEKLY-PLAN.md                  # 12-week sequenced checklist
├── OUTREACH-LOG.md                 # tracker for sent / replied / converted
├── 01-identity/
│   ├── linkedin-company-page.md    # About copy + 4 posts ready to go
│   ├── github-org-readme.md        # org profile README + repo seed plan
│   └── bluesky-setup.md            # bio + custom-domain handle + 5 posts
├── 02-community/
│   ├── discovered-targets.md       # 8 verified LibGuides + TeX SE queries
│   └── answer-templates.md         # T1–T4 + R1–R2 paste-ready answers
├── 03-launches/
│   ├── globepin-launch-kit.md      # Show HN / PH / Reddit / newsletters / LinkedIn / Bluesky
│   ├── haea-launch-kit.md          # same shape, fill in at launch
│   └── moderntex-launch-kit.md     # same shape, fill in at launch
├── 04-outreach/
│   ├── libguide-outreach.md        # 5 personalized emails to named librarians
│   └── newsletter-pitches.md       # iOS Dev Weekly, MacStories, etc.
└── automation/
    └── (the IndexNow ping script lives at /scripts/indexnow_ping.py)
```

## What's automated

- **Site-side technical work** — IndexNow key file deployed, ping script at `scripts/indexnow_ping.py`, `Organization.sameAs` placeholder in homepage JSON-LD.
- **Sunday 6pm nudge** — a scheduled task reads WEEKLY-PLAN.md + OUTREACH-LOG.md and surfaces this week's actions.
- **Monthly SEO drift check** — a scheduled task compares the live site to the saved drift baselines and reports regressions.
- **Quarterly target refresh** — manually rerun the discovery agent (instructions below).

## What requires you

- Creating accounts (LinkedIn, GitHub, Bluesky) under your real identity.
- Clicking "post" on community responses I drafted.
- Clicking "send" on outreach emails I wrote.
- Replying to anyone who responds.
- Posting on TeX StackExchange under your account.

## After registering each identity

When you create the LinkedIn page, GitHub org, and Bluesky profile, send me the three URLs (or just edit `site/index.html` line ~71 directly — the `Organization.sameAs` array is the only thing to update). I can also run that edit + commit + deploy for you in our next session.

## Quarterly target refresh

Every 3 months, re-run the discovery agent to find new TeX SE questions, fresh LibGuides, etc. From a future session:

> "Re-run the Outreach discovery: find 10 new TeX SE questions, 8 LibGuides, and any new Reddit threads matching the existing tool/guide list. Write to `Outreach/02-community/discovered-targets-Q[N].md`."

This keeps the weekly plan supplied with fresh targets without manual work.

## When you ship an app

Open the relevant launch kit (`03-launches/*-launch-kit.md`). Everything is pre-drafted with `[URL]` placeholders for the App Store URL. The day-of checklist is at the top. Plan to spend ~3-4 hours on launch day pushing the announcements simultaneously across all channels.

## Deploy hook

After every `netlify deploy`, run:

```
python /Volumes/Extreme\ SSD/Purplelink\ LLC/scripts/indexnow_ping.py
```

This pings Bing, Yandex, Seznam, and Naver about any URLs whose `lastmod` matches today. Fast (~2 seconds). Free indexing speed-up.

If you want fully hands-off pinging, you can wire it into your deploy command:

```
netlify deploy --prod --dir site && python scripts/indexnow_ping.py
```

## What to expect

Realistic 90-day outcomes if you stick to the 1hr/wk:

- 3 identity rails registered, all linked from the homepage `sameAs`
- 6-10 TeX StackExchange answers, 200-400 reputation
- 4-5 LibGuide inclusion attempts; expect 1-2 to land
- ~12 LinkedIn posts, ~10 Bluesky posts
- 1 newsletter placement (if a launch happens in the window)
- Total referring domains: 8-15 (up from ~2-3 at start)
- Total direct site traffic from these channels: 100-300/month by week 12

These are small numbers by SaaS standards but exactly right for a one-person craft studio. Compound growth comes after week 12.
