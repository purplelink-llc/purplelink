#!/usr/bin/env python3
"""Read Etsy, Payhip and (without an API token) Gumroad sales from the signed-in
automation Chrome and record them for the traffic dashboard.

Read-only: it only loads order pages and reads text. It never clicks, submits or
types, and it never signs in. A login wall is recorded as "signed out" for that
site and the site is skipped. Buyer names and emails are never stored; an order
keeps only id, date, listing title, price, fees and refund amount.

Needs the automation Chrome on port 9340 (profile ~/.photo-automation-chrome),
signed in to all three sites. Ben launches it from the Terminal panel.

    python3 record_marketplaces.py                # all three sites
    python3 record_marketplaces.py --site etsy    # one site
    python3 record_marketplaces.py --dry-run      # read and print, write nothing

Writes ~/.purplelink/traffic/marketplaces.json atomically (previous file kept as
marketplaces.json.bak). Exit code is a bitmask of the sites that did not read
cleanly: etsy=1, payhip=2, gumroad=4 (0 = all read). A site that fails leaves its
stored orders and asOf untouched; an empty read from a page that did not render
never replaces good data. Gumroad is skipped when GUMROAD_TOKEN is set in
~/.config/purplelink/traffic.env, because the dashboard reads the API itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT_DIR = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
PATH = OUT_DIR / "marketplaces.json"
CONFIG_PATH = Path.home() / ".config" / "purplelink" / "traffic.env"
BITS = {"etsy": 1, "payhip": 2, "gumroad": 4}

ETSY_LISTS = ["https://www.etsy.com/your/orders/sold", "https://www.etsy.com/your/orders/sold/completed"]
ETSY_ORDER = "https://www.etsy.com/your/orders/sold/{id}"
PAYHIP_PAGES = ["https://payhip.com/orders", "https://payhip.com/dashboard/orders", "https://payhip.com/sales"]
GUMROAD_PAGES = ["https://gumroad.com/customers"]


# ------------------------------------------------------------ pure parsers
# Everything below takes plain data (what the in-page JavaScript returns), so it
# runs offline in test_marketplaces.py.

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_money(text: str) -> int | None:
    """'$1,234.50' / 'US$12' / 'USD 12.00' -> cents. First amount in the text."""
    m = re.search(r"(-)?\s*(?:US\$|\$|USD\s?)\s*(-)?([\d,]+(?:\.\d{1,2})?)", text or "")
    if not m:
        return None
    cents = round(float(m.group(3).replace(",", "")) * 100)
    return -cents if (m.group(1) or m.group(2)) else cents


def parse_date(text: str, default_year: int | None = None) -> float | None:
    """A date (and optional time) in common formats -> local epoch seconds.
    A date with no time is taken as noon, so it never slips a day."""
    t = text or ""
    y = default_year or dt.date.today().year
    day = None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        day = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if not day:
        m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", t)
        if m and m.group(1)[:3].lower() in MONTHS:
            day = (int(m.group(3) or y), MONTHS[m.group(1)[:3].lower()], int(m.group(2)))
    if not day:
        m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", t)
        if m and m.group(2)[:3].lower() in MONTHS:
            day = (int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
    if not day:
        m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if m:
            day = (int(m.group(3)), int(m.group(1)), int(m.group(2)))
    if not day:
        return None
    hh, mm = 12, 0
    tm = re.search(r"\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?", t)
    if tm:
        hh, mm = int(tm.group(1)), int(tm.group(2))
        if tm.group(3):
            hh = hh % 12 + (12 if tm.group(3).lower() == "pm" else 0)
    try:
        return dt.datetime(day[0], day[1], day[2], hh, mm).timestamp()
    except ValueError:
        return None


def amount_after(lines: list[str], label: str) -> int | None:
    """Value of a 'Label   $x.xx' pair: same line, or the next line."""
    pat = re.compile(label, re.I)
    for i, ln in enumerate(lines):
        if pat.search(ln):
            v = parse_money(pat.split(ln, 1)[-1])
            if v is None and i + 1 < len(lines):
                v = parse_money(lines[i + 1])
            if v is not None:
                return v
    return None


FEE_LABELS = [r"transaction fee", r"processing fee", r"payment processing", r"regulatory operating fee",
              r"offsite ads fee", r"vat on fees"]


def parse_etsy_detail(text: str) -> dict:
    """An Etsy order page's text -> {'gross', 'fee', 'net', 'refunded'} where found.
    fee is the sum of the fee lines Etsy itemises; absent when none is shown, so
    the dashboard falls back to the published schedule."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    out: dict = {}
    gross = amount_after(lines, r"^(?:order total|total)\b") or amount_after(lines, r"^item total\b")
    if gross:
        out["gross"] = gross
    fees = [amount_after(lines, lab) for lab in FEE_LABELS]
    fees = [abs(f) for f in fees if f is not None]
    if fees:
        out["fee"] = sum(fees)
    net = amount_after(lines, r"^(?:net|you(?:'|’)ll receive|order net)\b")
    if net is not None:
        out["net"] = net
        if gross and "fee" not in out and gross > net:
            out["fee"] = gross - net
    ref = amount_after(lines, r"^refund(?:ed)?\b")
    if ref:
        out["refunded"] = abs(ref)
    return out


