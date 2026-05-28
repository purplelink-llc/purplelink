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
