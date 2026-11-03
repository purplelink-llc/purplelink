# Cost console

What each Claude Code session costs, at public API rates, from the transcripts already on disk. Design:
[docs/designs/cost-console.md](../../docs/designs/cost-console.md).

```bash
bash scripts/cost_console/run.sh            # last 14 days; --days N for another window
```

It reads `~/.claude/projects/` and the desktop app's session records (read-only) and writes
`~/.purplelink/cost-console/data.json` and `index.html` (folder 0700, files 0600). Publishing the page
needs a Claude session: publish `~/.purplelink/cost-console/index.html` to Ben's private cost console
artifact (its link is in the `cost-console-refresh` scheduled task). That task does both at 04:35 Eastern.

| File | What it does |
|---|---|
| `parse.py` | Scan, dedupe, price, flag; writes `data.json`; prints a cross-check against ECC's cost tracker |
| `pricing.json` | The price table (source and date inside) and the flag thresholds; edit here |
| `page.html` | The page template; `build_page.py` inlines the data at `/*__DATA__*/` |
| `build_page.py` | Writes `index.html` |
| `test_parse.py` | Tests on synthetic transcripts: `cd scripts/cost_console && python3 -m pytest -q` |

All figures are API-equivalent cost: on a subscription plan, what the same tokens would cost at API rates,
not cash billed. The page holds session titles and short tool previews; never commit its output or copy it
anywhere public.
