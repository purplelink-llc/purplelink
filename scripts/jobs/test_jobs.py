#!/usr/bin/env python3
"""Offline tests for the job infrastructure. Run: python3 scripts/jobs/test_jobs.py"""
import json
import os
import plistlib
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import llm_client as L  # noqa: E402
import plist as plist_mod  # noqa: E402
import quarantine as Q  # noqa: E402
import resolver as R  # noqa: E402
import runner  # noqa: E402

SECRET = "sk-test-SECRET-12345"


def oai_body(text="hi", pt=10, ct=5):
    return json.dumps({"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": pt, "completion_tokens": ct}}).encode()


def ant_body(text="hi", pt=10, ct=5):
    return json.dumps({"content": [{"type": "text", "text": text}], "usage": {"input_tokens": pt, "output_tokens": ct}}).encode()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["PURPLELINK_JOBS"] = str(self.tmp)
        os.environ["TEST_KEY"] = SECRET
        self.calls = []
        self._orig = (L._http_post, L._run_cli)
        self.script = []  # queue of behaviors for _http_post

        def fake_post(url, headers, body, timeout):
            self.calls.append((url, headers, json.loads(body)))
            b = self.script.pop(0)
            if isinstance(b, Exception):
                raise b
            return b

        L._http_post = fake_post

    def tearDown(self):
        L._http_post, L._run_cli = self._orig

    def eps(self):
        return [L.Endpoint("local", "openai", "m1", base_url="http://x/v1"),
                L.Endpoint("cloud", "anthropic", "m2", api_key_env="TEST_KEY", price_in_per_m=1.0, price_out_per_m=5.0)]


class TestClient(Base):
    def test_fallback_on_timeout_and_5xx(self):
        for first in (TimeoutError("t"), (503, b"")):
            self.calls.clear()
            self.script = [first, (200, ant_body("ok"))]
            r = L.LLMClient(self.eps(), usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}])
            self.assertTrue(r.fell_back)
            self.assertEqual(r.endpoint, "cloud")
            self.assertEqual(r.text, "ok")

    def test_first_endpoint_no_fallback_flag(self):
        self.script = [(200, oai_body())]
        r = L.LLMClient(self.eps(), usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}])
        self.assertFalse(r.fell_back)
        self.assertEqual(r.cost_usd, 0.0)

    def test_no_retry_on_401(self):
        self.script = [(401, b"{}"), (200, ant_body())]
        with self.assertRaises(L.AuthError):
            L.LLMClient(self.eps(), usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}])
        self.assertEqual(len(self.calls), 1)

    def test_anthropic_request_shape_and_cost(self):
        self.script = [(200, ant_body("a", 1000, 100))]
        c = L.LLMClient([self.eps()[1]], usage_log=self.tmp / "u.jsonl")
        r = c.chat([{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}])
        url, headers, body = self.calls[0]
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(body["system"], "sys")
        self.assertEqual([m["role"] for m in body["messages"]], ["user"])
        self.assertAlmostEqual(r.cost_usd, 0.001 + 0.0005)

    def test_openai_json_schema(self):
        self.script = [(200, oai_body("{}"))]
        L.LLMClient([self.eps()[0]], usage_log=self.tmp / "u.jsonl").chat(
            [{"role": "user", "content": "x"}], json_schema={"type": "object"})
        self.assertEqual(self.calls[0][2]["response_format"]["type"], "json_schema")
        self.assertTrue(self.calls[0][0].endswith("/chat/completions"))

    def test_usage_log_has_no_key(self):
        self.script = [(200, ant_body())]
        log = self.tmp / "u.jsonl"
        c = L.LLMClient([self.eps()[1]], usage_log=log)
        c.job = "j"
        c.chat([{"role": "user", "content": "x"}])
        text = log.read_text()
        self.assertNotIn(SECRET, text)
        rec = json.loads(text.splitlines()[0])
        for k in ("ts", "endpoint", "model", "prompt_tokens", "completion_tokens", "cost_usd", "seconds", "fell_back", "job"):
            self.assertIn(k, rec)

    def test_key_file_mode(self):
        kf = self.tmp / "key"
        kf.write_text(SECRET)
        os.chmod(kf, 0o644)
        ep = L.Endpoint("f", "openai", "m", base_url="http://x", api_key_file=str(kf))
        self.script = [(200, oai_body())]
        with self.assertRaises(L.AuthError):
            L.LLMClient([ep], usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}])
        os.chmod(kf, 0o600)
        r = L.LLMClient([ep], usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}])
        self.assertEqual(self.calls[0][1]["Authorization"], "Bearer " + SECRET)
        self.assertEqual(r.text, "hi")

    def test_claude_cli(self):
        seen = {}

        def fake_cli(cmd, stdin, timeout):
            seen["cmd"], seen["stdin"] = cmd, stdin
            out = {"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.002,
                   "usage": {"input_tokens": 3, "cache_read_input_tokens": 7, "output_tokens": 2}}
            return 0, json.dumps(out), ""

        L._run_cli = fake_cli
        ep = L.Endpoint("cli", "claude-cli", "haiku")
        r = L.LLMClient([ep], usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "hello"}])
        self.assertEqual((r.text, r.prompt_tokens, r.completion_tokens, r.cost_usd), ("ok", 10, 2, 0.002))
        self.assertEqual(seen["stdin"], "hello")
        self.assertIn("--tools", seen["cmd"])

    def test_claude_cli_auth_error_raises(self):
        out = {"is_error": True, "api_error_status": 401, "result": "expired"}
        L._run_cli = lambda c, s, t: (1, json.dumps(out), "")
        with self.assertRaises(L.AuthError):
            L.LLMClient([L.Endpoint("cli", "claude-cli", "haiku")], usage_log=self.tmp / "u.jsonl").chat(
                [{"role": "user", "content": "x"}])

    def test_named_endpoint(self):
        self.script = [(200, ant_body())]
        r = L.LLMClient(self.eps(), usage_log=self.tmp / "u.jsonl").chat([{"role": "user", "content": "x"}], endpoint="cloud")
        self.assertEqual(r.endpoint, "cloud")
        self.assertFalse(r.fell_back)


