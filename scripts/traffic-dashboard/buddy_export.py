#!/usr/bin/env python3
"""Write buddy_daily.json and buddy_summary.json: usage of Buddy, the site chat, for the dashboard's Buddy section. Counts only.

  python3 scripts/traffic-dashboard/buddy_export.py OUT_DIR

Reads the Modal Dict `buddy-chat` (backend/app.py, backend/latextools/buddy.py) and the free-check claims'
durable copy. No visitor message or reply is ever copied: a conversation record is read for its turn count
and expiry only, and its `replies` are not touched.

Key prefixes read: convo:<id> {n, replies, expires}, spend:day:/spend:month:, claim:<hash> (free Citation Gap
check) and claim:coupon:<hash> (emailed code), coupon:s:<id> {code, expires_at} (code asked for in chat),
strikelog:<day>:<kind>:<id>.

Modal's Dict forgets an entry after 7 days, so each run merges the days it can see into
~/.purplelink/traffic/buddy-history.json and the window is built from that file. When Modal cannot be reached
the section is skipped: nothing is written, the exit code stays 0 and the old files stay in place.

Both files are dataset arrays of rows, like the other artifact-data files: buddy_daily (one row per day, newest last)
and buddy_summary (one row: 28-day totals, spend, the free-check target and the A/B holdout status).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
CONVO_TTL_SECONDS = 3600          # buddy.CONVO_TTL_SECONDS: expires = last visitor turn + this
COUPON_ASK_SECONDS = 10 * 60      # buddy.COUPON_ASK_SECONDS: coupon:s expires_at = issue time + this
WINDOW_DAYS = 28
BURST_CONVOS = 10                 # this many conversations starting inside BURST_SECONDS is a test, not visitors
BURST_SECONDS = 3600
TEST_PREFIX = "live-test"
FREE_CHECK_TARGET = 10            # redeemed free checks by day 28 (docs/designs/buddy-chat.md)


def _day(ts: float) -> str:
    return dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).date().isoformat()


def _blank() -> dict:
    return {"convos": 0, "turns": 0, "test_convos": 0, "test_turns": 0, "free_sent": 0, "free_redeemed": 0,
            "coupons": 0, "strikes": {}, "spend": 0.0}


def find_bursts(starts: list[tuple[str, float]]) -> set[str]:
    """Ids of conversations that begin in a burst: BURST_CONVOS or more within BURST_SECONDS (a red-team run)."""
    ordered = sorted(starts, key=lambda x: x[1])
    flagged: set[str] = set()
    lo = 0
    for hi in range(len(ordered)):
        while ordered[hi][1] - ordered[lo][1] > BURST_SECONDS:
            lo += 1
        if hi - lo + 1 >= BURST_CONVOS:
            flagged.update(cid for cid, _ in ordered[lo:hi + 1])
    return flagged


def summarize(items, now: float | None = None) -> dict:
    """items: (key, value) pairs from the buddy-chat Dict (claims included) -> {day: counts, ...}."""
    days: dict[str, dict] = {}

    def row(day: str) -> dict:
        return days.setdefault(day, _blank())

    convos: list[tuple[str, float, int]] = []
    for key, val in items:
        key = str(key)
        try:
            if key.startswith("convo:") and isinstance(val, dict) and val.get("expires"):
                # `expires` is refreshed on every turn, so this is the day of the last visitor turn.
                convos.append((key[6:], float(val["expires"]) - CONVO_TTL_SECONDS, int(val.get("n") or 0)))
            elif key.startswith("spend:day:"):
                row(key[10:])["spend"] = round(float(val or 0), 4)
            elif key.startswith("claim:coupon:") and isinstance(val, dict) and val.get("at"):
                row(_day(val["at"]))["coupons"] += 1
            elif key.startswith("claim:") and isinstance(val, dict) and val.get("at"):
                r = row(_day(val["at"]))
                r["free_sent"] += 1
                if val.get("state") == "redeemed":
                    row(_day(val.get("redeemed_at") or val["at"]))["free_redeemed"] += 1
            elif key.startswith("coupon:s:") and isinstance(val, dict) and val.get("expires_at"):
                row(_day(float(val["expires_at"]) - COUPON_ASK_SECONDS))["coupons"] += 1
            elif key.startswith("strikelog:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    s = row(parts[1])["strikes"]
                    s[parts[2]] = s.get(parts[2], 0) + 1
        except (TypeError, ValueError, OSError, OverflowError):
            continue   # one odd record must not lose the rest
    bursts = find_bursts([(cid, st) for cid, st, _ in convos])
    for cid, start, n in convos:
        r = row(_day(start))
        if cid.startswith(TEST_PREFIX) or cid in bursts:
            r["test_convos"] += 1
            r["test_turns"] += n
        else:
            r["convos"] += 1
            r["turns"] += n
    return days


def merge_history(old: dict, new: dict) -> dict:
    """Merge today's view into the kept days. A day only ever loses records to Dict expiry, so the larger value wins."""
    out = {d: dict(r, strikes=dict(r.get("strikes") or {})) for d, r in (old or {}).items()}
    for d, r in new.items():
        cur = out.setdefault(d, _blank())
        for k, v in r.items():
            if k == "strikes":
                for kind, n in v.items():
                    cur["strikes"][kind] = max(cur["strikes"].get(kind, 0), n)
            else:
                cur[k] = max(cur.get(k, 0), v)
    return out


