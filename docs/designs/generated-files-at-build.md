# Build generated site files at deploy time, not in git

Status: revised after Goldfish review (four Sonnet reviewers, 2026-11-02; findings and resolutions in
`generated-files-at-build-review.md`). Approved by Ben 2026-11-02 (option 4 for phase 2). Phase 1 in progress. Owner: Ben.

## Problem

Scripts write three kinds of output into `site/`, and the repo commits that output:

| Output | Written by | Main commits that changed it, 2026-10-03 to 2026-11-02 |
|---|---|---|
| `site/search-index.json` (137 KB) | `scripts/gen_search_index.py` | 235 of 972 |
| `site/llms-full.txt` (780 KB) | `scripts/gen_llms_full.py` | 224 of 972 |
| `?v=<hash>` stamps on CSS, JS and logo references in 400 HTML files and `site/styles.css` | `scripts/fingerprint_assets.py`, plus the footer mark from `scripts/apply_layout.py` (`mark_src`, line 241) | each of the 30 changes to `site/styles.css` rewrote the stamp line in about 400 pages |

Two branches that both change any page, or both touch `styles.css` or `site.js`, disagree on these outputs.
Git reports a conflict and GitHub marks the pull request not mergeable, although no hand-written line
conflicts. PR 485 (a branch that edits `styles.css`) hit this three times on 2026-11-01 and 2026-11-02, and
each fix was the same routine: take main's copy, rerun the scripts, commit pages that main added, push.

Production never uses the committed copies: the Netlify build command (`netlify.toml`, `[build] command`)
reruns `apply_layout.py`, `fingerprint_assets.py`, `gen_search_index.py`, `gen_blog_feed.py` and
`gen_llms_full.py` on every build. The committed output exists because tests read it and because sessions are
told to run the scripts before a pull request.

## Goal

A pull request conflicts only where people wrote conflicting lines. Production output stays the same: same
stamps, same cache headers, same index, same `llms-full.txt`.

Non-goals: what the scripts generate; the shared nav and footer HTML from `apply_layout.py` (only its logo
stamp changes); `site/sitemap.xml` (its `lastmod` comes from git history, which the shallow Netlify clone
lacks); `site/blog/feed.xml` (5 changes in 30 days); one shared build script for Netlify, `deploy.sh` and CI
(they differ on purpose: `deploy.sh` also runs `gen_sitemap.py` and `gen_venue_json.py` and runs
`check_content.py --strict`; Netlify runs it lenient so one bad page never blocks an unattended build).

## Options considered for the stamps

1. **Leave it; Autofix resolves conflicts.** Costs a session merge after most busy days on main for every
   long-lived branch, and a merge that takes either side without regenerating publishes stale stamps until
   the next build.
2. **Custom git merge driver.** Rejected: drivers live in local git config; GitHub's mergeability check and
   web merges ignore them, so the PR still shows as conflicting.
3. **Stop stamping `/styles.css` and `/site.js` only**, and serve those two with
   `max-age=0, must-revalidate`. These two cause nearly all of the cross-page stamp conflicts, and the change
   is small (a skip in `fingerprint_assets.py`, two header blocks, a one-time strip). Cost: every page view by
   a returning visitor waits one conditional request (a 304) before it can render, because CSS blocks
   rendering. `netlify.toml` (comments above the `/styles.css` and `/tools/*.css` headers) records that the
   stamps were added on purpose to remove exactly this round trip and the one-day staleness seen twice on
   2026-09-04. This option reverses that decision.
4. **Stamp only in throwaway build checkouts; commit references bare.** Production keeps today's stamps and
   cache headers. More code than option 3 (below).

**Recommendation: phase 1 now; phase 2 as option 4.** Option 3 is the cheaper choice if Ben accepts the
revalidation cost; it is the one product decision in this document.

## Phase 1: stop committing the search index and llms-full

- Remove both files from git (`git rm --cached`) and add them to `.gitignore`.
- `netlify.toml`'s build command does not change, so `scripts/netlify_ignore.sh` `INPUTS` does not change.
- Tests that read the files (in `site-tests/`: `test_guides_m6_m8.py`, `test_intl_moderntex.py`,
  `test_intl_advertise.py`, `test_batterymeter_page.py`, `test_academic_email_signature.py`,
  `test_social_redirects.py`, `test_linkedin_redirects.py`; in `netlify/tests/`: the `keyfeel`, `legroom`,
  `tapefolio`, `pii-checker`, `transcript-cleaner` and `scholar-pro` site tests; `lenscrib-site` already
  tolerates a missing file) get the file through one helper per suite (`site-tests/common.py` and a small
  `netlify/tests/_generated.mjs`) that runs the generator once if the file is missing or older than the
  newest page. A fresh clone, a new worktree or a cloud session then passes without a manual step.
- CI (`site-tests.yml`) needs no build step, because the test helpers regenerate both files (not the full
  build). It adds a check that fails if either file is tracked again (`git ls-files` on the two paths must
  print nothing).
- After this merges, `git pull` deletes the two files from every other checkout; the next test run or build
  recreates them. The PR description says so.

## Phase 2: stamp only in throwaway checkouts