class TestBudget(unittest.TestCase):
    def res(self, tokens=0, usd=0.0, secs=0.0):
        return L.Result("", "m", "e", tokens, 0, usd, secs, False)

    def test_calls(self):
        b = L.Budget(max_calls=2)
        b.charge(self.res())
        b.charge(self.res())
        with self.assertRaises(L.BudgetExceeded):
            b.check()

    def test_tokens_usd_seconds(self):
        for kw, r in (({"max_tokens": 10}, self.res(tokens=11)), ({"max_usd": 0.1}, self.res(usd=0.2)),
                      ({"max_seconds": 1}, self.res(secs=2))):
            with self.assertRaises(L.BudgetExceeded):
                L.Budget(**kw).charge(r)

    def test_remaining_spent(self):
        b = L.Budget(max_calls=3, max_tokens=100)
        b.charge(self.res(tokens=40))
        self.assertEqual(b.remaining()["calls"], 2)
        self.assertEqual(b.remaining()["tokens"], 60)
        self.assertIsNone(b.remaining()["usd"])
        self.assertEqual(b.spent["tokens"], 40)

    def test_client_charges_and_stops(self):
        tmp = Path(tempfile.mkdtemp())
        L._http_post, orig = (lambda *a: (200, oai_body(pt=60, ct=60))), L._http_post
        try:
            c = L.LLMClient([L.Endpoint("l", "openai", "m", base_url="http://x")], L.Budget(max_tokens=100), tmp / "u.jsonl")
            with self.assertRaises(L.BudgetExceeded):
                c.chat([{"role": "user", "content": "x"}])
            self.assertEqual(len(c.usage_log.read_text().splitlines()), 1)  # the paid call is still logged
            with self.assertRaises(L.BudgetExceeded):
                c.chat([{"role": "user", "content": "x"}])  # refused before calling
        finally:
            L._http_post = orig


