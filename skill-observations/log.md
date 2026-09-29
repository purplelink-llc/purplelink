# Skill Observation Log

Observations captured during task-oriented work. Each entry identifies a
potential skill improvement or new skill opportunity.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created |
DECLINED = user decided not to pursue

---

### Observation 47: Partial staging from HEAD must accumulate, not restart, per file

**Status:** ACTIONED — Applied to finishing-a-development-branch 'Committing in a Shared Dirty Worktree' (build from index, not HEAD) — consolidated instead of a new skill (all-projects skill review 2026-09-28)
**Date:** 2026-09-23
**Session context:** Vitae Plus site work in a repo full of other sessions' uncommitted edits; staged only own hunks by writing HEAD+edit blobs into the index (git add -p unavailable).
**Skill:** New skill candidate: shared-worktree-partial-staging
**Type:** open-source
**Phase/Area:** Committing in a dirty shared worktree

**Issue:** A helper applied an edit to both the working file and `git show HEAD:file`, then staged the result via `git hash-object` + `git update-index --cacheinfo`. Calling it a second time on the same file rebuilt from HEAD again, silently dropping the first call's staged edits. Caught only by inspecting `git diff --cached`. Fixed by staging "working copy with the other sessions' hunks reverted" instead.

**Suggested improvement:** Document a partial-staging recipe: build the index blob from the current index (`git show :file`), not HEAD, when applying successive edits; or derive it once from the final working copy by reverting known foreign hunks. Always finish with `git diff --cached` (own hunks only) and `git diff` (foreign hunks only) checks.

**Principle:** When non-interactive tooling replaces `git add -p`, each staging step must build on the index state, and a two-sided diff check (cached vs unstaged) is the verification that proves only your own hunks are committed.

### Observation 48: Commit only your own edits in a file that already has someone else's uncommitted changes

**Status:** ACTIONED — Applied to finishing-a-development-branch 'Committing in a Shared Dirty Worktree' (partial-staging recipe + two-sided diff) — consolidated instead of a new skill (all-projects skill review 2026-09-28)
**Date:** 2026-09-23
**Session context:** Subagent converting Vitae Plus to a subscription in the Purplelink site repo, where site/privacy/index.html already carried another session's uncommitted asset-hash edits.
**Skill:** New skill candidate: shared-worktree-commit-hygiene (or an addition to finishing-a-development-branch)
**Type:** open-source
**Phase/Area:** Staging and committing in a dirty shared working tree

**Issue:** "Stage only the files you change" breaks down when a file you must edit already has unrelated uncommitted edits: `git add <file>` would commit the other session's work, and interactive `git add -p` is unavailable to agents. The agent applied the same scripted text replacements to both the working-tree file and `git show HEAD:<file>`, wrote the latter with `git hash-object -w --stdin`, and staged it with `git update-index --cacheinfo`. The commit then held only its own hunks, and the other session's edits stayed unstaged in the working tree.

**Suggested improvement:** Document this non-interactive partial-staging recipe (edit as exact-string replacements, apply to HEAD content, hash-object, update-index, then verify with `git diff --cached` and `git diff`) wherever skills tell agents to commit in shared or dirty trees.

**Principle:** When several agents share one working tree, per-file staging is not granular enough. Express edits as replayable replacements so they can be applied to HEAD and staged independently of whatever else is in the file.

### Observation 49: Search-summarised contact emails were wrong or mis-attributed; verify on the org's own page

