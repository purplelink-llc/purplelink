---
score: 32
total: 40
p0: 0
p1: 0
p2: 2
p3: 2
timestamp: 2026-11-14T16-30-00Z
slug: scripts-partials-report-pipeline-html
---
Target: the "How this report was made" figure (scripts/partials/report-pipeline.html, pipeline-compare.css) on
/tools/paper-review/, /tools/paper-review/confidential-manuscript-review/, /tools/paper-review/sample/ and
/publication-suite/. Before = origin/main at c4c498df9; after = branch claude/report-made-graphic.

## Design Health Score (before -> after)

| Heuristic | Before | After | Note |
|---|---|---|---|
| Visibility of system status | 2 | 3 | Four numbered stages on one rail show where each check sits |
| Match between system and real world | 3 | 4 | Chips name the real checks (statcheck, GRIM, CrossRef, seven reviewer roles) |
| User control and freedom | 2 | 3 | Detail moved into one `details` block; figure no longer forces a long read |
| Consistency and standards | 1 | 4 | Was three hand-copied variants; now one partial stamped by apply_layout.py |
| Error prevention | 2 | 3 | Claims now match the backend (CrossRef lookup, first 30 pages) |
| Recognition rather than recall | 2 | 3 | Shape carries the contrast; text not needed to see "one pass vs four stages" |
| Flexibility and efficiency | 3 | 3 | Container queries follow the column (860px sample page, phones) |
| Aesthetic and minimalist design | 2 | 3 | Sparse dashed track against a dense tinted one; 375px height 3456 -> ~1545 px |
| Recognize and recover from errors | 3 | 3 | n/a for a static figure; deletion wording now matches the privacy section |
| Help and documentation | 4 | 3 | Full detail kept, but one click away |
| **Total** | **24/40** | **32/40** | |

## Five-second test
Before: two similar card columns of bullet text; the difference had to be read. After: at 25% scale the dashed
three-dot track and the dense four-stage block are distinguishable without reading.

## Remaining issues
- P2: on a 375px phone the hub hero alone fills the first screen; the figure starts at ~900px.
- P2: stage 2 holds 18 chips; at 520-900px the column is long. Acceptable, watch on tablets.
- P3: the chat path's three labels are muted grey; intentional, but lowest-emphasis text in the figure (contrast 6.2:1).
- P3: one guide (/guides/get-feedback-on-a-paper-before-submitting/) still says the vision pass reads "every page".