class TestLock(unittest.TestCase):
    def test_lock(self):
        tmp = Path(tempfile.mkdtemp())
        a = runner.Lock("j", 100, tmp)
        a.acquire()
        with self.assertRaises(runner.LockHeld):
            runner.Lock("j", 100, tmp).acquire()
        a.release()
        runner.Lock("j", 100, tmp).acquire()

    def test_stale_lock(self):
        tmp = Path(tempfile.mkdtemp())
        a = runner.Lock("j", 5, tmp)
        a.acquire()
        old = time.time() - 60
        os.utime(a.path, (old, old))
        runner.Lock("j", 5, tmp).acquire()  # takes over


class TestQuarantine(unittest.TestCase):
    class Fake:
        def __init__(self, text):
            self.text = text

        def chat(self, messages, **kw):
            self.messages = messages
            return L.Result(self.text, "m", "e", 1, 1, 0, 0, False)

    good = {"title": "T", "summary": "See https://evil.example/x and www.bad.com now", "topics": ["a"],
            "mentions_products": [], "asks_for_action": False, "suspicious": False}

    def test_urls_stripped(self):
        out = Q.quarantine_summarize("raw", self.Fake(json.dumps(self.good)))
        self.assertNotIn("http", out["summary"])
        self.assertNotIn("www", out["summary"])
        self.assertFalse(out["suspicious"])

    def test_validation_failures_default_suspicious(self):
        bad = [
            "not json",
            json.dumps({**self.good, "extra": 1}),
            json.dumps({**self.good, "title": "x" * 121}),
            json.dumps({**self.good, "summary": "x" * 401}),
            json.dumps({**self.good, "topics": ["a"] * 7}),
            json.dumps({**self.good, "asks_for_action": "no"}),
            json.dumps({**self.good, "topics": [1]}),
            json.dumps([1]),
        ]
        for b in bad:
            out = Q.quarantine_summarize("raw", self.Fake(b))
            self.assertTrue(out["suspicious"], b)
            self.assertEqual(out["summary"], "")

    def test_prompt_and_truncation(self):
        f = self.Fake(json.dumps(self.good))
        Q.quarantine_summarize("z" * 10000, f, max_chars=100)
        self.assertIn("no tools", f.messages[0]["content"])
        self.assertLess(len(f.messages[1]["content"]), 200)


class TestResolver(unittest.TestCase):
    def test_urls(self):
        seen = []

        def fetch(url, method, timeout):
            seen.append((url, method))
            if "gone" in url:
                return 404, url, b""
            if "head405" in url and method == "HEAD":
                return 405, url, b""
            if "block" in url:
                return 403, url, b""
            return 200, url + "/final", b""

        out = R.resolve_urls(["https://a.example/x#frag.", "https://gone.example", "https://block.example",
                              "https://head405.example"], fetch=fetch)
        self.assertTrue(out["https://a.example/x#frag."]["ok"])
        self.assertEqual(seen[0][0], "https://a.example/x")
        self.assertFalse(out["https://gone.example"]["ok"])
        self.assertTrue(out["https://block.example"]["ok"])
        self.assertTrue(out["https://head405.example"]["ok"])

    def test_doi_ratio(self):
        body = json.dumps({"message": {"title": ["Deep Learning for Phishing Detection in Email"]}}).encode()
        fetch = lambda u, m, t: (200, u, body)
        good = R.check_doi("10.1/x", "Deep learning for phishing detection", fetch)
        self.assertTrue(good["match"])
        bad = R.check_doi("10.1/x", "Quantum gravity of bees", fetch)
        self.assertFalse(bad["match"])
        self.assertEqual(bad["real_title"], "Deep Learning for Phishing Detection in Email")
        self.assertFalse(R.check_doi("10.1/x", "t", lambda u, m, t: (404, u, b""))["exists"])

    def test_citation_list(self):
        body = json.dumps({"message": {"title": ["Real Title Here"]}}).encode()
        out = R.resolve_citation_list([{"doi": "10.1/x", "title": "Real Title Here"},
                                       {"doi": "10.1/x", "title": "Totally different words"}],
                                      fetch=lambda u, m, t: (200, u, body))
        self.assertEqual([r["verified"] for r in out], [True, False])


