# Skill Observation Log

Observations captured during task-oriented work. Each entry identifies a
potential skill improvement or new skill opportunity.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created |
DECLINED = user decided not to pursue

---

### Observation 1: PrecisionConference (PCS) reviewer-assignment workflow is non-obvious and benefits from a dedicated skill

**Status:** OPEN — no `pcs-reviewer-assignment` skill exists (verified 2026-08-29)
**Date:** 2026-05-28
**Session context:** Assigning reviewers to ICIS 2026 papers via PCS (new.precisionconference.com) as an Associate Editor, using the Chrome browser MCP.
**Skill:** New skill candidate: pcs-reviewer-assignment
**Type:** open-source
**Phase/Area:** Conference peer-review administration / browser automation

**Issue:** The PCS "Show potential reviewers" tab is not a curated/bidded shortlist — it is the entire conference reviewer corpus (4,494 rows for ICIS 2026), with the per-paper "Bid" column empty for everyone and the affinity/match "Score" column showing -1 (uncomputed) for all. Reviewer expertise is NOT in the sortable table (only score/name/committee-flag/volunteered/assigned counts); it lives solely on each reviewer's individual profile page. The actionable signals discovered: (a) "Volunteered Reviews > 0" is the real "requested reviews" filter (446 of 4,494 here), (b) "Assigned < Volunteered" = has capacity (peach background = at/over capacity), (c) self-rated expertise tiers (Expert/Competent/Novice) are heavily gamed by industry "expert-in-everything" signups, so they must be cross-checked against affiliation + a web search of the person. Efficient extraction: same-origin `fetch()` of the 446 profile pages run from the page console (via the JS tool), parsed with DOMParser, cached to localStorage to survive navigation. Assignment itself sends a declinable invitation email ("Assign and send email" vs "Assign but do not send email" vs "Do not assign").

**Suggested improvement:** Create an internal/open-source skill documenting the PCS AE reviewer-assignment workflow: how to read the potentials table, the vol>0 / capacity / peach semantics, the over-claimer trap, the bulk-profile-fetch+localStorage-cache technique, conflict-of-interest checks (author institutions), and the invitation vs force-assign distinction. Include the gotcha that get_page_text returns the full DOM (135K chars) regardless of DataTables pagination, so JS extraction beats text scraping.

**Principle:** When a web tool presents a huge unranked list with the useful discriminating data hidden in per-row detail pages, the scalable move is in-page scripted extraction (fetch + parse + cache) rather than manual paging — and self-reported metadata in crowd-sourced systems should always be triangulated against an independent source before acting on it.

### Observation 2: Citation-parsing specs must anticipate nobiliary-prefix and non-ASCII surnames

**Status:** ACTIONED — Applied to `writing-plans` §Self-Review item 4 (parsing edge cases) (skill review 2026-08-31)
**Date:** 2026-06-04
**Session context:** Subagent-driven implementation of the Deep Citation Audit feature (Paper Review Layer 2). Task 1 built an author-year in-text citation regex.
**Skill:** writing-plans (and any citation/bibliography-parsing skill: citation-audit, citation-checker)
**Type:** open-source
**Phase/Area:** Spec/plan completeness for text-parsing tasks

**Issue:** The plan's author-year citation regex required every author surname to begin with an uppercase ASCII letter (`[A-Z][A-Za-z\-]+`). The implementation passed all planned tests, but the code-quality reviewer caught that this silently drops citations with lowercase nobiliary particles common in ML/NLP literature — "(van der Berg et al., 2021)", "(de Bruijn and Smith, 2018)". The plan author (me) did not anticipate this real-world variation, so no test covered it. Fixed by adding an `_AUTHOR` sub-pattern allowing up to two lowercase particle words before the capitalized surname.

**Suggested improvement:** When a writing-plans spec involves parsing human names, citations, or bibliographic strings, include explicit edge-case requirements/tests for: nobiliary/lowercase prefixes (van, de, der, von, da, bin), hyphenated and accented (non-ASCII) surnames, and single-name authors. Add a checklist line to writing-plans' Self-Review for parsing tasks: "Does the spec cover non-ASCII / non-canonical input variants, not just the happy-path format?"

**Principle:** Happy-path regex specs for human-generated formats (names, dates, citations, addresses) systematically under-cover real-world variation. A plan's test set should be seeded with known messy variants of the domain, because the implementer will faithfully reproduce the spec's blind spots — adversarial code review, not the planned tests, is what catches them.

### Observation 3: all-miss test covers title-only ref — S2/CrossRef short-circuit rather than fail over HTTP

**Status:** ACTIONED — Applied to `writing-plans` §Self-Review item 5 (fallback-chain coverage) (skill review 2026-08-31)
**Date:** 2026-06-04
**Session context:** Code-quality review of Task 4 (async abstract fetch, feat/deep-citation-audit). Reviewing test coverage of the fallback chain.
**Skill:** writing-plans (and citation-audit, subagent-driven-development)
**Type:** open-source
**Phase/Area:** Test design for injected-client async fallback chains

**Issue:** The `test_fetch_source_abstract_all_miss_is_unavailable` test constructs a title-only PaperReference (no DOI, no arxiv_id). This means S2 and CrossRef exit before making any HTTP call — they short-circuit to `None` because neither identifier is present. The test exercises the "all None → unavailable" accumulator in `fetch_source_abstract`, but does NOT exercise S2 or CrossRef's HTTP-miss path. The OpenAlex title-search path IS exercised (the FakeClient returns 404). However, the spec says "try the three in order" — S2/CrossRef HTTP failures are not covered by either test.

**Suggested improvement:** Add a third test: a ref WITH a DOI, where all three endpoints return 404. This proves each fetcher swallows a non-200 response and that the chain truly falls through all three. One extra test, ~10 lines. The injected-client design makes this trivially cheap. Note for plans: "For a fallback chain of N sources, the minimum meaningful test set is: (a) first-source hit, (b) last-source-miss (all miss), (c) first-miss-second-hit (for each adjacent pair if budget allows), plus (d) all-miss-with-all-HTTP-attempted."

**Principle:** In an injected-client fallback chain, "all miss" can be reached two ways: no identifiers (every fetcher short-circuits before HTTP) or identifiers present but every HTTP call fails. Tests that conflate these two paths leave the HTTP-failure swallowing untested. A complete test suite for an N-source fallback needs at least one test where every fetcher reaches the network layer and still returns None.

### Observation 4: New LLM entry points must be routed through the centralized prompt-injection choke point

**Status:** ACTIONED — Applied to `writing-plans` §Self-Review item 6 (security parity) (skill review 2026-08-31)
**Date:** 2026-06-04
**Session context:** Subagent-driven implementation of Deep Citation Audit (Paper Review Layer 2). A new module added an LLM call (assess_claims) that sent manuscript claims AND fetched third-party abstracts to the model.
**Skill:** writing-plans (and any skill that builds LLM pipelines with centralized safety handling)
**Type:** open-source
**Phase/Area:** Security review of multi-LLM-call features

