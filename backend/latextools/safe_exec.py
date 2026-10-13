"""Environment for external tools that process uploaded files.

The web function mounts payment, e-mail and signing secrets as environment
variables. Tools such as pandoc, latexmk and pdflatex run on attacker-supplied
input, so they must not inherit that environment. They get PATH, a HOME inside
their own scratch directory, and a UTF-8 locale. The TeX Live in the image is
configured by /etc/texmf/texmf.d/99-hardening.cnf, not by environment
variables, so nothing else is needed.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin"


def minimal_env(workdir: str | os.PathLike | None = None) -> dict[str, str]:
    """Return a minimal environment for a subprocess that handles user input."""
    path = os.environ.get("PATH") or _DEFAULT_PATH
    home = str(Path(workdir)) if workdir is not None else "/tmp"
    return {"PATH": path, "HOME": home, "LANG": "C.UTF-8"}


def run_pandoc_sandboxed(cmd, *, cwd, timeout, fallback: bool = False):
    """Run pandoc with --sandbox (readers and writers may only read the files
    named on the command line; nothing is fetched over the network).

    *cmd* is the pandoc argv without --sandbox. With *fallback* True, a failed
    sandboxed run is repeated once without it, within the same time budget.
    Use that only for output formats whose writer may need data files the
    sandbox cannot reach, and only when the input has already been checked.
    Raises subprocess.TimeoutExpired like subprocess.run.
    """
    import subprocess
    import time

    deadline = time.monotonic() + timeout
    env = minimal_env(cwd)
    sandboxed = [cmd[0], "--sandbox", *cmd[1:]]
    proc = subprocess.run(
        sandboxed, cwd=cwd, capture_output=True, text=True,
        timeout=timeout, env=env,
    )
    if proc.returncode == 0 or not fallback:
        return proc
    remaining = deadline - time.monotonic()
    if remaining < 5:
        return proc
    return subprocess.run(
        list(cmd), cwd=cwd, capture_output=True, text=True,
        timeout=remaining, env=env,
    )


def run_pandoc_plain(cmd, *, cwd, timeout):
    """Run pandoc WITHOUT --sandbox, with the minimal environment.

    The packaged pandoc on the Modal image cannot reach its own data files in
    sandbox mode (docx and pdf writers fail with "Could not find data file"),
    and its --sandbox does not stop the docx writer embedding a local file named
    by an image path. Callers must therefore remove file references from the
    document tree themselves (see NO_IMAGES_LUA in app.py).
    """
    import subprocess

    return subprocess.run(
        list(cmd), cwd=cwd, capture_output=True, text=True,
        timeout=timeout, env=minimal_env(cwd),
    )
