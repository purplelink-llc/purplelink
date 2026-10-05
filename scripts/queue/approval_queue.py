#!/usr/bin/env python3
"""Approval queue for Purplelink jobs. See docs/growth-briefs/approval-queue-spec.md.

One markdown file per decision, in ~/.purplelink/queue/{pending,approved,done,rejected,
expired,needs-work,snoozed,evidence}. Nothing outward happens without an item in
approved/. Stdlib only.

  approval_queue.py init
  approval_queue.py new FILE.md | -          create from a markdown item (lint decides pending vs needs-work)
  approval_queue.py lint ID_OR_FILE [--offline]
  approval_queue.py list [--status pending] [--json]
  approval_queue.py digest [--max 7] [--write]
  approval_queue.py approve ID [--note TEXT]
  approval_queue.py reject ID --reason CODE [--text TEXT]
  approval_queue.py edit ID --file NEWDRAFT.md   store the edit as a diff, status edited
  approval_queue.py snooze ID YYYY-MM-DD
  approval_queue.py done ID [--result TEXT]
  approval_queue.py expire                       move overdue items to expired/
  approval_queue.py requeue                      re-lint needs-work; move passing items to pending
  approval_queue.py stats [--days 30]
  approval_queue.py status                       one line (used by the dashboard and daily update)
"""
import argparse, datetime as dt, difflib, json, os, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("PURPLELINK_QUEUE") or Path.home() / ".purplelink" / "queue")
FOLDERS = ["pending", "approved", "done", "rejected", "expired", "needs-work", "snoozed", "evidence"]
KINDS = {"post", "email", "listing", "pr", "spend", "decision", "check", "submission"}
OUTWARD = {"post", "email", "listing", "spend", "submission"}
EXECUTORS = {"ben", "claude-chrome", "claude-code", "auto"}
RISKS = {"low", "medium", "high"}
REASONS = {"tone", "wrong-target", "wrong-fact", "not-now", "no-value", "risk"}
REQUIRED_FIELDS = ["id", "created", "job", "model", "kind", "target", "executor", "risk", "effort_minutes", "expires", "expected_effect", "ledger", "status"]
REQUIRED_SECTIONS = ["Ask", "Why now", "Draft", "Verify", "If approved", "If rejected", "Evidence"]
WORD_CAPS = {"email": 150, "post": 220}
PENDING_CAP = 15
SELF_PROMO = {"post", "submission", "email"}

BANNED_PHRASES = [
    "game-changer", "game changer", "revolutionize", "revolutionary", "cutting-edge", "cutting edge",
    "unlock the power", "supercharge", "seamless", "leverage", "delve", "in today's fast-paced",
    "elevate your", "take your", "next level", "unleash", "empower", "robust solution",
    "look no further", "dive into", "it's important to note", "in the realm of", "tapestry",
]
FAKE_REVIEW = [r"aggregaterating", r"\b\d(\.\d)?\s*(/\s*5|stars?)\b.*\b(reviews?|ratings?)\b", r"customers? (love|rave)", r"\bbest[- ]?seller\b", r"\b\d[\d,]*\+? (happy )?(customers|buyers|users) (love|trust)"]
GLP1_TERMS = re.compile(r"glp-?1|semaglutide|tirzepatide|ozempic|wegovy|zepbound|mounjaro", re.I)
GLP1_BAD = re.compile(r"\b(dose|dosing|dosage|\d+(\.\d+)?\s?mg|units? of)\b|prevents? muscle loss|guarantee[sd]?|cures?\b|treats?\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆✅❌]")


# ---------------------------------------------------------------- parsing
def parse_scalar(v: str):
    v = v.strip()
    if not v:
        return ""
    if v[0] in "\"'":
        q = v[0]
        end = v.find(q, 1)
        while end > 0 and v[end - 1] == "\\":
            end = v.find(q, end + 1)
        inner = v[1:end] if end > 0 else v[1:]
        return json.loads('"' + inner.replace('"', '\\"') + '"') if q == '"' and "\\" in inner else inner
    if v[0] == "{":
        close = v.rfind("}")
        body = v[1:close]
        out = {}
        for part in re.split(r",\s*(?=[A-Za-z0-9_\-]+\s*:)", body):
            if ":" in part:
                k, val = part.split(":", 1)
                out[k.strip()] = parse_scalar(val)
        return out
    v = re.split(r"\s+#", v, 1)[0].strip()
    return v