def build(history: dict, today: dt.date, holdout: dict | None, generated: str) -> dict:
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS - 1, -1, -1)]
    rows = [{"day": d, **(history.get(d) or _blank())} for d in days]
    totals = _blank()
    for r in rows:
        for k, v in r.items():
            if k == "day":
                continue
            if k == "strikes":
                for kind, n in v.items():
                    totals["strikes"][kind] = totals["strikes"].get(kind, 0) + n
            else:
                totals[k] += v
    totals["spend"] = round(totals["spend"], 4)
    month = today.strftime("%Y-%m")
    return {"generated": generated, "window_days": WINDOW_DAYS, "days": rows, "totals": totals,
            "month_spend": round(sum(r.get("spend", 0) for d, r in history.items() if d.startswith(month)), 4),
            "free_check_target": FREE_CHECK_TARGET, "holdout": holdout,
            "note": "Counts only; no message or reply text is read. Test conversations (live-test ids and bursts) are listed apart."}


def datasets(out: dict) -> tuple[list, list]:
    """The two dataset arrays the dashboard page reads: (daily rows, one summary row)."""
    def kinds(st: dict) -> str:
        return ", ".join(f"{k} {n}" for k, n in sorted(st.items())) or ""

    daily = [{**{k: v for k, v in r.items() if k != "strikes"}, "strikesTotal": sum(r["strikes"].values()),
              "strikes": kinds(r["strikes"])} for r in out["days"]]
    t, h = out["totals"], out.get("holdout") or {}
    summary = [{"asOf": out["generated"], "windowDays": out["window_days"], "convos": t["convos"], "turns": t["turns"],
                "testConvos": t["test_convos"], "testTurns": t["test_turns"], "freeSent": t["free_sent"],
                "freeRedeemed": t["free_redeemed"], "freeTarget": out["free_check_target"], "coupons": t["coupons"],
                "strikesTotal": sum(t["strikes"].values()), "strikes": kinds(t["strikes"]), "spend": t["spend"],
                "monthSpend": out["month_spend"], "holdoutVerdict": h.get("verdict"),
                "holdoutPairs": h.get("pairs_complete"), "holdoutPairsTotal": h.get("pairs_total"),
                "holdoutMeanDiff": h.get("mean_diff_b_minus_a"), "holdoutP": h.get("p_two_sided")}]
    return daily, summary


def holdout_status(traffic: Path) -> dict | None:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import buddy_holdout_report as hr

        out = hr.report(json.loads((traffic / "history.json").read_text(encoding="utf-8")))
        return {k: out[k] for k in ("pairs_complete", "pairs_total", "mean_diff_b_minus_a", "p_two_sided", "verdict")}
    except Exception as exc:  # noqa: BLE001
        print(f"  ! buddy holdout status unavailable: {str(exc)[:100]}", file=sys.stderr)
        return None


def fetch_items() -> list | None:
    """Every (key, value) in the buddy-chat Dict plus the durable claims; None when Modal is unreachable."""
    try:
        import modal

        d = modal.Dict.from_name("buddy-chat")
        items = [(k, v) for k, v in d.items()]
        try:
            sys.path.insert(0, str(ROOT / "backend"))
            from latextools.durable_dict import DurableDict

            kept = DurableDict(d, modal.Volume.from_name("paper-review-durable"), "buddy-claims", key_prefix="claim:")
            seen = {str(k) for k, _ in items}
            items += [(k, v) for k, v in kept.items() if str(k) not in seen]
        except Exception as exc:  # noqa: BLE001 -- the Dict alone still answers most of it
            print(f"  ! buddy durable claims unavailable: {str(exc)[:100]}", file=sys.stderr)
        return items
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Buddy chat counters unavailable: {str(exc)[:100]}", file=sys.stderr)
        return None


def run(out_dir: Path, traffic: Path = TRAFFIC, items=None, now: dt.datetime | None = None) -> bool:
    items = fetch_items() if items is None else items
    if items is None:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    hist_path = traffic / "buddy-history.json"
    try:
        old = json.loads(hist_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    merged = merge_history(old, summarize(items))
    traffic.mkdir(parents=True, exist_ok=True)
    hist_path.write_text(json.dumps(merged, indent=1, sort_keys=True), encoding="utf-8")
    out = build(merged, now.date(), holdout_status(traffic), now.strftime("%Y-%m-%d %H:%M UTC"))
    out_dir.mkdir(parents=True, exist_ok=True)
    daily, summary = datasets(out)
    (out_dir / "buddy_daily.json").write_text(json.dumps(daily, separators=(",", ":")), encoding="utf-8")
    (out_dir / "buddy_summary.json").write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        ok = run(Path(sys.argv[1]))
    except Exception as exc:  # noqa: BLE001 -- never sink the export
        print(f"  ! buddy export failed: {str(exc)[:120]}", file=sys.stderr)
        return 0
    print("  ok Buddy chat usage" if ok else "  - Buddy section skipped (Modal unreachable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
