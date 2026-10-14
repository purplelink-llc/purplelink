# A/B tests

One test at a time. Check date is 14 days after the live date.

| id | page | element | control | variant | hypothesis | live date | check date | unchanged comparison | status | result |
|---|---|---|---|---|---|---|---|---|---|---|
| ab-001 | / | meta description | "Apps and tools from a one-person studio in Atlanta: ModernTex, a $19.99 LaTeX editor; Outbound Veil, which checks what you type for personal information; Legroom for disk space; GlobePin for travel; and free online tools." (221 chars, truncates in results) | "Mac and iPhone apps and free tools from a one-person studio in Atlanta: ModernTex, a $19.99 LaTeX editor, Outbound Veil, Legroom and GlobePin." (138 chars) | A description that fits the results snippet and names Mac and iPhone raises homepage CTR. | not live | live date + 14 days | /tools/, /guides/latex/ | dry run: committed locally on branch ab/home-meta-description in the _worktrees folder, not pushed | none |
| ab-001 (2nd attempt) | / | meta description | same control as above | same variant as above (138 chars) | same | not live | 14 days after live | /tools/, /guides/latex/ | PR #95 open, 2026-10-14, not merged: site CI red on main (sitemap lastmod test, unrelated) | none |
