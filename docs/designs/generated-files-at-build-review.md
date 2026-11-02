# Goldfish review: generated-files-at-build.md

Review of the first draft, 2026-11-02, by four zero-context Sonnet reviewers: zoom-out (scope), design
(failure modes), codebase details (accuracy), implementation readiness. Findings are merged where reviewers
raised the same point.

| # | Finding | Raised by | Resolution in the revised draft |
|---|---|---|---|
| 1 | One `build_site.sh` for Netlify, `deploy.sh` and CI hides real differences: `gen_venue_json.py` and `gen_sitemap.py` are deploy-only, `check_content` is strict only in `deploy.sh`, `check_games` is Netlify-only | all four | Dropped the shared script; listed as a non-goal with the reasons. The Netlify command is unchanged in phase 1. |
| 2 | `scripts/netlify_ignore.sh` has its own in-repo `INPUTS` list, which the draft missed | all four | Moot now that no build script is added and the Netlify command is unchanged in phase 1; phase 2 adds only a `--check` call to an existing script already in `INPUTS`. |
| 3 | "Locally the files keep existing" is false: `git pull` deletes them, and fresh worktrees and clones never have them | zoom-out, design, readiness | Test helpers regenerate a missing or stale file; the PR description warns about the delete on pull. |
| 4 | Running the full mutating build in CI adds new failure sources and hides drift | zoom-out, design, readiness | Phase 1 CI runs only the two generators. |
| 5 | `apply_layout.py` writes the footer mark stamp itself (`mark_src`, line 241) | design, codebase | Phase 2 makes it emit the bare path; the fingerprint step stamps it at build time. |
| 6 | A silent no-op default is unsafe under the `immutable` headers; `go-live-app.py` calls the script without flags | design, codebase, zoom-out | Without a build environment the script now exits 2 instead of doing nothing; Netlify runs `--check` after stamping; `go-live-app.py` is updated. |
| 7 | Stamp-asserting tests were listed incompletely | codebase | Full list given (`test_support_box`, `test_asset_fingerprints`, `test_layout_in_sync`, pii-checker, transcript-cleaner, trial-reminder-apps). |
| 8 | Intermediate commits would be red; ordering unstated | readiness | One squash commit per phase, with the internal order given. |
| 9 | The 400-page migration could reset sitemap `lastmod` and trigger IndexNow | readiness | Checked: `gen_sitemap.py` lines 86-94 ignore stamp-only diffs. Stated in the doc. |
| 10 | No rollback | readiness, design | Rollback section added. |
| 11 | No proof that production output is unchanged | design, readiness | Parity check: build branch and main with `NETLIFY=true` in two temporary clones and diff `site/`. |
| 12 | `deploy.sh` and `test_site.sh` `EXIT` traps could strip a person's uncommitted edits | design, readiness | `test_site.sh` dropped; `deploy.sh` refuses to run on a dirty `site/` and restores with `git checkout -- site`. |
| 13 | Direct pushes to main skip PR CI | zoom-out | `--check-bare` added to `.githooks/pre-commit`. |
| 14 | A narrow Option 3 (unstamp only `styles.css` and `site.js`) was not priced | zoom-out | Added as option 3 with its cost: one 304 round trip before render on every returning page view, reversing the 2026-09 decision recorded in `netlify.toml`. Left to Ben. |
| 15 | Build into a copy (`dist/`) instead of strip and stamp | zoom-out, design | Not taken: every generator and about 20 tests hardcode `site/`. Stamping in place only inside throwaway checkouts (Netlify, CI) gets the same result with fewer changes. |
| 16 | `.gitignore` does not fail `git add site/`, it skips silently | codebase, design | Wording fixed; CI fails if either file is tracked. |
| 17 | `site/blog/digest/` no longer exists; `netlify.toml` comments go stale | zoom-out, codebase | The skip stays in code in every mode; the comments are in the docs step. |
| 18 | Verification steps were vague | readiness | Concrete commands for both phases. |

Not verified by the reviewers: the commit counts and file sizes (taken from `git log` and `ls` by the
author), and the external `~/.purplelink/bin/netlify-batch-build.sh`, which only needs a change if a new
build script is added (none is now).
