import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from latextools import bibcheck
text = open(sys.argv[1], encoding="utf-8").read()
res = bibcheck.parse_bib(text)
out = {"summary": bibcheck.summarize(res),
       "entries": [{"key": r.key, "type": r.entry_type, "missing_fields": r.missing_fields, "overall": r.overall()} for r in res],
       "annotated_bib": bibcheck.annotate_bib(text, res)}
print(json.dumps(out, indent=2))
