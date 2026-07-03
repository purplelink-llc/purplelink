# Skill Observation Log

Observations captured during task-oriented work. Each entry identifies a
potential skill improvement or new skill opportunity.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created |
DECLINED = user decided not to pursue

---

### Observation 1: PrecisionConference (PCS) reviewer-assignment workflow is non-obvious and benefits from a dedicated skill

**Date:** 2026-05-28
**Session context:** Assigning reviewers to ICIS 2026 papers via PCS (new.precisionconference.com) as an Associate Editor, using the Chrome browser MCP.
**Skill:** New skill candidate: pcs-reviewer-assignment
**Type:** open-source
**Phase/Area:** Conference peer-review administration / browser automation

**Issue:** The PCS "Show potential reviewers" tab is not a curated/bidded shortlist — it is the entire conference reviewer corpus (4,494 rows for ICIS 2026), with the per-paper "Bid" column empty for everyone and the affinity/match "Score" column showing -1 (uncomputed) for all. Reviewer expertise is NOT in the sortable table (only score/name/committee-flag/volunteered/assigned counts); it lives solely on each reviewer's individual profile page. The actionable signals discovered: (a) "Volunteered Reviews > 0" is the real "requested reviews" filter (446 of 4,494 here), (b) "Assigned < Volunteered" = has capacity (peach background = at/over capacity), (c) self-rated expertise tiers (Expert/Competent/Novice) are heavily gamed by industry "expert-in-everything" signups, so they must be cross-checked against affiliation + a web search of the person. Efficient extraction: same-origin `fetch()` of the 446 profile pages run from the page console (via the JS tool), parsed with DOMParser, cached to localStorage to survive navigation. Assignment itself sends a declinable invitation email ("Assign and send email" vs "Assign but do not send email" vs "Do not assign").

**Suggested improvement:** Create an internal/open-source skill documenting the PCS AE reviewer-assignment workflow: how to read the potentials table, the vol>0 / capacity / peach semantics, the over-claimer trap, the bulk-profile-fetch+localStorage-cache technique, conflict-of-interest checks (author institutions), and the invitation vs force-assign distinction. Include the gotcha that get_page_text returns the full DOM (135K chars) regardless of DataTables pagination, so JS extraction beats text scraping.

**Principle:** When a web tool presents a huge unranked list with the useful discriminating data hidden in per-row detail pages, the scalable move is in-page scripted extraction (fetch + parse + cache) rather than manual paging — and self-reported metadata in crowd-sourced systems should always be triangulated against an independent source before acting on it.

### Observation 2: Citation-parsing specs must anticipate nobiliary-prefix and non-ASCII surnames

**Date:** 2026-06-04
**Session context:** Subagent-driven implementation of the Deep Citation Audit feature (Paper Review Layer 2). Task 1 built an author-year in-text citation regex.
**Skill:** writing-plans (and any citation/bibliography-parsing skill: citation-audit, citation-checker)
**Type:** open-source
**Phase/Area:** Spec/plan completeness for text-parsing tasks

**Issue:** The plan's author-year citation regex required every author surname to begin with an uppercase ASCII letter (`[A-Z][A-Za-z\-]+`). The implementation passed all planned tests, but the code-quality reviewer caught that this silently drops citations with lowercase nobiliary particles common in ML/NLP literature — "(van der Berg et al., 2021)", "(de Bruijn and Smith, 2018)". The plan author (me) did not anticipate this real-world variation, so no test covered it. Fixed by adding an `_AUTHOR` sub-pattern allowing up to two lowercase particle words before the capitalized surname.

**Suggested improvement:** When a writing-plans spec involves parsing human names, citations, or bibliographic strings, include explicit edge-case requirements/tests for: nobiliary/lowercase prefixes (van, de, der, von, da, bin), hyphenated and accented (non-ASCII) surnames, and single-name authors. Add a checklist line to writing-plans' Self-Review for parsing tasks: "Does the spec cover non-ASCII / non-canonical input variants, not just the happy-path format?"

