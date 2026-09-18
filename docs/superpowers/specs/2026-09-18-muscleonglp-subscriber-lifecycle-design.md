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

4. **Revision 2026-09-18: Buttondown's own automatic triggers are paid
   add-ons ($9/mo RSS-to-email, $29/mo Automations) — but sending itself is
   free, so this spec now does its own triggering instead of paying for
   theirs.** Checked the account directly: `POST /v1/emails` returns `201`
   with `should_trigger_pay_per_email_billing: false` on the current (free)
   plan, and per-subscriber tagging is already live in production
   (`subscribe.mjs` has been tagging every signup since launch). What's
   gated is specifically Buttondown deciding *when* to fire on its own; we
   already have working cron infrastructure in both repos (the Modal
   pipeline for §1, a new Netlify Scheduled Function for §2) that can decide
   the timing instead and just call Buttondown's send API directly. Full
   mechanics — confirmed against Buttondown's real OpenAPI schema
   (`api.buttondown.email/v1/openapi.json`), not scraped docs — in §1 and §2
   below. **Net cost: $0/month.**

   Also checked the account's actual current audience while verifying this:
   **3 subscribers total, 2 of them Ben's own test addresses.** One real
   subscriber. Both parts of this spec are worth building because they're
   now free and the content/copy work is done either way, but list *growth*
   is the real bottleneck, not send capability — see the follow-up note at
   the end of this spec.

---

## 1. Weekly roundup → subscriber broadcast

### Approach: the Modal job sends it directly via the Buttondown API

No RSS feed, no RSS-to-email add-on. `mailer.py` gains a second function,
`notify_subscribers()`, called from `app.py` right after `notify_review()`
on every successful publish. It creates one Buttondown email via
`POST /v1/emails` with no `filters` (the default —
`{"filters": [], "groups": [], "predicate": "and"}` — matches the entire
list, exactly what a broadcast needs) and:

```json
{
  "subject": "<digest.week_label> — GLP-1 & Muscle Research Roundup",
  "body": "<clean HTML built from WeeklyDigest, NOT the site page's HTML — no nav/chrome>",
  "status": "scheduled",
  "publish_date": "<now + 24h, ISO 8601>"
}
```

`status: "scheduled"` with a future `publish_date` is what makes Buttondown
send it automatically at that time with no further action — confirmed
against the real `EmailInput`/`EmailStatus` schema, not guessed. The 24h
delay preserves the same review buffer §1 always intended: Ben's existing
`notify_review()` email still arrives immediately, so anything worth
pulling can be pulled before the public send goes out the next day.

Body content: a short, email-native HTML rendering of the `WeeklyDigest` —
intro, then each `DigestItem`'s title/venue/summary/link — in the same
inline-styled, no-external-CSS style `notify_review()`'s `body` string
already uses (email clients don't load stylesheets), not a reuse of
`renderer.py`'s full page HTML (which includes nav, footer, and JSON-LD
meant for a browser, not an inbox).

### Requirements

- New Modal secret: `buttondown` → `BUTTONDOWN_API_KEY`, added to
  `app.py`'s `@app.function(secrets=[...])` list alongside the existing
  four.
- No RSS feed needed at all — the earlier plan to add `research/feed.xml`
  to `publisher.py` is dropped; this is simpler and gets the real
  structured digest content into the email instead of round-tripping
  through a scraped feed.

### Resolved item

The §0.4 "confirm the plan covers this" open item is now moot for §1 —
sending an email via the API doesn't require any paid add-on.

---

## 2. New-subscriber → Complete Pack sequence

### Approach: a daily Netlify Scheduled Function + Buttondown's per-subscriber send endpoint

Not the $29/mo Automations add-on. Not a tag-filter broadcast either — while
digging into the real API schema for this, found something simpler than
both: `POST /subscribers/{email}/emails/{email_id}` — "Send a specific
email to a specific subscriber," no request body, no tag-ID resolution, no
filter-group JSON to build. This is a much cleaner primitive than what was
originally planned around Automations.

**One-time setup** (done once, not part of the daily job): create three
Buttondown emails via `POST /v1/emails` with `status: "draft"` (so they
never broadcast on their own), one per stage, body = the final copy below.
Record the three returned `id`s (`em_...`) as config in the new function.