def parse_etsy_rows(rows: list[dict]) -> list[dict]:
    """Rows from the Sold Orders list: {'href', 'text', 'listings': [titles]}."""
    orders, seen = [], set()
    for r in rows:
        m = re.search(r"/your/orders/sold/(?:completed/)?(\d{6,})", r.get("href", "")) or \
            re.search(r"Order\s*#\s*(\d{6,})", r.get("text", ""))
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        text = r.get("text", "")
        titles = [t.strip() for t in r.get("listings", []) if t and t.strip()]
        o = {"id": m.group(1), "ts": parse_date(text), "title": titles[0] if titles else "",
             "gross": parse_money(text)}
        if re.search(r"\brefund", text, re.I):
            o["refunded"] = o["gross"]
        orders.append(o)
    return orders


HEADER_KEYS = {
    "id": r"^(order|id|reference|invoice|#)", "date": r"date|time|created|when",
    "title": r"product|item|listing|name of", "gross": r"^(total|amount|price|paid|gross|sale)",
    "fee": r"fee", "net": r"^(net|earnings|payout|you (get|earn|receive))", "status": r"status|refund",
}


def parse_table(headers: list[str], rows: list[list[str]], market: str) -> list[dict]:
    """A dashboard table (Payhip orders, Gumroad sales) -> orders. Columns are
    found by header name, never by position. No id column: the id is a hash of
    date, title and amount plus an occurrence counter, stable across reads."""
    cols: dict[str, int] = {}
    for key, pat in HEADER_KEYS.items():
        for i, h in enumerate(headers):
            if re.search(pat, h.strip().lower()) and i not in cols.values():
                cols[key] = i
                break
    if "gross" not in cols or "date" not in cols:
        return []
    orders, counts = [], {}
    for cells in rows:
        if len(cells) <= max(cols.values()):
            continue
        get = lambda k: cells[cols[k]] if k in cols else ""  # noqa: E731
        gross, ts = parse_money(get("gross")), parse_date(get("date"))
        if not gross or gross <= 0 or ts is None:
            continue
        title = re.sub(r"\s+", " ", get("title")).strip()
        if "id" in cols and get("id").strip():
            oid = re.sub(r"[^A-Za-z0-9_-]", "", get("id").strip())[:40]
        else:
            base = f"{ts}|{title}|{gross}"
            counts[base] = counts.get(base, 0) + 1
            oid = hashlib.sha1(f"{base}|{counts[base]}".encode()).hexdigest()[:12]
        o = {"id": oid, "ts": ts, "title": title, "gross": gross}
        fee, net = parse_money(get("fee")) if "fee" in cols else None, parse_money(get("net")) if "net" in cols else None
        if fee is not None:
            o["fee"] = abs(fee)
        elif net is not None and 0 < net < gross:
            o["fee"] = gross - net
        if re.search(r"refund|chargeback|disput", " ".join(cells), re.I):
            o["refunded"] = gross
        orders.append(o)
    return orders


def classify_page(url: str, text: str, has_password: bool) -> str:
    """'signed out', 'not found' or 'ok' from what the page shows."""
    if has_password or re.search(r"/(sign-?in|log-?in|signin|login)\b", url or "", re.I):
        return "signed out"
    if re.search(r"page (you requested )?(was )?not found|doesn't exist|404", (text or "")[:400], re.I):
        return "not found"
    return "ok"


