#!/usr/bin/env python3
"""Render the collected stats history into a single self-contained HTML page."""
import json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "photo-licensing-workspace" / "stats"
HISTORY = OUT / "history.json"
PAGE = OUT / "dashboard.html"

LABELS = {"fineartamerica": "Fine Art America", "adobe_stock": "Adobe Stock", "alamy": "Alamy"}


def fmt(v, money=False):
    if v is None:
        return "—"
    if money:
        return f"${v:,.2f}"
    return f"{v:,}"


def delta(cur, prev):
    if cur is None or prev is None or cur == prev:
        return ""
    d = cur - prev
    cls = "up" if d > 0 else "down"
    sign = "+" if d > 0 else ""
    return f'<span class="d {cls}">{sign}{d:,.0f}</span>'


def main():
    hist = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    if not hist:
        PAGE.write_text("<p>No data collected yet. Run scripts/stats-collect.py</p>")
        return
    cur = hist[-1]
    prev = hist[-2] if len(hist) > 1 else {"platforms": {}}
    P, PP = cur["platforms"], prev.get("platforms", {})

    def g(plat, key):
        return (P.get(plat) or {}).get(key)

    def gp(plat, key):
        return (PP.get(plat) or {}).get(key)

    total_bal = sum(v for v in (g("fineartamerica", "balance"), g("alamy", "balance")) if v)
    cards = [
        ("Total balance", fmt(total_bal, True), ""),
        ("FAA sales (30d)", fmt(g("fineartamerica", "sales_30d"), True), ""),
        ("FAA visitors (7d)", fmt(g("fineartamerica", "visitors_7d")),
         delta(g("fineartamerica", "visitors_7d"), gp("fineartamerica", "visitors_7d"))),
        ("Adobe downloads", fmt(g("adobe_stock", "downloads")),
         delta(g("adobe_stock", "downloads"), gp("adobe_stock", "downloads"))),
        ("Alamy images on sale", fmt(g("alamy", "on_sale_good")),
         delta(g("alamy", "on_sale_good"), gp("alamy", "on_sale_good"))),
        ("Alamy sales to date", fmt(g("alamy", "sales_to_date")), ""),
    ]

    rows = ""
    for key, label in LABELS.items():
        d = P.get(key) or {}
        status = ('<span class="ok">connected</span>' if d.get("ok")
                  else f'<span class="bad">needs re-login</span>')
        detail = ", ".join(f"{k.replace('_',' ')}: {fmt(v, 'balance' in k or 'sales_30d' in k)}"
                           for k, v in d.items()
                           if k not in ("ok", "error", "profile") and v is not None) or "—"
        if not d.get("ok"):
            detail = d.get("error", "")[:90]
        rows += f"<tr><td>{label}</td><td>{status}</td><td class='det'>{detail}</td></tr>"

    spark = ""
    if len(hist) > 1:
        pts = [(h["date"], ((h["platforms"].get("fineartamerica") or {}).get("visitors_7d") or 0))
               for h in hist[-30:]]
        mx = max(v for _, v in pts) or 1
        bars = "".join(
            f'<div class="bar" style="height:{max(3, round(100*v/mx))}%" title="{d}: {v}"></div>'
            for d, v in pts)
        spark = f'<h2>FAA visitors, last {len(pts)} collections</h2><div class="spark">{bars}</div>'

    PAGE.write_text(f"""<meta charset="utf-8"><title>Photo licensing dashboard</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 15px/1.5 -apple-system, system-ui, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; }}
 h1 {{ font-size: 1.4rem; margin-bottom: .2rem; }}
 .sub {{ color: #888; font-size: .85rem; margin-bottom: 1.5rem; }}
 .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .8rem; }}
 .card {{ border: 1px solid #8883; border-radius: 10px; padding: .9rem 1rem; }}
 .card .k {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: #888; }}
 .card .v {{ font-size: 1.6rem; font-weight: 600; margin-top: .2rem; }}
 .d {{ font-size: .8rem; margin-left: .4rem; }} .up {{ color: #1a7f37; }} .down {{ color: #c33; }}
 table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; }}
 th, td {{ text-align: left; padding: .5rem .4rem; border-bottom: 1px solid #8883; vertical-align: top; }}
 .det {{ color: #777; font-size: .85rem; }}
 .ok {{ color: #1a7f37; }} .bad {{ color: #c33; }}
 .spark {{ display: flex; align-items: flex-end; gap: 3px; height: 90px; margin-top: .6rem; }}
 .bar {{ flex: 1; background: #6a5acd; border-radius: 2px 2px 0 0; min-height: 3px; }}
 h2 {{ font-size: .95rem; margin-top: 2rem; }}
</style>
<h1>Photo licensing dashboard</h1>
<div class="sub">Collected {cur['collected_at'].replace('T', ' ')} · {len(hist)} day(s) of history</div>
<div class="cards">
{''.join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}{d}</div></div>' for k, v, d in cards)}
</div>
{spark}
<h2>Platforms</h2>
<table><tr><th>Platform</th><th>Status</th><th>Detail</th></tr>{rows}</table>
<p class="sub" style="margin-top:2rem">Re-authenticate with <code>scripts/stats-collect.py --login</code></p>
""")
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()
