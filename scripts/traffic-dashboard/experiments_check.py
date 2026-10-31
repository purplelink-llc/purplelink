#!/usr/bin/env python3
"""Check the experiment ledger against the dashboard's data.

  python3 scripts/traffic-dashboard/experiments_check.py            # human summary
  python3 scripts/traffic-dashboard/experiments_check.py --json     # machine-readable
  python3 scripts/traffic-dashboard/experiments_check.py --alerts   # only what needs a decision

Reads docs/growth-briefs/experiments.json (kept out of git: strategy notes) and
~/.purplelink/traffic/history.json (or $PURPLELINK_TRAFFIC_DIR). Read-only.
A row with a "forms_rule" (a waitlist test) also gets a line with its Netlify form count from
artifact-data/forms.json (written by forms_export.py) next to each build-rule threshold.
Verdicts: SCALE, KILL, REVIEW (review date reached), PENDING (needs Ben), PROPOSED (not started), HOLD
(running, no trigger), MANUAL (nothing measurable), DONE (killed/scaled already).
Guards: a kill needs age >= after_days; an orders-based scale needs n >= min_n.
"""
import datetime as dt, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path(os.environ.get("PURPLELINK_EXPERIMENTS") or ROOT / "docs" / "growth-briefs" / "experiments.json")
TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
FORMS = Path(os.environ.get("PURPLELINK_FORMS_JSON") or TRAFFIC / "artifact-data" / "forms.json")
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
    if kind == "forms":
        site = (history.get("sites") or {}).get(metric.get("site", "purplelink")) or {}
        rows = ((site.get("latest") or {}).get("formBreakdown")) or []
        v = next((p["count"] for p in rows if p.get("key") == metric["form"]), 0)
        return {"value": v, "n": v}
    if kind == "clicks":
        site = (history.get("sites") or {}).get(metric.get("site", "purplelink")) or {}
        rows = ((site.get("latest") or {}).get("checkoutByProduct")) or []
        v = next((p["count"] for p in rows if p.get("key") == metric["product"]), 0)
        return {"value": v, "n": v}
    return {"value": None, "n": 0}


def forms_line(rule: dict, forms_doc, history: dict) -> str:
    """One line for a waitlist review: the form's verified count (and Yes share) against each build-rule threshold.

    rule: {"form", "path"?, "yes_field"?, "yes_value"?, "any_of": [{"signups_gte", "yes_share_gte"?, "visits_lt"?}]}.
    A missing forms.json or form says so; it is never read as 0 signups.
    """
    form = rule["form"]
    row = next((r for r in (forms_doc or {}).get("forms", []) if r.get("form") == form), None)
    if forms_doc is None:
        return f"{form}: forms.json missing (run forms_export.py), so the signup count is not measured"
    if row is None:
        return f"{form}: no such Netlify form in forms.json ({str(forms_doc.get('generated', ''))[:10]}), so not measured"
    n = row.get("total", 0)
    parts = [f"{n} signup{'s' if n != 1 else ''}"]
    yes_share = None
    if rule.get("yes_field"):
        yes = ((row.get("answers") or {}).get(rule["yes_field"]) or {}).get(rule.get("yes_value", "Yes"), 0)
        yes_share = yes / n if n else None
        parts.append(f"{yes} {rule.get('yes_value', 'Yes')}" + (f" ({yes_share:.0%})" if n else ""))
    if row.get("spam"):
        parts.append(f"{row['spam']} in spam")
    visits = None
    if rule.get("path"):
        site = (history.get("sites") or {}).get(rule.get("site", "purplelink")) or {}
        paths = ((site.get("latest") or {}).get("topPaths")) or []
        hit = next((p["count"] for p in paths if p.get("key") == rule["path"]), None)
        # topPaths is the collector's path list; a page missing from it had no counted views (or fell below its cut).
        visits = hit or 0
        parts.append(f"{visits} views of {rule['path']} in 30 days" + ("" if hit is not None else " (not in the path list)"))
    tests = []
    for c in rule.get("any_of", []):
        bits, ok = [f">={c['signups_gte']} signups"], n >= c["signups_gte"]
        if "yes_share_gte" in c:
            bits.append(f">={c['yes_share_gte']:.0%} {rule.get('yes_value', 'Yes')}")
            ok = ok and yes_share is not None and yes_share >= c["yes_share_gte"]
        if "visits_lt" in c:
            bits.append(f"from <{c['visits_lt']} visits")
            ok = ok and visits is not None and visits < c["visits_lt"]
        tests.append(" ".join(bits) + (" [met]" if ok else " [not met]"))
    as_of = str(forms_doc.get("generated", ""))[:10]
    return f"{form} ({as_of}): " + ", ".join(parts) + ("; build rule: " + " or ".join(tests) if tests else "")


def evaluate(ex: dict, history: dict, today: dt.date, forms_doc=None) -> dict:
    out = {"id": ex["id"], "name": ex.get("name", ex["id"]), "status": ex.get("status", "running")}
    m = ex.get("metric") or {}
    st = ex.get("status", "running")
    # A proposed row may have no start date yet (started: null); one such row must not stop every other alert.
    if not isinstance(ex.get("started"), str) or not ex["started"]:
        out.update(age_days=None, verdict="PROPOSED" if st == "proposed" else "NOSTART",
                   detail="not started; " + (m.get("how") or ex.get("hypothesis", "")))
        return out
    started = dt.date.fromisoformat(ex["started"])
    age = (today - started).days
    out["age_days"] = age
    if st in ("killed", "scaled"):
        out.update(verdict="DONE", detail=st)
        return out
    if st == "kill-pending-ben":
        out.update(verdict="PENDING", detail=ex.get("on_kill", "needs Ben"))
        return out
    if st == "proposed":
        out.update(verdict="PROPOSED", detail="not started; " + (m.get("how") or ex.get("hypothesis", "")))
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
    if ex.get("forms_rule"):
        out["forms"] = forms_line(ex["forms_rule"], forms_doc, history)
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
    try:
        forms_doc = json.loads(FORMS.read_text())
    except Exception:
        forms_doc = None
    today = dt.date.today()
    res = [evaluate(e, history, today, forms_doc) for e in json.loads(LEDGER.read_text())["experiments"]]
    if "--json" in args:
        print(json.dumps(res, indent=1))
        return 0
    alert = {"SCALE", "KILL", "REVIEW", "PENDING"}
    rows = [r for r in res if r["verdict"] in alert] if "--alerts" in args else res
    if "--alerts" in args and not rows:
        print(f"Experiments: {len(res)} tracked, nothing at a threshold.")
        return 0
    for r in rows:
        age = "-" if r["age_days"] is None else r["age_days"]
        print(f"{r['verdict']:<8} {r['id']:<22} day {age:>3}  {r['detail']}")
        if r.get("forms"):
            print(f"{'':<8} {'':<22}          {r['forms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
