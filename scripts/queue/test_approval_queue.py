#!/usr/bin/env python3
"""Offline tests for approval_queue.py. Run: python3 scripts/queue/test_approval_queue.py"""
import datetime as dt, importlib.util, os, sys, tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["PURPLELINK_QUEUE"] = tmp + "/q"
spec = importlib.util.spec_from_file_location("aq", Path(__file__).with_name("approval_queue.py"))
aq = importlib.util.module_from_spec(spec); spec.loader.exec_module(aq)

TODAY = dt.date.today()
EXP = (TODAY + dt.timedelta(days=10)).isoformat()


def item(**over):
    fm = {"id": "", "job": "test", "model": "hosted:claude", "kind": "submission", "target": "Product Hunt: ModernTex", "executor": "ben",
          "risk": "low", "effort_minutes": "20", "expires": EXP, "expected_effect": "20-80 visits (estimate)", "ledger": "directory-submissions"}
    fm.update(over)
    body = over.pop("_body", None) if "_body" in over else None
    fm.pop("_body", None)
    b = body or ("## Ask\nSubmit ModernTex to Product Hunt.\n\n## Why now\n- Product Hunt is free (producthunt.com/launch, read 2026-09-29).\n- No listing yet.\n\n"
                 "## Draft\n```\nNative macOS LaTeX editor for journal manuscripts.\n```\n\n## Verify\n- Price: site/llms.txt line 33.\n\n"
                 "## If approved\nBen submits.\n\n## If rejected\nGive a reason code.\n\n## Evidence\nnone\n")
    return aq.join_item(fm, b), fm, b


def write(name, text):
    p = Path(tmp) / name; p.write_text(text); return str(p)


def check(cond, msg):
    if not cond:
        print("FAIL:", msg); sys.exit(1)


aq.main(["init"])

# parse and roundtrip
text, fm, body = item()
fm2, body2 = aq.split_item(text)
check(fm2["target"] == "Product Hunt: ModernTex" and fm2["effort_minutes"] == "20", "roundtrip quoting")
check(aq.parse_scalar("{a: pass, b: fail}") == {"a": "pass", "b": "fail"}, "inline map")

# good item goes pending
r = aq.main(["new", write("a.md", text), "--offline"])
check(r == 0 and len(list((aq.ROOT / "pending").glob("*.md"))) == 1, "good item pending")

# duplicate target within 30 days
r = aq.main(["new", write("b.md", item()[0]), "--offline"])
check(r == 3 and len(list((aq.ROOT / "needs-work").glob("*.md"))) == 1, "duplicate goes to needs-work")

# lint failures
for label, kw in [("em dash", {"_body": "## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\nHello — there\n```\n\n## Verify\n- site/llms.txt line 1\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n"}),
                  ("auto outward", {"executor": "auto", "target": "Uneed"}),
                  ("reddit not ben", {"kind": "post", "target": "r/LaTeX thread", "executor": "claude-chrome"}),
                  ("banned phrase", {"target": "X1", "_body": "## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\nA game-changer for LaTeX\n```\n\n## Verify\n- site/llms.txt line 1\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n"}),
                  ("unverified", {"target": "X2", "_body": "## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\nok\n```\n\n## Verify\nUNVERIFIED price\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n"}),
                  ("glp1 dosing", {"target": "X3", "_body": "## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\nTake 2.5 mg of semaglutide weekly\n```\n\n## Verify\n- site/llms.txt line 1\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n"}),
                  ("early low risk", {"kind": "spend", "target": "X4", "executor": "ben", "n_conversions": "2", "risk": "low"}),
                  ("expired", {"target": "X5", "expires": (TODAY - dt.timedelta(days=1)).isoformat()}),
                  ("word cap", {"kind": "email", "target": "X6", "_body": "## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\n" + "word " * 200 + "\n```\n\n## Verify\n- site/llms.txt line 1\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n"})]:
    t, f, b = item(**kw)
    checks, problems = aq.lint(f, b, offline=True, others=aq.all_items())
    check(problems, f"lint should flag: {label}")

# rate limit: second self-promo to same subreddit
_, f1, b1 = item(kind="post", target="r/macapps App Pile reply", executor="ben")
aq.main(["new", write("c.md", aq.join_item(f1, b1)), "--offline"])
_, f2, b2 = item(kind="post", target="r/macapps main feed post", executor="ben")
c, p = aq.lint(f2, b2, offline=True, others=aq.all_items())
check(c["rate_limit"] == "fail", "subreddit rate limit")

# quotes from evidence
(aq.ROOT / "evidence" / "src.md").write_text("The quick brown fox jumps over the lazy dog while the small quiet cat sleeps on the warm windowsill today")
_, f3, b3 = item(target="X7", _body="## Ask\nx\n\n## Why now\n- a\n\n## Draft\n```\nthe quick brown fox jumps over the lazy dog while the small quiet cat sleeps on the warm windowsill today\n```\n\n## Verify\n- site/llms.txt line 1\n\n## If approved\nx\n\n## If rejected\nx\n\n## Evidence\nx\n")
c, p = aq.lint(f3, b3, offline=True, others=aq.all_items())
check(c["untrusted_quotes"] == "fail", "long quote from evidence flagged")

# decisions
pend = sorted((aq.ROOT / "pending").glob("*.md"))
ident = aq.split_item(pend[0].read_text())[0]["id"]
aq.main(["approve", ident, "--note", "ok"])
check(any(aq.split_item(p.read_text())[0]["id"] == ident for p in (aq.ROOT / "approved").glob("*.md")), "approve moves file")
aq.main(["done", ident, "--result", "https://example.com/x"])
check(len(list((aq.ROOT / "done").glob("*.md"))) == 1, "done")
ident2 = aq.split_item(next((aq.ROOT / "pending").glob("*.md")).read_text())[0]["id"]
aq.main(["reject", ident2, "--reason", "tone", "--text", "too salesy"])
check(len(list((aq.ROOT / "rejected").glob("*.md"))) == 1, "reject")
try:
    aq.main(["reject", "nope", "--reason", "bad"]); check(False, "bad reason should exit")
except SystemExit:
    pass

# stats and digest cap
s = aq.stats(30)
check(s["approved"] == 1 and s["rejected"] == 1 and s["acceptance_pct"] == 50 and s["reasons"] == {"tone": 1}, f"stats {s}")
for n in range(10):
    _, fx, bx = item(target=f"Target {n}", effort_minutes=str(5 + n), value=str(1 + n % 5))
    aq.main(["new", write(f"n{n}.md", aq.join_item(fx, bx)), "--offline"])
txt = aq.digest_text(7)
check(txt.count("-> approve") == 7 and "more pending" in txt, "digest caps at 7")

# expire sweep
_, fe, be = item(target="Old")
fe["expires"] = (TODAY - dt.timedelta(days=1)).isoformat(); fe["id"] = "q-old-001"; fe["status"] = "pending"
(aq.ROOT / "pending" / "old.md").write_text(aq.join_item(fe, be))
aq.main(["expire"])
check((aq.ROOT / "expired" / "old.md").exists(), "expire sweep")
check("Approval queue" in txt and Path(aq.ROOT / "queue.json").exists(), "index written")
print("approval queue tests ok")
