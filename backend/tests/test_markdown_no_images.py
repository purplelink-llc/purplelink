"""The markdown endpoints must not let user Markdown name a file for pandoc to open.

Pandoc cannot run here (x86 binary), so this checks the pieces: the Lua filter text and that
the markdown-convert command carries it and does not rely on --sandbox (which fails for the
docx and pdf writers on the Modal image and does not stop image embedding).
"""
import re
from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


def test_lua_filter_replaces_images():
    m = re.search(r'NO_IMAGES_LUA = """(.*?)"""', APP, re.S)
    assert m, "NO_IMAGES_LUA missing"
    lua = m.group(1)
    assert "function Image(" in lua
    assert "pandoc.Span" in lua  # alt text stays, no file reference survives


def test_markdown_convert_uses_filter_and_plain_pandoc():
    block = APP[APP.index("async def markdown_convert_endpoint"):]
    block = block[:block.index("return Response(") if "return Response(" in block else 4000]
    assert "--lua-filter=" in block
    assert "run_pandoc_plain(" in block
    assert "run_pandoc_sandboxed(" not in block
