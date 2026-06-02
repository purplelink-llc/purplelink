import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import pdf_structure as ps


def test_safe_convert_kwargs_uses_modern_convert_signature():
    # convert() takes output_dir + format=[...]; output_folder/generate_markdown
    # belong to the DEPRECATED run() wrapper and would raise TypeError here.
    kw = ps.safe_convert_kwargs("/in/input.pdf", "/out")
    assert kw["input_path"] == "/in/input.pdf"
    assert kw["output_dir"] == "/out"
    assert "json" in kw["format"] and "markdown" in kw["format"]
    # Guard against accidentally reintroducing the deprecated kwargs.
    assert "output_folder" not in kw
    assert "generate_markdown" not in kw
    # OCR / hybrid / picture-description must never be enabled.
    blob = " ".join(str(k).lower() for k in kw)
    assert "ocr" not in blob
    assert "hybrid" not in blob
    assert "picture" not in blob


def test_summarize_real_shape_recursive():
    doc = {
        "file name": "x.pdf",
        "number of pages": 3,
        "kids": [
            {"type": "heading", "content": "Intro"},
            {"type": "paragraph", "content": "hello world foo bar"},
            {"type": "table", "kids": [
                {"type": "paragraph", "content": "cell one"},
            ]},
            {"type": "image", "content": "Figure 1 caption"},
            {"type": "table"},
        ],
    }
    s = ps.summarize(doc)
    assert s["pages"] == 3
    assert s["tables"] == 2
    assert s["figures"] == 1
    assert s["words"] >= 6


def test_summarize_tolerates_missing_fields():
    assert ps.summarize({}) == {"pages": 0, "tables": 0, "figures": 0, "words": 0}


def test_parse_output_dir_reads_md_and_json():
    files = {"out.md": "# Title\n\ntext", "out.json": '{"number of pages": 1, "kids": []}'}
    res = ps.parse_output_dir("/out", read_text=lambda n: files[n], list_files=lambda _: list(files))
    assert res["markdown"].startswith("# Title")
    assert res["json"]["number of pages"] == 1
    assert res["summary"]["pages"] == 1