- **Who may stamp.** `fingerprint_assets.py` stamps in place only when `NETLIFY=true` (Netlify's build) or
  `CI=true` (GitHub Actions) is set, or `--force-in-place` is given. Otherwise it exits 2 with a message
  saying the build adds stamps and the committed tree stays bare. It fails loudly rather than doing nothing,
  so no caller silently ships unstamped output. New modes: `--strip` (remove stamps) and `--check-bare`
  (exit 1 listing any committed file with a stamp). `--check` (stamps current) stays for the built tree, and
  the Netlify command adds `python3 scripts/fingerprint_assets.py --check` after stamping, so a build that
  would publish unstamped HTML under the `immutable` headers fails.
- **The footer mark.** `apply_layout.py` `mark_src()` returns the bare `/assets/purplelink-mark.svg`;
  `fingerprint_assets.py` already matches that path and stamps it at build time. `test_layout_in_sync.py`
  then compares bare to bare.
- **Callers.** `scripts/go-live-app.py` (line 62) drops its `fingerprint_assets.py` call.
  `scripts/deploy.sh` refuses to start if `site/` has uncommitted changes, runs with
  `--force-in-place`, and restores the tree afterwards with `git checkout -- site` (safe because it was
  clean), so a manual deploy never leaves stamps behind.
- **CI order.** `--check-bare` first, then the generators with `CI=true`, then the tests. Tests that assert a
  stamp (`test_support_box.py`, `test_asset_fingerprints.py`, and in `netlify/tests/` the `pii-checker`,
  `transcript-cleaner` and `trial-reminder-apps` tests) accept a bare or a stamped reference when run locally
  and require the stamp when `CI=true`. New unit tests in `test_asset_fingerprints.py` cover `--strip`,
  `--check-bare`, the refusal, and a round trip on a temporary copy of `site/` (strip then stamp reproduces
  the current bytes).
- **Direct pushes to main**, which skip PR CI: `.githooks/pre-commit` (the repo's `core.hooksPath`) runs
  `--check-bare` on staged `site/` files. A cloud session without the hooks still has to open a PR under the
  `CLAUDE.md` rule, so CI catches it there.
- **Migration.** One commit runs `--strip` over `site/` (about 400 HTML files and `styles.css`).
  `gen_sitemap.py` (lines 86-94) already ignores stamp-only diffs, so no `lastmod` moves and no IndexNow
  burst follows. Open branches conflict once; `--check-bare` prints the fix: merge `origin/main`, take
  main's side for stamp lines, run `--strip`.
- **Docs.** `CLAUDE.md` (automated sessions, step 2) drops "run `fingerprint_assets.py`"; the `netlify.toml`
  comments above the immutable headers ("the fingerprints are committed"), the `fingerprint_assets.py`
  docstring, `site-tests/README.md` and the `deploy.sh` comment change to match. The `site/blog/digest/` skip
  stays in code, applied in every mode, though the directory was removed on 2026-10-17.

## Risks

- **A Netlify build step fails.** The build fails and Netlify keeps serving the previous deploy, as today.
- **Someone stamps and commits anyway.** The pre-commit hook or CI's `--check-bare` stops it with the fix.
  Production is unaffected either way, because the build stamps everything.
- **`git add site/` or `git add -A` after phase 1** silently skips the ignored files (an explicit path
  errors); CI's tracked-file check catches a forced add.
- **Production differs after a phase.** Each phase's PR includes a parity check: build the branch and main in
  two temporary clones with `NETLIFY=true` and diff the two `site/` trees; the only allowed differences are
  the files the PR meant to change.

## Rollback

- Phase 1: revert the PR, then `git add -f site/search-index.json site/llms-full.txt` from a fresh build.
- Phase 2: revert the PR, then run `fingerprint_assets.py --force-in-place` and commit (a plain revert brings
  back stamps that may be stale). Netlify's "publish previous deploy" is the immediate stop for either.

## Detailed Implementation Plan

Phase 1, one pull request (all steps in one squash commit, so no commit has tests without their files):

1. Add the two test helpers and switch the listed tests to them; confirm both suites pass with the two files
   deleted locally.
2. `git rm --cached` both files; add them to `.gitignore`.
3. `site-tests.yml`: add the tracked-file check (the helpers from step 1 generate the files).
4. Parity check as in Risks; attach the result to the PR.
5. Ben merges. After the next scheduled build: `curl -s https://purplelink.llc/search-index.json | python3 -c
   "import json,sys;print(len(json.load(sys.stdin)))"` equals the local count, and `/llms-full.txt` returns
   200 with the same line count as a local build.

Phase 2, a second pull request after one scheduled build of phase 1, one squash commit, with commits in the
order: script modes and tests, then callers (`apply_layout.py`, `go-live-app.py`, `deploy.sh`, pre-commit,
Netlify `--check` step), then the strip migration, then the CI `--check-bare` step, then docs:

1. `fingerprint_assets.py` modes and refusal, with the unit tests above.
2. `apply_layout.py` bare mark; `go-live-app.py`; `deploy.sh` clean-tree guard and restore; pre-commit
   `--check-bare`; Netlify command adds `fingerprint_assets.py --check` after stamping.
3. Migration: `--strip` over `site/`.
4. CI: `--check-bare` before the generators; stamp-asserting tests switch on `CI`.
5. Docs as listed.
6. Parity check; Ben merges; after the next build, compare `?v=` on `/` for `styles.css` with
   `shasum -a 256 site/styles.css | cut -c1-10` computed in a build checkout.
