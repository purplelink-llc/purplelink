#!/usr/bin/env python3
"""Check the experiment ledger against the dashboard's data.

  python3 scripts/traffic-dashboard/experiments_check.py            # human summary
  python3 scripts/traffic-dashboard/experiments_check.py --json     # machine-readable
  python3 scripts/traffic-dashboard/experiments_check.py --alerts   # only what needs a decision

Reads docs/growth-briefs/experiments.json (kept out of git: strategy notes) and
~/.purplelink/traffic/history.json (or $PURPLELINK_TRAFFIC_DIR). Read-only.
Verdicts: SCALE, KILL, REVIEW (review date reached), PENDING (needs Ben), HOLD
(running, no trigger), MANUAL (nothing measurable), DONE (killed/scaled already).
Guards: a kill needs age >= after_days; an orders-based scale needs n >= min_n.
"""
import datetime as dt, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path(os.environ.get("PURPLELINK_EXPERIMENTS") or ROOT / "docs" / "growth-briefs" / "experiments.json")
TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
MARKET_PREFIX = {"etsy": "etsy:", "gumroad": "gumroad:", "payhip": "payhip:"}


def source_of(row_id: str) -> str:
    for name, pre in MARKET_PREFIX.items():
        if str(row_id).startswith(pre):
            return name
    return "stripe"


def measure(metric: dict, history: dict, started: dt.date) -> dict:
    kind = metric.get("kind")
    if kind in ("orders", "revenue"):
        lo = dt.datetime.combine(started, dt.time.min).timestamp()
        n, net = 0, 0.0
        products, src = set(metric.get("products") or []), metric.get("source")
        for r in (history.get("ledger") or {}).values():
            if r.get("ts", 0) < lo or (r.get("gross") or 0) <= 0:
                continue
            if products and r.get("product") not in products:
                continue
            if src and source_of(r.get("id", "")) != src:
                continue
            base = r["net"] if r.get("net") is not None else r.get("gross", 0)
            n += 1
            net += (base - (r.get("refunded") or 0)) / 100
        return {"value": n if kind == "orders" else round(net, 2), "n": n, "net": round(net, 2)}
    if kind == "views":
        site = (history.get("sites") or {}).get(metric.get("site", "purplelink")) or {}
        paths = ((site.get("latest") or {}).get("topPaths")) or []
        v = next((p["count"] for p in paths if p.get("key") == metric["path"]), 0)
        return {"value": v, "n": v}
    if kind == "clicks":
        site = (history.get("sites") or {}).get(metric.get("site", "purplelink")) or {}
        rows = ((site.get("latest") or {}).get("checkoutByProduct")) or []
        v = next((p["count"] for p in rows if p.get("key") == metric["product"]), 0)
        return {"value": v, "n": v}
    return {"value": None, "n": 0}


def evaluate(ex: dict, history: dict, today: dt.date) -> dict:
    out = {"id": ex["id"], "name": ex.get("name", ex["id"]), "status": ex.get("status", "running")}
    started = dt.date.fromisoformat(ex["started"])
    age = (today - started).days
    out["age_days"] = age
    m = ex.get("metric") or {}
    st = ex.get("status", "running")
    if st in ("killed", "scaled"):
        out.update(verdict="DONE", detail=st)
        return out
    if st == "kill-pending-ben":
        out.update(verdict="PENDING", detail=ex.get("on_kill", "needs Ben"))
        return out
    got = measure(m, history, started)
    out["measured"] = got["value"]
    review = dt.date.fromisoformat(ex["review"]) if ex.get("review") else None
    verdict, detail = "HOLD", ""
    scale, kill = ex.get("scale_if"), ex.get("kill_if")
    if m.get("kind") == "manual":
        verdict, detail = "MANUAL", m.get("how", "")
    else:
        v = got["value"]
        if scale and v is not None and v >= scale["gte"] and got["n"] >= scale.get("min_n", 0):
            verdict, detail = "SCALE", f"{v} >= {scale['gte']}: {ex.get('on_scale', '')}"
        elif kill and v is not None and v <= kill["lte"] and age >= kill.get("after_days", 0):
            verdict, detail = "KILL", f"{v} <= {kill['lte']} after {age} days: {ex.get('on_kill', '')}"
        else:
            detail = f"{v}" + (f" (baseline {m['baseline']})" if m.get("baseline") is not None else "")
    if review and today >= review and verdict in ("HOLD", "MANUAL"):
        verdict = "REVIEW"
        detail = (f"review date {review} reached; " + detail).strip("; ")
    out.update(verdict=verdict, detail=detail)
    return out


def main() -> int:
    args = set(sys.argv[1:])
    if not LEDGER.exists():
        print(f"no ledger at {LEDGER}", file=sys.stderr)
        return 2
    try:
        history = json.loads((TRAFFIC / "history.json").read_text())
    except Exception as e:
        print(f"cannot read history.json: {e}", file=sys.stderr)
        return 2
    today = dt.date.today()
    res = [evaluate(e, history, today) for e in json.loads(LEDGER.read_text())["experiments"]]
    if "--json" in args:
        print(json.dumps(res, indent=1))
        return 0
    alert = {"SCALE", "KILL", "REVIEW", "PENDING"}
    rows = [r for r in res if r["verdict"] in alert] if "--alerts" in args else res
    if "--alerts" in args and not rows:
        print(f"Experiments: {len(res)} tracked, nothing at a threshold.")
        return 0
    for r in rows:
        print(f"{r['verdict']:<8} {r['id']:<22} day {r['age_days']:>3}  {r['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
