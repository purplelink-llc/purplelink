# Contest finder: discovery, terms check and prefilled entries

Status: reviewed (EGM Goldfish review, four Sonnet reviewers, 2026-11-02), resolved and built in the same change.
Owner: Ben. Where the built version differs from draft 1, the section "Changes after review" wins. Review log at the end.

## Concepts brief

**Problem.** Ben asked to "automatically sign up for contests". Photo contests, app awards, pitch competitions and
small-business grants turn up all year, each with its own deadline, fee and terms, and the terms are where the cost
hides. The reference case is the Sony World Photography Awards Single Image competition (run by Creo). Its 2027
rules, clause 7.2, grant a non-exclusive, irrevocable, worldwide licence on "any image submitted", not only winners,
for three years after the April 2027 announcement, and 7.2(h) adds that an image put in a device gallery stays there
"perpetually" and royalty free. The September 2026 shortlist had marked Sony "no rights grab"; a person reading it
missed both the scope (every entry) and the perpetual tail.

**What is automated and what is not.** Fully automatic entry is out. Many contest rules forbid automated or
third-party entry or require the entrant to be the author entering in their own name, and an agent may not create
accounts, accept terms, pay fees or solve CAPTCHAs. So the finder does everything up to the submit button and stops:

1. finds open contests every week from stable sources, dedupes them and tracks deadlines;
2. reads each contest's terms and flags the fee, eligibility, AI rules, the licence and any ban on automated entry;
3. scores each one and picks the few worth entering;
4. prepares those entries (photos or product materials, statements, a checklist) so Ben only signs in, checks and
   clicks submit;
5. records candidates, entries and results in the marketing hub and queues an approval item for each pick.

**Success measure.** After 12 weekly runs (2027-01-25): Ben has entered at least 4 contests from the digest, no entry
went in with an unflagged all-entries or perpetual licence, and each entry has a result recorded. Stop rule: if Ben
enters none of the picks in those 12 weeks, the weekly job is turned off and the code stays for manual use.

**Boundaries.** Nothing outward. The finder fetches public pages with plain GET requests and writes private files and
local queue items. It never signs in, submits, pays, accepts terms, uploads or contacts an organiser. It never
touches the originals in Ben's photo library: it reads metadata and copies files into the entry folder. Anything run
by or involving Georgia State University is dropped at discovery and never shown.

## What exists today

- `docs/photo-licensing/contests-shortlist.md` (git-ignored): a hand-researched table of 13 photo contests from
  2026-09-24 with fee, prize, AI rules, stock rules and a "rights grab?" column. It is the seed list and the model for
  the terms check, but it is a one-off and already stale (four of its deadlines have passed).
- `scripts/hub/hub.py`: the marketing hub. `import` rebuilds `~/.purplelink/hub/hub.sqlite` from sources
  (`from_queue`, `from_social`, `from_outreach`, `from_videos`, `from_app_releases`, `from_macupdate`,
  `from_campaigns`); `utm URL --asset A --channel C` makes a link with a `utm_content` no placement uses.
- `scripts/queue/approval_queue.py`: one markdown file per decision in `~/.purplelink/queue/<folder>/`. `new FILE`
  lints an item into `pending/` or `needs-work/`. Kind `submission` is outward, and `executor: ben` is the only fit
  here. Lint requires the sections Ask, Why now, Draft, Verify, If approved, If rejected, Evidence, rejects em dashes,
  emoji and banned phrases in the draft, and needs a `utm_source` plus unique `utm_content` on every purplelink.llc
  link.
- Photo metadata, git-ignored, in `photo-licensing-workspace/`: `alamy-metadata.csv` (filename, caption, tags,
  title, editorial flag; about 600 rows) and the Alamy export `exports/BenjaminAmpel_*.csv` (adds location, date
  taken, number of people, releases). The originals are JPEGs in `/Volumes/Extreme SSD/Nikon Photos/` (965 files).
- Product facts: `site/llms.txt` (one section per product with price and summary) and the product pages under
  `site/<product>/` with their screenshots.
