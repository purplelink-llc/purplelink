# Newsletter pitches

Pitching to a niche-tech newsletter is one of the strongest ROI outreach moves available — a single placement in iOS Dev Weekly or MacStories can outperform months of community work. But the pitch quality matters enormously. Generic press releases get filtered.

## Rules

- **Pitch the specific person, not the publication.** Each newsletter has an editor whose voice the audience knows. Address them by name.
- **Lead with the angle, not the company.** Why is this newsletter-worthy?
- **Be quotable.** Editors crib copy from the pitch into the newsletter; make your phrasing usable verbatim.
- **No exclusivity offers** to small newsletters — they don't need them and it reads as pushy.
- **One-shot, not a campaign.** No follow-ups; one well-crafted pitch beats five mediocre ones.

## Tier A — high-leverage, pitch when shipping

### iOS Dev Weekly (Dave Verwer)

**When:** Each app launch day (GlobePin first, then Haea, then ModernTex — though ModernTex is Mac, lighter fit).

**Subject:** Show HN-grade iOS launch — [App name], solo-built privacy-first iOS app

**Template body:** See `03-launches/globepin-launch-kit.md` for the GlobePin version.

**Why this works:** Dave reads pitches; he replies to genuine ones. The newsletter has covered solo iOS launches before. The architectural-privacy angle is the kind of thing he highlights.

### MacStories (Federico Viticci)

**When:** Each app launch day, especially Haea (privacy fit) and ModernTex (Mac native fit).

**Pitch shape:** longer, story-style. MacStories loves detailed write-ups about indie iOS/Mac development. Offer to do a written Q&A if they're interested.

**Template body:** in the launch kits.

**Why:** Federico has covered solo macOS developers many times. The "10-year Mac native" angle (no Electron, native PDFKit, etc.) is exactly the kind of detail MacStories audiences care about.

### Indie Hackers (founder community)

**When:** Each launch. Format: "I just shipped..." post in the IH forum, not a private email.

**Why:** Different audience from iOS Dev Weekly — they care about the business model, MRR potential, solo-founder mechanics. Frame each launch in those terms.

## Tier B — niche, fits specific apps

### iOS Dev Weekly Jobs newsletter

Lower priority. Skip unless hiring.

### Hacker Noon (engineering-blog audience)

**Fit:** ModernTex specifically. The architectural decisions in ModernTex (tree-sitter, native PDFKit, FTS index for BibTeX autocomplete) are interesting enough for a Hacker Noon write-up. Pitch as a guest post, not a launch announcement.

**Body shape:** "I built a native macOS LaTeX editor instead of an Electron one. Here's what that actually means in 2026."

### iOS Goodies / Indie Goodies

**Fit:** any of the three apps. Smaller audience but high quality. They appreciate when developers send a press kit + a TestFlight code.

### The Sweet Setup

**Fit:** ModernTex specifically. They cover Mac apps for academic / writing workflows. ModernTex is the strongest match.

**Body shape:** offer a free copy for review, plus a 30-minute call to walk through how it differs from TeXShop / Texifier.

### PrivacyGuides.org

**Fit:** Haea exclusively. They maintain a curated list of privacy-focused apps. Submission is via PR on their GitHub. Not a "pitch" — a contribution.

**How:** Open a PR to https://github.com/privacyguides/privacyguides.org with Haea added to the relevant page. Include verifiable architecture claims (no network calls for health data) and link to the architecture write-up.

## Tier C — broader tech press

**Honest:** Tier C placements are real long shots for a solo studio. Skip them unless launch numbers warrant it.

- **The Verge** — only if a launch hits 1000+ HN points
- **Ars Technica** — only if there's a deeply technical angle that pairs with their reporting
- **MIT Tech Review** — only for Haea, only if the privacy-as-architecture framing aligns with something they're already covering

Don't waste time on Tier C until Tier A is exhausted and at least one Tier A placement has converted to traffic.

## Email infrastructure

Send these from `ben@purplelink.llc`, not a generic `hello@`. Reply-to should also be `ben@`. Use plain text, not HTML. Include:
- One link to the App Store URL (per app)
- One link to the relevant blog post or guide
- Your name + studio + email signature

No tracking pixels, no UTM parameters in the links (newsletters notice these and many editors won't share tracked links).

## Tracking

When you send, log in `OUTREACH-LOG.md`:
```
| Date       | Target              | Status   | Notes |
|------------|---------------------|----------|-------|
| 2026-MM-DD | iOS Dev Weekly      | sent     | -     |
| 2026-MM-DD | MacStories          | sent     | -     |
```

Track responses for 4 weeks, then archive.
