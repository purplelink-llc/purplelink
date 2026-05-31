# GlobePin — launch kit

Per the changelog, GlobePin is nearest to App Store submission (build 79+). Use this on launch day.

## Day-of checklist

- [ ] App is live on the App Store; URL captured
- [ ] Press kit (`Social Media/`) is up to date with App Store screenshots
- [ ] Update `site/globepin/` with the App Store badge linking to the real URL
- [ ] Update `Organization.sameAs` JSON-LD on homepage to include the App Store URL (and `SoftwareApplication.downloadUrl` on `/globepin/`)
- [ ] Post the launch announcement (below) on:
  - [ ] LinkedIn company page
  - [ ] Bluesky (@purplelink.llc)
  - [ ] r/iOSProgramming (text post — they ban link-only posts)
  - [ ] r/Swift
  - [ ] Hacker News (Show HN)
  - [ ] Product Hunt (scheduled for the day before; launches at midnight PT)
  - [ ] Indie Hackers
- [ ] Email pitches to 3 newsletters (templates below)
- [ ] Reply to every comment in the first 3 hours (algorithm + goodwill)
- [ ] Run `python scripts/indexnow_ping.py` after deploy to ping Bing/Yandex about /globepin/

---

## Show HN copy

**Title** (Show HN titles need to be specific + curiosity-piquing without hype; 80 char max):
> Show HN: GlobePin – a private iOS travel map with a 3D globe and a flight log

