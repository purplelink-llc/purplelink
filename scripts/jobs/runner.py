#!/usr/bin/env python3
"""Job runner: python3 runner.py run JOB [--dry-run] | list | plist JOB [--daemon] [--out DIR]

A job is jobs/<name>/job.json plus run.py exposing run(ctx). The runner gives it
an LLM client with the job's budget, a run log, a queue writer that shells out to
approval_queue.py, the resolver and the quarantine module. Exit codes: 0 ok,
2 budget or wall-clock stop, 3 error or lock held.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import llm_client  # noqa: E402
import quarantine  # noqa: E402
import resolver  # noqa: E402
from llm_client import Budget, BudgetExceeded, LLMClient, jobs_dir  # noqa: E402

JOBS_ROOT = HERE / "jobs"
QUEUE_CLI = HERE.parent / "queue" / "approval_queue.py"
DEFAULT_WALL = 600


class WallClockExceeded(Exception):
    pass


class LockHeld(Exception):
    pass


def load_spec(name: str, root: Path | None = None) -> dict:
    spec = json.loads(((root or JOBS_ROOT) / name / "job.json").read_text())
    for k in ("name", "schedule", "budget", "endpoints"):
        if k not in spec:
            raise ValueError(f"job.json missing {k!r}")
    spec.setdefault("writes_queue", False)
    return spec


class Lock:
    """One instance per job. A lock older than max_seconds is stale and taken over."""

    def __init__(self, name: str, max_seconds: float, base: Path | None = None):
        self.path = (base or jobs_dir()) / "locks" / f"{name}.lock"
        self.max_seconds = max_seconds

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                age = time.time() - self.path.stat().st_mtime
                if age > self.max_seconds:
                    self.path.unlink(missing_ok=True)
                    continue
                raise LockHeld(f"{self.path.name} held for {int(age)}s")
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
            return
        raise LockHeld("could not take lock")

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


class RunLog:
    def __init__(self, name: str, base: Path | None = None):
        d = (base or jobs_dir()) / "runs" / name
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / (time.strftime("%Y%m%dT%H%M%S") + ".jsonl")

    def __call__(self, event: str, **fields) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")


def run_job(name: str, dry_run: bool = False, *, client=None, root: Path | None = None,
            base: Path | None = None) -> int:
    spec = load_spec(name, root)
    budget_spec = spec["budget"]
    wall = int(budget_spec.get("max_seconds") or DEFAULT_WALL)
    log = RunLog(name, base)
    lock = Lock(name, wall, base)
    try:
        lock.acquire()
    except LockHeld as exc:
        log("error", error=str(exc))
        print(f"{name}: {exc}", file=sys.stderr)
        return 3

    budget = Budget(**{k: budget_spec.get(k) for k in ("max_calls", "max_tokens", "max_usd", "max_seconds")})
    if client is None:
        try:
            by_name = {e.name: e for e in llm_client.load_endpoints()}
        except (OSError, ValueError, TypeError) as exc:
            log("error", error=f"cannot load endpoints.json: {type(exc).__name__}")
            print(f"{name}: cannot load endpoints.json", file=sys.stderr)
            lock.release()
            return 3
        eps = [by_name[n] for n in spec["endpoints"] if n in by_name]
        client = LLMClient(eps, budget, (base or jobs_dir()) / "usage.jsonl")
    else:
        client.budget = budget
    client.job = name
    queued = []

    def queue_new(markdown_text: str):
        if not spec["writes_queue"]:
            raise PermissionError(f"job {name} has writes_queue false")
        if dry_run:
            log("queue_new_skipped", reason="dry_run")
            return "dry-run: not created", 0
        p = subprocess.run([sys.executable, str(QUEUE_CLI), "new", "-"], input=markdown_text,
                           capture_output=True, text=True, timeout=60)
        out = (p.stdout + p.stderr).strip()
        log("queue_new", status=p.returncode, output=out[:500])
        if p.returncode == 0:
            queued.append(out)
        return out, p.returncode

    ctx = SimpleNamespace(client=client, log=log, queue_new=queue_new, resolver=resolver,
                          quarantine=quarantine, dry_run=dry_run, job=spec)

    def on_alarm(signum, frame):
        raise WallClockExceeded()

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(wall)
    t0 = time.monotonic()
    code, status = 0, "ok"
    log("start", job=name, dry_run=dry_run)
    try:
        mod_spec = importlib.util.spec_from_file_location(f"job_{name}", (root or JOBS_ROOT) / name / "run.py")
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
        mod.run(ctx)
    except BudgetExceeded as exc:
        code, status = 2, "budget_stop"
        log("budget_stop", reason=str(exc), note="partial results kept")
    except WallClockExceeded:
        code, status = 2, "wall_clock_stop"
        log("wall_clock_stop", max_seconds=wall)
    except Exception as exc:  # any job failure is logged, never raised past the runner
        code, status = 3, "error"
        log("error", error=f"{type(exc).__name__}: {exc}")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        lock.release()
    s = budget.spent
    log("summary", status=status, calls=s["calls"], tokens=s["tokens"], cost_usd=round(s["usd"], 6),
        seconds=round(time.monotonic() - t0, 2), queue_items=len(queued))
    print(f"{name}: {status} (calls={s['calls']} tokens={s['tokens']} queue_items={len(queued)}) log={log.path}")
    return code


def cmd_list(root: Path | None = None) -> int:
    for d in sorted((root or JOBS_ROOT).iterdir()):
        if (d / "job.json").exists():
            spec = load_spec(d.name, root)
            print(f"{spec['name']}\t{spec['schedule']}\t{spec.get('description', '')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("job")
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("list")
    p = sub.add_parser("plist")
    p.add_argument("job")
    p.add_argument("--daemon", action="store_true")
    p.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return run_job(a.job, a.dry_run)
    if a.cmd == "list":
        return cmd_list()
    import plist
    args = [a.job] + (["--daemon"] if a.daemon else []) + (["--out", a.out] if a.out else [])
    return plist.main(args)


if __name__ == "__main__":
    sys.exit(main())