def split_item(text: str):
    if not text.startswith("---"):
        raise ValueError("missing front matter")
    end = text.find("\n---", 3)
    if end < 0:
        raise ValueError("unterminated front matter")
    fm_text, body = text[3:end].strip("\n"), text[end + 4:].lstrip("\n")
    fm = {}
    for line in fm_text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"bad front matter line: {line[:50]}")
        k, v = line.split(":", 1)
        fm[k.strip()] = parse_scalar(v)
    return fm, body


def fmt_scalar(v):
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {fmt_scalar(x)}" for k, x in v.items()) + "}"
    s = str(v)
    if s == "" or re.search(r"[:#\"'{}\[\],&*!|>%@`]|^\s|\s$", s) and not re.fullmatch(r"\d{4}-\d\d-\d\d(T[\d:+\-]+)?", s):
        return json.dumps(s)
    return s


def join_item(fm: dict, body: str) -> str:
    order = [k for k in REQUIRED_FIELDS if k in fm] + [k for k in fm if k not in REQUIRED_FIELDS]
    return "---\n" + "\n".join(f"{k}: {fmt_scalar(fm[k])}" for k in order) + "\n---\n\n" + body.lstrip("\n")


def sections(body: str) -> dict:
    out, cur = {}, None
    for line in body.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def drafts_of(sec_text: str) -> list:
    return re.findall(r"```[^\n]*\n(.*?)```", sec_text, flags=re.S)


def words(s: str) -> list:
    return re.findall(r"[A-Za-z0-9$%'’\-]+", s.lower())


# ---------------------------------------------------------------- storage
def ensure_root():
    for f in FOLDERS:
        (ROOT / f).mkdir(parents=True, exist_ok=True)


def all_items():
    items = []
    for f in FOLDERS:
        if f == "evidence":
            continue
        for p in sorted((ROOT / f).glob("*.md")):
            try:
                fm, body = split_item(p.read_text())
            except Exception:
                continue
            items.append({"folder": f, "path": p, "fm": fm, "body": body})
    return items


def find_item(ident: str):
    p = Path(ident)
    if p.exists() and p.suffix == ".md":
        fm, body = split_item(p.read_text())
        return {"folder": p.parent.name, "path": p, "fm": fm, "body": body}
    for it in all_items():
        if it["fm"].get("id") == ident or it["path"].stem == ident or it["path"].stem.endswith(ident):
            return it
    sys.exit(f"no item {ident!r}")


def git_commit(msg: str):
    if not (ROOT / ".git").exists():
        return
    subprocess.run(["git", "-C", str(ROOT), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(ROOT), "-c", "user.name=queue", "-c", "user.email=queue@localhost", "commit", "-q", "-m", msg], capture_output=True)


def log_event(item_id: str, action: str, actor: str = "ben", extra: dict | None = None):
    rec = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "id": item_id, "action": action, "actor": actor}
    rec.update(extra or {})
    with (ROOT / "log.jsonl").open("a") as fh:
        fh.write(json.dumps(rec) + "\n")


def write_index():
    items = all_items()
    idx = {"updated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "counts": {f: sum(1 for i in items if i["folder"] == f) for f in FOLDERS if f != "evidence"},
           "stats30": stats(30),
           "pending": [{"id": i["fm"].get("id"), "kind": i["fm"].get("kind"), "expires": i["fm"].get("expires"),
                        "risk": i["fm"].get("risk"), "file": i["path"].name} for i in items if i["folder"] == "pending"]}
    (ROOT / "queue.json").write_text(json.dumps(idx, indent=1))
    return idx


