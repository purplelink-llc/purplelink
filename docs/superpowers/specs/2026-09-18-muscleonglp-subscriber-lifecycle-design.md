# MuscleOnGLP subscriber lifecycle: weekly roundup broadcast + new-subscriber sequence

**Status:** spec, not started · **Owner:** Ben · **Requested:** 2026-09-18, from
"what does the subscribe do long term?" — the answer at the time was "nothing
after the welcome email," which led to two asks: send subscribers the weekly
research roundup, and build a sequence introducing the Complete Pack.

---

## 0. Corrected baseline — read this first

Two assumptions got corrected mid-brainstorm; scoping this against what's
actually true, not against the first guess:

1. **The weekly research roundup already exists and is already automated.**
   `backend/research_digest/` is a live Modal cron (`app.py`, schedule
   `0 13 * * 1` — Mondays 13:00 UTC): harvests GLP-1/muscle literature
   (`harvester.py`), curates and summarizes via Claude (`curator.py`), and
   auto-publishes to `https://getmuscleonglp.com/research/` — both a per-week
   post and a rebuilt hub page — via `publisher.py`'s `write_into()`, which
   clones the site repo, renders, commits, and deploys through the Netlify
   CLI. Nine weeks of real history (2026-07-13 through 2026-09-14+). This
   spec does **not** touch any of that generation logic — it already works
   and already meets the site's real-citations-only content policy.

2. **It already emails a review copy — but only to Ben, not subscribers.**
   `mailer.py`'s `notify_review()` sends `ben@purplelink.llc` a "roundup is
   live, please skim it and pull or edit anything that reads wrong" email via
   Resend, immediately after each auto-publish. This is an internal QA gate,
   not a subscriber-facing send. **The actual gap is a second recipient
   path** — subscribers — not a new content pipeline.

3. **No drip/automation infrastructure exists anywhere in either repo** —
   confirmed by search (no cron, no launchd job, no scheduled Netlify
   Function). `subscribe.mjs` (`muscleonglp-site/netlify/functions/`) does
   exactly one thing today: adds the address to Buttondown, tagged
   `["protein-playbook", source]`, and returns a signed 14-day link to the
   free lead magnet (the Protein Playbook — see the corrected
   [[muscleonglp-marketing]] memory). Nothing else is coded to happen after
   that.

4. **Buttondown itself already has both features this spec needs**,
   confirmed against Buttondown's own docs — so neither part below needs new
   custom infrastructure, only configuration plus (for Part A) one small
   code change:
   - **RSS-to-email**: point it at a feed URL; it auto-sends a broadcast to
     the whole list when new items appear, on an Immediate (30 min poll),
     Weekly, or Monthly schedule, with an option to auto-send or hold as a
     draft for manual review first.
   - **Automations**: delay-based drip sequences ("after N days, send X"),
     triggerable off subscriber state, configured in the dashboard.
   - **Both are marked paid features** in Buttondown's docs. This site's
     current Buttondown plan tier is not visible from the codebase —
     confirm it covers both before building on top of them.

---

## 1. Weekly roundup → subscriber broadcast

### Approach: Buttondown RSS-to-email (not a custom API integration)

Considered and rejected: (a) a custom `notify_subscribers()` in `mailer.py`
POSTing to Buttondown's `/v1/emails` API — would need a new Modal secret and
reimplements unsubscribe/compliance handling Buttondown already provides for
free; (b) fetching subscribers and sending via Resend directly, alongside
the existing Ben-only review email — same problem, worse, since Resend has
no list-management concept at all. RSS-to-email needs zero new secrets and
zero new send-side code; the only gap is that no RSS feed exists yet for
`/research/` to point it at.

### Code change: add an RSS feed to the existing publish step

`publisher.py`'s `write_into()` already writes three things into the cloned
site checkout on every run: the post HTML, the rebuilt hub HTML, and a
sitemap update (`_sitemap_add`). Add a fourth: `research/feed.xml`, a
standard RSS 2.0 feed built from the same `manifest` list `render_hub_html`
already consumes (`slug`, `week_label`, `date`, `blurb` — all present today).
Reuse `renderer.py`'s existing `SITE` constant and `post_url()` helper for
the feed's `<link>`/`<guid>` entries rather than rebuilding the URL logic a
third time. Cap the feed at the most recent ~20 entries (RSS convention;
the manifest itself is unbounded and already sorted newest-first).

No Modal secret, no new dependency (writing an RSS XML string is the same
kind of string templating `render_hub_html` already does — no need for an
RSS-generation library).

### Dashboard configuration (manual, Ben — no code)

1. Buttondown → Settings → Basic → RSS-to-email.
2. Feed URL: `https://getmuscleonglp.com/research/feed.xml`.
3. Schedule: **Weekly**, set ~24h after the Monday 13:00 UTC publish (e.g.
   Tuesday morning) — not Immediate. Reasoning: Immediate polls every 30
   minutes, which could broadcast to the whole list before Ben's own review
   email even lands, let alone before he's had a chance to read it and pull
   anything wrong. A day's buffer keeps this fully automatic in the normal
   case while preserving the review window the pipeline was already built
   around.
4. Send behavior: auto-send (not draft-for-review) — the review step is
   already covered by step 3's buffer plus the existing `notify_review()`
   email; adding a second manual approval click every week would undercut
   the point of automating this.

### Open item

Confirm the Buttondown plan on this account actually includes RSS-to-email
before relying on it (see §0.4) — flagged, not resolved, since it needs
account/billing access this scan can't see.

---

## 2. New-subscriber → Complete Pack sequence

### Approach: Buttondown native Automations (not custom code)

