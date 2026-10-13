"""Make an uploaded LaTeX project safe to hand to pandoc.

pandoc's LaTeX reader follows \\input, \\include and similar commands by
opening the named file, and its writers fetch \\includegraphics targets. On
untrusted input that is a file-disclosure risk (an absolute path, a ``..``
path, a symlink, or a URL). pandoc's ``--sandbox`` option blocks all of it, but
it also stops pandoc reading any file that is not named on the command line,
which would break projects split across several .tex files and would drop
figures from the Word output.

So the control lives here instead, in plain Python with no pandoc needed:

* every relative include that resolves to a regular .tex file inside the work
  directory is inlined, recursively, with a depth, cycle and total-size cap;
* any file reference that is absolute, contains ``..``, is a URL, resolves
  outside the work directory, or goes through a symlink is removed;
* image references that pass the same checks are kept, and the caller is told
  (``needs_fs``) that pandoc has to read the file system for them, so it can
  use ``--sandbox`` whenever nothing on disk is needed.

This module never reads anything outside the work directory.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from latextools import core

MAX_DEPTH = 10
MAX_TOTAL_BYTES = 5 * 1024 * 1024

# One argument, inlined as LaTeX source.
_INCLUDE_CMDS = frozenset({"input", "include", "subfile", "subfileinclude"})
# Two arguments (directory, file), inlined as LaTeX source.
_IMPORT_CMDS = frozenset({
    "import", "subimport", "includefrom", "subincludefrom", "inputfrom", "subinputfrom",
})
# One argument naming a file whose content pandoc would read or embed.
_READ_CMDS = frozenset({
    "lstinputlisting", "verbatiminput", "VerbatimInput", "BVerbatimInput",
    "LVerbatimInput", "includesvg", "includepdf", "csvautotabular",
    "pgfplotstableread", "markdownInput",
})
# Second argument is the file.
_READ2_CMDS = frozenset({"inputminted"})
_GRAPHICS_CMDS = frozenset({"includegraphics"})
# Comma-separated bibliography file lists.
_BIB_CMDS = frozenset({"bibliography", "addbibresource", "addglobalbib", "addsectionbib"})
# Command that takes the file as first argument followed by two more groups.
_IFEXISTS_CMDS = frozenset({"InputIfFileExists", "IfFileExists"})
# Low-level macros that can assemble a command name at run time. A document that
# uses them is not given file access, whatever else it contains.
_RISKY_CMDS = frozenset({"csname", "catcode", "scantokens", "@namedef", "readline", "read"})

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg")

_TOKEN = re.compile(r"%[^\n]*|\\[^A-Za-z@]|\\(?P<name>[A-Za-z@]+)(?P<star>\*?)")


@dataclass
class Prepared:
    tex: str
    needs_fs: bool = False
    risky: bool = False
    notes: list[str] = field(default_factory=list)


class _State:
    def __init__(self, workdir: Path):
        self.root = workdir.resolve()
        self.total = 0
        self.kept_files = False
        self.risky = False
        self.notes: list[str] = []


def resolve_inside(workdir: Path, rel: str) -> Path | None:
    """Resolve *rel* against *workdir*. Return the real path, or None when the
    reference is absolute, uses '..', is a URL, leaves the directory, or goes
    through a symlink. The file does not have to exist."""
    root = Path(workdir).resolve()
    s = rel.strip()
    if not s or len(s) > 500:
        return None
    if any(ch in s for ch in ("\x00", "\\", "|", "$", "~", "{", "}", "\n", "\r")):
        return None
    if "://" in s or s.startswith(("/", "-")) or re.match(r"^[A-Za-z]:", s):
        return None
    parts = [p for p in s.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    cand = root.joinpath(*parts)
    try:
        real = cand.resolve()
    except (OSError, RuntimeError):
        return None
    if not real.is_relative_to(root):
        return None
    # A symlink anywhere on the path makes the resolved path differ from the
    # lexical one.
    if real != Path(os.path.abspath(cand)):
        return None
    return real


def _read_group(text: str, i: int) -> tuple[str, int] | None:
    """Read one balanced {...} group at or after *i* (whitespace skipped)."""
    n = len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    if i >= n or text[i] != "{":
        return None
    depth = 0
    j = i
    while j < n:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return None


def _skip_optional(text: str, i: int) -> int:
    """Skip any number of [..] option groups (and whitespace) at *i*."""
    n = len(text)
    while True:
        k = i
        while k < n and text[k] in " \t\r\n":
            k += 1
        if k < n and text[k] == "[":
            end = text.find("]", k)
            if end == -1 or end - k > 2000:
                return i
            i = end + 1
        else:
            return i


def _read_args(text: str, i: int, count: int, optional: bool = True) -> tuple[list[str], int] | None:
    if optional:
        i = _skip_optional(text, i)
    args: list[str] = []
    for _ in range(count):
        g = _read_group(text, i)
        if g is None:
            return None
        args.append(g[0])
        i = g[1]
    return args, i


def _read_bare_filename(text: str, i: int) -> tuple[str, int] | None:
    """\\input foo.tex  (no braces)."""
    m = re.compile(r"[ \t]*([^\s{}\\%]+)").match(text, i)
    if not m:
        return None
    return m.group(1), m.end()


def _resolve_tex(state: _State, name: str) -> Path | None:
    name = name.strip()
    cands = [name] if name.lower().endswith(".tex") else [name + ".tex", name]
    for c in cands:
        real = resolve_inside(state.root, c)
        if real is not None and real.is_file() and real.suffix.lower() == ".tex":
            return real
    return None


def _body_of_subfile(text: str) -> str:
    b = text.find("\\begin{document}")
    e = text.rfind("\\end{document}")
    if b != -1 and e > b:
        return text[b + len("\\begin{document}"):e]
    return text


def _process(text: str, state: _State, stack: tuple[Path, ...]) -> str:
    out: list[str] = []
    last = 0
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.search(text, pos)
        if not m:
            break
        pos = m.end()
        name = m.group("name")
        if name is None:
            continue
        if name in _RISKY_CMDS:
            state.risky = True
            continue
        start = m.start()

        def replace(repl: str, end: int) -> None:
            nonlocal last, pos
            out.append(text[last:start])
            out.append(repl)
            last = end
            pos = end

        if name in _INCLUDE_CMDS:
            got = _read_args(text, pos, 1, optional=False)
            if got is None:
                bare = _read_bare_filename(text, pos) if name == "input" else None
                if bare is None:
                    continue
                fname, end = bare
            else:
                fname, end = got[0][0], got[1]
            replace(_inline(state, stack, fname, name == "subfile"), end)
        elif name in _IMPORT_CMDS:
            got = _read_args(text, pos, 2, optional=False)
            if got is None:
                continue
            d, f = got[0]
            fname = d.rstrip("/") + "/" + f if d.strip() else f
            replace(_inline(state, stack, fname, False), got[1])
        elif name in _IFEXISTS_CMDS:
            got = _read_args(text, pos, 3, optional=False)
            if got is None:
                continue
            state.notes.append(f"removed \\{name}")
            replace("", got[1])
        elif name in _READ_CMDS or name in _READ2_CMDS or name in _GRAPHICS_CMDS:
            count = 2 if name in _READ2_CMDS else 1
            got = _read_args(text, pos, count)
            if got is None:
                continue
            target = got[0][-1]
            if resolve_inside(state.root, target) is None:
                state.notes.append(f"removed \\{name} with an unsafe path")
                replace("", got[1])
            else:
                state.kept_files = True
                pos = got[1]
        elif name in _BIB_CMDS:
            got = _read_args(text, pos, 1)
            if got is None:
                continue
            names = [x for x in got[0][0].split(",") if x.strip()]
            if any(resolve_inside(state.root, x) is None for x in names):
                state.notes.append(f"removed \\{name} with an unsafe path")
                replace("", got[1])
            else:
                pos = got[1]
        elif name == "graphicspath":
            got = _read_args(text, pos, 1, optional=False)
            if got is None:
                continue
            entries = re.findall(r"\{([^{}]*)\}", got[0][0])
            if any(resolve_inside(state.root, e) is None for e in entries):
                state.notes.append("removed \\graphicspath with an unsafe path")
                replace("", got[1])
            else:
                pos = got[1]
    out.append(text[last:])
    return "".join(out)


def _inline(state: _State, stack: tuple[Path, ...], fname: str, subfile: bool) -> str:
    real = _resolve_tex(state, fname)
    if real is None or real in stack or len(stack) >= MAX_DEPTH:
        state.notes.append("removed an include that could not be inlined")
        return ""
    try:
        data = real.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    state.total += len(data.encode("utf-8"))
    if state.total > MAX_TOTAL_BYTES:
        raise core.ValidationError("The project's .tex files are too large to convert.")
    if subfile:
        data = _body_of_subfile(data)
    return "\n" + _process(data, state, stack + (real,)) + "\n"


def prepare_for_pandoc(workdir: Path, main_text: str, main_path: Path | None = None) -> Prepared:
    """Flatten relative includes and strip unsafe file references.

    *main_text* is the content of the main .tex file. Raises
    core.ValidationError when the included files are too large.
    """
    state = _State(Path(workdir))
    state.total = len(main_text.encode("utf-8"))
    stack = (main_path.resolve(),) if main_path is not None else ()
    flat = _process(main_text, state, stack)
    needs_fs = False
    if state.kept_files:
        # pandoc has to read figures or listings from disk unless the
        # project holds nothing besides the main .tex and the .bib.
        needs_fs = any(
            p.is_file() and p.suffix.lower() not in (".tex", ".bib")
            for p in state.root.rglob("*")
        )
    return Prepared(flat, needs_fs=needs_fs, risky=state.risky, notes=state.notes)