EMPTY_PHRASES = {
    "etsy": r"take a tour|no orders|you don.t have any (open |completed )?orders|orders\s+easily manage",
    "payhip": r"no orders|no sales|nothing here yet",
    "gumroad": r"no sales|no customers|you haven.t (made|had) any",
}


def rendered(market: str, text: str, rows: int) -> bool:
    """True when the page shows orders, or the site's own empty-state wording. A
    blank or half-loaded page is not an answer of zero."""
    return rows > 0 or bool(re.search(EMPTY_PHRASES[market], text or "", re.I))


def merge_read(data: dict, market: str, status: str, orders: list[dict], now: str, note: str = "") -> dict:
    """Fold one site's read into the stored file. Orders only ever accumulate;
    a failed site changes only its status."""
    data.setdefault("orders", {})
    data.setdefault("asOf", {})
    data.setdefault("status", {})
    data.setdefault("errors", [])
    data["status"][market] = status
    if status == "ok":
        data["asOf"][market] = now
        for o in orders:
            key = f"{market}:{o['id']}"
            prev = data["orders"].get(key, {})
            data["orders"][key] = {**prev, **{k: v for k, v in o.items() if v is not None}, "site": market}
        data["errors"] = [e for e in data["errors"] if not e.startswith(market + ":")]
    else:
        data["errors"] = [e for e in data["errors"] if not e.startswith(market + ":")] + [f"{market}: {status}{(' - ' + note) if note else ''}"]
    return data


# ------------------------------------------------------------ browser side

JS_ROWS = r"""(() => {
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href*="/your/orders/sold/"]')) {
    const m = a.href.match(/\/your\/orders\/sold\/(?:completed\/)?(\d{6,})/);
    if (!m || seen.has(m[1])) continue;
    seen.add(m[1]);
    let row = a;
    for (let i = 0; i < 8 && row.parentElement; i++) {
      row = row.parentElement;
      if (row.querySelectorAll('a[href*="/your/orders/sold/"]').length > 1 && i > 0) { row = row.querySelector('a[href*="/your/orders/sold/"]').parentElement; break; }
      if (/\$\s?\d/.test(row.innerText) && row.innerText.length > 40) break;
    }
    out.push({href: a.href, text: row.innerText.slice(0, 800),
              listings: [...row.querySelectorAll('a[href*="/listing/"]')].map(x => x.innerText.trim()).filter(Boolean)});
  }
  return out;
})()"""

JS_TABLE = r"""(() => {
  const t = [...document.querySelectorAll('table')].sort((a, b) => b.rows.length - a.rows.length)[0];
  if (!t) return {headers: [], rows: []};
  const cells = r => [...r.cells].map(c => c.innerText.trim());
  let head = [...t.querySelectorAll('thead tr')].map(cells)[0];
  const body = [...t.querySelectorAll('tbody tr')].map(cells);
  if (!head) head = cells(t.rows[0]);
  return {headers: head, rows: body.length ? body : [...t.rows].slice(1).map(cells)};
})()"""

JS_META = "({url: location.href, text: document.body ? document.body.innerText : '', pw: !!document.querySelector('input[type=password]')})"


class Unresponsive(Exception):
    pass


def open_page(url: str, settle: float = 5.0):
    """Open url in a new tab of the automation Chrome. Raises Unresponsive when
    the page never answers (the renderer occasionally hangs)."""
    from cdp_tab import Tab
    tab = Tab.new(url)
    try:
        tab.ws.settimeout(20)
        tab.front()
        deadline = time.time() + 45
        while time.time() < deadline:
            if tab.eval("document.readyState") == "complete":
                break
            time.sleep(1)
        time.sleep(settle)
        return tab, tab.eval(JS_META)
    except Exception as exc:  # noqa: BLE001 - socket timeouts, CDP errors
        try:
            tab.close()
        except Exception:  # noqa: BLE001
            pass
        raise Unresponsive(type(exc).__name__) from exc