class TestPlist(unittest.TestCase):
    spec = {"name": "demo", "schedule": {"hour": 7, "minute": 5, "weekdays": [1, 7]}}

    def test_content(self):
        tmp = Path(tempfile.mkdtemp())
        p = plist_mod.write_plist(self.spec, tmp, jobs=tmp)
        d = plistlib.loads(p.read_bytes())
        self.assertEqual(d["Label"], "llc.purplelink.job.demo")
        self.assertEqual(d["ProgramArguments"][:3], ["/usr/bin/env", "python3", d["ProgramArguments"][2]])
        self.assertEqual(d["ProgramArguments"][-2:], ["run", "demo"])
        self.assertEqual(d["StartCalendarInterval"], [{"Hour": 7, "Minute": 5, "Weekday": 1},
                                                      {"Hour": 7, "Minute": 5, "Weekday": 0}])
        self.assertIn("PURPLELINK_JOBS", d["EnvironmentVariables"])
        self.assertNotIn("UserName", d)
        self.assertTrue(d["StandardOutPath"].startswith(str(tmp)))

    def test_daemon(self):
        d = plist_mod.build_plist(self.spec, daemon=True, user="ben")
        self.assertEqual(d["UserName"], "ben")


class TestRunner(Base):
    def make_root(self, writes_queue, body):
        root = self.tmp / "jobsroot"
        (root / "t").mkdir(parents=True)
        (root / "t" / "job.json").write_text(json.dumps({
            "name": "t", "schedule": {"hour": 1, "minute": 0}, "endpoints": ["local"],
            "budget": {"max_calls": 5, "max_seconds": 30}, "writes_queue": writes_queue}))
        (root / "t" / "run.py").write_text(body)
        return root

    def client(self):
        return L.LLMClient([L.Endpoint("local", "openai", "m", base_url="http://x")], usage_log=self.tmp / "usage.jsonl")

    def summary(self):
        f = sorted((self.tmp / "runs" / "t").glob("*.jsonl"))[-1]
        return json.loads(f.read_text().splitlines()[-1])

    def test_queue_refused_when_not_allowed(self):
        root = self.make_root(False, "def run(ctx):\n    ctx.queue_new('x')\n")
        self.assertEqual(runner.run_job("t", root=root, client=self.client()), 3)
        f = next((self.tmp / "runs" / "t").glob("*.jsonl")).read_text()
        self.assertIn("writes_queue false", f)

    def test_queue_allowed_uses_cli(self):
        root = self.make_root(True, "def run(ctx):\n    print(ctx.queue_new('x'))\n")
        fake = self.tmp / "fakeq.py"
        fake.write_text("import sys\nprint('created ' + sys.argv[1] + ' ' + sys.argv[2])\n")
        orig, runner.QUEUE_CLI = runner.QUEUE_CLI, fake
        try:
            self.assertEqual(runner.run_job("t", root=root, client=self.client()), 0)
        finally:
            runner.QUEUE_CLI = orig
        self.assertEqual(self.summary()["queue_items"], 1)

    def test_budget_stop_exit_2_keeps_partial(self):
        self.script = [(200, oai_body(pt=100, ct=100))]
        root = self.make_root(False, "def run(ctx):\n    ctx.log('partial', n=1)\n"
                                     "    ctx.client.chat([{'role':'user','content':'x'}])\n    ctx.log('never')\n")
        c = self.client()
        job = json.loads((root / "t" / "job.json").read_text())
        job["budget"]["max_tokens"] = 50
        (root / "t" / "job.json").write_text(json.dumps(job))
        self.assertEqual(runner.run_job("t", root=root, client=c), 2)
        text = next((self.tmp / "runs" / "t").glob("*.jsonl")).read_text()
        self.assertIn("partial", text)
        self.assertNotIn("never", text)
        self.assertEqual(self.summary()["status"], "budget_stop")
        self.assertIn('"job": "t"', (self.tmp / "usage.jsonl").read_text())

    def test_lock_blocks_second_run(self):
        root = self.make_root(False, "def run(ctx):\n    pass\n")
        lock = runner.Lock("t", 30)
        lock.acquire()
        self.assertEqual(runner.run_job("t", root=root, client=self.client()), 3)
        lock.release()
        self.assertEqual(runner.run_job("t", root=root, client=self.client()), 0)

    def test_example_job_dry_run(self):
        self.assertEqual(runner.run_job("example_job", dry_run=True, client=self.client()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