**Issue:** The codebase routes all untrusted content through one safety module (sanitize + data-fence wrap + a system-prompt "untrusted boundary" preamble). The implementation plan specified a brand-new LLM call but did NOT require it to use that choke point, so the first implementation inserted attacker-controllable text (a cited preprint's abstract) into the prompt raw. Every planned unit test passed; only the adversarial FINAL code review (an opus reviewer explicitly asked to check prompt-injection parity) caught it. Fixed by adding the safety preamble to the system prompt and sanitizing+fencing both inputs, plus registering the new fence tags.

**Suggested improvement:** Add a checklist item to writing-plans' Self-Review for any feature that adds an LLM/tool call: "Does every new model/tool entry point route untrusted inputs through the project's existing sanitization/guardrail layer, matching sibling call sites? Add an explicit task + a test that an injection in each untrusted input is neutralized." When a codebase has a centralized safety/guardrail module, the plan should name it and require parity for new call sites.

**Principle:** Centralized security controls are only as good as their coverage. A new code path that bypasses the shared choke point is the most likely place for a regression, and happy-path unit tests never reveal it — an adversarial review pass that explicitly checks "does this new entry point match the security posture of its siblings?" is what catches it. Plans should make security-parity for new entry points an explicit, tested requirement, not an implicit assumption.

### Observation 5: UI audits of large SwiftUI apps need a grep-first inventory pass before reading

**Status:** OPEN — no `swiftui-consistency-audit` / design-system-conformance-audit skill exists (verified 2026-08-29)
**Date:** 2026-06-04
**Session context:** UI consistency + usability audit of the Helm macOS SwiftUI app (~20 screens, 257KB Screens.swift). Tasked with finding inconsistencies, a11y regressions, missing confirmations, validation gaps, empty-state gaps, and emoji.
**Skill:** New skill candidate: swiftui-consistency-audit (or generalize: design-system-conformance-audit)
**Type:** open-source
**Phase/Area:** Audit methodology

**Issue:** The most efficient path through a huge single-file UI codebase was not linear reading but a battery of targeted greps against the known design-system tokens: list every `struct *Screen`, count `.helmScreen(` adoption, grep color literals (`.red/.green/.orange/Color.yellow`) vs `Theme.positive/negative/accent`, grep `GroupBox` vs `Card`, grep `EmptyState(` vs `ContentUnavailableView`, grep `role: .destructive` then classify each as immediate vs `confirmationDialog`-gated, grep `.disabled(` to check Save-button validation, grep `String(format:.*/100` for money-formatting bypasses of the canonical `CockpitData.money`, and a Unicode-range grep for emoji. Reading specific contexts came only after greps localized the suspects. This turned a 5000-line file into ~15 high-signal findings in a few passes.

**Suggested improvement:** Capture a reusable "design-system conformance audit" checklist that, given a token/component vocabulary (color tokens, spacing scale, the screen-scaffold modifier, the empty-state component, the money formatter, the confirmation pattern), runs as a fixed sequence of greps producing an adoption matrix (which screens use the canonical pattern vs an ad-hoc equivalent). Key heuristic: the strongest findings are where a canonical primitive EXISTS but newer code reaches for the framework default instead (e.g. `ContentUnavailableView` instead of the app's `EmptyState`, or `.red` instead of `Theme.negative`) — i.e. drift between older and newer screens.

**Principle:** In a mature codebase the bugs of consistency are "two ways to do the same thing." Auditing for them is a set-difference operation (canonical primitives ∖ their framework-default twins), which greps answer faster than reading. Inventory by grep, then read only the localized suspects.

### Observation 6: Swift money-parsing crash pattern recurs across a finance codebase

**Status:** OPEN — no `swift-secure-code-review` skill exists; `swift-security-expert.md` does not cover trapping numeric conversions (verified 2026-08-29)
**Date:** 2026-06-05
**Session context:** NIST SSDF security scan of the Helm macOS finance app (Swift Package). Found the same crash-inducing money-conversion idiom in four independent files.
**Skill:** New skill candidate: swift-secure-code-review (or security-review checklist addendum)
**Type:** open-source
**Phase/Area:** Crash-as-DoS from external input / integer & float-to-int conversion

**Issue:** Two distinct but related unsafe idioms appeared repeatedly when converting external numeric input to integer minor units (cents):
1. `whole * 100 + cents` where `whole` is `Int(userString)` — traps on overflow for valid-but-large integers (parseMoneyMinor in AppModel.swift:1752, CSVImporter.swift:212).
2. `Int((value * 100).rounded())` where `value` is `Double(externalString)` — traps when the Double is NaN/Inf or exceeds Int range (ReceiptParser.swift:55, PlaidConnector.swift:78, AppStoreConnectClient.swift:87). Swift's `Int(Double)` initializer is a *trapping* conversion, unlike many developers' mental model. Inputs come from OCR text, CSV files, and API JSON — all attacker-influenceable.

**Suggested improvement:** A Swift-focused secure-code-review checklist should call out: (a) `Int(_: Double)` is trapping — require `Int(exactly:)` or explicit finite/range guards before any Double→Int money conversion; (b) integer arithmetic on parsed input needs `multipliedReportingOverflow`/`addingReportingOverflow` or a bound check; (c) grep heuristic `Int(.*\* 100` and `\* 100 +` to find these sites quickly. Treat "parses cleanly but is enormous" as a first-class test input, not just non-numeric junk.

**Principle:** When the same unsafe primitive shows up in N independent files, the fix isn't N point-patches — it's a shared safe helper plus a review-checklist rule, because the pattern will keep reappearing wherever a new connector/importer is added. Language-specific trapping conversions (Swift `Int(Double)`, `arr[i]`, force-unwrap) deserve dedicated checklist entries in any language-specific security-review skill.

### Observation 7: Preserve exact parser semantics by delegating only the unsafe step

**Status:** ACTIONED — Applied to `test-driven-development` §"'Preserve Behavior Except the Crash' Refactors" (skill review 2026-08-31)
**Date:** 2026-06-05
**Session context:** Fixing a crash-DoS bug class (trapping numeric conversions) in the Helm Swift finance app, TDD, across 5 sites in 3 modules.
**Skill:** test-driven-development
**Type:** open-source
**Phase/Area:** Refactoring untrusted-input parsers without behavior change

**Issue:** The task spec supplied a generic `minorUnits(fromString:)` helper and suggested reimplementing two existing money-string parsers (`parseMoneyMinor`, CSV `parseMinor`) on top of it. But the two existing parsers had divergent, stricter accepted-format rules (European decimal-comma disambiguation, strict all-digit validation, positive-only vs signed). Wholesale replacement with the generic helper would have silently widened/narrowed accepted inputs. The safer move was to keep each parser's existing preprocessing/validation intact and extract ONLY the overflow-prone final arithmetic (`whole * 100 + cents`) into a shared `minorUnits(whole:cents:negative:)` combiner. This fixed the crash without touching which inputs are accepted/rejected.

**Suggested improvement:** When a security/robustness refactor must "preserve behavior except for the crash," identify the minimal unsafe operation and replace only that, rather than swapping in a more general helper that subtly changes accepted inputs. Add a TDD note: diff the accepted-input set before/after, not just the happy path.

**Principle:** "Preserve behavior" refactors are safest when the change surface is the single failing operation, not the whole function. A more general helper is a behavior change in disguise unless proven to be a strict superset.

### Observation 8: Warning-elimination tasks must include the test target, not just sources

**Status:** OPEN — no build-hygiene skill covers "rebuild every target including tests" (verified 2026-08-29)
**Date:** 2026-06-05
**Session context:** Task to make the Helm macOS Swift package build with zero compiler warnings. The task brief enumerated warnings only in Sources/ (Reporting.swift, AppModel.swift, the LedgerCore/CRM stores). After fixing all of those and confirming `swift build` was clean, `swift test` surfaced two additional identical `var comps` warnings in Tests/LedgerCoreTests/MRRTests.swift that the source-only build never compiled.

**Suggested improvement:** When a "zero warnings" hygiene task is specified, the verification step should always run the test build (`swift test` / equivalent), not just the product/library build, because test targets compile separately and carry their own warnings. Add this as an explicit verification sub-step in any build-hygiene workflow/checklist.

**Principle:** "Zero warnings" is only meaningful if every compiled target is checked. Library/app builds skip test targets entirely; a clean app build can still leave warnings in test code. Always enumerate and re-build all targets (sources + tests) before declaring a warning-free state.

### Observation 9: SwiftUI .onChange additions can break type-checker on large View bodies

**Status:** OPEN — no SwiftUI skill covers the type-checker ceiling / consolidated .onChange key (verified 2026-08-29)
**Date:** 2026-06-05
**Session context:** Helm crash-DoS sweep — adding `.onChange(of:)` triggers to a SwiftUI ReportsScreen body to refresh a cached budget card.
**Skill:** New skill candidate: swiftui-large-body-guard (or note for any Swift/SwiftUI engineering skill)
**Type:** open-source
**Phase/Area:** SwiftUI view-body editing

**Issue:** Adding a third `.onChange(of:)` modifier to an already-large SwiftUI `var body` tipped the Swift compiler into "unable to type-check this expression in reasonable time." The fix was to fold two `loadData()` triggers into a single `.onChange` keyed on a cheap computed `Equatable` signature (a String built from the relevant model fields), keeping the modifier-chain length flat. A naive `.onChange(of: model.budgets)` also wouldn't have been Equatable (Budget wasn't Equatable), and a `.count`-based key would have missed in-place edits (same count, changed amount) — the signature had to capture id/target/category.

**Suggested improvement:** When adding reactive triggers to a SwiftUI body, prefer consolidating multiple identical-action triggers into one `.onChange` keyed on a combined Equatable signature, rather than appending modifiers. For change-detection keys, capture the mutated fields (not just collection count) so in-place edits are detected.

**Principle:** SwiftUI view bodies have a practical complexity ceiling for the type-checker; each added modifier raises inference cost. Consolidating reactive triggers behind a single derived key is both cheaper to compile and more correct than chaining per-property observers — and change keys must reflect value mutations, not just element count.

### Observation 10: Parallel coding subagents on one working tree can destroy each other's uncommitted work via git cleanup

**Status:** ACTIONED — Verified already implemented in skill `dispatching-parallel-agents`, §0 Isolation Preflight items 1–3 (worktree isolation when another writer is active; subagents are filesystem-only and run NO git commands; disjoint file sets). The "commit all completed work before dispatching" sub-point is implied by the single-writer index rule but is not stated as its own step. (status backfill 2026-08-29)
**Date:** 2026-07-02
**Session context:** Helm release-readiness sprint. Three changes in flight on one git working tree: the coordinator editing LedgerStore/LedgerImporter inline, plus two background Haiku agents (Reporting.swift optimization, OnboardingView fix). One background agent apparently encountered a mid-build inconsistency caused by the coordinator's in-flight edits and ran a git restore-style cleanup, silently reverting ALL uncommitted tracked changes — the coordinator's edits and the other agent's completed fix. Untracked files (new tests) survived; only the reverting agent's own file remained modified.
**Skill:** superpowers:dispatching-parallel-agents (also superpowers:subagent-driven-development)
**Type:** open-source
**Phase/Area:** Parallel subagent dispatch on a shared repository

**Issue:** Nothing in the dispatch prompts forbade git state-mutation commands, and the coordinator treated "different files" as sufficient isolation. But a shared build graph (swift build compiles the whole package) means one agent's build failure can be caused by another agent's half-applied edit — and an agent that "fixes" that by reverting the tree destroys sibling work. File-level disjointness is NOT isolation when build/test steps and git state are shared.

**Suggested improvement:** Any skill that dispatches multiple coding agents against one working tree should mandate: (1) every agent prompt includes an explicit prohibition on git restore/checkout/stash/reset and on reverting files the agent didn't change, with instruction to STOP and report if the tree looks broken; (2) commit all completed work before dispatching agents; (3) run coding agents sequentially unless given true worktree isolation; read-only research agents may parallelize freely.

**Principle:** A shared working tree plus a shared build graph makes "editing different files" a false isolation boundary. Uncommitted work is unprotected work: commit before dispatch, forbid git mutations in agent prompts, and reserve parallelism for read-only agents or isolated worktrees.

### Observation 11: Verify the requester's factual premises against the manuscript before writing a referee report

**Status:** ACTIONED — Applied to `misq-cds-reviewer` §How to read the manuscript (verify every asserted absence) (skill review 2026-08-31)
**Date:** 2026-07-03
**Session context:** Writing a TMIS peer review of the KADI paper in the style of a supplied JMIS review, using misq-cds-reviewer + benampel.
**Skill:** misq-cds-reviewer (also applies to is-writing)
**Type:** open-source
**Phase/Area:** Reading the manuscript / Major Concerns construction

**Issue:** The user directed the review to argue rejection because "this doesn't even cite a TMIS paper as far as I can tell." A grep of the manuscript's reference list showed the opposite: it cites three TMIS/ACM Trans. Manage. Inf. Syst. papers (Chau & Xu 2025 [11], Dumas et al. 2023 [13], Zoubek et al. 2025 [65]) plus a dedicated "In the information systems literature" paragraph. Encoding the user's premise verbatim would have handed the authors an instant, credibility-destroying rebuttal. The defensible argument (papers cited but only descriptively, in one paragraph, never used to build the gap or contribution) was stronger and survived scrutiny.

**Suggested improvement:** Add a step to the misq-cds-reviewer "How to read the manuscript" section: before writing any Major Concern that asserts an absence ("does not cite X," "no baseline," "never measures Y"), verify the absence against the actual manuscript text (grep the references/sections). If the requester supplied the premise, verify it independently and, if false, surface the correction and reframe to the defensible version rather than repeating it.

**Principle:** A referee's credibility collapses on the first checkable false claim. Any assertion of absence in a review must be verified against the source, especially when it originates from the requester rather than the reviewer's own reading.

### Observation 12: When an exemplar review is supplied, mirror its structure over the skill's fixed output format

**Status:** ACTIONED — Applied to `misq-cds-reviewer` §Required Output ("Exemplar override") (skill review 2026-08-31)
**Date:** 2026-07-03
**Session context:** Same TMIS/KADI review session; user asked for the review "in the style of the attached JMIS review."
**Skill:** misq-cds-reviewer
**Type:** open-source
**Phase/Area:** Required Output (the ten-section format)

**Issue:** The misq-cds-reviewer skill mandates a fixed ten-section output. The user instead supplied a JMIS referee report as a style exemplar (opening stance paragraph → numbered Major Comments → bulleted Minor Comments → References) and asked to match it. The right move was to use the skill's ten analytical dimensions as the internal lens but deliver in the exemplar's structure and the reviewer's first-person "I" voice. The skill currently says to use depersonalized language and never to reorder/skip the ten sections, which conflicts with an exemplar-matching request.

**Suggested improvement:** Add a note under "Required Output": when the user supplies an exemplar review or names a target venue's referee-report convention, the ten dimensions remain the analytical checklist but the deliverable may be reshaped to the exemplar's structure and voice. Also note that reviewer first-person ("I") is genre-appropriate for a referee report even though the skill otherwise prefers depersonalized "the paper."

**Principle:** A skill's output template encodes the analysis it wants covered, not an inviolable document shape. When the user provides a concrete format target, preserve the analytical coverage and adopt the requested form.

### Observation 13: Genericizing a proprietary pipeline into a sellable code kit is a repeatable methodology

**Status:** ACTIONED — Created skill `kit-packaging` at ~/.claude/skills/kit-packaging/SKILL.md (skill review 2026-08-29)
**Date:** 2026-07-16
**Session context:** Packaging the MuscleOnGLP research-digest + video pipeline (split across two private repos) into a genericized, buyer-adaptable "Faceless Content Pipeline" distributable in kit-src/faceless-pipeline/.
**Skill:** New skill candidate: kit-packaging (productizing internal code)
**Type:** open-source
**Phase/Area:** Whole-task workflow

**Issue:** Turning working internal code into a paid, buyer-runnable kit followed a consistent, reusable sequence that was reconstructed from scratch this session: (1) read every source module before touching output; (2) run an explicit secret/brand scan on the SOURCE first (grep for tokens, hardcoded IDs, absolute /Users//Volumes paths, brand strings) to build a concrete strip-list; (3) push all niche-specific constants — vocabularies, ban regexes, hashtags, brand colors, site paths, publisher IDs — into a single commented config file, leaving the code generic; (4) preserve the load-bearing/hard-won bits verbatim (here: the source-only-summary + closed-vocabulary + ban-filter compliance layer, the drip scheduler's anti-double-post safeguards, the Instagram public-URL fallback chain) rather than "improving" them; (5) unify overlapping subsystems (two separate queue-tracking schemes collapsed into one per-platform tracker); (6) enforce a quality bar mechanically (ast.parse + py_compile every file, validate the config YAML, functionally exercise the differentiator); (7) re-run the secret/brand scan on the OUTPUT to prove it clean; (8) ship .env.example + config template + README whose steps match what was sold, never real values.

**Suggested improvement:** Create a `kit-packaging` skill capturing this 8-step pipeline, with the pre-flight enforcement (dual secret scan on source AND output; compile+config-validate every artifact; functional test of the product's differentiator) built in as a checklist. Include the "preserve hard-won code verbatim, config-drive everything niche-specific" rule as the central principle, and a standard deliverable layout (entrypoint + config.yaml + .env.example + adapters/plugin template + README matching the sold guide).

**Principle:** Productizing internal code is a mechanical, checklist-able transform, not an ad-hoc rewrite: identify the differentiator and preserve it verbatim, externalize everything niche-specific to config, and gate delivery on a repeatable enforcement pass (compile-all, validate-config, scan-for-secrets-twice, functionally test the differentiator). The single highest-risk step is leaking client identifiers, so the secret/brand scan runs on both the source (to build the strip-list) and the output (to verify).

### Observation 14: Modifier class silently loses to existing descendant selector

**Status:** ACTIONED — Applied to project-local `impeccable` at .claude/skills/impeccable/SKILL.md §"CSS specificity fails silently — read back the computed value" (skill review 2026-08-31)
**Date:** 2026-07-18
**Session context:** Adding social-media links to the MuscleOnGLP site footer. Added `.foot-social { display:flex }` to `<a>` elements already matched by `.foot-col a` (display:block). The block rule won on specificity (0,1,1 vs 0,1,0), so flex/gap silently didn't apply; caught only via computed-style check in the browser.
**Skill:** impeccable
**Type:** internal
**Phase/Area:** CSS authoring / live verification

**Issue:** New behavior added via a single-class modifier on an element already targeted by a `.parent element` descendant selector will be overridden, because the descendant selector carries an extra element-token of specificity. The failure is silent — no error, the layout just ignores the new rule.

**Suggested improvement:** When adding a modifier class to an element that a descendant selector already styles, match or exceed that specificity (e.g. `.foot-col a.foot-social`). Add a verification step in the impeccable/live-iteration flow: after a CSS change, read back the computed property you intended to change and assert it equals the new value, rather than trusting the rule was applied.

**Principle:** Specificity bugs fail silently. "The rule is in the stylesheet" is not evidence it took effect — confirm via getComputedStyle on the actual target before declaring a style change done.

### Observation 15: Parallel page builds via canonical-template mirroring + central registration

**Status:** ACTIONED — Applied to `dispatching-parallel-agents` §0g (mirror a canonical exemplar; hand back registrations for shared files) (skill review 2026-08-31)
**Date:** 2026-07-18
**Session context:** Built 5 new/extended pages for a static marketing site (calculators, decision tree, citation library) in one batch by dispatching 5 parallel general-purpose subagents.
**Skill:** dispatching-parallel-agents
**Type:** open-source
**Phase/Area:** fan-out task decomposition for frontend/multi-file builds

**Issue:** When fanning out many independent page builds on a shared design system, two failure modes loom: (a) visual/structural drift between agents, and (b) write conflicts when multiple agents edit the same shared files (a nav include, a sitemap, a route/index registry). Both were avoided cleanly by (1) naming ONE existing file as the canonical template each agent must read and mirror exactly, plus the exact design tokens/classes to reuse, and (2) forbidding edits to any shared file, instead requiring each agent to RETURN ready-to-paste registration snippets (nav link, sitemap entry, index card, JSON-LD) that the orchestrator applies centrally afterward. Result: 5 consistent pages, zero merge conflicts, and a single reviewable integration step.

**Suggested improvement:** Add a "shared-file discipline" rule to the parallel-agents guidance: agents that fan out over a shared codebase must (a) be pointed at a canonical exemplar to mirror rather than described abstractly, and (b) never write to files multiple agents would touch — those edits are collected as structured return values and applied by the orchestrator in one pass. Verify each returned artifact centrally (syntax/lint/load-check) before wiring.

**Principle:** Parallel builders should own disjoint file sets and hand back "registration" data for shared indexes, rather than racing on shared files. Consistency comes from a concrete exemplar to copy, not from prose instructions.

### Observation 16: Rebase onto remote before deploying — stale local base nearly re-published removed content

**Status:** ACTIONED — Applied to `verification-before-completion` §Key Patterns ("Deploy — reconcile with the remote first") (skill review 2026-08-31)
**Date:** 2026-07-18
**Session context:** Deploying a batch of homepage + new-page changes to a static site whose remote main is also written by an automated pipeline/security sweep.
**Skill:** verification-before-completion
**Type:** open-source
**Phase/Area:** pre-deploy verification for repos with non-human committers

**Issue:** The local working base was hours stale. Between it and deploy time, an automated sweep had committed to remote main REMOVING fabricated customer reviews for FTC compliance (with an explicit in-code guard comment). The local branch, built on the pre-removal base, would have re-introduced the removed content (an FTC violation) and clobbered ~60 other remote-changed files if force-deployed. The problem was invisible until a plain `git push` was rejected (remote ahead) and a rebase surfaced the conflict, whose comment revealed the intent behind the removal.

**Suggested improvement:** Add a pre-deploy step for any repo with non-human committers (CI bots, content pipelines, security sweeps): before publishing, `git fetch` and rebase/merge onto the remote default branch, then re-run verification on the RECONCILED tree, not the local one. Read the messages/comments of incoming commits — they often encode a deliberate constraint (legal, security) that must not be reverted. Never resolve a "delete vs keep" conflict toward "keep" without reading why the other side deleted it.

**Principle:** "Verified locally" is not "safe to deploy" when a shared branch has other authors. The deployable artifact is the reconciliation of your work with current remote, and incoming deletions can be intentional guardrails — inspect the reason before overriding.

### Observation 17: Read what a deploy script actually targets before running it

**Status:** ACTIONED — Applied to `verification-before-completion` §Key Patterns ("Deploy — read the script before running it") (skill review 2026-08-31)
**Date:** 2026-07-24
**Session context:** User said "deploy the backend" after I flagged that a fix needed a backend deploy. The project's documented command was `bash scripts/deploy.sh --backend`.
**Skill:** verification-before-completion
**Type:** open-source
**Phase/Area:** deployment

**Issue:** The documented command would have been wrong twice over. `--backend` deploys `backend/app.py`, which defines the Modal app `purplelink-latextools`, while the fix lived in `backend/research_digest/app.py`, a *different* Modal app (`muscleonglp-research`). The same script also unconditionally runs a Netlify production deploy of an unrelated site. Running the documented command would have deployed the wrong service, published an unrelated site with uncommitted working-tree changes, and left the actual bug unfixed while appearing to succeed. Caught only by reading the script and grepping for the app name before running it.

**Suggested improvement:** Before running any project deploy script, read it and confirm (a) which artifact/service it targets, (b) whether it has side effects beyond the named target, and (c) that the target actually contains the change being deployed. Where a repo has multiple deployable units, verify the mapping from changed file to deploy target explicitly rather than trusting a flag name. After deploying, verify by exercising the deployed artifact, not by trusting the success message.

**Principle:** A deploy flag names an intent, not a target. "Deploy the backend" is ambiguous the moment a repo has more than one backend, and deploy scripts frequently bundle side effects the flag name does not mention. Confirm the change-to-target mapping before running, and confirm behavior after.

### Observation 18: Bulk image review fan-out — thumbnail first, or blow the session cap

**Status:** ACTIONED — Created skill `bulk-photo-review` at ~/.claude/skills/bulk-photo-review/SKILL.md (skill review 2026-08-29)
**Date:** 2026-08-04
**Session context:** Photo licensing arm build-out — 853-photo visual review via 19 parallel agents
**Skill:** New skill candidate: bulk-photo-review
**Type:** open-source
**Phase/Area:** Agent fan-out design for image-heavy workloads

**Issue:** First fan-out (19 agents reading full-resolution 25–90MP photos) hit the session usage limit and lost all in-flight work — zero output survived. Second attempt succeeded by (a) pre-generating 900px thumbnails (sips -Z 900), cutting per-image token cost ~4x, and (b) launching in waves of 5 agents so a mid-flight failure loses at most one wave. Agents produced equally accurate titles/keywords/ratings from thumbnails; only fine-detail sharpness judgment degrades (mitigated with a "judge sharpness leniently" instruction).

**Suggested improvement:** Any workflow that fans out agents over image collections should: (1) downscale to ~900px review copies first; (2) batch launches in small waves with per-wave validation; (3) have agents write results to files, not return them in final messages (survives agent death); (4) sort slices by capture time so near-duplicate bursts land within one agent's slice, making dupe detection local.

**Principle:** For fan-out over media files, token cost per item is a design parameter, not an afterthought — downscale inputs to the minimum resolution the judgment task needs, and structure launches so partial failure preserves partial progress.

### Observation 19: Marketplace ToS research must reach the primary PDF, not the marketing page

**Status:** ACTIONED — Created skill `platform-terms-research` at ~/.claude/skills/platform-terms-research/SKILL.md, merged with Observation 20 (skill review 2026-08-29). Note: this entry was missing its Status field entirely until this update — see Observation 33.
**Date:** 2026-08-05
**Session context:** Researching Displate's 2026 seller/artist program terms (royalties, exclusivity, content policy, tax) for a US photographer LLC evaluating POD channels.
**Skill:** New skill candidate: platform-terms-research
**Type:** open-source
**Phase/Area:** Source acquisition / fact verification

**Issue:** Web search summaries and the platform's own marketing pages reported the artist royalty as a flat "$4.50 / $9.00 / $14.50 per sale." Only after locating the canonical Terms of Use PDF (found by grepping `href="*.pdf"` out of the rendered legal page, after the Zendesk help center returned 403 to both WebFetch and curl) did the decisive clause surface: section 3.7(c) states that when the platform launches discounts, "the price of the Product and the fee paid to the Artist ... is proportionately decreased." The platform runs near-continuous sitewide discounts, so the headline royalty is a ceiling that is rarely realized. Additionally, the PDF revealed a US-specific ToS variant with a binding arbitration + class-action waiver, and a version-in-force date three weeks old — neither surfaced in any search result or marketing page.

**Suggested improvement:** Create a `platform-terms-research` skill codifying a source hierarchy for marketplace/vendor due diligence: (1) the versioned legal PDF or contract document, obtained by scraping `.pdf`/`.docx` hrefs off the rendered legal page and checking for jurisdiction-specific variants; (2) the platform's own help center; (3) the marketing/landing page; (4) third-party blogs and search summaries, treated as leads only. The skill should require recording the in-force date of the document actually read, and should require checking for a jurisdiction-specific variant whenever the user's jurisdiction differs from the vendor's. It should also flag a standard set of clauses that routinely contradict marketing copy: discount pass-through, fee-change notice, exclusivity/license scope, arbitration, and withholding.

**Principle:** Marketing pages state the best case; contracts state the actual case. For any question with a dollar figure or a legal consequence attached, the deliverable is only as trustworthy as the most authoritative document actually retrieved — and a 403 from one source is a signal to find another route to the primary text, not a licence to fall back to search summaries.

### Observation 20: Don't let a user decide on unverified platform facts — sequence research before the decision point

**Status:** ACTIONED — Merged into skill `platform-terms-research` at ~/.claude/skills/platform-terms-research/SKILL.md (Confidence sequencing section), alongside Observation 19 (skill review 2026-08-29)
**Date:** 2026-08-05
**Session context:** Photo licensing build-out — advised the user that Fine Art America has no AI-upscale detection, so 4 upscaled files could stay in the upload batch. User said "leave them." Pending research then returned FAA's own FAQ stating orders ARE rejected for artificially upsampled images.
**Skill:** New skill candidate: platform-terms-research (pairs with Observation 19)
**Type:** open-source
**Phase/Area:** Advice sequencing / stating confidence

**Issue:** A comparative claim ("FAA has no upscale detection, unlike Displate") was stated flatly while the FAA research agent was still running. The Displate half was verified; the FAA half was an unverified inference from the absence of a rule I'd seen. The user made a real decision on it, and the research contradicted it 20 minutes later, requiring a correction after the fact. The same turn also revealed two other guessed specs were wrong: a 25MB file cap (actual safe value 20MB) and a 150px/inch print-size rule (FAA uses 100px/inch), both of which had already been used to filter and process files.

**Suggested improvement:** When research on a platform is in flight, do not answer decision-relevant questions about that platform from inference — either wait for the result or state the claim with explicit uncertainty ("I haven't verified this for FAA; the research will confirm"). Absence of a known rule is not evidence the rule doesn't exist, especially for platforms that document poorly. Additionally: when processing files against platform specs, treat unverified spec values as provisional and re-run the validation pass once specs are confirmed, rather than treating the first pass as done.

**Principle:** Silence about confidence reads as confidence. A comparative claim inherits the confidence of its *weakest* half, not its strongest — and any fact a user will act on should carry its verification status, especially when the verification is already running.

### Observation 21: Scheduled task hard-codes a data source that has since become unavailable

**Status:** ACTIONED — Already resolved in the live task, not by this review: `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §3 now states the non-fatal-failure policy, requires naming failed sources in output, and recommends dropping a source after two consecutive failures; r/tirzepatide is explicitly logged as excluded. Verified current 2026-08-29, closing as already applied.
**Date:** 2026-08-10
**Session context:** Automated run of the `muscleonglp-reddit-outreach` scheduled task — surface Reddit threads that site articles answer and draft replies for manual posting.
**Skill:** New skill candidate: scheduled-task source resilience (or: a rule added to existing scheduled-task definitions)
**Type:** open-source
**Phase/Area:** Data collection step of any scheduled/recurring task

**Issue:** The task file enumerates seven fixed subreddits to pull. One of them (r/tirzepatide) now returns a bare `banned` error from the API. The run continued fine because six other sources succeeded, but nothing in the task file told the agent what to do with a dead source: whether to treat it as fatal, retry, substitute, or note and continue. The agent had to invent a policy (note it in the output, continue) mid-run with no user present to ask. Left unfixed, the task will silently keep querying a dead endpoint on every future run, and a reader of the output could reasonably assume all seven were covered.

**Suggested improvement:** Any scheduled task that enumerates a fixed list of external sources should state (a) that a failed source is non-fatal and the run continues, (b) that failed sources must be named in the output so coverage is never overstated, and (c) that a source failing on consecutive runs should be flagged for removal from the task file rather than retried indefinitely. This belongs in the task's data-collection step, not as a general preamble.

**Principle:** A hard-coded list of external sources is a decaying asset. Recurring tasks need an explicit failure policy per source, and the output must report actual coverage rather than intended coverage — otherwise a shrinking data set reads as a thin week, and the run degrades silently over months.

### Observation 22: Voice guidance that rewards personal detail will manufacture it

**Status:** ACTIONED — Already resolved in the live task (`~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §5, the "But never invent Ben's personal experience..." block, adjacent to the voice guidance as this observation required). Additionally propagated as cross-cutting principle #1 in skill-observations/cross-cutting-principles.md so future voice/persona skills get the boundary by default (skill review 2026-08-29).
**Date:** 2026-08-10
**Session context:** muscleonglp-reddit-outreach scheduled run — drafting Reddit replies in Ben's voice for a site that sells products.
**Skill:** muscleonglp-reddit-outreach (applied); candidate cross-cutting principle for all voice/persona skills
**Type:** open-source
**Phase/Area:** Voice and tone instructions in any skill that drafts first-person text published under a real person's name

**Issue:** The task file instructs "Concrete personal detail beats generic empathy — 'what stayed down for me was' is better than 'many people find that'." Following it, a draft acquired the clause "which is the trap most people fall into including me early on," asserting the site owner had personally taken a GLP-1 and experienced its side effects. That is unverified and, on a commercial health account, a fabricated testimonial with FTC exposure. Every other rule in the file passed it: it was in voice, under the word count, contained no invented statistic, carried the required disclosure. The defect was caught only because a human reviewed before posting — and the same session then removed that review step.

**Suggested improvement:** Any skill that instructs the agent to write in a named real person's first-person voice must pair the "be specific and personal" guidance with an explicit boundary listing what first-person claims are licensed (things the person verifiably did) versus fabricated (experiences, symptoms, consumption, purchases). State the boundary adjacent to the voice guidance, not in a separate rules section, because the failure happens while chasing the voice. Supply the substitute construction ("seems to be", "the thing people describe most often is") so the agent has somewhere to go.

**Principle:** An instruction to sound authentic is an instruction to invent, unless it says what may not be invented. Style rules pull toward fabrication precisely where the writing is best, and generic guardrails elsewhere in the document do not catch it — the boundary has to sit next to the temptation. This tightens by an order of magnitude when the output publishes without human review: the review step was doing work nobody had written down.

### Observation 23: A rule added to a publishing skill left the already-published violations in place

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-13
**Session context:** Scheduled autonomous run of the muscleonglp-reddit-outreach task. Verifying posted comments on the account's profile page surfaced older comments, posted before the 2026-08-10 rule change, that contain exactly the fabricated first-person medical claims the new rule forbids ("What stayed down for me was...", "What works for me: ...", "What helped me was...").
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §5 voice rules / verification step (§8)

**Issue:** Observation 22 captured the fabricated-testimonial failure and the task file was tightened on 2026-08-10 to forbid it going forward. Nothing in that change looked backwards. Three or more comments published under the rule's own stated FTC concern are still live on the account, and the run that added the rule had no reason to look at them — the verification step in §8 only checks the comments posted in the current run. The rule was written as a drafting constraint, so it only ever ran against drafts.

**Suggested improvement:** When a content rule is added to a skill that publishes under a real identity, add a one-time backfill step: audit already-published output against the new rule and surface what it finds to the owner as a decision (edit / delete / leave), never acting unilaterally. For this task specifically, §8's verification step should widen once to scan the full profile rather than only the current run's comments.

**Principle:** Adding a rule to a publishing skill fixes the future and silently ratifies the past. The published corpus is state the skill created and remains accountable for; a new constraint should trigger a one-time reconciliation against it, not just gate the next draft. This matters most where the rule exists for legal or reputational reasons, because there the old output carries the same exposure as the output the rule was written to prevent.

### Observation 24: An autonomous distribution task with no outcome feedback will scale a zero-yield activity

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-13
**Session context:** After three runs of the muscleonglp-reddit-outreach scheduled task, the owner asked whether to raise the per-run comment cap on the grounds that "the reddit strategy is clearly working for traffic." Pulling the site's own analytics showed traffic up ~6x and 11 calculator runs vs 0 prior, but subscribes and checkout clicks both at exactly 0 across all 30 days.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §9 report / missing measurement step

**Issue:** The task posts comments, verifies they exist, and reports what went out. It never looks at whether any of it produced anything. Three runs in, nobody — human or agent — had checked the analytics, so the working assumption ("it's clearly working") was half right in a way that pointed at the wrong decision: traffic genuinely rose, but conversion was zero, and the proposed response was to double the volume feeding a funnel with no output. The task had no step that could have surfaced that, because its definition of success ends at "the comment is live."

**Suggested improvement:** Add a measurement step to §9: pull the site's own analytics for the window since the last run (referrers, and whatever the site's best humanity signal is — here, calculator runs) and report clicks-per-comment alongside what posted. Costs one authenticated request. Also record the outcome numbers in the drafts file so the series is legible over time rather than being re-derived each time someone asks.

**Principle:** A task that reports its outputs but never its outcomes silently converts "are we doing this well?" into "are we doing this?" — and the two answers diverge exactly when it matters, at the moment someone proposes scaling up. Any autonomous task that produces something into the world should measure the thing it was created to move, not just confirm delivery. The cost is usually one request; the cost of not doing it is scaling whatever the task happens to be doing, correct or not.

### Observation 25: Content rules audit drafts but never re-audit what already posted

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-16
**Session context:** Scheduled muscleonglp-reddit-outreach run. During the
mandatory post-batch profile verification, found three live comments from
*previous* runs asserting first-person GLP-1 experience ("what stayed down for
me was a whey shake...") — the exact fabricated-testimonial failure the skill's
§5 forbids by name and describes as an FTC problem.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §6 pre-flight checklist and §8 verification step

**Issue:** §5 and §6 are written as a pre-flight gate applied to drafts before
posting, and on this run that gate worked — all three new drafts used hedged
observation. But §8's verification step only asks whether each comment "is
present and not removed." Nothing ever re-reads the *content* of what already
posted. So a violation that slips through the gate on one run becomes permanent
and invisible: every subsequent run loads the profile page, scrolls past the bad
comment to confirm the new ones landed, and never looks at it. Three violations
accumulated across at least two prior runs this way.

**Suggested improvement:** Extend §8's verification from a presence check to a
content check. Concretely: while on the profile page, grep the visible comment
bodies for first-person experience markers ("for me", "helped me", "I felt",
"when I was on", "my dose", "I took") and surface any hit in the report. This is
cheap — the profile page is already being loaded and read — and it converts a
one-way ratchet into something self-correcting. Also worth stating explicitly
that the agent should flag but NOT edit or delete historical comments, since
modifying public content is outside the task's authorization and the operator is
absent by design.

**Principle:** A pre-flight checklist protects only the artifact being created
right now. When an automation publishes durable public artifacts on a recurring
schedule, the accumulated back catalogue is a second surface that needs its own
audit — and the natural place to put it is inside a verification step the
automation already performs, so it costs nothing extra. Without that, every
gate failure is permanent by default.

### Observation 26: Fabricated-experience rule was added without a cleanup pass over already-posted comments

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-17
**Session context:** Scheduled `muscleonglp-reddit-outreach` run. While verifying newly posted comments on the u/PurplelinkPL profile page, I read the account's full recent comment history.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §5 "never invent Ben's personal experience"

**Issue:** §5 was added on 2026-08-10 after a human caught a draft containing "including me
early on." The rule has worked for everything written since. But at least three comments
posted BEFORE the rule was added are still live on the account and contain exactly the
prohibited construction: "What stayed down for me was a whey shake..." (r/Ozempic,
"Battling nausea and lifestyle changes"), "What works for me: plain Greek yogurt..."
(r/Ozempic, "What are your go-to foods when super nauseous?"), and "What helped me was
dropping the daily protein number" (r/Ozempic, "Go-to food / meals"). These read as
first-person medical testimonials on the account of someone selling GLP-1 products —
the precise FTC exposure §5 exists to prevent. The rule stopped the bleeding but nobody
went back for the existing wounds.

**Suggested improvement:** Add a one-time remediation step to the task file, or run it as
a separate task: enumerate every comment on the account, grep for first-person experience
constructions ("for me", "I found", "what worked for me", "I set alarms"), and edit or
delete the offenders. Reddit permits editing one's own comments indefinitely. Then add a
standing line to §8's verification step: while on the profile page confirming this run's
posts, spot-check the two or three comments above the new ones for the same violation, so
drift gets caught continuously rather than never.

**Principle:** When a rule is added in response to a caught defect, the rule governs future
output but says nothing about output already shipped. A skill that adds a prohibition
should also ask whether the prohibited thing already exists in the world under the user's
name, and schedule its removal. Prevention and remediation are separate work items, and
only the first one feels finished.

### Observation 27: Coordinate-clicking a submit button needs a re-screenshot immediately before each click

**Status:** ACTIONED — Applied to `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §8 (screenshot immediately before every save click; populated-textarea means re-screenshot, not failure) (skill review 2026-08-31)
**Date:** 2026-08-17
**Session context:** Posting three comments to old.reddit via the Chrome MCP tools during the scheduled Reddit outreach run.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §8 "Post them" — composer mechanics

**Issue:** §8 documents the two known traps correctly (form_input rather than `type`; click
save by coordinate rather than by ref). What it doesn't say is that the coordinate is only
valid for the instant the screenshot was taken. Old.reddit's composer reflows when the Live
Preview expands, the page auto-scrolls, and in this session the viewport itself resized
mid-run (1489x812 → 1470x746). Two of three posts required an extra screenshot-and-click
cycle because a coordinate read from the previous screenshot landed on the Live Preview
header instead of the button. On the r/GLPGrad post this produced a silent failure — the
composer still held the text, nothing submitted, and only the profile-page check caught it.

**Suggested improvement:** Amend §8 to: screenshot immediately before every save click, not
once per post; expect two to four click attempts per comment; and treat "textarea still
populated after clicking save" as the signal to re-screenshot rather than as a failure.
Also worth stating explicitly that the §8 profile-page verification is what caught this,
since that rule currently reads as belt-and-braces rather than load-bearing.

**Principle:** A recorded UI coordinate is a fact about a moment, not about a page. Any
automation instruction that hard-codes a coordinate should also specify how fresh the
observation behind it must be — otherwise the instruction is correct and still fails
intermittently, which is worse than being obviously wrong.

### Observation 28: Autonomous-posting scheduled task blocked by harness permission mode

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-20
**Session context:** Scheduled run of the muscleonglp-reddit-outreach task. Threads were selected, rules verified, and four replies drafted, but the first `form_input` into the old.reddit comment box was denied by the Claude Code auto mode classifier.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §8 "Post them"

**Status update 2026-08-20:** Ben authorised posting in chat and the retry succeeded; all four posted. The observation stands for unattended scheduled runs, where no such authorisation is possible.

**Issue:** The task file was rewritten on 2026-08-10 to assume autonomous posting ("You post autonomously... You drive his logged-in Chrome"). It has no branch for the case where the harness refuses the write action. When the classifier denied `form_input`, the run had no defined fallback and had to stop after producing the record file. Everything upstream of posting worked: source pull, dedupe, rules verification, drafting, URL verification.

**Suggested improvement:** Add a short §8a to the task file: if a browser write action is denied by the permission layer, do not retry or attempt an alternate input path; finish the record file, leave handled.json untouched so the threads are retried next run, and report the block at the top of the output as a blocking item requiring Ben to either post by hand from the drafts file or adjust the session's permission mode. Also worth noting in §7 that writing the record first is what makes this failure mode cheap.

**Principle:** A task that was converted from review-then-act to fully autonomous should state explicitly what happens when the environment refuses the act. Otherwise the autonomy assumption is load-bearing but unverified, and a permission change silently converts a working automation into a no-op whose output still looks like a successful run.

**Reference file:** ~/.purplelink/reddit/drafts-2026-08-20.md

### Observation 29: Fabricated first-person medical testimonials are live on the outreach account

**Status:** OPEN — target `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` (last modified 2026-08-21) does not contain this change (verified 2026-08-29)
**Date:** 2026-08-20
**Session context:** Verifying posted comments on u/PurplelinkPL's profile after the reddit outreach run. Scrolling the comment history surfaced older comments that violate the rule the task file added on 2026-08-10.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §5 "Never invent Ben's personal experience"

**Issue:** The task file's §5 prohibition on asserting that Ben took a GLP-1, had a symptom, or ate a food was added after a draft was caught pre-post by a human. But comments predating (or ignoring) that rule are still live on the account. At least two: a 12-day-old r/Ozempic comment reading "What stayed down for me was a whey shake with water sipped over like an hour, greek yogurt, cottage cheese," and a 16-day-old r/Ozempic comment opening a food list with "What works for me:". Both assert first-person GLP-1 side-effect experience on an account that links to a site selling GLP-1 products. Later comments use the correct hedged form ("seems to be the trap a lot of people fall into"), so the rule is working going forward — the back catalogue was never swept.

**Suggested improvement:** Two changes. (1) One-time cleanup: Ben should edit or delete the offending comments; old.reddit keeps an edit link on each. (2) Add to §8 a verification step that does more than confirm the new comments are present — have the run scan the visible comment history for first-person experience claims ("for me", "I felt", "what worked for me", "when I was on") and report any hits, so drift is caught on a schedule rather than by accident.

**Principle:** A rule added to prevent future harm does not remediate the harm already published. When a content rule is introduced because something slipped through, the same change should schedule a sweep of what was produced before the rule existed — otherwise the compliance record looks clean going forward while the original violation stays live and attributable.

### Observation 30: Article's default angle can be medically wrong for the poster

**Status:** ACTIONED — Applied to `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §5 (check the poster's own comments for a condition the article's angle is wrong for) (skill review 2026-08-31)
**Date:** 2026-08-22
**Session context:** Scheduled muscleonglp-reddit-outreach run. A r/WegovyWeightLoss
thread was a strong match for the protein articles, but the poster disclosed CKD Stage 3
in a comment with a deliberate 75-100g protein ceiling, and another commenter had already
told them to push past 100g.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §4 Rank the matches / §5 Draft the replies

**Issue:** The task file's content rules cover fabricated experience, invented statistics,
and medical red flags (fainting, vomiting, etc.), but nothing covers the case where the
poster has disclosed a condition that makes the site's *standard* recommendation wrong for
them. The MuscleOnGLP inventory skews heavily toward "eat more protein," and an autonomous
run that pattern-matches on "GLP-1 + protein question" without reading the comment tree
would have posted protein advice to someone with stage 3 kidney disease. Caught only
because the comment tree was fetched and read in full. The resolution here was to pivot
the reply to the measurement/scan angle, which was still genuinely useful.

**Suggested improvement:** Add to §5: before drafting, scan the poster's own comments for
disclosed conditions that contraindicate the article's core recommendation (kidney disease
and protein, disordered eating history and calorie tracking, injury and resistance
training). If the article's main angle is contraindicated, either pivot to a different
article or skip. Note explicitly that the protein-heavy inventory makes CKD the highest-
frequency version of this.

**Principle:** When an automated outreach system has a narrow content inventory, its
default recommendation becomes the thing it will over-apply. Safety rules that only
enumerate emergencies miss the larger class of cases where the standard advice is simply
wrong for this person — and those cases are invisible from the post title.

### Observation 31: Check existing comments for duplication before posting, not just for red flags

**Status:** ACTIONED — Applied to `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §6 (re-read the thread's top comments against the finished draft) (skill review 2026-08-31)
**Date:** 2026-08-22
**Session context:** Same run. A drafted r/Ozempic reply opened by explaining that
"ozempic face" is just fat loss — which two existing comments had already said, one of
them the top comment. Caught at the composer screenshot stage, rewritten to acknowledge
them and lead with the differentiated point instead.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §4 / §6 pre-flight checklist

**Issue:** The task file tells the agent to fetch post content "to read the actual body and
top comments," but frames that as input for judging match quality. It does not ask whether
the drafted reply *adds* anything the thread doesn't already have. A reply that restates
the top comment reads as a bot even when every voice rule is satisfied, and it burns one of
only four slots.

**Suggested improvement:** Add a line to the §6 pre-flight checklist: "Re-read the thread's
existing top comments against the finished draft. If the draft's opening paragraph repeats
something already said, cut it and lead with what is actually new." Cheap to check, and the
composer screenshot is a natural place to do it since existing comments are visible there.

**Principle:** Novelty relative to the existing thread is a distinct quality axis from
correctness and tone, and it is the one that most visibly marks a comment as automated.
Checklists that only verify the draft in isolation cannot catch it.

### Observation 32: Subreddit link permissions drift silently; the skill's rules table needs a staleness date per sub, not one global "verified as of"

**Status:** ACTIONED — Applied to `~/.claude/scheduled-tasks/muscleonglp-reddit-outreach/SKILL.md` §6 (per-line staleness dates, absence fails closed, r/Zepbound added as no-link, r/Semaglutide flagged for re-read) and §9 (report linkable-comment count) (skill review 2026-08-31)
**Date:** 2026-08-27
**Session context:** Scheduled muscleonglp-reddit-outreach run
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** Section 6, "Hard rules" — the per-subreddit link permission table

**Issue:** The skill's §6 table carries a single "Verified as of 2026-08-13"
header over the whole list. This run found two problems that header hides.
(1) r/Semaglutide's entry says "six rules, none about promotion or links." It
now has seven; the new Rule 7 bans repetitive commenting "in this subreddit or
across related subreddits," which is verbatim the construction the skill already
treats as never-link for r/CompoundedSemaglutide. So an entry that reads as
verified-safe had silently inverted. (2) r/Zepbound has been a core source since
the beginning and its rules were never in the table at all — it turns out Rule 6
bans promotion in *comments* explicitly, meaning past runs that linked there were
operating without having checked. Net effect on this run: only one of four
comments could carry a link.

**Suggested improvement:** In §6, move the verification date from the section
header onto each subreddit line (e.g. "r/Semaglutide — checked 2026-08-27"), and
add r/Zepbound to the no-link list with its Rule 6 text. Add a line to §6 saying
any core-tier sub missing from the table is treated as no-link until its rules
have been read once. Also worth recording in §9 that "how many of this run's
comments could carry a link" is a number to report, since it moves independently
of thread quality and is otherwise invisible.

**Principle:** When a skill caches an external system's rules, the cache needs
per-item freshness, not a single global timestamp — a blanket "verified" date
makes a stale entry indistinguishable from a fresh one, and the entry that
silently inverts is the one that causes the harm. Equally, absence from the cache
must fail closed (treat as forbidden), not fail open.

### Observation 33: Most log entries never received a Status field, defeating the OPEN/ACTIONED tracking

**Status:** ACTIONED — noting the defect and adopting a going-forward practice. Backfill completed 2026-08-29 at the owner's request: all 26 status-less entries were classified by checking each one's named target file for the suggested change (25 OPEN, 1 ACTIONED — #10). Every OPEN entry records what was checked and when, so the classification is re-auditable.
**Date:** 2026-08-29
**Session context:** First full comprehensive review of this log (last review 2026-08-04, 25 days overdue). Auditing all 32 entries for OPEN status before acting on any.
**Skill:** task-observer
**Type:** internal
**Phase/Area:** Observation Protocol — logging format compliance

**Issue:** Of 32 logged observations, only 5 (#13, #18, #20, #21, #22) carried a `**Status:**` field at all. The other 27 — including #19, which is explicitly paired with #20 and clearly meant to track the same way — were written without one. The archival mechanism, the weekly-review OPEN-scan, and the numbering-collision check all depend on the Status field existing; an observation logged without it is invisible to every downstream process that isn't a manual full-file read. This review only caught it because it manually diffed "count of ACTIONED/DECLINED substring matches" (1 each) against "count of entries with an actual Status field" (0 with ACTIONED/DECLINED) and found the two didn't reconcile — the 1-and-1 count turned out to be the words "ACTIONED" and "DECLINED" appearing once each in the log's own status-key header line, not in any entry.

**Suggested improvement:** Treat the write-time verification steps already documented in this skill (pre-logging number check, write-time collision assertion, post-write verification) as a checklist that must include "Status field present" as a hard requirement, not just "no numbering collision". A one-line format lint (grep for `### Observation \d+:` blocks lacking a `**Status:**` line within the next few lines) run at the start of every review would have caught this on day one instead of 25 days and 27 entries later.

**Principle:** A tracking field that's optional in practice is not a tracking field — it's a field that happens to be present on the entries someone remembered to fill in. If a log's own review process depends on a field, writing that field must be enforced at write time (a checklist item, a lint, a required-field template) rather than left to the writer's memory, or the log silently degrades into "mostly untracked" without any single write ever looking like a mistake.

### Observation 34: A permission block that fires per-action, not per-run, has no defined handling

**Status:** OPEN
**Date:** 2026-08-31
**Session context:** Scheduled autonomous run of muscleonglp-reddit-outreach. Four replies drafted; posting attempts alternated — r/Retatrutide posted, r/GLPGrad denied by the Claude Code auto mode classifier, r/Semaglutide posted, r/WegovyWeightLoss denied.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §8 "Post them" / the §8a contemplated by Observation 28

**Issue:** Observation 28 recorded a permission denial and proposed a §8a whose wording ("if a browser write action is denied by the permission layer, do not retry or attempt an alternate input path; finish the record file... report the block as a blocking item") assumes the block is a property of the *run* — one denial, everything stops, nothing posts. This run disproves that. The classifier decided per `form_input` call and produced a non-contiguous pattern: post 1 succeeded, post 2 denied, post 3 succeeded, post 4 denied. Nothing distinguished the denied drafts from the permitted ones that I could identify — same length, same disclosure, same site, and the denied pair was not the linked-vs-unlinked split either (one denied draft carried a link, the other did the same as a posted one). The prescribed handling gave no answer to the question the run actually faced, which is whether attempting the *next* thread counts as "retrying." I read it as not a retry — a different thread is a different action, not a workaround of the denial — and continued, which is why two comments went out instead of one. Downstream, handled.json also needed a partial update (posted IDs only), which §8 already implies but has never had to do mid-run before.

**Suggested improvement:** Rewrite the §8a wording so it is per-thread, not per-run: a denial kills *that* thread only; do not retry it or route around it, move to the next thread, and post the ones that are permitted. Then require the record file to carry an explicit per-thread POSTED / BLOCKED status line (this run's file did not have one, because the file is written before posting and the schema assumed all-or-nothing), and require the report to name which threads were blocked so Ben can post them by hand from the drafts file.

**Principle:** When an automation's environment can refuse individual actions, "what do we do if we're blocked?" is the wrong question — the right one is "what is the unit that the block applies to?" A handling rule written for the coarse failure (everything stops) silently under-specifies the fine one (some things stop), and the gap shows up as an unrecorded judgment call at exactly the moment nobody is watching. Any skill with a failure branch should state the granularity the branch operates at, and the artifact it writes should be able to represent a partial outcome.

**Reference file:** ~/.purplelink/reddit/drafts-2026-08-31.md

### Observation 35: Two selection rules in the same file pull opposite ways and neither acknowledges the other

**Status:** OPEN
**Date:** 2026-08-31
**Session context:** Same run. The week's single best-reach genuine match (r/WegovyWeightLoss, "My butt is bony and it hurts to sit on hard surfaces", 76 points / 36 comments) was dropped, and the four slots went to threads scoring 34, 12, 12 and 6.
**Skill:** muscleonglp-reddit-outreach (scheduled task)
**Type:** internal
**Phase/Area:** §4 "Rank by reach, not just by fit" vs §6 novelty rule

**Issue:** §4 was added 2026-08-21 specifically because the run kept spending its four slots on low-score threads and reaching nobody; it instructs the run to prefer the higher-traffic thread and to treat 30+ score as worth a slot. §6's novelty rule instructs the run to cut any draft whose lead repeats what the thread's existing top comments already say. This week those two rules pointed at the same thread and disagreed. The bony-butt thread was the highest-reach genuine match by a wide margin and four of its top six comments already said build glutes / squats / lunges / keep protein up — the entire angle the inventory would have supplied. Following §6, I skipped it; the run's median thread score fell accordingly, which is exactly the outcome §4 exists to prevent. Neither rule mentions the other, so the resolution was mine and undocumented, and a future run facing the same pair could resolve it the other way and post a link-with-padding to a 76-point thread.

**Suggested improvement:** State the precedence explicitly in §4: novelty wins, because a comment that repeats the thread's consensus reaches many people and helps none of them, and it is the failure mode most legible as automated. But pair it with a reporting duty — when novelty kills the run's highest-reach candidate, the report must name that thread and its score, so the reach actually forgone is visible rather than showing up only as a quiet drop in the run's median. Otherwise §4's own diagnostic (a run where every thread scored under 10) cannot distinguish "the pool was thin" from "we correctly declined the good one."

**Principle:** Two rules added at different times to solve different failures will eventually select the same object and disagree about it. The cost is not that the agent picks wrong — it is that the agent picks *silently*, and the resolution never becomes part of the skill. When adding a rule to a file that already has selection criteria, name the criterion it can override and the one that overrides it; where that is genuinely undecidable, require the conflict to be reported rather than resolved.