**Principle:** Happy-path regex specs for human-generated formats (names, dates, citations, addresses) systematically under-cover real-world variation. A plan's test set should be seeded with known messy variants of the domain, because the implementer will faithfully reproduce the spec's blind spots — adversarial code review, not the planned tests, is what catches them.

### Observation 3: all-miss test covers title-only ref — S2/CrossRef short-circuit rather than fail over HTTP

**Date:** 2026-06-04
**Session context:** Code-quality review of Task 4 (async abstract fetch, feat/deep-citation-audit). Reviewing test coverage of the fallback chain.
**Skill:** writing-plans (and citation-audit, subagent-driven-development)
**Type:** open-source
**Phase/Area:** Test design for injected-client async fallback chains

**Issue:** The `test_fetch_source_abstract_all_miss_is_unavailable` test constructs a title-only PaperReference (no DOI, no arxiv_id). This means S2 and CrossRef exit before making any HTTP call — they short-circuit to `None` because neither identifier is present. The test exercises the "all None → unavailable" accumulator in `fetch_source_abstract`, but does NOT exercise S2 or CrossRef's HTTP-miss path. The OpenAlex title-search path IS exercised (the FakeClient returns 404). However, the spec says "try the three in order" — S2/CrossRef HTTP failures are not covered by either test.

**Suggested improvement:** Add a third test: a ref WITH a DOI, where all three endpoints return 404. This proves each fetcher swallows a non-200 response and that the chain truly falls through all three. One extra test, ~10 lines. The injected-client design makes this trivially cheap. Note for plans: "For a fallback chain of N sources, the minimum meaningful test set is: (a) first-source hit, (b) last-source-miss (all miss), (c) first-miss-second-hit (for each adjacent pair if budget allows), plus (d) all-miss-with-all-HTTP-attempted."

**Principle:** In an injected-client fallback chain, "all miss" can be reached two ways: no identifiers (every fetcher short-circuits before HTTP) or identifiers present but every HTTP call fails. Tests that conflate these two paths leave the HTTP-failure swallowing untested. A complete test suite for an N-source fallback needs at least one test where every fetcher reaches the network layer and still returns None.

### Observation 4: New LLM entry points must be routed through the centralized prompt-injection choke point

**Date:** 2026-06-04
**Session context:** Subagent-driven implementation of Deep Citation Audit (Paper Review Layer 2). A new module added an LLM call (assess_claims) that sent manuscript claims AND fetched third-party abstracts to the model.
**Skill:** writing-plans (and any skill that builds LLM pipelines with centralized safety handling)
**Type:** open-source
**Phase/Area:** Security review of multi-LLM-call features

