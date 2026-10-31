#!/usr/bin/env python3
"""Write forms.json: submission counts per Netlify form on purplelink.llc, for waitlist experiment reviews.

  python3 scripts/traffic-dashboard/forms_export.py OUT_DIR

Read-only against the Netlify API, with the token the Netlify CLI already stores (traffic_dashboard._netlify_token).
Only dates, counts and the answers to fixed-choice questions in ANSWER_FIELDS are kept. Submissions also carry email
addresses and free text; those are never read into the output.
experiments_check.py --alerts reads the file to print each waitlist review's count next to its build rule.
"""
import datetime as dt, json, sys, urllib.request
from pathlib import Path

SITE_ID = "b264591f-fbbe-4048-9d9d-7051cf497823"   # purplelink.llc (same as traffic_dashboard.PURPLELINK_SITE_ID)
PER_PAGE = 100
# Fixed-choice questions whose answers a build rule reads (form name -> field names). Nothing else is copied.
ANSWER_FIELDS = {"grant-review-waitlist": ["would-pay-19", "funder", "role"]}


def summarize(forms: list, today: dt.date) -> list:
    """forms: [{"name", "spam", "submissions": [{"created_at", "data": {...}}]}] -> one row per form, most submissions first.

    total, last30, first and last count verified submissions only; spam is the count Netlify's filter held back (None
    when not fetched)."""
    cut = (today - dt.timedelta(days=30)).isoformat()
    rows = []
    for f in forms:
        name = f.get("name", "form")
        subs = f.get("submissions", [])
        days = sorted(str(s.get("created_at", ""))[:10] for s in subs if s.get("created_at"))
        row = {"form": name, "total": len(days), "last30": sum(d > cut for d in days),
               "first": days[0] if days else None, "last": days[-1] if days else None, "spam": f.get("spam")}
        fields = ANSWER_FIELDS.get(name)
        if fields:
            answers = {k: {} for k in fields}
            for s in subs:
                data = s.get("data") or {}
                for k in fields:
                    v = str(data.get(k) or "").strip() or "(blank)"
                    answers[k][v] = answers[k].get(v, 0) + 1
            row["answers"] = answers
        rows.append(row)
    rows.sort(key=lambda r: (-r["total"], r["form"]))
    return rows


def fetch(token: str, site_id: str = SITE_ID) -> list:
    def api(path):
        req = urllib.request.Request(f"https://api.netlify.com/api/v1/{path}",
                                     headers={"Authorization": f"Bearer {token}", "User-Agent": "purplelink-forms-export"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def pages(path):
        page = 1
        while True:
            batch = api(f"{path}per_page={PER_PAGE}&page={page}")
            yield from batch
            if len(batch) < PER_PAGE:
                return
            page += 1

    out = []
    for form in api(f"sites/{site_id}/forms"):
        keep = ANSWER_FIELDS.get(form.get("name"), [])
        # Keep only what summarize reads, so an email address is dropped as soon as it arrives.
        subs = [{"created_at": s.get("created_at"), "data": {k: (s.get("data") or {}).get(k) for k in keep}}
                for s in pages(f"forms/{form['id']}/submissions?")]
        # Netlify's spam filter can hold a real signup; a count of 0 verified with some in spam reads differently.
        spam = sum(1 for _ in pages(f"forms/{form['id']}/submissions?state=spam&"))
        out.append({"name": form.get("name", "form"), "submissions": subs, "spam": spam})
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: forms_export.py OUT_DIR", file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import traffic_dashboard as td
    token = td._netlify_token()
    if not token:
        print("forms export: no Netlify token; forms.json not written", file=sys.stderr)
        return 1
    rows = summarize(fetch(token), dt.date.today())
    doc = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "site": "purplelink.llc", "forms": rows}
    (Path(sys.argv[1]) / "forms.json").write_text(json.dumps(doc, separators=(",", ":")))
    print("forms", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