def move(it, folder: str, fm_updates: dict | None = None, body: str | None = None):
    fm = dict(it["fm"]); fm.update(fm_updates or {})
    dest = ROOT / folder / it["path"].name
    dest.write_text(join_item(fm, body if body is not None else it["body"]))
    if dest != it["path"]:
        it["path"].unlink()
    it.update(folder=folder, path=dest, fm=fm)
    write_index()


# ---------------------------------------------------------------- lint
def _ssl_context():
    """python.org framework builds ship without CA roots (same fix as the dashboard)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def url_ok(url: str) -> bool:
    url = url.split("#", 1)[0]
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (compatible; purplelink-queue-lint)"})
            with urllib.request.urlopen(req, timeout=12, context=_ssl_context()) as r:
                return r.status < 400
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 405, 429):  # reachable but refuses this client
                return True
        except Exception:
            continue
    return False


def lint(fm: dict, body: str, offline: bool = False, others: list | None = None, today: dt.date | None = None) -> tuple:
    """Returns (checks dict of pass/fail/skip, list of problems)."""
    problems, checks = [], {}
    today = today or dt.date.today()

    missing = [k for k in REQUIRED_FIELDS if k not in fm or fm[k] in ("", None)]
    if missing:
        problems.append(f"missing fields: {', '.join(missing)}")
    if fm.get("kind") not in KINDS:
        problems.append(f"kind must be one of {sorted(KINDS)}")
    if fm.get("executor") not in EXECUTORS:
        problems.append(f"executor must be one of {sorted(EXECUTORS)}")
    if fm.get("risk") not in RISKS:
        problems.append(f"risk must be one of {sorted(RISKS)}")
    if fm.get("kind") in OUTWARD and fm.get("executor") == "auto":
        problems.append("outward kinds cannot use executor auto")
    if fm.get("kind") == "post" and "reddit" in str(fm.get("target", "")).lower() and fm.get("executor") != "ben":
        problems.append("Reddit posts must use executor ben (the Chrome tool blocks reddit.com)")
    try:
        exp = dt.date.fromisoformat(str(fm.get("expires", ""))[:10])
        if exp < today:
            problems.append("already expired")
    except Exception:
        problems.append("expires must be YYYY-MM-DD")

    sec = sections(body)
    for s in REQUIRED_SECTIONS:
        if not sec.get(s):
            problems.append(f"missing or empty section: {s}")
    checks["structure"] = "fail" if any("missing" in p or "must" in p or "auto" in p or "Reddit" in p for p in problems) else "pass"

    # verify section: unverified claims block pending
    ver = sec.get("Verify", "")
    if re.search(r"\bUNVERIFIED\b", ver) and fm.get("kind") not in ("check", "decision"):
        problems.append("Verify lists UNVERIFIED claims; resolve them before this can be pending")
        checks["claims_sourced"] = "fail"
    elif ver and not re.search(r"(https?://|line \d+|\.md|\.txt|\.html|\.mjs|\.py|dashboard|ledger)", ver):
        problems.append("Verify names no source (URL, file or line)")
        checks["claims_sourced"] = "fail"
    else:
        checks["claims_sourced"] = "pass"

    draft_text = sec.get("Draft", "")
    all_text = body
    # copy lint
    copy_problems = []
    if "—" in draft_text:
        copy_problems.append("em dash in draft")
    if EMOJI.search(draft_text):
        copy_problems.append("emoji in draft")
    low = draft_text.lower()
    for ph in BANNED_PHRASES:
        if ph in low:
            copy_problems.append(f"phrase: {ph}")
    cap = WORD_CAPS.get(fm.get("kind"))
    if cap:
        for blk in drafts_of(draft_text) or [draft_text]:
            if len(words(blk)) > cap:
                copy_problems.append(f"draft over {cap} words ({len(words(blk))})")
    problems += copy_problems
    checks["lint"] = "fail" if copy_problems else "pass"

    # policy lint
    pol = []
    lower_all = all_text.lower()
    for pat in FAKE_REVIEW:
        if re.search(pat, draft_text, re.I):
            pol.append("possible fake-review or rating claim")
            break
    if GLP1_TERMS.search(all_text) and GLP1_BAD.search(draft_text):
        pol.append("GLP-1 draft contains dosing or medical-claim wording")
    if "scholar.google" in lower_all and re.search(r"inject|overlay|banner", draft_text, re.I) and fm.get("kind") == "pr":
        pol.append("ad-like injection into Scholar pages")
    problems += pol
    checks["policy"] = "fail" if pol else "pass"

    # sample size
    n = fm.get("n_conversions")
    if fm.get("kind") in ("spend", "decision"):
        try:
            small = int(n) < 5
        except (TypeError, ValueError):
            small = True
            problems.append("spend/decision items must state n_conversions")
        if small and fm.get("risk") == "low":
            problems.append("EARLY sample (fewer than 5): risk cannot be low")
        checks["sample_size"] = "early" if small else "pass"

    # untrusted quotes
    ev_dir = ROOT / "evidence"
    quote_hit = None
    if ev_dir.exists():
        dw = words(draft_text)
        for p in ev_dir.glob("*.md"):
            ew = " " + " ".join(words(p.read_text())) + " "
            for i in range(0, max(0, len(dw) - 15)):
                if " " + " ".join(dw[i:i + 16]) + " " in ew:
                    quote_hit = p.name
                    break
            if quote_hit:
                break
    if quote_hit:
        problems.append(f"draft quotes more than 15 words from scraped evidence ({quote_hit})")
    checks["untrusted_quotes"] = "fail" if quote_hit else "pass"

    # duplicates and rate limits
    dup, rate = False, False
    if others is not None:
        tgt = str(fm.get("target", "")).strip().lower()
        sub = re.search(r"r/[a-z0-9_]+", tgt)
        for o in others:
            ofm = o["fm"]
            if ofm.get("id") == fm.get("id") or o["folder"] in ("rejected", "expired", "needs-work"):
                continue
            try:
                when = dt.datetime.fromisoformat(str(ofm.get("created")))
                age_days = (dt.datetime.now(when.tzinfo) - when).days
            except Exception:
                age_days = 0
            if age_days > 30:
                continue
            if str(ofm.get("target", "")).strip().lower() == tgt and tgt:
                dup = True
            if sub and fm.get("kind") in SELF_PROMO and ofm.get("kind") in SELF_PROMO and sub.group(0) in str(ofm.get("target", "")).lower():
                rate = True
        if dup:
            problems.append("another item targets the same place within 30 days")
        if rate:
            problems.append("community self-promotion limit: one per 30 days")
    checks["duplicate_30d"] = "fail" if dup else "pass"
    checks["rate_limit"] = "fail" if rate else "pass"

    # urls
    urls = sorted({u.rstrip(".,;:") for u in re.findall(r"https?://[^\s)>\]\"']+", draft_text + "\n" + ver)})
    if offline or not urls:
        checks["urls_resolved"] = "skip" if offline else "pass"
    else:
        bad = [u for u in urls if not url_ok(u)]
        if bad:
            problems.append("URLs do not resolve: " + ", ".join(bad[:4]))
        checks["urls_resolved"] = "fail" if bad else "pass"
    return checks, problems


# ---------------------------------------------------------------- commands
def cmd_init(a):
    ensure_root()
    if not (ROOT / ".git").exists():
        subprocess.run(["git", "-C", str(ROOT), "init", "-q"], capture_output=True)
        (ROOT / ".gitignore").write_text("queue.json\nTODAY.md\n")
    write_index(); git_commit("init")
    print(f"queue ready at {ROOT}")


def next_id():
    today = dt.date.today().strftime("%Y%m%d")
    used = [int(m.group(1)) for i in all_items()
            if (m := re.fullmatch(rf"q-{today}-(\d+)", str(i["fm"].get("id", ""))))]
    n = max(used, default=0) + 1
    return f"q-{today}-{n:03d}"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "item"


def cmd_new(a):
    ensure_root()
    text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text()
    fm, body = split_item(text)
    fm.setdefault("created", dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    fm.setdefault("status", "pending")
    if not fm.get("id"):
        fm["id"] = next_id()
    others = all_items()
    checks, problems = lint(fm, body, offline=a.offline, others=others)
    pending = sum(1 for i in others if i["folder"] == "pending")
    if not problems and pending >= PENDING_CAP:
        problems.append(f"pending is at the cap ({PENDING_CAP}); name an older item this replaces")
    fm["checks"] = checks
    folder = "needs-work" if problems else "pending"
    fm["status"] = "pending" if folder == "pending" else "needs-work"
    name = f"{dt.date.today().isoformat()}-{fm.get('kind', 'item')}-{slugify(str(fm.get('target', 'item')))}.md"
    dest = ROOT / folder / name
    dest.write_text(join_item(fm, body))
    write_index(); log_event(fm["id"], f"new:{folder}", fm.get("job", "job")); git_commit(f"new {fm['id']}")
    print(f"{fm['id']} -> {folder}")
    for p in problems:
        print(f"  - {p}")
    return 0 if not problems else 3


def cmd_lint(a):
    it = find_item(a.item)
    checks, problems = lint(it["fm"], it["body"], offline=a.offline, others=all_items())
    print(json.dumps(checks))
    for p in problems:
        print("  -", p)
    return 0 if not problems else 3


def cmd_list(a):
    rows = [i for i in all_items() if not a.status or i["folder"] == a.status or i["fm"].get("status") == a.status]
    if a.json:
        print(json.dumps([{"id": i["fm"].get("id"), "folder": i["folder"], "kind": i["fm"].get("kind"), "target": i["fm"].get("target"), "expires": i["fm"].get("expires")} for i in rows], indent=1))
    else:
        for i in rows:
            print(f"{i['folder']:<10} {i['fm'].get('id')}  {i['fm'].get('kind'):<10} exp {i['fm'].get('expires')}  {str(i['fm'].get('target'))[:60]}")


def score(fm: dict) -> float:
    try:
        eff = max(1.0, float(fm.get("effort_minutes", 10)))
    except (TypeError, ValueError):
        eff = 10.0
    try:
        val = float(fm.get("value", 3))
    except (TypeError, ValueError):
        val = 3.0
    risk_pen = {"low": 1.0, "medium": 0.85, "high": 0.6}.get(fm.get("risk"), 0.85)
    return val * risk_pen / eff


def first_line(txt: str) -> str:
    for line in txt.split("\n"):
        if line.strip():
            return line.strip()
    return ""


def digest_text(maxn: int = 7, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    items = [i for i in all_items() if i["folder"] == "pending"]
    def expires_soon(i):
        try:
            return (dt.date.fromisoformat(str(i["fm"].get("expires"))[:10]) - today).days <= 2
        except Exception:
            return False
    items.sort(key=lambda i: (not expires_soon(i), -score(i["fm"])))
    s = stats(30)
    counts = write_index()["counts"]
    head = (f"Approval queue, {today.isoformat()}. {counts['pending']} pending, {counts['needs-work']} in needs-work, "
            f"acceptance rate (30d) {s['acceptance_pct']}%." if s["decided"] else
            f"Approval queue, {today.isoformat()}. {counts['pending']} pending, {counts['needs-work']} in needs-work, no decisions yet.")
    lines = [head, ""]
    for n, it in enumerate(items[:maxn], 1):
        fm, sec = it["fm"], sections(it["body"])
        why = [l.strip("- ").strip() for l in sec.get("Why now", "").split("\n") if l.strip().startswith("-")][:2]
        lines.append(f"{n}. [{fm.get('kind')}] {first_line(sec.get('Ask', ''))} {fm.get('effort_minutes')} min, expires {fm.get('expires')}, risk {fm.get('risk')}.")
        for w in why:
            lines.append(f"   Evidence: {w}")
        lines.append(f"   -> approve {fm.get('id')}")
        lines.append("")
    extra = len(items) - maxn
    if extra > 0:
        lines.append(f"+ {extra} more pending (backlog).")
    if not items:
        lines.append("Nothing pending.")
    return "\n".join(lines).rstrip() + "\n"


def cmd_digest(a):
    ensure_root()
    txt = digest_text(a.max)
    if a.write:
        (ROOT / "TODAY.md").write_text(txt)
    print(txt, end="")


def decide(it, folder, status, updates=None, note=None, actor="ben"):
    updates = dict(updates or {}); updates["status"] = status
    updates["decided"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    body = it["body"]
    if note:
        body = body.rstrip() + f"\n\n## Decision note\n{note}\n"
    move(it, folder, updates, body)
    log_event(it["fm"]["id"], status, actor, {"note": note} if note else None)
    git_commit(f"{status} {it['fm']['id']}")


def cmd_approve(a):
    it = find_item(a.item)
    if it["folder"] not in ("pending", "snoozed"):
        sys.exit(f"{it['fm'].get('id')} is in {it['folder']}, not pending")
    checks, problems = lint(it["fm"], it["body"], offline=True, others=None)
    hard = [p for p in problems if "expired" in p or "outward" in p]
    if hard:
        sys.exit("cannot approve: " + "; ".join(hard))
    decide(it, "approved", "approved", note=a.note)
    print(f"approved {it['fm']['id']}: executor {it['fm'].get('executor')}")


def cmd_reject(a):
    if a.reason not in REASONS:
        sys.exit(f"reason must be one of {sorted(REASONS)}")
    it = find_item(a.item)
    decide(it, "rejected", "rejected", {"reason": a.reason}, a.text)
    print(f"rejected {it['fm']['id']} ({a.reason})")


def cmd_edit(a):
    it = find_item(a.item)
    new_body = Path(a.file).read_text()
    diff = "\n".join(difflib.unified_diff(it["body"].split("\n"), new_body.split("\n"), "before", "after", lineterm=""))
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / f"{it['path'].stem}.edit.diff").write_text(diff)
    move(it, it["folder"], {"status": "edited"}, new_body)
    log_event(it["fm"]["id"], "edited")
    git_commit(f"edited {it['fm']['id']}")
    print(f"edited {it['fm']['id']}; diff stored")


def cmd_snooze(a):
    dt.date.fromisoformat(a.date)
    it = find_item(a.item)
    move(it, "snoozed", {"status": "snoozed", "snooze_until": a.date})
    log_event(it["fm"]["id"], "snoozed", extra={"until": a.date}); git_commit(f"snooze {it['fm']['id']}")
    print(f"snoozed {it['fm']['id']} until {a.date}")


def cmd_done(a):
    it = find_item(a.item)
    if it["folder"] != "approved":
        sys.exit("only approved items can be marked done")
    body = it["body"].rstrip() + f"\n\n## Result\n{a.result or 'done'} ({dt.datetime.now().astimezone().isoformat(timespec='minutes')})\n"
    move(it, "done", {"status": "done"}, body)
    log_event(it["fm"]["id"], "done"); git_commit(f"done {it['fm']['id']}")
    print(f"done {it['fm']['id']}")


def cmd_requeue(a):
    """Re-lint everything in needs-work; move passing items to pending."""
    moved = 0
    for it in [i for i in all_items() if i["folder"] == "needs-work"]:
        checks, problems = lint(it["fm"], it["body"], offline=a.offline, others=all_items())
        pending = sum(1 for i in all_items() if i["folder"] == "pending")
        if not problems and pending < PENDING_CAP:
            move(it, "pending", {"status": "pending", "checks": checks}); log_event(it["fm"]["id"], "requeued", "queue"); moved += 1
        else:
            print(f"{it['fm'].get('id')} still needs work: " + "; ".join(problems or ["pending at cap"]))
    git_commit("requeue")
    print(f"{moved} item(s) moved to pending")


def cmd_expire(a):
    today = dt.date.today(); n = 0
    for it in all_items():
        fm = it["fm"]
        if it["folder"] == "snoozed":
            try:
                if dt.date.fromisoformat(str(fm.get("snooze_until"))) <= today:
                    move(it, "pending", {"status": "pending"}); n += 1
            except Exception:
                pass
        elif it["folder"] == "pending":
            try:
                if dt.date.fromisoformat(str(fm.get("expires"))[:10]) < today:
                    move(it, "expired", {"status": "expired"}); log_event(fm["id"], "expired", "queue"); n += 1
            except Exception:
                pass
    write_index(); git_commit("expire sweep")
    print(f"{n} item(s) moved")


def stats(days: int = 30) -> dict:
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=days)
    acc = rej = exp = ed = done = 0
    reasons: dict = {}
    for it in all_items():
        fm = it["fm"]
        try:
            when = dt.datetime.fromisoformat(str(fm.get("decided") or fm.get("created")))
            if when.tzinfo is None:
                when = when.astimezone()
        except Exception:
            continue
        if when < cutoff:
            continue
        f = it["folder"]
        if f in ("approved", "done"):
            acc += 1; done += f == "done"; ed += fm.get("status") == "edited"
        elif f == "rejected":
            rej += 1; reasons[fm.get("reason", "?")] = reasons.get(fm.get("reason", "?"), 0) + 1
        elif f == "expired":
            exp += 1
    decided = acc + rej
    handled = acc + rej + exp
    return {"days": days, "approved": acc, "done": done, "rejected": rej, "expired_unread": exp, "decided": decided,
            "acceptance_pct": round(100 * acc / decided) if decided else 0,
            "expired_pct": round(100 * exp / handled) if handled else 0, "reasons": reasons}


def cmd_stats(a):
    s = stats(a.days)
    print(f"Last {s['days']} days: {s['approved']} approved ({s['done']} done), {s['rejected']} rejected, {s['expired_unread']} expired unread.")
    print(f"Acceptance rate {s['acceptance_pct']}% of {s['decided']} decisions; expired-unread {s['expired_pct']}% of handled items.")
    if s["reasons"]:
        print("Rejection reasons: " + ", ".join(f"{k} {v}" for k, v in sorted(s["reasons"].items(), key=lambda x: -x[1])))
    log = ROOT / "log.jsonl"
    if log.exists():
        acts = sum(1 for l in log.read_text().splitlines() if l.strip())
        print(f"Log events on record: {acts}")


def cmd_status(a):
    if not ROOT.exists():
        print("Approval queue: not set up"); return
    idx = write_index() if (ROOT / "queue.json").exists() is False else json.loads((ROOT / "queue.json").read_text())
    c = idx["counts"]; s = stats(30)
    soon = 0
    for p in idx.get("pending", []):
        try:
            if (dt.date.fromisoformat(str(p["expires"])[:10]) - dt.date.today()).days <= 2:
                soon += 1
        except Exception:
            pass
    print(f"Approval queue: {c['pending']} pending ({soon} expiring within 2 days), {c['needs-work']} in needs-work, "
          f"{c['approved']} approved awaiting action, acceptance {s['acceptance_pct']}% over {s['decided']} decisions.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("new"); p.add_argument("file"); p.add_argument("--offline", action="store_true")
    p = sub.add_parser("lint"); p.add_argument("item"); p.add_argument("--offline", action="store_true")
    p = sub.add_parser("list"); p.add_argument("--status"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("digest"); p.add_argument("--max", type=int, default=7); p.add_argument("--write", action="store_true")
    p = sub.add_parser("approve"); p.add_argument("item"); p.add_argument("--note")
    p = sub.add_parser("reject"); p.add_argument("item"); p.add_argument("--reason", required=True); p.add_argument("--text")
    p = sub.add_parser("edit"); p.add_argument("item"); p.add_argument("--file", required=True)
    p = sub.add_parser("snooze"); p.add_argument("item"); p.add_argument("date")
    p = sub.add_parser("done"); p.add_argument("item"); p.add_argument("--result")
    sub.add_parser("expire")
    p = sub.add_parser("requeue"); p.add_argument("--offline", action="store_true")
    p = sub.add_parser("stats"); p.add_argument("--days", type=int, default=30)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    fn = globals()["cmd_" + a.cmd]
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
