"""Run the manuscript coherence check on a local file.

  python3 backend/scripts/coherence_check.py paper.tex --rules-only           # free rule checks, no key
  BENCH_ANTHROPIC_KEY=sk-ant-... python3 backend/scripts/coherence_check.py paper.pdf --out reports/x

The full check calls the Anthropic API, and only that API, with the manuscript. It takes BENCH_ANTHROPIC_KEY,
never the production key (see the Paper Review memory note on benchmark keys). Writes <out>.json and <out>.md;
put --out somewhere git-ignored, since the report quotes the manuscript.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latextools import coherence, papercheck  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--out", help="output path without extension (default: print markdown)")
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--max-cost", type=float, default=3.0)
    args = ap.parse_args()

    if not args.rules_only:
        key = os.environ.get("BENCH_ANTHROPIC_KEY", "")
        if not key:
            print("Set BENCH_ANTHROPIC_KEY (a separate key, not the production one) or pass --rules-only.",
                  file=sys.stderr)
            return 2
        os.environ["ANTHROPIC_API_KEY"] = key

    path = Path(args.path)
    ms = coherence.load_manuscript(path.read_bytes(), path.name)
    print(f"{len(ms.sections)} sections, {sum(len(s.text) for s in ms.sections)} chars, "
          f"source {ms.source_kind}{' (truncated)' if ms.truncated else ''}", file=sys.stderr)

    async def go():
        with papercheck.UsageTracker(max_cost_usd=args.max_cost) as usage:
            report = await coherence.run_coherence_check(
                ms, use_model=not args.rules_only, verify_findings=not args.no_verify)
        report["usage"] = usage.to_dict()
        report["usage"]["calls_detail"] = usage.records
        return report

    report = asyncio.run(go())
    md = coherence.render_markdown(report)
    if args.out:
        # Appended, not with_suffix: "reports/2512.00869" would lose ".00869".
        json_path, md_path = Path(args.out + ".json"), Path(args.out + ".md")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        md_path.write_text(md)
        print(f"wrote {json_path} and {md_path}", file=sys.stderr)
    else:
        print(md)
    u = report["usage"]
    print(f"{len(report['findings'])} findings, {len(report['dropped'])} dropped by the verifier, "
          f"{len(report['bible']['items'])} bible items, {u['calls']} calls, ${u['cost_usd']:.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