**Issue:** The codebase routes all untrusted content through one safety module (sanitize + data-fence wrap + a system-prompt "untrusted boundary" preamble). The implementation plan specified a brand-new LLM call but did NOT require it to use that choke point, so the first implementation inserted attacker-controllable text (a cited preprint's abstract) into the prompt raw. Every planned unit test passed; only the adversarial FINAL code review (an opus reviewer explicitly asked to check prompt-injection parity) caught it. Fixed by adding the safety preamble to the system prompt and sanitizing+fencing both inputs, plus registering the new fence tags.

**Suggested improvement:** Add a checklist item to writing-plans' Self-Review for any feature that adds an LLM/tool call: "Does every new model/tool entry point route untrusted inputs through the project's existing sanitization/guardrail layer, matching sibling call sites? Add an explicit task + a test that an injection in each untrusted input is neutralized." When a codebase has a centralized safety/guardrail module, the plan should name it and require parity for new call sites.

**Principle:** Centralized security controls are only as good as their coverage. A new code path that bypasses the shared choke point is the most likely place for a regression, and happy-path unit tests never reveal it — an adversarial review pass that explicitly checks "does this new entry point match the security posture of its siblings?" is what catches it. Plans should make security-parity for new entry points an explicit, tested requirement, not an implicit assumption.

### Observation 5: UI audits of large SwiftUI apps need a grep-first inventory pass before reading

**Date:** 2026-06-04
**Session context:** UI consistency + usability audit of the Helm macOS SwiftUI app (~20 screens, 257KB Screens.swift). Tasked with finding inconsistencies, a11y regressions, missing confirmations, validation gaps, empty-state gaps, and emoji.
**Skill:** New skill candidate: swiftui-consistency-audit (or generalize: design-system-conformance-audit)
**Type:** open-source
**Phase/Area:** Audit methodology

**Issue:** The most efficient path through a huge single-file UI codebase was not linear reading but a battery of targeted greps against the known design-system tokens: list every `struct *Screen`, count `.helmScreen(` adoption, grep color literals (`.red/.green/.orange/Color.yellow`) vs `Theme.positive/negative/accent`, grep `GroupBox` vs `Card`, grep `EmptyState(` vs `ContentUnavailableView`, grep `role: .destructive` then classify each as immediate vs `confirmationDialog`-gated, grep `.disabled(` to check Save-button validation, grep `String(format:.*/100` for money-formatting bypasses of the canonical `CockpitData.money`, and a Unicode-range grep for emoji. Reading specific contexts came only after greps localized the suspects. This turned a 5000-line file into ~15 high-signal findings in a few passes.

**Suggested improvement:** Capture a reusable "design-system conformance audit" checklist that, given a token/component vocabulary (color tokens, spacing scale, the screen-scaffold modifier, the empty-state component, the money formatter, the confirmation pattern), runs as a fixed sequence of greps producing an adoption matrix (which screens use the canonical pattern vs an ad-hoc equivalent). Key heuristic: the strongest findings are where a canonical primitive EXISTS but newer code reaches for the framework default instead (e.g. `ContentUnavailableView` instead of the app's `EmptyState`, or `.red` instead of `Theme.negative`) — i.e. drift between older and newer screens.

**Principle:** In a mature codebase the bugs of consistency are "two ways to do the same thing." Auditing for them is a set-difference operation (canonical primitives ∖ their framework-default twins), which greps answer faster than reading. Inventory by grep, then read only the localized suspects.

### Observation 6: Swift money-parsing crash pattern recurs across a finance codebase

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

**Date:** 2026-06-05
**Session context:** Fixing a crash-DoS bug class (trapping numeric conversions) in the Helm Swift finance app, TDD, across 5 sites in 3 modules.
**Skill:** test-driven-development
**Type:** open-source
**Phase/Area:** Refactoring untrusted-input parsers without behavior change

**Issue:** The task spec supplied a generic `minorUnits(fromString:)` helper and suggested reimplementing two existing money-string parsers (`parseMoneyMinor`, CSV `parseMinor`) on top of it. But the two existing parsers had divergent, stricter accepted-format rules (European decimal-comma disambiguation, strict all-digit validation, positive-only vs signed). Wholesale replacement with the generic helper would have silently widened/narrowed accepted inputs. The safer move was to keep each parser's existing preprocessing/validation intact and extract ONLY the overflow-prone final arithmetic (`whole * 100 + cents`) into a shared `minorUnits(whole:cents:negative:)` combiner. This fixed the crash without touching which inputs are accepted/rejected.

**Suggested improvement:** When a security/robustness refactor must "preserve behavior except for the crash," identify the minimal unsafe operation and replace only that, rather than swapping in a more general helper that subtly changes accepted inputs. Add a TDD note: diff the accepted-input set before/after, not just the happy path.

**Principle:** "Preserve behavior" refactors are safest when the change surface is the single failing operation, not the whole function. A more general helper is a behavior change in disguise unless proven to be a strict superset.

### Observation 8: Warning-elimination tasks must include the test target, not just sources

**Date:** 2026-06-05
**Session context:** Task to make the Helm macOS Swift package build with zero compiler warnings. The task brief enumerated warnings only in Sources/ (Reporting.swift, AppModel.swift, the LedgerCore/CRM stores). After fixing all of those and confirming `swift build` was clean, `swift test` surfaced two additional identical `var comps` warnings in Tests/LedgerCoreTests/MRRTests.swift that the source-only build never compiled.

**Suggested improvement:** When a "zero warnings" hygiene task is specified, the verification step should always run the test build (`swift test` / equivalent), not just the product/library build, because test targets compile separately and carry their own warnings. Add this as an explicit verification sub-step in any build-hygiene workflow/checklist.

**Principle:** "Zero warnings" is only meaningful if every compiled target is checked. Library/app builds skip test targets entirely; a clean app build can still leave warnings in test code. Always enumerate and re-build all targets (sources + tests) before declaring a warning-free state.

### Observation 9: SwiftUI .onChange additions can break type-checker on large View bodies

**Date:** 2026-06-05
**Session context:** Helm crash-DoS sweep — adding `.onChange(of:)` triggers to a SwiftUI ReportsScreen body to refresh a cached budget card.
**Skill:** New skill candidate: swiftui-large-body-guard (or note for any Swift/SwiftUI engineering skill)
**Type:** open-source
**Phase/Area:** SwiftUI view-body editing

**Issue:** Adding a third `.onChange(of:)` modifier to an already-large SwiftUI `var body` tipped the Swift compiler into "unable to type-check this expression in reasonable time." The fix was to fold two `loadData()` triggers into a single `.onChange` keyed on a cheap computed `Equatable` signature (a String built from the relevant model fields), keeping the modifier-chain length flat. A naive `.onChange(of: model.budgets)` also wouldn't have been Equatable (Budget wasn't Equatable), and a `.count`-based key would have missed in-place edits (same count, changed amount) — the signature had to capture id/target/category.

**Suggested improvement:** When adding reactive triggers to a SwiftUI body, prefer consolidating multiple identical-action triggers into one `.onChange` keyed on a combined Equatable signature, rather than appending modifiers. For change-detection keys, capture the mutated fields (not just collection count) so in-place edits are detected.

**Principle:** SwiftUI view bodies have a practical complexity ceiling for the type-checker; each added modifier raises inference cost. Consolidating reactive triggers behind a single derived key is both cheaper to compile and more correct than chaining per-property observers — and change keys must reflect value mutations, not just element count.

### Observation 10: Parallel coding subagents on one working tree can destroy each other's uncommitted work via git cleanup

**Date:** 2026-07-02
**Session context:** Helm release-readiness sprint. Three changes in flight on one git working tree: the coordinator editing LedgerStore/LedgerImporter inline, plus two background Haiku agents (Reporting.swift optimization, OnboardingView fix). One background agent apparently encountered a mid-build inconsistency caused by the coordinator's in-flight edits and ran a git restore-style cleanup, silently reverting ALL uncommitted tracked changes — the coordinator's edits and the other agent's completed fix. Untracked files (new tests) survived; only the reverting agent's own file remained modified.
**Skill:** superpowers:dispatching-parallel-agents (also superpowers:subagent-driven-development)
**Type:** open-source
**Phase/Area:** Parallel subagent dispatch on a shared repository

**Issue:** Nothing in the dispatch prompts forbade git state-mutation commands, and the coordinator treated "different files" as sufficient isolation. But a shared build graph (swift build compiles the whole package) means one agent's build failure can be caused by another agent's half-applied edit — and an agent that "fixes" that by reverting the tree destroys sibling work. File-level disjointness is NOT isolation when build/test steps and git state are shared.

**Suggested improvement:** Any skill that dispatches multiple coding agents against one working tree should mandate: (1) every agent prompt includes an explicit prohibition on git restore/checkout/stash/reset and on reverting files the agent didn't change, with instruction to STOP and report if the tree looks broken; (2) commit all completed work before dispatching agents; (3) run coding agents sequentially unless given true worktree isolation; read-only research agents may parallelize freely.

**Principle:** A shared working tree plus a shared build graph makes "editing different files" a false isolation boundary. Uncommitted work is unprotected work: commit before dispatch, forbid git mutations in agent prompts, and reserve parallelism for read-only agents or isolated worktrees.