- Scheduled jobs run repo code through `~/.purplelink/bin/repo-ro.sh exec`, from a worktree that sits at origin/main,
  wrapped in `~/.purplelink/run-when-online.sh`. Git-ignored data is addressed by absolute path or environment
  variable, since the job worktree does not have it.

## Goals and non-goals

Goals:
1. A weekly scan that finds open contests in four groups: photography (travel, landscape, wildlife, architecture),
   app and software awards, indie and startup pitch competitions, and small-business and creator grants.
2. One record per contest across weeks and sources, with a deadline, and never a second listing for a contest Ben
   entered or rejected.
3. A terms check that flags broad licences, at least on the Creo terms, and says which claims it could not verify.
4. A score that ranks contests by expected value minus rights cost and fees, with every input visible.
5. Two or more fully prefilled entries per run when anything qualifies.
6. Every picked contest, entry and result visible in the hub; a private weekly digest; queue items for the picks.

Non-goals:
- Submitting, signing in, creating accounts, paying, accepting terms, solving CAPTCHAs. These stay Ben's steps.
- Reading terms with an LLM. The check is rules over text, so it is deterministic and testable. A human (Ben, or a
  Claude session he asks) reads the terms of anything he decides to enter; the flags tell him where to look.
- Crawling search engines or scraping sites that block automated fetches.
- Judging photo quality. Photo choice is by subject fit and rule fit (capture date, people, editorial); Ben picks
  the final frames from a short list.

## Design

### Files

| Path | Tracked | What |
|---|---|---|
| `scripts/contests/contests.py` | yes | the CLI and all logic; stdlib only, like `hub.py` |
| `scripts/contests/sources.json` | yes | the registry: known contests (official pages) and listing feeds |
| `scripts/contests/profile.json` | yes | what Purplelink can enter: themes, products, country, business type, scoring weights |
| `site-tests/test_contest_finder.py` | yes | offline tests, run by Site tests in CI |
| `site-tests/fixtures/contests/` | yes | page fixtures, including a Creo-style licence clause |
| `scripts/contests/com.purplelink.contest-finder.plist` | yes | the weekly launchd job |
| `~/.purplelink/contests/ledger.json` | no | the state: one record per contest, with history (`PURPLELINK_CONTESTS`) |
| `~/.purplelink/contests/pages/` | no | the last fetched text of each page, for change detection |
| `docs/growth-briefs/contests/digest-YYYY-MM-DD.md` | no (git-ignored) | the weekly digest |
| `docs/growth-briefs/contests/entries/<id>/` | no | a prefilled entry: `entry.md`, copied photos or product files |

The registry is public information (contest names and official URLs), so it is tracked. Everything about Ben's
choices, entries and results is private and stays under `~/.purplelink/` or `docs/growth-briefs/`.

### Commands

```
contests.py scan [--offline] [--only ID]   fetch registry pages and feeds, update the ledger
contests.py list [--status S] [--all]      the ledger, ranked
contests.py show ID                        one contest: terms flags, score inputs, history
contests.py digest [--write]               the weekly digest (top 5, deadlines, red flags, changes)
contests.py prefill ID [--n 5]             build the entry folder for one contest
contests.py queue ID                       write and lint an approval-queue item for a prefilled entry
contests.py mark ID STATUS [--note T] [--url U]   entered, skipped, rejected (by Ben), shortlisted, won, lost
contests.py weekly                         scan, digest --write, prefill and queue the top picks (the launchd job)
```

A contest is added by hand by adding a registry entry to `sources.json` (a reviewed change), not by a command.

### Discovery

Two kinds of source in `sources.json`:

- **Registry entries**: a known contest with its official rules page, category, themes and a `cadence`
  (`annual`, `rolling`, `nomination`). The seed is the photo contests in the shortlist plus the app awards, pitch
  competitions and grants found on 2026-11-02. Each entry also carries the facts a person read, with the date read
  (`read: 2026-11-02`): deadline, fee, prize, licence summary. A contest's page is fetched each week; the text is
  reduced to plain words and hashed. A changed hash re-runs the terms check and is listed under "Changed this week"
  in the digest, because organisers change fees and terms between editions.
