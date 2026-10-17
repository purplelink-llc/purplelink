"""The uptime workflow and its two scripts. Local only: a loopback HTTP server and a fake `gh`."""
import os
import re
import stat
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from common import ROOT, read

SCRIPTS = ROOT / "scripts"


class Handler(BaseHTTPRequestHandler):
    codes = {}

    def do_GET(self):
        self.send_response(Handler.codes.get(self.path, 404))
        self.end_headers()

    def log_message(self, *a):
        pass


class Workflow(unittest.TestCase):
    def setUp(self):
        self.yml = read(".github/workflows/uptime.yml")

    def test_schedule_and_permissions(self):
        self.assertIn('cron: "*/15 * * * *"', self.yml)
        self.assertIn("issues: write", self.yml)
        self.assertNotIn("secrets.", self.yml, "uses only the built-in GITHUB_TOKEN")
        self.assertIn("github.token", self.yml)

    def test_actions_are_pinned_to_a_commit(self):
        for line in self.yml.splitlines():
            m = re.search(r"uses:\s*(\S+)", line)
            if m:
                self.assertRegex(m.group(1), r"@[0-9a-f]{40}$", line)

    def test_checks_cover_everything_asked_for(self):
        checks = read("scripts/uptime-checks.txt")
        for needle in (
            "https://purplelink.llc/|200",
            "/.netlify/functions/health|200",
            "/.netlify/functions/checkout|405",
            "/.netlify/functions/stripe-webhook|405",
            "purplelink-latextools-web.modal.run",
            "purplelink-citation-mcp-web.modal.run/health|200",
        ):
            self.assertIn(needle, checks)
        for line in checks.splitlines():
            if line and not line.startswith("#"):
                self.assertEqual(line.split("|")[1], "GET", "probes never POST or create anything")


class CheckScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_check(self, codes):
        Handler.codes = codes
        with tempfile.TemporaryDirectory() as d:
            checks = Path(d, "checks.txt")
            checks.write_text(
                f"# comment\nhome|GET|http://127.0.0.1:{self.port}/|200\n"
                f"hook|GET|http://127.0.0.1:{self.port}/hook|405\n"
            )
            failed = Path(d, "failed.txt")
            env = dict(os.environ, UPTIME_FAILED_FILE=str(failed), RETRY_DELAY="0", CHECK_TIMEOUT="5")
            r = subprocess.run(["bash", str(SCRIPTS / "uptime_check.sh"), str(checks)], env=env, capture_output=True, text=True)
            return r.returncode, failed.read_text().split()

    def test_all_pass(self):
        self.assertEqual(self.run_check({"/": 200, "/hook": 405}), (0, []))

    def test_unexpected_status_fails_and_names_the_check(self):
        self.assertEqual(self.run_check({"/": 200, "/hook": 500}), (1, ["hook"]))
        self.assertEqual(self.run_check({"/": 503, "/hook": 404}), (1, ["home", "hook"]))

    def test_a_blip_is_forgiven_by_the_retry(self):
        calls = {"n": 0}

        class Flaky(Handler):
            def do_GET(self):
                calls["n"] += 1
                code = 500 if calls["n"] == 1 else 200
                self.send_response(code if self.path == "/" else 405)
                self.end_headers()

        old = self.server.RequestHandlerClass
        self.server.RequestHandlerClass = Flaky
        try:
            self.assertEqual(self.run_check({}), (0, []))
        finally:
            self.server.RequestHandlerClass = old


class IssueScript(unittest.TestCase):
    def run_issue(self, failed, open_issue, body=""):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d, "calls.log")
            gh = Path(d, "gh")
            gh.write_text(
                "#!/usr/bin/env bash\n"
                f'echo "$*" >> "{log}"\n'
                'case "$1 $2" in\n'
                f'  "issue list") echo "{open_issue}" ;;\n'
                f'  "issue view") printf "%s" "{body}" ;;\n'
                "esac\n"
            )
            gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
            ff = Path(d, "failed.txt")
            ff.write_text(failed)
            env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", GITHUB_REPOSITORY="o/r", GITHUB_RUN_ID="1")
            r = subprocess.run(["bash", str(SCRIPTS / "uptime_issue.sh"), str(ff)], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return log.read_text().splitlines()

    def test_failure_opens_one_labelled_issue(self):
        calls = self.run_issue("checkout\nsite-home\n", "")
        create = [c for c in calls if c.startswith("issue create")]
        self.assertEqual(len(create), 1)
        self.assertIn("--label uptime", create[0])
        self.assertIn("checkout,site-home", create[0])

    def test_same_failure_does_not_comment_again(self):
        calls = self.run_issue("checkout\n", "7", "x <!-- failing: checkout -->")
        self.assertFalse([c for c in calls if c.startswith(("issue create", "issue comment", "issue edit"))])

    def test_changed_failure_set_updates_the_open_issue(self):
        calls = self.run_issue("checkout\nsite-home\n", "7", "x <!-- failing: checkout -->")
        self.assertTrue([c for c in calls if c.startswith("issue edit 7")])
        self.assertTrue([c for c in calls if c.startswith("issue comment 7")])
        self.assertFalse([c for c in calls if c.startswith("issue create")])

    def test_recovery_comments_and_closes(self):
        calls = self.run_issue("", "7")
        self.assertTrue([c for c in calls if c.startswith("issue comment 7")])
        self.assertTrue([c for c in calls if c.startswith("issue close 7")])

    def test_healthy_with_no_issue_does_nothing(self):
        calls = self.run_issue("", "")
        self.assertFalse([c for c in calls if c.startswith(("issue create", "issue comment", "issue close"))])


if __name__ == "__main__":
    unittest.main()