**Body** (link to https://purplelink.llc/globepin/ in the URL field; this goes in the text-body):

> Hi HN — I'm Ben, building Purplelink LLC, a one-person studio in Atlanta.
>
> GlobePin is my take on personal travel mapping for iOS. The mental model is "Letterboxd for travel": a private record of every place you've been, every flight you've taken, and every destination on the list. The map is the main view; a 3D globe rotates to show all your pins; a flight log tallies miles, longest flight, busiest airport, anniversaries.
>
> Where it differs from Polarsteps (the obvious comparison): no automatic GPS tracking, no Polarsteps account, no social feed. Pins are added by you, sync happens through your own iCloud (CloudKit, no Purplelink account). The architectural form of "we don't track you" — there is no Purplelink server holding your data.
>
> Why? Most travel apps optimize for trip-storytelling and engagement. I wanted the opposite: a long-tail record-keeping tool that respects that not everyone wants their travel history on a server.
>
> Tech stack notes for the curious: SwiftUI for the UI, GRDB.sqlite for the on-device store, CloudKit for sync, MapKit for the 2D map and an SCNView rotating globe for the 3D view. App Store: [URL]. Waitlist signups got a notification an hour ago.
>
> Happy to answer questions. Comparison guide vs Polarsteps + Visited: https://purplelink.llc/guides/globepin-vs-polarsteps/

---

## Product Hunt page (schedule for 12:01am PT)

**Tagline** (max 60 chars):
> A private iOS travel map with a 3D globe and flight log

**Description** (max 260 chars):
> Track every place you've been, every flight you've taken, and every destination on the list. 3D globe view, flight stats dashboard, anniversary reminders. iCloud sync, no separate account. No social feed.

**First comment** (you make the first comment to set the tone — this is standard PH play):
> Hey Product Hunt — Ben here, founder of Purplelink. GlobePin started as the travel app I wanted for myself after realizing every option either required GPS tracking or a social feed I didn't want.
>
> A few things I'm proud of:
> · The 3D globe (SCNView) is the most-used screen for power users.
> · No Purplelink account — your data lives in your own iCloud via CloudKit. Verifiable: there's no server to leak.
> · Flight log gives you stats like longest flight, busiest airport, anniversary reminders.
>
> Free to download. Premium adds [add premium features when finalized]. Comparison vs Polarsteps + Visited: https://purplelink.llc/guides/globepin-vs-polarsteps
>
> AMA in the thread.

**Gallery images** (need before launch):
- [ ] App Store hero shot
- [ ] 3D globe screen
- [ ] Map view with pins
- [ ] Flight log stats
- [ ] Goal tracking screen

---

## r/iOSProgramming text post

**Title:**
> [Launch] GlobePin – a private travel mapping app I built solo. AMA on the architecture.

**Body:**
> One-person studio, 18 months from idea to App Store. GlobePin is a personal travel record for iOS: places visited, flights taken, destinations on the list. iCloud sync (CloudKit), no account, no social feed.
>
> Tech choices I'd be happy to dig into:
> - **GRDB.sqlite** for the on-device store. Considered Core Data. Don't regret the choice.
> - **CloudKit** for sync, with `NSPersistentCloudKitContainer`-equivalent abstractions. Smooth-ish; the limit-on-record-size edge cases were the most painful.
> - **SCNView** for the 3D globe. Considered SceneKit-via-RealityKit; decided on raw SCNView for tighter control.
> - **No analytics SDK**. Verifiable in the network panel.
>
> Comparison vs Polarsteps and Visited if you're curious: https://purplelink.llc/guides/globepin-vs-polarsteps
>
> App Store: [URL]. Happy to answer questions about anything — including the bits that didn't work.

---

## r/Swift post

Same as r/iOSProgramming but with the title:
> [OC] Built a SwiftUI travel app solo — lessons from 18 months of working alone

Focus the body more on solo-development lessons than the app itself; the app is the proof, not the point.

---

## LinkedIn post

> GlobePin ships today. 🌍 (using one emoji here intentionally — LinkedIn audiences expect it)
>
> A private iOS travel map I've been building for 18 months as a one-person studio. Every place you've been, every flight you've taken, every destination on the list — visible on a 3D globe and a flight stats dashboard. iCloud sync; no Purplelink account; no social feed.
>
> The architectural form of "we don't track you": there is no Purplelink server holding your data.
>
> Free on the App Store: [URL]
> Behind-the-build: purplelink.llc/blog/what-globepin-does-differently
> How it compares: purplelink.llc/guides/globepin-vs-polarsteps
>
> Thanks to everyone on the waitlist who stuck around. This is the first of three apps shipping in 2026.
>
> #IndieDev #iOS #SwiftUI #Travel

---

## Bluesky post

> GlobePin shipped today.
>
> A private iOS travel map I built solo over 18 months. Places, flights, goals — on a 3D globe. iCloud sync, no Purplelink account, no social feed.
>
> App Store: [URL]
> Why it's different from Polarsteps: purplelink.llc/guides/globepin-vs-polarsteps

---

## Newsletter pitches

### iOS Dev Weekly (Dave Verwer)

**Subject:** Show HN-grade iOS launch — GlobePin, solo-built private travel mapping

> Hi Dave,
>
> Long-time iOS Dev Weekly reader. I just shipped GlobePin — a private travel-mapping iOS app I built solo over 18 months, launching today on Show HN and the App Store.
>
> Three things that might fit the newsletter:
>
> 1. **Architecture decisions** — chose GRDB over Core Data, CloudKit over a homebrew sync layer, raw SCNView over RealityKit for the 3D globe. Happy to expand on any of these.
> 2. **No analytics SDK** — verifiable claim, not marketing. The privacy-first iOS niche has been growing.
> 3. **Solo studio model** — Purplelink LLC is one person; GlobePin is the first of three apps shipping in 2026.
>
> Not asking for a feature — just thought it might be worth a look. App Store: [URL]. Behind-the-build piece: purplelink.llc/blog/what-globepin-does-differently
>
> Either way, thanks for the weekly digest. It's been part of my Sunday for years.
>
> Best,
> Benjamin Ampel
> ben@purplelink.llc

### MacStories / Federico Viticci

**Subject:** GlobePin — a private travel map I built solo for iOS

> Hi Federico,
>
> I built GlobePin over 18 months as a one-person studio — a private iOS travel map (places visited, flights taken, destinations on the list) with a 3D globe and a flight log. Launching today. No account, no social feed; iCloud sync only. Privacy is architectural, not promised — there's no Purplelink server holding your data.
>
> If it's the kind of indie iOS thing MacStories occasionally covers, I'd love your team's take. Press kit and an explainer below; happy to do a written interview if useful.
>
> · App Store: [URL]
> · Behind-the-build: purplelink.llc/blog/what-globepin-does-differently
> · Comparison vs Polarsteps + Visited: purplelink.llc/guides/globepin-vs-polarsteps
>
> Thanks for everything you've shipped over the years.
>
> Benjamin Ampel
> ben@purplelink.llc

### Indie Hackers

**Subject:** [Launch] GlobePin — 18 months solo, App Store today

Same body shape as the LinkedIn / Hacker News announcement, but with milestones (MRR target, waitlist size at launch, etc.) — the Indie Hackers audience cares about the business side.

---

## Day-after follow-up

- [ ] If Show HN gains traction, write a "what worked, what didn't" follow-up post for /blog/ within 7 days while interest is fresh.
- [ ] Reply to every comment from the first 24 hours, even the negative ones (especially the negative ones).
- [ ] Add the launch post URLs to the homepage Organization `sameAs` array.
- [ ] Submit the App Store URL to PrivacyGuides, Awesome Privacy, EFF resources if the privacy claims hold up under scrutiny.