Same reasoning as §1: Buttondown's delay-based automations do exactly what
was about to get custom-built (a scheduled send N days after an event).
Trigger: new subscriber (equivalent today to "tagged `protein-playbook`",
since `subscribe.mjs` applies that tag to every signup — either trigger
works; "new subscriber" is simpler and doesn't silently break if the tag
ever changes). Zero code.

### Sequence

The existing Day-0 welcome email (Protein Playbook link) is unchanged and
not part of this spec. Three new emails follow it:

| # | Delay | Subject | Purpose |
|---|---|---|---|
| 2 | Day 3 | The protein target isn't the hard part | Pure value, no pitch |
| 3 | Day 7 | Weight coming off isn't the same as fat coming off | Value, soft mention of the Pack |
| 4 | Day 12 | Everything, in one file | The offer |

Deliberately three, not more: escalates from pure value to a calm, single
offer without turning into a hard-sell sequence, matching the site's
existing "value-first, 9:1" ethic (the same rule the Reddit playbook already
enforces for that channel). No scarcity or countdown language anywhere in
the sequence — see the pricing note below for why.

### Final copy

**Email 2 — Day 3 — "The protein target isn't the hard part"**

> Quick follow-up on the Playbook.
>
> Most people can find their daily protein number — it's the eating part
> that gets hard on a GLP-1. Appetite drops, and a target that made sense at
> your old appetite stops being realistic.
>
> The four-meal system in the Playbook exists for exactly that: smaller,
> protein-forward meals spread out, instead of three meals you can't finish.
> If you haven't tried spacing it out yet, that's the one thing worth
> testing this week.
>
> — MuscleOnGLP

No link required. If Buttondown's editor wants one anyway, a soft link to
`https://getmuscleonglp.com/learn/protein-on-glp1/` at the bottom is fine —
not a pitch, just more of the same free content.

**Email 3 — Day 7 — "Weight coming off isn't the same as fat coming off"**

> One thing worth knowing that most people don't hear from their
> prescriber: the scale doesn't tell you what you're losing.
>
> Rapid loss on a GLP-1 can come from muscle as easily as fat, especially
> without resistance training in the mix. That's the whole reason this list
> exists — the eating side (protein, timing) is half of it; the training
> side is the other half.
>
> If you want the complete picture — training plan included, not just the
> nutrition piece — [The Complete Pack](https://getmuscleonglp.com/#pricing)
> has everything in one download. But if you just want to keep reading for
> now, [the free articles](https://getmuscleonglp.com/learn/) cover the
> training side too.
>
> — MuscleOnGLP

**Email 4 — Day 12 — "Everything, in one file"**

> You've had the Protein Playbook for a couple weeks now. If it's been
> useful, the rest of it might be too.
>
> **The Complete Pack** is all five guides — the full handbook, Protein
> Playbook, creatine, the no-gym plan, and the off-ramp guide — merged into
> one 60-page download. $29. Buying the same six separately comes to $34;
> this is one checkout, one file, less than the parts.
>
> Every claim in it is cited to a real, linked study, same as everything
> you've already read from us. No subscription, nothing to cancel — buy it
> once and it's yours.
>
> [Get the Complete Pack →](https://getmuscleonglp.com/#pricing)
>
> Not the right time? No worries — you'll keep getting the free articles
> and research roundups either way.
>
> — MuscleOnGLP

### Pricing and promo note

Copy cites $29 / $34 (verified against the live `#pricing` section in
`muscleonglp-site/index.html` on 2026-09-18). The page currently also shows
a time-boxed free bonus ("through September 30") — deliberately **not**
included in this copy. This sequence runs indefinitely once configured, and
a hardcoded date would be wrong for anyone who signs up after it passes. The
`#pricing` link is the single source of truth for whatever bonus is live
when the reader actually clicks; if a future promo should be pushed
specifically through this sequence, that is a separate, explicit edit to
make at that time, not something to bake in now.

### Dependency between the two parts

Email 4's closing line ("you'll keep getting the free articles and research
roundups either way") assumes §1 is live. If §1 ships later than §2, or
either part gets descoped independently, drop that clause from Email 4
until §1 is confirmed live — otherwise it's a promise the system isn't
keeping yet.

### Sender identity

Signed "MuscleOnGLP," not a named person — matches the site's existing
deliberate faceless/brand-only positioning (see
[[muscleonglp-marketing]]: "Owner wants it faceless/brand-only, NOT a
named-expert byline").

### Open item

Same as §1: confirm the Buttondown plan covers Automations before
configuring this.

---

## What's code vs. what's configuration

Being explicit about this since it's unusual for a spec to be this
code-light:

- **Code** (the only part `writing-plans` needs to turn into an
  implementation plan): the RSS feed addition to `publisher.py`, §1.
- **Dashboard configuration** (Ben, in Buttondown — no code, this spec's
  steps above are the instructions): RSS-to-email settings (§1), the
  Automation itself and its three email bodies (§2, copy above ready to
  paste in).
- **Blocked on account access this scan can't verify**: whether the current
  Buttondown plan includes both paid features (§0.4).

## Tests

- Unit: RSS feed generation produces valid, well-formed XML from a fixture
  manifest (reuse whatever fixture pattern `test_muscleonglp_*` in
  `backend/tests/` already uses for `research_digest`, if any exist there —
  check before writing a new one).
- Unit: feed entries use the same `post_url()` the hub page and sitemap
  already use, so a URL format change anywhere doesn't silently diverge
  between the three.
- Live: once deployed, fetch `https://getmuscleonglp.com/research/feed.xml`
  and validate it against Buttondown's actual RSS parser expectations
  (their docs don't specify exact requirements beyond "standard RSS" — a
  real fetch-and-eyeball check after the next Monday publish is the
  practical verification here, not something to over-engineer a test for).