- **Feeds** (dropped from v1 after review): every curated listing probed on 2026-11-02 refused automated reads
  (contestwatchers, photocontestinsider, photocompetitions, lensculture, grantwatch: 403, 523 or timeouts). New
  contests come instead from research passes saved as JSON arrays in `~/.purplelink/contests/proposals/`; the
  digest lists them under "Found by research, not in the registry yet" and they are never picked until a person reads
  the rules and adds a registry entry.

Fetching is plain `urllib` GET with a descriptive User-Agent, a 20 s timeout, at most one request per host per second,
and one retry. A 403 or a bot-check page is recorded as `fetch: blocked`, not as a change, and the previous text is
kept. Nothing is fetched behind a sign-in.

**Dedupe.** A contest's key is its normalised name: lower case, edition markers removed (years, ordinals such as
"24th", bare edition numbers), "awards/award", "competition/contest", "photographer of the year/poty" folded,
leading "the" and punctuation dropped. Two records are the same contest when their keys match, when their canonical
URLs (host without `www`, path without trailing slash or query) match, or when the keys are at least 0.92 similar
(difflib) and the hosts match. An edition lives inside the record (`edition: 2027`), so next year's edition updates
the same record and keeps the history of past entries and results.

**Deadlines.** `parse_deadline(text, today)` finds dates near deadline words ("deadline", "closes", "closing",
"entries close", "submit by", "until", "ends"). It reads ISO dates, "1 December 2026", "December 1, 2026", "Dec. 1st
2026" and "1st Dec 2026", with an optional time and zone kept as a note. Numeric dates with slashes are read only
when they are unambiguous (one part above 12); otherwise they are ignored. When several dates qualify, the earliest
date on or after today wins, and dates next to "early bird" are kept separately. A date with no year takes the next
occurrence. The result carries `deadline_source`: `page` (parsed this week), `registry` (read by a person) or
`expected` (last edition's date plus a year). The registry date wins when the page date disagrees by more than 60
days, and both are shown. A deadline past today moves the record to `closed` until a new edition appears.

**Filters.** Dropped before scoring, with the reason kept: past deadline; not open to a US entrant or a US LLC; run
by or involving Georgia State University (any of "Georgia State", "GSU", "gsu.edu" in the name, organiser or URL);
Ben's status `entered`, `rejected` or `skipped` for this edition. `rejected` means Ben said no and is kept across
editions unless he clears it.

### Terms check

`check_terms(text)` returns flags, each with a severity, the rule that fired and the matching sentence (cut to 25
words, for Ben's eyes only; it is never published). A licence sentence is one that contains "licen[cs]e", "grant",
"right to use", "permission to use" or a clause continuing a grant (a lettered item under one). The rules:

| Flag | Fires on | Severity |
|---|---|---|
| `licence_all_entries` | a licence sentence whose subject is every entrant or entry ("each entrant grants", "all entries", "any image submitted", "by entering ... you grant") and that does not limit it to winners, finalists or shortlisted entries | high |
| `irrevocable` | "irrevocable" in a licence sentence | medium |
| `perpetual` | "perpetual", "perpetually", "in perpetuity", "without time limit" in a licence sentence | high |
| `worldwide` | "worldwide", "throughout the world" | low |
| `sublicensable` | "sub-licens", "sublicens", "transferable" | medium |
| `commercial_use` | "any purpose", "commercial", "merchandise", "products", "sold" in a licence sentence, not negated | high (medium when "following agreement" or "separate agreement" qualifies it) |
| `royalty_free` | "royalty free", "without payment", "no fee", "without compensation" in a licence sentence | low |
| `copyright_transfer` | "assign", "transfer of copyright", "becomes the property of" | severe |
| `exclusive` | "exclusive licence/license" not preceded by "non-" | severe |
| `moral_rights_waiver` | "waive ... moral rights" | medium |
| `term_years` | "for N years", "N-year", "period of N years" in a licence sentence; N is kept | info |
| `automated_entry_banned` | "automated", "bot", "script", "bulk", "third party", "on behalf of" in an entry sentence with "not", "prohibited", "permitted only", "void" or "disqualif" | info (the finder never automates entry anyway) |
| `ai_rules` | "artificial intelligence", "AI-generated", "generative", "computer generated", "AI tools", "upscal" | info, with the sentence |
| `fee` | "free to enter", "no entry fee", or an amount with a currency near "fee", "per image", "per entry" | parsed into `fee_usd` |
| `eligibility` | "open to", "residents of", "excluding", "must be", "aged" | info, with the sentence; the United States in an exclusion sets `us_eligible: false` |

The flagger splits text into sentences, so a "winners only" limit in the same sentence suppresses
`licence_all_entries`; a limit in a separate sentence does not, and the flag notes "check scope". That keeps the
check biased toward flagging. A page with no licence sentence at all gets `licence_not_found` (high), because
silence is not safety.

The Creo test fixture is a paraphrase of the Sony 2027 rules clause 7 in the same structure (7.1 copyright kept, 7.2
grant on any image submitted, lettered uses (a) to (h), 7.2(h) perpetual device gallery), with the trigger phrases
kept. It must produce `licence_all_entries`, `irrevocable`, `worldwide`, `perpetual`, `term_years` (3), and a
medium `commercial_use` (products only after individual agreement).

**Rights cost.** Flags turn into a cost in dollars, because the score is in dollars:
`rights_cost = images × value_per_image × multiplier`. `value_per_image` is set in `profile.json` (photo: $40, a
rough two-year stock and print revenue for a good frame; product materials: $0, since screenshots and descriptions
are meant to spread). The multiplier sums the flags: all-entries 1.0 (0.1 when limited to winners), perpetual 1.0,
commercial use 1.5 (0.5 when it needs a separate agreement), sub-licensable 0.3, irrevocable 0.2. Copyright
transfer or an exclusive licence excludes the contest unless Ben overrides it in its registry entry. The weights live
in `profile.json` so they can be tuned without code changes.

**Verification state.** Every terms field says where it came from: `page` (parsed from the fetched page this week),
`registry` (read by a person, with the date), or `unknown`. The digest marks anything not `page` or a registry read
within 60 days as "check before entering".

### Score

```
ev     = prize_usd × odds × fit
score  = ev + exposure_usd − fee_usd − rights_cost
```

- `prize_usd`: top cash prize plus half the category prize (when the entry can win one). Grants use the grant
  amount. Prizes in goods count at 50%.
- `odds`: a prior per group in `profile.json` (large international photo contest 1/3000, small or new contest
  1/400, grant 1/2000, app award 1/500, pitch 1/200), multiplied by the number of images entered for photo contests
  (each image is a ticket), capped at 5.
- `fit`: 0 to 1. The share of the contest's themes that the profile covers, halved when the eligible material is
  thin (fewer than 3 matching photos, or no product for an app award's platform).
- `exposure_usd`: a small fixed value for awards whose listing alone brings traffic (Apple Design Awards, Webby,
  Product Hunt), set in the registry entry; 0 otherwise.
- Contests with a deadline within 3 days are shown but not picked: there is no time for Ben to review.

The score is a ranking aid, not a forecast. The digest shows the inputs beside the number so a wrong prior is easy to
spot.

### Prefilled entries

`prefill ID` writes `docs/growth-briefs/contests/entries/<id>-<edition>/`:

- **Photo contests.** Photos are matched from `alamy-metadata.csv` (caption, tags, title) joined to the Alamy export
  by filename (location, date taken, people). A photo is eligible when its file exists in the library, it is not
  editorial (editorial captions name events and people), it has no people, and it meets the contest's capture-date
  rule (`taken_from`/`taken_to` in the registry; the Sony Single Image needs 2026 captures). It is scored by
  overlap between its tags and the contest's theme words, and the top N (5 by default, or the entry limit) are
  picked, at most two from the same location so the set is varied. Each pick is copied with `shutil.copy2` into
  `photos/`: the original is opened for reading only, never moved or written. When the contest gives a size limit,
  `sips` resizes the copy. `entry.md` lists each pick with its source path, title, caption and why it fits.
- **App awards, pitches and grants.** The product is chosen by the contest's themes (LaTeX and academic: ModernTex;
  privacy: Outbound Veil; general Mac app awards: the registry entry names it). The entry takes the product's
  section from `site/llms.txt`, lists its screenshots from `site/<product>/`, and makes a link with the hub's
  `make_utm` (`channel: contest`, `source: <contest id>`).
- **Statements.** Short, calm and plain, in the site's voice: what the photo shows and where, or what the app does
  and for whom. No superlatives, no em dashes, no emoji; the approval-queue lint runs on them. Photo statements
  disclose processing (denoise, sharpening) where the rules ask.
- **Checklist.** Generated from the flags: the rules URL to re-read, the fee and how to pay it, the account Ben needs,
  the image specs, the declarations to make (processing, capture date), the red flags to accept or walk away from,
  and the deadline with its time zone. The last item is always "Ben: submit, then run `contests.py mark ID entered
  --url <confirmation>`".

### Queue, hub and digest

- `queue ID` writes an approval item: `kind: submission`, `executor: ben`, `job: contest-finder`, `target: <contest
  name> (<url>)`, `contest: <id>`, `expires: <deadline>`, risk from the worst flag. Its Draft is the entry statement,
  its Verify names the rules URL and the date the terms were read, and its Evidence is the entry folder path. It goes
  through `approval_queue.py new`, so the normal lint decides pending or needs-work. Approving it means only "Ben
  will enter this"; the entry itself is still Ben's click.
- The hub gets one new source, `from_contests`, that reads the ledger: one placement per contest edition that was
  picked, queued, entered or decided (`channel: contest`; status `candidate` when picked, `queued`, `live` once
  entered, `won`, `shortlisted` or `not-placed` after the result), with the result in the results table
  (`contest_result`: 1 won, 0.5 shortlisted or finalist, 0 not placed) and any prize as `contest_prize_usd`. Queue
  items with `job: contest-finder` are skipped by `from_queue`, so a contest is not counted twice; the contest
  placement keeps the queue id in `approval`. Candidates that were never picked are not placements; they stay in the
  ledger only.
- `digest --write` writes `digest-YYYY-MM-DD.md`: the top 5 with deadline, fee, prize, score and red flags;
  deadlines in the next 30 days; new this week; changed terms; entries waiting on results; and what was dropped and
  why.

### Scheduling

`com.purplelink.contest-finder` runs `contests.py weekly` on Mondays at 06:40 local time through
`run-when-online.sh` and `repo-ro.sh exec`, with `PURPLELINK_CONTEST_BRIEFS` set to the shared checkout's
`docs/growth-briefs/contests` and `PURPLELINK_PHOTO_WORKSPACE` to its `photo-licensing-workspace`. A second slot at
09:40 runs only if the first did not finish (a stamp per ISO week). It logs to
`~/Library/Logs/purplelink-contest-finder.log`. `weekly` never re-queues a contest that already has a queue item for
the same edition.

## Failure modes

| Failure | Effect | Handling |
|---|---|---|
| A page blocks automated fetches | no fresh terms | kept text and `fetch: blocked`; the digest says "terms not re-read since DATE" |
| The organiser changes the terms after the read | wrong flags | hash change re-runs the check and shows in "Changed this week"; the checklist's first item is to re-read the rules |
| The deadline parser picks the wrong date | missed deadline | the registry date wins on a large disagreement; both are shown |
| A licence limit is in a separate sentence | over-flagging | accepted: the flag says "check scope" |
| A licence uses wording no rule knows | under-flagging | `licence_not_found` when no licence sentence is found |
| Photo metadata is missing or stale | weak picks | Ben picks from the short list; the entry lists the source file of each pick |
| A feed floods with off-theme items | noise | the theme filter; feed candidates are never prefilled |

## Rollback

Unload the launchd job and delete `scripts/contests/`. The hub source is one function and one `build()` line; without
a ledger it adds nothing. The ledger and digests are private files that can be deleted.

## Changes after review

The build follows the reviewers where the fix was clear. These replace the matching parts of draft 1 above.

**Rights gate on by default.** An all-entries licence that is also perpetual, any copyright transfer, or an exclusive
licence keeps a contest out of the picks. `"allow_rights": true` on a registry entry lifts it for that contest.
This was open trade-off 2; the reviewers argued (correctly) that the Sony case is exactly a free contest that a score
would keep positive.

**Scope travels with clauses.** Rules text is split into sentences and numbered or lettered items (`7.2`, `(4)`,
`(h)`). An item inherits the licence context and the scope of the grant above it, so Sony's 7.2(h) is a perpetual
flag on every entry, and the items under Wildlife Photographer of the Year's rule 8(5) ("any photograph you submit
that wins an Award") are winners-only. "The chance to win" is not a winners-only limit. `non-commercial`, a
negation in the six words before a trigger, and "we will seek your permission" all lower or clear the commercial
flag. Whole-word matching throughout.

**Rights cost.** `images x value_per_image x min(uses, cap)`. `uses` starts at `base_use` (0.25: judging and
promotion) and adds perpetual 1.0, commercial 1.5 (0.1 when it needs Ben's separate agreement), sub-licensable 0.3,
irrevocable 0.2. Each counts in full when it applies to every entry and at 0.1 when it applies to winners only.
No licence wording found costs 0.5 on every entry. Cap 3.

**Unknown is not free or safe.** An unknown fee leaves a contest unscored and unpicked. A deadline that is expected,
rolling or unknown is never picked. Unknown US eligibility is never picked. Exposure value is shown beside the score,
never added to it.

**Pick rule.** Status `open`, in the registry, a verified deadline at least 3 days away, open now, no rights gate, US
eligibility confirmed, and a score above `min_score` (-40: the largest expected loss per entry treated as an
acceptable lottery ticket). Up to 3 a week, best score first.

**Deadlines.** The registry date is authoritative. A page date that differs is a warning; when the registry date has
passed and the page shows a later one, the page date is used and the digest asks for a re-read. "until" and "ends"
are not deadline labels. A yearless date that has passed this year is read as next year only within 120 days.

**Dedupe.** Exact matches only merge (id, normalised name, canonical URL with the query kept). A near match (same
host, 0.92 similar) is listed under "Possible duplicates" and never merged, because a false merge would hand one
contest another's entered or rejected status.

**Photos.** Originals are copied with `shutil.copy2`; the copy's destination must resolve outside the library, and
`sips` and `exiftool` (GPS removal) only ever touch the copy. Picks skip editorial images, people, Alamy-exclusive
images, capture dates outside the contest's window (EXIF `DateTimeOriginal`, then the Alamy export date), and, when
the rules require wild subjects (`non-captive` in the text, or `wild_only` in the registry), any caption or tag that
mentions a zoo, exhibit, garden or farm. That last rule was added after the first real Wildlife Photographer of the
Year picks included a poison dart frog "in a rainforest exhibit".

**Queue items.** All of `approval_queue.py`'s required fields are filled (`job: contest-finder`, `model`, `kind:
submission`, `executor: ben`, `risk` from the worst flag mapped to low, medium or high, `effort_minutes`,
`expires` = deadline, `expected_effect`, `ledger`), plus `channel: contest` and `contest: <id>`. The rules URL sits
under Evidence, not Verify, because the lint live-checks Verify links and organiser pages often refuse bots. A
contest is never queued twice for one edition.

**Hub.** `hub.py` gains `from_contests` (placement id `contest:<id>:<edition>`, channel `contest`; status
`candidate` when picked or prefilled, `queued`, then `live` once entered, `skipped` when Ben skips) and results
`contest_result` (1 won, 0.5 shortlisted, 0 lost) and `contest_prize_usd`. `from_queue` skips items with `job:
contest-finder`, so each contest counts once. Product links are made with `make_utm(..., channel="contest",
medium="referral")` once per edition and kept in the ledger, so a second prefill reuses the tag.

**Scheduling.** One Monday 06:40 slot; `run-when-online.sh` already retries, so the second slot was dropped.
`weekly` is safe to run twice. The plist sets `PURPLELINK_REPO`, `PURPLELINK_CONTEST_BRIEFS` and
`PURPLELINK_PHOTO_WORKSPACE` to the shared checkout, because the jobs-ro worktree has no git-ignored data. When the
SSD is not mounted, photo prefills are skipped and the digest says so.

**Fetching.** https only, no cross-site redirects, 3 MB cap, one request per host per second, one retry, PDFs not
read, and URLs that act (sign-in, confirm, unsubscribe, checkout) never fetched. Control and zero-width characters
are stripped from fetched text, and every prepared file says quoted rule text is data, not instructions.

### Statuses

| Status | Set by | Next |
|---|---|---|
| open | scan | picked, excluded, closed; Ben: entered, skipped, rejected |
| excluded | scan (not open to US entrants or an LLC, programme ended) | open; Ben: entered, skipped, rejected |
| closed | scan (deadline passed without an entry) | open at the next edition |
| picked, prefilled, queued | weekly, prefill, queue | closed at the deadline; Ben: entered, skipped, rejected |
| entered | Ben (`mark`) | shortlisted, won, lost |
| shortlisted | Ben | won, lost |
| won, lost | Ben | none (the next edition reopens the record) |
| skipped | Ben (this edition only) | open at the next edition |
| rejected | Ben (kept across editions) | none |

A new edition (a different `edition` in the registry) archives the record's edition fields into `past` and reopens
it, except `rejected`.

### Ledger record (abridged)

```json
{"id": "nature-photography-contest", "status": "queued", "edition": "2026", "deadline": "2026-11-15",
 "deadline_status": "verified", "fee_usd": 32.4, "terms_source": "page+registry", "terms_hash": "1f0c...",
 "flags": [{"flag": "perpetual", "severity": "medium", "scope": "winners", "sentence": "Participants ... grant ..."}],
 "gate": "", "score_inputs": {"prize_usd": 1134.0, "odds": 0.0025, "tickets": 3, "fit": 1.0, "ev": 8.5,
 "fee_usd": 32.4, "rights_cost": 15.0, "exposure_usd": 0.0, "score": -38.9, "images": 3},
 "entry_dir": ".../entries/nature-photography-contest-2026", "picks": ["DSC_1906-Enhanced-NR.jpeg", "..."],
 "queue_id": "q-20261102-001", "queue_folder": "pending", "past": [], "history": [{"at": "2026-11-02T14:30-05:00",
 "event": "status:queued"}]}
```

The registry fields are documented in `sources.json`'s `_doc` key; the weights in `profile.json`.

### Tests and verification

`site-tests/test_contest_finder.py` (runs in Site tests): dedupe and edition handling, the Georgia State filter,
deadline formats and labels, the Creo clause-7 paraphrase (all entries, irrevocable, worldwide, three years,
perpetual 7.2(h), products only by agreement, non-commercial viewing not flagged), winners-only, rights-grab and
no-licence fixtures, the score formula and pick rule, status transitions, photo rules (wild-only, capture dates),
an end-to-end `weekly` with a fake fetcher (originals byte-identical afterwards, no second queue item on a re-run),
the product entry and its tag, the hub source and the queue lint. First real run, 2026-11-02: 27 registry entries,
24 pages read (3 refused), one pick, two prefilled entries, two pending queue items, three hub placements.

## Open trade-offs for Ben (after review)

1. **`min_score` -40 and the $40 per image.** On these priors almost every paid contest has a negative expected
   value; -40 lets a cheap entry through. Raise it to 0 to enter only free contests, as the photography plan's idea
   10 suggested.
2. **The Sony site-wide terms.** Clause 4 of worldphoto.org's general terms says any material sent through the site
   becomes WPO's property. The competition rules defer to their own clause 7, so it probably does not reach entries,
   but the flagger reports it as a copyright transfer. Worth one read.
3. **New-contest discovery.** No listing feed allows automated reads, so new contests arrive through research
   passes into `proposals/`. A monthly Sonnet research task would keep that going; it costs tokens each run and is not
   set up.
4. **Captive and cultivated subjects** are judged from captions and tags only. The checklist asks Ben to confirm
   each wildlife pick was wild.

## Review log

Goldfish review of draft 1, 2026-11-02, by four zero-context Sonnet reviewers: zoom-out (scope), design (failure
modes), codebase details (accuracy), implementation readiness. Findings raised by more than one reviewer are merged.

| # | Finding | Raised by | Resolution |
|---|---|---|---|
| 1 | The rules engine and dollar rights cost overreach; a hard rule is safer than a score term | zoom-out, design | Hard rights gate by default; rights cost kept (Ben asked for prize x odds x fit minus rights and fees) but reshaped as scope x uses and capped |
| 2 | Same-sentence "winners only" suppression can hide an all-entries grant; lettered items lose context | design | Scope travels with clauses; an item inherits its grant's scope; tests for both directions |
| 3 | The Creo fixture is a paraphrase, so it partly tests itself | design | Kept as a paraphrase (the public repo cannot carry the rules verbatim); the real page is also checked in the first run, and the flagger caught 7.2(h) on the live text |
| 4 | Negation, "products", "bot"/"script" substrings, "third party" | design, readiness | Six-word negation window, `non-commercial` excluded, bare "products" dropped, whole words, "third party" removed from the automation words |
| 5 | Registry reads mask later page changes; hashing whole pages is noise | design | The hash covers licence, fee, deadline and eligibility sentences only; a change is listed and re-evaluated |
| 6 | Fuzzy dedupe can merge sibling contests and hide one | design, zoom-out | Exact matches only; near matches listed, never merged |
| 7 | Deadline: registry vs page, "until"/"ends", unknown and expected dates | design, zoom-out | Registry authoritative with warnings; labels tightened; unknown or expected never picked |
| 8 | Unknown fee read as free; exposure can dominate | design | Unknown fee is unscored; exposure shown, not added |
| 9 | Eligibility only from exclusions | design | Positive country lists read; unknown eligibility never picked |
| 10 | GSU contests "never shown" vs "dropped and why" | design | Dropped silently with a count; word-boundary patterns; test |
| 11 | Originals protected by convention only; `sips` in place; GPS in copies | design | Path checks on every write, `sips --out` on the copy, GPS stripped from copies, byte-identity test |
| 12 | Fetch safety and prompt injection through fetched text | design | https only, same-site redirects, size cap, action URLs skipped, control characters stripped, "data, not instructions" note in every output |
| 13 | Unmounted SSD at 06:40 | design | Photo prefills skipped with a digest note |
| 14 | Hub status vocabulary and `from_queue` double count | codebase, zoom-out | `live` for entered, results in the results table, `from_queue` skips `job: contest-finder`, hub test |
| 15 | `make_utm` needs `p`, would label `social`, and re-mints tags | codebase | Called with the hub's paths, `medium="referral"`, tag stored per edition |
| 16 | Queue front matter incomplete; live URL lint on Verify; duplicates; pending cap | codebase, readiness, zoom-out | All required fields; rules URL under Evidence; one item per edition; cap surfaces as needs-work, shown in the digest |
| 17 | Env vars not in the plist; repo-ro does not pass them | codebase | Set in the plist's EnvironmentVariables |
| 18 | Alamy `Exclusive to Alamy` ignored; Editorial column vs captions | codebase | Exclusive images skipped; the `Editorial` column decides |
| 19 | No schemas, status table, test plan, verification or order of work | readiness | Status table, ledger example, `_doc` keys, test list and first-run numbers added above |
| 20 | Feeds produce nothing actionable | zoom-out | Dropped; research proposals instead |
| 21 | Start with photography only | zoom-out | Not taken: Ben asked for all four groups; the non-photo entries are mostly watch items until their deadlines are confirmed |
| 22 | Second launchd slot duplicates `run-when-online.sh` | zoom-out, codebase | Dropped |
| 23 | Measure whether the flags matched the terms | design | `mark ... entered --terms-matched yes|no` records Ben's check |