def read_etsy(known: dict) -> tuple[str, list[dict], str]:
    orders: list[dict] = []
    for url in ETSY_LISTS:
        tab, meta = open_page(url)
        try:
            state = classify_page(meta["url"], meta["text"], meta["pw"])
            if state != "ok":
                return state, [], url
            rows = parse_etsy_rows(tab.eval(JS_ROWS) or [])
            if not rendered("etsy", meta["text"], len(rows)):
                return "not rendered", [], url
            orders += [o for o in rows if o["id"] not in {x["id"] for x in orders}]
        finally:
            tab.close()
    for o in orders:  # fees: only for orders whose fee is not stored yet
        if (known.get(f"etsy:{o['id']}") or {}).get("fee") is not None:
            continue
        tab, meta = open_page(ETSY_ORDER.format(id=o["id"]), settle=3)
        try:
            if classify_page(meta["url"], meta["text"], meta["pw"]) == "ok":
                d = parse_etsy_detail(meta["text"])
                for k in ("fee", "refunded"):
                    if d.get(k) is not None:
                        o[k] = d[k]
                if d.get("gross") and not o.get("gross"):
                    o["gross"] = d["gross"]
        finally:
            tab.close()
    return "ok", [o for o in orders if o.get("gross") and o.get("ts")], ""


def read_table_site(market: str, pages: list[str]) -> tuple[str, list[dict], str]:
    last = "not found"
    for url in pages:
        tab, meta = open_page(url)
        try:
            state = classify_page(meta["url"], meta["text"], meta["pw"])
            if state == "signed out":
                return state, [], url
            if state != "ok":
                last = state
                continue
            t = tab.eval(JS_TABLE) or {"headers": [], "rows": []}
            orders = parse_table(t["headers"], t["rows"], market)
            if not rendered(market, meta["text"], len(t["rows"])):
                last = "not rendered"
                continue
            if t["rows"] and not orders:
                return "unrecognised table", [], url
            return "ok", orders, url
        finally:
            tab.close()
    return last, [], pages[-1]


def gumroad_token_set() -> bool:
    if os.environ.get("GUMROAD_TOKEN"):
        return True
    try:
        return any(ln.split("=", 1)[0].strip() == "GUMROAD_TOKEN" and ln.split("=", 1)[1].strip()
                   for ln in CONFIG_PATH.read_text().splitlines() if "=" in ln and not ln.lstrip().startswith("#"))
    except OSError:
        return False


def write_atomic(data: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    if PATH.exists():
        shutil.copy2(PATH, PATH.with_suffix(".json.bak"))
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, PATH)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", choices=list(BITS), action="append", help="only this site (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sites = args.site or list(BITS)

    try:
        data = json.loads(PATH.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    code, any_ok = 0, False
    for m in sites:
        if m == "gumroad" and gumroad_token_set() and not args.site:
            print("gumroad: skipped, GUMROAD_TOKEN is set (the dashboard reads the API)")
            continue
        try:
            if m == "etsy":
                status, orders, where = read_etsy(data.get("orders") or {})
            elif m == "payhip":
                status, orders, where = read_table_site("payhip", PAYHIP_PAGES)
            else:
                status, orders, where = read_table_site("gumroad", GUMROAD_PAGES)
        except Unresponsive as exc:
            status, orders, where = f"browser did not respond ({exc})", [], ""
        except Exception as exc:  # noqa: BLE001 - one site must not stop the others
            status, orders, where = f"error: {type(exc).__name__}", [], ""
        if status == "ok":
            any_ok = True
            print(f"{m}: ok, {len(orders)} order(s) on the page, "
                  f"{sum(1 for o in orders if o.get('fee') is not None)} with a fee shown")
        else:
            code |= BITS[m]
            print(f"{m}: {status}" + (" (sign in to it in the automation Chrome yourself)" if status == "signed out" else ""),
                  file=sys.stderr)
        merge_read(data, m, status, orders, now, where)
    if not any_ok:
        # Only statuses change: orders are never removed, so a dead page cannot erase data.
        print("no site rendered; recording statuses only, stored orders untouched", file=sys.stderr)
        code = code or 8
    if args.dry_run:
        print(json.dumps({k: data[k] for k in ("status", "asOf")}, indent=1))
    else:
        write_atomic(data)
        print(f"wrote {PATH} ({len(data.get('orders', {}))} order(s) on file)")
    return code


if __name__ == "__main__":
    sys.exit(main())
