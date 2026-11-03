"""scripts/fingerprint_assets.py: the committed pages are bare, the build stamps them (docs/designs/generated-files-at-build.md,
phase 2). CI stamps its checkout before the tests, so there the tree must be fully stamped; locally it must be bare."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from common import IN_CI, ROOT, SITE

SCRIPT = ROOT / "scripts" / "fingerprint_assets.py"
# What the stamper reads or rewrites: pages, stylesheets, scripts and the logo files. Images, video and fonts are left out
# of the copy; no stamp points at them.
KEEP = (".html", ".css", ".js", ".mjs", ".svg", ".png")


def run(root: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("CI", "NETLIFY")}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(root / "scripts" / "fingerprint_assets.py"), *args], cwd=root,
                          capture_output=True, text=True, timeout=120, env=env)


class Fingerprints(unittest.TestCase):
    def test_tree_is_in_the_expected_state(self):
        mode = "--check" if IN_CI else "--check-bare"
        r = run(ROOT, mode, env_extra={"CI": "true"} if IN_CI else None)
        self.assertEqual(r.returncode, 0, f"{mode} failed\n" + r.stdout + r.stderr)


class Modes(unittest.TestCase):
    """The modes, on a throwaway copy of site/, so the checkout is never written."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        (cls.root / "scripts").mkdir()
        shutil.copy2(SCRIPT, cls.root / "scripts" / SCRIPT.name)

        def ignore(d, names):
            return [n for n in names if (Path(d) / n).is_file() and not n.endswith(KEEP)]
        shutil.copytree(SITE, cls.root / "site", ignore=ignore)
        if IN_CI:  # CI stamped the checkout first; the copy starts from the committed, bare form
            r = run(cls.root, "--strip")
            assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def snapshot(self) -> dict:
        site = self.root / "site"
        return {p.relative_to(site).as_posix(): p.read_bytes()
                for p in site.rglob("*") if p.is_file() and p.suffix in (".html", ".css")}

    def test_refuses_to_stamp_a_working_tree(self):
        before = self.snapshot()
        r = run(self.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--force-in-place", r.stderr)
        self.assertEqual(self.snapshot(), before, "the refusal must not write anything")

    def test_round_trip_and_check_bare(self):
        bare = self.snapshot()
        self.assertEqual(run(self.root, "--check-bare").returncode, 0)
        self.assertEqual(run(self.root, "--check").returncode, 1, "a bare tree is not a built tree")

        r = run(self.root, env_extra={"NETLIFY": "true"})
        self.assertEqual(r.returncode, 0, r.stderr)
        stamped = self.snapshot()
        self.assertNotEqual(stamped, bare)
        self.assertEqual(run(self.root, "--check").returncode, 0)
        r = run(self.root, "--check-bare")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--strip", r.stderr)
        self.assertEqual(run(self.root, "site/styles.css", "--check-bare").returncode, 1, "styles.css carries logo stamps")

        self.assertEqual(run(self.root, "--force-in-place").returncode, 0)
        self.assertEqual(self.snapshot(), stamped, "stamping is idempotent")

        self.assertEqual(run(self.root, "--strip").returncode, 0)
        self.assertEqual(self.snapshot(), bare, "strip then stamp then strip gives back the committed bytes")

    def test_strip_leaves_other_queries_alone(self):
        page = self.root / "site" / "_strip_case.html"
        text = ('<a href="https://www.youtube.com/watch?v=b5iFfo1E_lY">x</a>\n'
                '<script src="/site.js?v=0123456789"></script>\n'
                '<link rel="stylesheet" href="/styles.css?theme=dark">\n')
        page.write_text(text)
        try:
            self.assertEqual(run(self.root, "site/_strip_case.html", "--check-bare").returncode, 1)
            run(self.root, "--strip")
            self.assertEqual(page.read_text(), text.replace("/site.js?v=0123456789", "/site.js"))
        finally:
            page.unlink()


if __name__ == "__main__":
    unittest.main()