**New file**: `muscleonglp-site/netlify/functions/subscriber-sequence.mjs`,
`export const config = { schedule: "@daily" }`. For each of the three
stages (day 3 / day 7 / day 12), independently:

1. `GET /subscribers?type=regular&date__end=<now - N days, ISO>&-tag=seqN-sent`
   — `type=regular` excludes anyone unsubscribed/churned/blocked (this is
   what keeps the send list honest without re-implementing suppression
   logic); `date__end` catches everyone who *crossed* the threshold, not
   just those exactly N days old today, so a missed run self-heals instead
   of permanently skipping someone; `-tag=seqN-sent` excludes anyone this
   stage has already reached. All three filters are real, documented query
   parameters on `GET /subscribers` — confirmed against the schema, not
   assumed.
2. For each subscriber returned: `POST /subscribers/{email}/emails/{em_id}`
   (send), then `PATCH /subscribers/{email}` with `tags` set to their
   existing tags array plus `seqN-sent` (mark done). A `409` from the send
   call means Buttondown itself already considers this email sent to this
   person — treat that as success and still apply the tag, rather than
   erroring the run.
3. Nothing to do if step 1 returns no results — the common case at current
   volume, and cheap to check.

No tag-ID lookups, no `EmailFilterGroup` construction, no dependency on the
$29/mo Automations product at all — three plain REST calls per eligible
subscriber, using only what's confirmed free on this account today.

### Requirements

- `BUTTONDOWN_API_KEY` is already set on the muscleonglp Netlify site (used
  today by `subscribe.mjs`) — no new secret needed.
- The three draft email IDs from one-time setup need to live somewhere the
  function reads them from — plain constants in the file are fine at this
  scale; move to env vars only if that ever gets awkward to redeploy for.

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

None — resolved by the endpoint discovery above. No paid feature, no
account/billing question left blocking this.

---

## What's code vs. what's configuration

Revised now that both parts are code-driven instead of dashboard-driven:

- **Code**: `notify_subscribers()` in `mailer.py` + the new Modal secret
  wiring (§1); the new `subscriber-sequence.mjs` scheduled function (§2).
- **One-time setup, via the API, not the dashboard** (can be done directly
  with `curl` + the existing `BUTTONDOWN_API_KEY` — no Buttondown UI
  needed): create the three draft emails for §2 and record their IDs.
- **Nothing left gated on Buttondown account/billing access.** The
  earlier open items in both sections were about confirming a paid plan
  tier; that's moot now that neither part needs one.

## Tests

- Unit (§1): `notify_subscribers()`'s HTML body renders every `DigestItem`
  from a fixture `WeeklyDigest`, same fixture-style test as whatever
  `test_muscleonglp_*` in `backend/tests/` already uses for
  `research_digest`, if one exists — check before writing a new pattern.
- Unit (§1): the request body sent to `POST /v1/emails` has no `filters`
  key set to anything but the all-subscribers default, and `publish_date`
  is ~24h after the call, not immediate — a regression here would mean the
  review buffer silently stopped existing.
- Unit (§2): the `GET /subscribers` query string for each of the three
  stages has the right `date__end` math (N days back from "now", not from
  the wrong epoch) and always includes `type=regular`.
- Unit (§2): a subscriber who already has `seqN-sent` is excluded from that
  stage's candidate list even when constructed from a fixture that would
  otherwise match on date alone.
- Unit (§2): a `409` from the send call still results in the tag being
  applied (idempotent re-run behavior), not a thrown error.
- Live (§2): after the one-time draft-email setup, manually trigger the
  function once against a real test subscriber (an address like
  `ben+seqtest@purplelink.llc`, matching the existing `ben+magnet-test@`
  pattern already in the account) with a manually-backdated `creation_date`
  or a temporarily-lowered day threshold, and confirm the send actually
  arrives and the tag gets applied — before trusting it against real
  subscribers.
- Live (§1): after the next Monday publish, confirm the scheduled email
  actually appears in the Buttondown dashboard with the right
  `publish_date` and un-filtered audience, before the 24h window elapses
  (so there's still time to cancel it by hand if something rendered wrong).

## Next (explicitly out of scope here)

Both parts of this spec are worth building regardless, since the copy is
done and the send mechanics are now free — but with a real audience of one,
the actual constraint on this whole effort mattering is list growth, not
send capability. That's a separate investigation (why is signup conversion
this low despite capture forms already being on every page and every
article) and a separate spec once this one ships.
