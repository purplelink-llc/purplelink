"""Recall benchmark for the coherence check (backend/latextools/coherence.py): plant known defects, score.

Precision of the coherence check was judged by hand on two papers (14/15), but a report that is right about
everything it says can still miss most of what is wrong. This script measures what it misses. Three
open-access arXiv papers (CC BY or CC BY-SA; one .tex source, two PDFs) get 8 or 9 defects each, written to
match one of the check's types (CHECK_TYPES), and the full check runs on each planted copy:

  abstract number changed         hypothesis or role labels swapped    a hypothesis result dropped
  a construct redefined           a promised contribution not delivered a term renamed midway
  an unqualified claim that a stated limitation contradicts            a theory, a research question or a
                                                                       citation that goes nowhere

A plant counts as found when a kept finding names it (a regex on the finding's title, why, fix and
quotes) with one of the plant's accepted types ("strict"), or with any type ("lenient"). "Candidates" also
counts findings the verifier dropped, which shows how much recall the verifier costs. Every other kept
finding is unplanted: either a real issue the original paper already has, or a false alarm. Those are
judged by hand in judgments.json and give the precision on unplanted findings.

Each paper is also run unplanted (the baseline), so a planted run's unplanted findings can be compared
with what the original paper produces.

    cd backend && python3 benchmark/coherence_planted.py --dry-run          # free: plants apply, rules only
    cd backend && BENCH_ANTHROPIC_KEY=... python3 benchmark/coherence_planted.py   # full run, about $3
    cd backend && python3 benchmark/coherence_planted.py --score-only       # rescore saved runs, free

COSTS REAL MONEY (about $0.50 per check, so about $3 for three papers planted and unplanted; --max-cost
stops it). Uses BENCH_ANTHROPIC_KEY only, never the production key. Writes to
docs/growth-briefs/coherence-recall/ (git-ignored): the downloaded papers, every report, results.md.
The papers' licences allow adapted copies; the planted copies stay private.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from latextools import coherence as co  # noqa: E402

OUT = HERE.parents[1] / "docs" / "growth-briefs" / "coherence-recall"
UA = {"User-Agent": "purplelink-coherence-bench/1.0 (ben@purplelink.llc)"}


@dataclass
class Plant:
    id: str
    type: str                  # the CHECK_TYPES entry it is written for, or "hypothesis_label_swap"
    desc: str
    edits: list                # [(old, new)]; old is literal (whitespace-flexible) or "re:<regex>" (DOTALL)
    accept: set                # finding types that count as a strict hit
    match: str                 # regex (case-insensitive) a finding must contain to be about this plant
    fields: str = "all"        # "all" searches title, why, fix and quotes; "prose" skips the quotes


@dataclass
class Paper:
    key: str
    arxiv: str
    licence: str
    kind: str                  # "tex" (e-print source, \input flattened) or "pdf"
    title: str
    plants: list = field(default_factory=list)
    main: str = "main.tex"


# A label swap has no type of its own; any finding that names the swapped labels counts.
ANY_HYP = {"hypothesis_untested", "hypothesis_undeclared", "construct_definition_conflict", "term_drift",
           "abstract_results_mismatch", "label_gap", "sample_inconsistency", "contribution_undelivered",
           "research_question_unanswered", "limitation_contradicts_claim"}

PAPERS = [
    Paper("A", "2411.17157v1", "CC BY 4.0", "tex",
          "Anthropomorphism in role-playing AI chatbots and media dependency (CHI-style user study)", [
        Plant("A1", "abstract_results_mismatch", "Abstract sample 149 changed to 194",
              [("We invited 149 users", "We invited 194 users")],
              {"abstract_results_mismatch", "sample_inconsistency"}, r"\b194\b"),
        Plant("A2", "hypothesis_label_swap", "Conclusion swaps Role 2 and Role 3 (which roles supported the hypothesis)",
              [(r"(\ie Roles 1, 3, and 4)", r"(\ie Roles 1, 2, and 4)"),
               ("(especially Role 2)", "(especially Role 3)")],
              ANY_HYP, r"\broles?\s*[23]\b|roles 1, 2,? and 4", "prose"),
        Plant("A3", "hypothesis_untested", "A second hypothesis (gaming experience moderates) that is never tested",
              [("we hope to bring new insights to the research of role-playing chatbots.",
                "we hope to bring new insights to the research of role-playing chatbots. We further hypothesize "
                "that users' prior gaming experience strengthens the effect of anthropomorphism on media dependency.")],
              {"hypothesis_untested"}, r"gaming experience|prior gaming"),
        Plant("A4", "construct_definition_conflict", "Discussion redefines media dependency as logged minutes per day",
              [("with this relationship mediated by users' satisfaction.",
                "with this relationship mediated by users' satisfaction. Here, media dependency was measured as the "
                "minutes per day each participant spent chatting, taken from platform logs.")],
              {"construct_definition_conflict", "term_drift"}, r"minutes per day|platform logs"),
        Plant("A5", "contribution_undelivered", "Intro promises anti-addiction design implications; Discussion's design implications removed",
              [("we discuss our observations and implications that may inspire future research.",
                "we discuss our observations and implications that may inspire future research. This work makes three "
                "contributions: an empirical test of media dependency theory on role-playing chatbots, an "
                "interview-based account of when that relationship breaks down, and concrete design implications "
                "for anti-addiction features."),
               (r"re:We thus see two design implications.*?based on user characteristics accordingly\.", "")],
              {"contribution_undelivered"}, r"anti-addiction|design implication"),
        Plant("A6", "term_drift", "Satisfaction renamed 'enjoyment' in the Role 3, Role 4 and summary results",
              [("users' satisfaction (B = 0.761", "users' enjoyment (B = 0.761"),
               ("users' satisfaction (B = 0.486", "users' enjoyment (B = 0.486"),
               ("the users' satisfaction with the chatbots was also", "the users' enjoyment of the chatbots was also")],
              {"term_drift", "construct_definition_conflict"}, r"enjoyment"),
        Plant("A7", "limitation_contradicts_claim", "Conclusion claims the findings hold on every platform and for all ages",
              [("with satisfaction acting as a positive mediator.",
                "with satisfaction acting as a positive mediator. These findings hold for role-playing chatbots on "
                "every platform and for users of all ages.")],
              {"limitation_contradicts_claim", "sample_inconsistency"}, r"every platform|all ages"),
        Plant("A8", "theory_unused", "Social presence theory introduced as a second lens, never used",
              [("by drawing upon the media dependency theory in communication studies.",
                "by drawing upon the media dependency theory in communication studies. We also draw on social "
                "presence theory as a second lens to explain why anthropomorphism increases dependency.")],
              {"theory_unused"}, r"social presence"),
        Plant("A9", "citation_role_conflict", "Li and Sung cited in the Discussion for the opposite of the Related Work claim",
              [("care must be taken to avoid designs that may evoke this negative response.",
                "care must be taken to avoid designs that may evoke this negative response. Li and "
                r"Sung~\cite{li2021anthropomorphism} similarly found that anthropomorphism increases the psychological "
                "distance between users and smart speakers and lowers their satisfaction.")],
              {"citation_role_conflict"}, r"li2021|li and sung|psychological distance"),
    ], main="main.tex"),
    Paper("B", "2105.08927v1", "CC BY 4.0", "pdf",
          "Digital competency of educators and Moodle use (TTF, SEM, 7 hypotheses)", [
        Plant("B1", "abstract_results_mismatch", "Abstract sample 238 changed to 283",
              [("survey was conducted with 238 teaching staff", "survey was conducted with 283 teaching staff")],
              {"abstract_results_mismatch", "sample_inconsistency"}, r"\b283\b"),
        Plant("B2", "hypothesis_label_swap", "H2 and H3 labels swapped in the hypothesis-testing table",
              [("H2 KD → TTF 0.49", "H3 KD → TTF 0.49"), ("H3 PRS → TTF 0.27", "H2 PRS → TTF 0.27")],
              ANY_HYP, r"\bH[23]\b", "prose"),
        Plant("B3", "hypothesis_untested", "H4 row removed from the hypothesis-testing table",
              [("H4 PFS→ TTF 0.21 2.693 0.011 Accepted", "")],
              {"hypothesis_untested"}, r"\bH4\b|professional skills|\bPFS\b", "prose"),
        Plant("B4", "construct_definition_conflict", "Method operationalises utilization as intention to adopt",
              [("performance [5], respectively.",
                "performance [5], respectively. Utilization was operationalised as teachers' stated intention to adopt "
                "Moodle in the coming semester.")],
              {"construct_definition_conflict", "term_drift"}, r"intention to adopt|coming semester|stated intention"),
        Plant("B5", "contribution_undelivered", "Intro promises a training checklist that never appears",
              [("for practitioners, academics, and policymakers.",
                "for practitioners, academics, and policymakers. In addition, the study contributes a practical "
                "training checklist that universities can use to raise each of the four digital competencies.")],
              {"contribution_undelivered"}, r"checklist"),
        Plant("B6", "term_drift", "Knowledge deepening renamed knowledge broadening in the Discussion",
              [("knowledge deepening (KD), presentation skills (PRS)", "knowledge broadening (KD), presentation skills (PRS)"),
               ("the knowledge deepening (KD) variable", "the knowledge broadening (KD) variable")],
              {"term_drift", "construct_definition_conflict", "acronym_conflict"}, r"broadening"),
        Plant("B7", "limitation_contradicts_claim", "Conclusion generalises a purposive sample to every Malaysian institution",
              [("individuals’ capability using any technology.",
                "individuals’ capability using any technology. Because the sample covers university educators across "
                "Malaysia, these findings generalise to every higher education institution in the country.")],
              {"limitation_contradicts_claim", "sample_inconsistency"}, r"generali[sz]e to every|every higher education"),
        Plant("B8", "theory_unused", "Self-Determination Theory introduced as a second lens, never used",
              [("can better conclude the inferences.",
                "can better conclude the inferences. We also draw on Self-Determination Theory as a second lens to "
                "explain why educators choose to use Moodle.")],
              {"theory_unused"}, r"self-determination|\bSDT\b"),
    ]),
    Paper("C", "2209.04900v1", "CC BY 4.0 (arXiv: CC BY-SA 4.0)", "pdf",
          "Web 3.0 adoption behaviour (PLS-SEM, 3 hypotheses, Twitter sentiment)", [
        Plant("C1", "abstract_results_mismatch", "Abstract share of positive tweets 56% changed to 64%",
              [("explored that 56% tweets", "explored that 64% tweets")],
              {"abstract_results_mismatch"}, r"\b64\b"),
        Plant("C2", "hypothesis_label_swap", "H2 and H3 swapped in the results narrative (table unchanged)",
              [("Therefore, H2 (eWOM→INT)", "Therefore, H3 (eWOM→INT)"),
               ("sturdily supported H3 (DD→INT)", "sturdily supported H2 (DD→INT)")],
              ANY_HYP, r"\bH[23]\b", "prose"),
        Plant("C3", "sample_inconsistency", "Method says 176 responses; abstract and elsewhere 167",
              [("Total 167 responses were collected", "Total 176 responses were collected")],
              {"sample_inconsistency", "abstract_results_mismatch"}, r"\b176\b|\b167\b"),
        Plant("C4", "construct_definition_conflict", "Digital Dexterity measured as hours on crypto platforms, one item",
              [("Digital Dexterity was measured by adopting six items from [11] and [24].",
                "Digital Dexterity was measured as the number of hours per week a respondent spends on cryptocurrency "
                "platforms, from a single self-reported item.")],
              {"construct_definition_conflict", "term_drift"}, r"hours per week|single self-reported|cryptocurrency platforms"),
        Plant("C5", "term_drift", "Electronic Word-of-Mouth renamed 'social influence' in the Conclusion",
              [("users who consider the Electronic Word -of-Mouth as", "users who consider social influence as"),
               ("relationships of Dig ital Dexterity and Electronic Word - of-Mouth towards",
                "relationships of Digital Dexterity and social influence towards")],
              {"term_drift", "construct_definition_conflict"}, r"social influence"),
        Plant("C6", "contribution_undelivered", "Intro promises a Web3 readiness index that never appears",
              [("advances the knowledge towards Web3.",
                "advances the knowledge towards Web3. It also contributes a validated Web3 readiness index that "
                "practitioners can use to score their users.")],
              {"contribution_undelivered"}, r"readiness index"),
        Plant("C7", "limitation_contradicts_claim", "Conclusion generalises a small snowball sample worldwide",
              [("explored the different perspectives of Web3 adoption.",
                "explored the different perspectives of Web3 adoption. These results generalise to Internet users "
                "worldwide, across every region and age group.")],
              {"limitation_contradicts_claim", "sample_inconsistency"}, r"worldwide|every region"),
        Plant("C8", "research_question_unanswered", "Unlabelled question (developers vs ordinary users) never answered",
              [("process of PLS -SEM and Sentiment analysis.",
                "process of PLS -SEM and Sentiment analysis. We also ask whether the sentiment of tweets differs "
                "between Web3 developers and ordinary users.")],
              {"research_question_unanswered"}, r"developers"),
    ]),
]


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

def fetch(paper: Paper) -> Path:
    """Download the paper once into OUT/cache/<id>/ (a .pdf, or the e-print source unpacked into src/)."""
    import httpx

    d = OUT / "cache" / paper.arxiv
    d.mkdir(parents=True, exist_ok=True)
    if paper.kind == "pdf":
        target = d / "paper.pdf"
        if not target.exists():
            r = httpx.get(f"https://arxiv.org/pdf/{paper.arxiv}", headers=UA, follow_redirects=True, timeout=60)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF-"):
                raise SystemExit(f"{paper.arxiv}: not a PDF")
            target.write_bytes(r.content)
            time.sleep(3)              # arXiv asks for a pause between requests
        return target
    src = d / "src"
    if not (src / paper.main).exists():
        r = httpx.get(f"https://arxiv.org/e-print/{paper.arxiv}", headers=UA, follow_redirects=True, timeout=60)
        r.raise_for_status()
        src.mkdir(exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:*") as tf:
            tf.extractall(src, filter="data")          # refuses absolute paths, links out, devices
        time.sleep(3)
    return src / paper.main


def flatten_tex(main: Path) -> str:
    """Inline \\input{...} children (the loader reads one file); only files inside the source folder."""
    return _flatten(main, main.parent.resolve(), 0)


def _flatten(path: Path, root: Path, depth: int) -> str:
    text = path.read_text("utf-8", "replace")

    def sub(m: re.Match) -> str:
        name = m.group(1).strip()
        child = (root / (name if name.endswith(".tex") else name + ".tex")).resolve()
        if depth > 4 or root not in child.parents or not child.exists():
            return m.group(0)
        return _flatten(child, root, depth + 1)

    return re.sub(r"(?<!%)\\(?:input|include)\{([^}]+)\}", sub, text)


def _pattern(old: str) -> re.Pattern:
    if old.startswith("re:"):
        return re.compile(old[3:], re.S)
    return re.compile(r"\s+".join(re.escape(tok) for tok in old.split()))


def apply_edits(text: str, edits: list) -> tuple[str, list[str]]:
    """Apply (old, new) edits in order; each old must match exactly once. Returns (text, problems)."""
    problems = []
    for old, new in edits:
        pat = _pattern(old)
        hits = len(pat.findall(text))
        if hits != 1:
            problems.append(f"{hits} matches for {old[:60]!r}")
            continue
        text = pat.sub(lambda _m: new, text, count=1)
    return text, problems


def plant_manuscript(ms: co.Manuscript, plant: Plant) -> list[str]:
    """Apply a plant to the extracted section text of a PDF manuscript (in place)."""
    problems = []
    for old, new in plant.edits:
        pat = _pattern(old)
        total = sum(len(pat.findall(s.text)) for s in ms.sections)
        if total != 1:
            problems.append(f"{total} matches for {old[:60]!r}")
            continue
        s = next(s for s in ms.sections if pat.search(s.text))
        s.text = pat.sub(lambda _m: new, s.text, count=1)
        if s.role == "abstract":
            ms.abstract = s.text
    return problems


def load(paper: Paper, planted: bool) -> tuple[co.Manuscript, dict]:
    path = fetch(paper)
    problems: dict = {}
    if paper.kind == "tex":
        src = flatten_tex(path)
        if planted:
            for p in paper.plants:
                src, probs = apply_edits(src, p.edits)
                if probs:
                    problems[p.id] = probs
        return co.from_latex(src), problems
    ms = co.load_manuscript(path.read_bytes(), path.name)
    if planted:
        for p in paper.plants:
            probs = plant_manuscript(ms, p)
            if probs:
                problems[p.id] = probs
    return ms, problems


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _finding_text(f: dict, fields: str) -> str:
    parts = [f.get("title", ""), f.get("why", ""), f.get("fix", "")]
    if fields == "all":
        parts += [q.get("text", "") for q in f.get("quotes", [])]
    return " ".join(parts)


def matches(plant: Plant, f: dict) -> bool:
    return bool(re.search(plant.match, _finding_text(f, plant.fields), re.I))


def judgment_key(paper_key: str, f: dict) -> str:
    return f"{paper_key}|{re.sub(r'[^a-z0-9]+', ' ', f.get('title', '').lower()).strip()[:120]}"


def score_run(paper: Paper, report: dict, judgments: dict) -> dict:
    kept, dropped = report.get("findings", []), report.get("dropped", [])
    plants = []
    for p in paper.plants:
        hits = [f for f in kept if matches(p, f)]
        strict = [f for f in hits if f["type"] in p.accept]
        plants.append({
            "id": p.id, "type": p.type, "desc": p.desc,
            "strict": bool(strict), "lenient": bool(hits),
            "candidate": bool(hits) or any(matches(p, f) for f in dropped),
            "dropped_by_verifier": not hits and any(matches(p, f) for f in dropped),
            "by_rule": any(f.get("source") == "rule" for f in hits),
            "found_as": sorted({f["type"] for f in hits}),
        })
    unplanted = []
    for f in kept:
        if any(matches(p, f) for p in paper.plants):
            continue
        k = judgment_key(paper.key, f)
        unplanted.append({"key": k, "type": f["type"], "source": f.get("source"), "title": f.get("title", ""),
                          "verdict": judgments.get(k, {}).get("verdict", "unjudged")})
    return {"plants": plants, "unplanted": unplanted, "n_kept": len(kept), "n_dropped": len(dropped),
            "cost_usd": report.get("usage", {}).get("cost_usd")}


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "0/0"


def write_results(runs: dict, judgments: dict) -> str:
    """runs: {(paper_key, label): report}. Writes results.md and results.json and returns the markdown."""
    by_key = {p.key: p for p in PAPERS}
    planted = {k: v for k, v in runs.items() if k[1].startswith("planted")}
    scored = {k: score_run(by_key[k[0]], r, judgments) for k, r in planted.items()}
    lines = ["# Coherence check: planted-defect recall", "",
             f"Generated {time.strftime('%Y-%m-%d %H:%M')} by backend/benchmark/coherence_planted.py.", "",
             "Strict: a kept finding names the plant with an accepted type. Lenient: any type. Candidates: before "
             "the verifier (kept plus dropped).", ""]
    types = list(dict.fromkeys(p.type for paper in PAPERS for p in paper.plants))
    lines += ["## Recall by type", "", "| Type | Plants | Strict | Lenient | Candidates | Dropped by verifier |",
              "|---|---|---|---|---|---|"]
    tot = dict.fromkeys(("n", "strict", "lenient", "candidate", "dropped"), 0)
    for t in types:
        rows = [pl for s in scored.values() for pl in s["plants"] if pl["type"] == t]
        n = len(rows)
        st, le, ca, dr = (sum(r[x] for r in rows) for x in ("strict", "lenient", "candidate", "dropped_by_verifier"))
        for k_, v in zip(tot, (n, st, le, ca, dr)):
            tot[k_] += v
        lines.append(f"| `{t}` | {n} | {_pct(st, n)} | {_pct(le, n)} | {_pct(ca, n)} | {dr} |")
    lines.append(f"| **All** | {tot['n']} | {_pct(tot['strict'], tot['n'])} | {_pct(tot['lenient'], tot['n'])} | "
                 f"{_pct(tot['candidate'], tot['n'])} | {tot['dropped']} |")
    lines += ["", "## Per plant", "", "| Run | Plant | Type | Found | As | Rule | Plant |", "|---|---|---|---|---|---|---|"]
    for (pk, label), s in sorted(scored.items()):
        for pl in s["plants"]:
            found = "strict" if pl["strict"] else "lenient" if pl["lenient"] else \
                "verifier dropped" if pl["dropped_by_verifier"] else "missed"
            lines.append(f"| {pk} {label} | {pl['id']} | `{pl['type']}` | {found} | {', '.join(pl['found_as'])} | "
                         f"{'yes' if pl['by_rule'] else ''} | {pl['desc']} |")
    lines += ["", "## Unplanted findings (precision)", ""]
    verdicts = [u["verdict"] for s in scored.values() for u in s["unplanted"]]
    real, false, unj = (verdicts.count(v) for v in ("real", "false", "unjudged"))
    lines.append(f"Planted runs: {real} real, {false} false, {unj} unjudged. Precision on judged unplanted findings: "
                 f"{_pct(real, real + false)}.")
    kept_total = sum(s["n_kept"] for s in scored.values())
    lines.append(f"Kept findings in planted runs: {kept_total}, of which {kept_total - len(verdicts)} name a plant.")
    base = {k: v for k, v in runs.items() if k[1] == "baseline"}
    if base:
        lines += ["", "Baseline (unplanted papers): " + ", ".join(
            f"{k[0]} {len(v.get('findings', []))} kept / {len(v.get('dropped', []))} dropped"
            for k, v in sorted(base.items()))]
    lines += ["", "| Run | Type | Source | Verdict | Title |", "|---|---|---|---|---|"]
    for (pk, label), s in sorted(scored.items()):
        for u in s["unplanted"]:
            lines.append(f"| {pk} {label} | `{u['type']}` | {u['source']} | {u['verdict']} | {u['title'][:140]} |")
    for (pk, label), r in sorted(base.items()):
        for f in r.get("findings", []):
            k = judgment_key(pk, f)
            lines.append(f"| {pk} baseline | `{f['type']}` | {f.get('source')} | "
                         f"{judgments.get(k, {}).get('verdict', 'unjudged')} | {f.get('title', '')[:140]} |")
    cost = sum((r.get("usage") or {}).get("cost_usd") or 0 for r in runs.values())
    lines += ["", f"Model cost of all saved runs: ${cost:.2f}.", ""]
    md = "\n".join(lines)
    (OUT / "results.md").write_text(md)
    (OUT / "results.json").write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in scored.items()}, indent=2))
    return md


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def dry_run() -> int:
    """No model: check every plant applies exactly once, and show what the free rules already catch."""
    bad = 0
    for paper in PAPERS:
        base, _ = load(paper, planted=False)
        ms, problems = load(paper, planted=True)
        print(f"\n{paper.key} {paper.arxiv} ({paper.kind}): {len(ms.sections)} sections, "
              f"{sum(len(s.text) for s in ms.sections)} chars")
        for pid, probs in problems.items():
            bad += 1
            print(f"  PLANT {pid} DID NOT APPLY: {'; '.join(probs)}")
        base_titles = {f.title for f in co.rule_findings(base)}
        for f in co.rule_findings(ms):
            hit = [p.id for p in paper.plants if matches(p, f.to_dict())]
            tag = ", ".join(hit) if hit else ("baseline" if f.title in base_titles else "unplanted")
            print(f"  rule [{tag}] {f.type}: {f.title}")
    print(f"\n{'all plants applied' if not bad else f'{bad} plants did not apply'}")
    return 1 if bad else 0


async def full_run(args) -> int:
    from latextools import papercheck

    key = os.environ.get("BENCH_ANTHROPIC_KEY", "")
    if not key:
        print("Set BENCH_ANTHROPIC_KEY (a separate key with spare credit, not the production key).", file=sys.stderr)
        return 2
    os.environ["ANTHROPIC_API_KEY"] = key
    runs_dir = OUT / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for paper in PAPERS:
        if args.papers and paper.key not in args.papers:
            continue
        if not args.no_baseline:
            jobs.append((paper, "baseline", False))
        for r in range(1, args.repeats + 1):
            jobs.append((paper, f"planted-r{r}", True))
    spent = 0.0
    with papercheck.UsageTracker(max_cost_usd=args.max_cost) as usage:
        for paper, label, planted in jobs:
            path = runs_dir / f"{paper.key}-{label}.json"
            if path.exists() and not args.force:
                print(f"{paper.key} {label}: saved, skipped (--force to rerun)", file=sys.stderr)
                continue
            ms, problems = load(paper, planted)
            if problems:
                print(f"{paper.key}: plants did not apply, run --dry-run", file=sys.stderr)
                return 1
            before = len(usage.records)
            t0 = time.time()
            report = await co.run_coherence_check(ms, use_model=True, verify_findings=True)
            recs = usage.records[before:]
            cost = sum(r["cost_usd"] for r in recs)
            spent += cost
            report["usage"] = {"cost_usd": cost, "calls": len(recs), "seconds": round(time.time() - t0)}
            report["bench"] = {"paper": paper.key, "arxiv": paper.arxiv, "label": label}
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"{paper.key} {label}: {len(report['findings'])} kept, {len(report['dropped'])} dropped, "
                  f"${cost:.3f} (total ${spent:.2f})", file=sys.stderr)
    return 0


def load_runs() -> dict:
    runs = {}
    for p in sorted((OUT / "runs").glob("*.json")):
        k, label = p.stem.split("-", 1)
        runs[(k, label)] = json.loads(p.read_text())
    return runs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="apply the plants and run the rules only (free)")
    ap.add_argument("--score-only", action="store_true", help="rescore saved runs (free)")
    ap.add_argument("--papers", nargs="*", help="paper keys to run (A B C)")
    ap.add_argument("--repeats", type=int, default=1, help="planted runs per paper")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--force", action="store_true", help="rerun runs already saved")
    ap.add_argument("--max-cost", type=float, default=5.0, help="stop spending at this many dollars")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        return dry_run()
    if not args.score_only:
        rc = asyncio.run(full_run(args))
        if rc:
            return rc
    jpath = OUT / "judgments.json"
    judgments = json.loads(jpath.read_text()) if jpath.exists() else {}
    print(write_results(load_runs(), judgments))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