**Status:** ACTIONED — Applied to competitive-landscape-research 'Contact details for outreach lists' — instead of a new skill (all-projects skill review 2026-09-28)
**Date:** 2026-09-24
**Session context:** Built a direct-licensing pitch list (photo-licensing arm): matched metadata-master.csv subjects to hotels, attractions and tourism boards, found their press or marketing contacts, and drafted pitches
**Skill:** New skill candidate: direct-licensing-outreach (or extend competitive-landscape-research's tiered-source rules)
**Type:** open-source
**Phase/Area:** Contact discovery

**Issue:** The web-search summaries gave confident but wrong contact data. One hotel email came back on a group domain, but the hotel's own site shows a different address. A railway's media email was presented as if it were on the railway's site, when it is only published on the parent holding company's newsroom. One tourism board's emails appear as `name[at]domain`. Several official sites were JS-rendered (React or Cloudflare-blocked), so curl and WebFetch found nothing, and the address only appeared after rendering the page in the browser pane (get_page_text or find "@"). Per-subject metadata keywords were mostly lowercase, so a proper-noun count over keywords missed nearly all named places. Named subjects had to be extracted from titles and descriptions instead.

**Suggested improvement:** For any outreach-list task: (1) accept an email only after seeing it on a page on the organisation's own or parent domain, and record that URL. (2) Use curl or grep first, then the browser pane for JS-rendered or 403 pages. (3) Record "form only" rather than inferring an address. (4) Find named subjects in titles and descriptions as well as keywords. (5) Filter image sets for identifiable people and third-party artwork or trademarks before offering them for marketing use.

**Principle:** A search engine's summary of contact details is only a lead. The source of record is the organisation's own rendered page, and each contact field needs a source URL next to it.

### Observation 50: Summarizer fetch misreads "stock" clauses; raw-text grep of the primary rules page is more reliable

**Status:** ACTIONED — Applied to platform-terms-research Source hierarchy tier 4 + 'Reaching the verbatim text' + pre-flight (all-projects skill review 2026-09-28)
**Date:** 2026-09-24
**Session context:** Building a photo-contest shortlist (docs/photo-licensing/contests-shortlist.md) that required reading ~20 contest rules pages for stock-licensing, rights-grant and AI-processing clauses.
**Skill:** platform-terms-research
**Type:** open-source
**Phase/Area:** Source hierarchy / reading the primary document

**Issue:** The WebFetch small-model summary of the Epson Pano Awards rules reported "Previously Published/Stock Images: Explicitly prohibited", but the actual clause only bans purchased third-party stock *elements* inside an entry — the entrant's own stock-licensed photo is unaffected. Pulling the page with curl, stripping HTML, and grepping for keywords (stock|licen|publish|exclusiv|AI|noise|upscal|perpetu|merch) surfaced the exact clauses and avoided the misread. Several sites also needed a cookie jar (redirect loop without one) or were Cloudflare/403-blocked, which WebFetch could not get past but curl -c/-b sometimes could.

**Suggested improvement:** In platform-terms-research "Source hierarchy", add: when a decision hinges on a specific clause, fetch the raw page text (curl + HTML strip, cookie jar enabled) and grep a fixed keyword list; treat any fetch-tool summary of a legal clause as a tier-4 lead until the verbatim clause is read. Add a keyword list for rights grants (perpetual, sub-licens, merchandis, commercial, derivative) to the pre-flight checklist.

**Principle:** Summarizers collapse "X is prohibited inside your work" into "X is prohibited" — the verbatim clause, not a paraphrase, is the primary source.

### Observation 51: Zendesk help centers that 403 WebFetch are readable through the public Help Center JSON API

**Status:** ACTIONED — Applied to platform-terms-research 'Reaching the verbatim text' (Zendesk Help Center API, stop at bot challenges) + pre-flight (all-projects skill review 2026-09-28)
**Date:** 2026-09-24
**Session context:** Researched terms for Pixsy, Zazzle, Picfair, Vecteezy, Magnific and AI-data buyers (docs/photo-licensing/new-channels-terms.md)
**Skill:** platform-terms-research
**Type:** open-source
**Phase/Area:** Source hierarchy / reaching the primary document

**Issue:** support.picfair.com and eezycontributors.zendesk.com (Vecteezy) returned 403 to WebFetch. The public endpoints `/api/v2/help_center/articles/search.json?query=...` and `/api/v2/help_center/en-us/articles/<id>.json` returned the full article body with `edited_at` dates. `/articles/<id>/attachments.json` surfaced the Vecteezy Contributor Agreement PDF (2025-08-04), which the article page only links to. That access also showed that the internal matrix's claim of "Picfair marketplace demand" is out of date. Picfair now has no central marketplace, and free Lite accounts cannot sell. Magnific/Freepik uses an Akamai bot challenge, which was correctly left alone. Tier-3 sources were used there, and marked as such.

**Suggested improvement:** Add to "Source hierarchy": if a help center is Zendesk (URL pattern /hc/en-us/articles/<id>), try the Help Center JSON API before falling back to search snippets. Record `edited_at` as the in-force date proxy. Check article attachments for the actual agreement PDF. Never script around bot challenges (Akamai or Cloudflare interstitials). Mark those platforms' facts as tier 3 and verify them in the dashboard after login.

**Principle:** A 403 on the rendered help page often has a documented public API behind it. Use the official unauthenticated endpoint and stop at a bot challenge.

### Observation 52: Reddit outreach §9 analytics step doesn't say how to authenticate
**Status:** OPEN
**Date:** 2026-09-28
**Session context:** Scheduled muscleonglp-reddit-outreach run (interim hand-off path).
**Skill:** muscleonglp-reddit-outreach (scheduled task SKILL.md)
**Type:** internal
**Phase/Area:** §9 "Report outcomes" — "one authenticated request"

**Issue:** §9 says to pull the site's analytics with "one authenticated request" but not how. The obvious guess (Bearer header with MUSCLEONGLP_STATS_TOKEN from ~/.config/purplelink/traffic.env) returns {"error":"unauthorized"}; the function (muscleonglp-site/netlify/functions/stats.mjs) takes ?token=SECRET&days=N. Cost two extra round trips. Separately, a run on three consecutive runs' data found reddit referrals flat and the 09-25 linked article at 0 views, i.e. hand-offs are probably not being posted — the task has no step that asks Ben to confirm, so the unconfirmed list just grows.

**Suggested improvement:** In §9 give the exact call: curl -G --data-urlencode "token=$MUSCLEONGLP_STATS_TOKEN" -d days=N https://getmuscleonglp.com/.netlify/functions/stats. In §8 interim path, add: if two consecutive runs' linked articles show zero views, say at the top that hand-offs appear unposted and recommend a verification-only pass until Ben confirms or the API lands.

**Principle:** A step that says "authenticate" without the mechanism gets re-derived by trial and error every run; write the exact call. And a hand-off loop needs a confirmation signal, or it silently turns into drafting for nobody.
