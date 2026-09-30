#!/usr/bin/env python3
"""LLM client for Purplelink jobs: ordered endpoints, fallback, budget, usage log.

Kinds: "openai" (OpenAI-compatible, incl. llama.cpp server), "anthropic" (Messages
API), "claude-cli" (headless `claude -p`, tools disabled). Stdlib only.

Fallback rule: timeout, connection error, HTTP 5xx and 429 move to the next
endpoint and set fell_back=True. Other 4xx (bad key, bad request) raise
AuthError immediately and are never retried. Keys are read from an env var or a
mode-600 file and are never logged or printed.
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"  # value documented at platform.claude.com/docs/en/api/versioning


def jobs_dir() -> Path:
    return Path(os.environ.get("PURPLELINK_JOBS") or Path.home() / ".purplelink" / "jobs")


@dataclass
class Endpoint:
    name: str
    kind: str  # "openai" | "anthropic" | "claude-cli"
    model: str
    base_url: str = ""
    api_key_env: str = ""
    api_key_file: str = ""
    timeout: int = 120
    price_in_per_m: float = 0.0
    price_out_per_m: float = 0.0


@dataclass
class Result:
    text: str
    model: str
    endpoint: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    seconds: float
    fell_back: bool


class BudgetExceeded(Exception):
    pass


class LLMError(Exception):
    """Every endpoint failed with a retryable error."""


class AuthError(LLMError):
    """A 4xx response: do not retry, do not fall back."""


class _Retryable(Exception):
    pass


class Budget:
    def __init__(self, max_calls=None, max_tokens=None, max_usd=None, max_seconds=None):
        self.max = {"calls": max_calls, "tokens": max_tokens, "usd": max_usd, "seconds": max_seconds}
        self.spent = {"calls": 0, "tokens": 0, "usd": 0.0, "seconds": 0.0}

    def _over(self) -> str | None:
        for k, limit in self.max.items():
            if limit is None:
                continue
            if k == "calls" and self.spent[k] >= limit:
                return k
            if k != "calls" and self.spent[k] > limit:
                return k
        return None

    def check(self) -> None:
        """Refuse a new call once calls are used up or any other limit is passed."""
        k = self._over()
        if k:
            raise BudgetExceeded(f"{k} budget reached ({self.spent[k]} of {self.max[k]})")

    def charge(self, result: Result) -> None:
        self.spent["calls"] += 1
        self.spent["tokens"] += result.prompt_tokens + result.completion_tokens
        self.spent["usd"] += result.cost_usd
        self.spent["seconds"] += result.seconds
        for k, limit in self.max.items():
            if limit is not None and self.spent[k] > limit:
                raise BudgetExceeded(f"{k} budget exceeded ({self.spent[k]} of {limit})")

    def remaining(self) -> dict:
        return {k: (None if lim is None else lim - self.spent[k]) for k, lim in self.max.items()}


# ---------------------------------------------------------------- transport
def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi; fall back to the system store."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _http_post(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, bytes]:
    """Return (status, body). Raises OSError-family on connection problems."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _run_cli(cmd: list[str], stdin: str, timeout: float) -> tuple[int, str, str]:
    """Run the claude CLI in an empty temp dir. Returns (returncode, stdout, stderr)."""
    with tempfile.TemporaryDirectory(prefix="pl-claude-") as cwd:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def _read_key(ep: Endpoint) -> str:
    if ep.api_key_env and os.environ.get(ep.api_key_env):
        return os.environ[ep.api_key_env].strip()
    if ep.api_key_file:
        p = Path(ep.api_key_file).expanduser()
        if not p.exists():
            raise AuthError(f"{ep.name}: key file missing")
        if p.stat().st_mode & 0o077:
            raise AuthError(f"{ep.name}: key file must be mode 600")
        return p.read_text().strip().splitlines()[0].strip()
    if ep.kind == "openai" and not (ep.api_key_env or ep.api_key_file):
        return ""  # local server without auth
    raise AuthError(f"{ep.name}: no key found (env var or key file)")


def _cost(ep: Endpoint, pt: int, ct: int) -> float:
    return pt * ep.price_in_per_m / 1e6 + ct * ep.price_out_per_m / 1e6


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    return system, [m for m in messages if m.get("role") != "system"]


def _schema_note(schema: dict) -> str:
    return "Reply with JSON only, matching this JSON schema:\n" + json.dumps(schema)


def _check_status(ep: Endpoint, status: int, body: bytes) -> None:
    if status >= 500 or status == 429:
        raise _Retryable(f"HTTP {status}")
    if status >= 400:
        raise AuthError(f"{ep.name}: HTTP {status}")


class LLMClient:
    def __init__(self, endpoints: list[Endpoint], budget: Budget | None = None, usage_log: Path | None = None):
        self.endpoints = list(endpoints)
        self.budget = budget
        self.usage_log = Path(usage_log) if usage_log else jobs_dir() / "usage.jsonl"
        self.job: str | None = None

    # -- per kind
    def _call_openai(self, ep, messages, json_schema, max_tokens, temperature):
        headers = {"Content-Type": "application/json"}
        key = _read_key(ep)
        if key:
            headers["Authorization"] = "Bearer " + key
        payload = {"model": ep.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if json_schema:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "output", "strict": True, "schema": json_schema}}
        url = ep.base_url.rstrip("/") + "/chat/completions"
        status, raw = _http_post(url, headers, json.dumps(payload).encode(), ep.timeout)
        _check_status(ep, status, raw)
        data = json.loads(raw)
        text = data["choices"][0]["message"].get("content") or ""
        u = data.get("usage") or {}
        return text, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), None

    def _call_anthropic(self, ep, messages, json_schema, max_tokens, temperature):
        key = _read_key(ep)
        headers = {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
        system, rest = _split_system(messages)
        if json_schema:
            system = (system + "\n\n" if system else "") + _schema_note(json_schema)
        payload = {"model": ep.model, "messages": rest, "max_tokens": max_tokens, "temperature": temperature}
        if system:
            payload["system"] = system
        status, raw = _http_post(ANTHROPIC_URL, headers, json.dumps(payload).encode(), ep.timeout)
        _check_status(ep, status, raw)
        data = json.loads(raw)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage") or {}
        pt = int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0) or 0) \
            + int(u.get("cache_read_input_tokens", 0) or 0)
        return text, pt, int(u.get("output_tokens", 0)), None

    def _call_cli(self, ep, messages, json_schema, max_tokens, temperature):
        # The CLI has no max_tokens or temperature flag; both are ignored here.
        system, rest = _split_system(messages)
        if json_schema:
            system = (system + "\n\n" if system else "") + _schema_note(json_schema)
        prompt = "\n\n".join(m["content"] if len(rest) == 1 else f"{m['role']}: {m['content']}" for m in rest)
        cmd = ["claude", "-p", "--model", ep.model, "--output-format", "json",
               "--tools", "", "--no-session-persistence"]
        if system:
            cmd += ["--system-prompt", system]
        try:
            rc, out, err = _run_cli(cmd, prompt, ep.timeout)
        except subprocess.TimeoutExpired as exc:
            raise _Retryable("claude-cli timeout") from exc
        except FileNotFoundError as exc:
            raise _Retryable("claude CLI not found") from exc
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            raise _Retryable(f"claude-cli bad output (exit {rc})")
        if data.get("is_error") or rc != 0:
            code = data.get("api_error_status")
            if isinstance(code, int) and 400 <= code < 500 and code != 429:
                raise AuthError(f"{ep.name}: claude-cli HTTP {code}")
            raise _Retryable(f"claude-cli error (exit {rc})")
        u = data.get("usage") or {}
        pt = int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0) or 0) \
            + int(u.get("cache_read_input_tokens", 0) or 0)
        cost = data.get("total_cost_usd")
        return str(data.get("result", "")), pt, int(u.get("output_tokens", 0)), cost

    _KINDS = {"openai": "_call_openai", "anthropic": "_call_anthropic", "claude-cli": "_call_cli"}

    def chat(self, messages: list[dict], *, json_schema: dict | None = None, max_tokens: int = 1024,
             temperature: float = 0.2, endpoint: str | None = None) -> Result:
        if self.budget:
            self.budget.check()
        eps = [e for e in self.endpoints if endpoint is None or e.name == endpoint]
        if not eps:
            raise LLMError(f"no endpoint named {endpoint!r}" if endpoint else "no endpoints configured")
        last: Exception | None = None
        for i, ep in enumerate(eps):
            method = self._KINDS.get(ep.kind)
            if not method:
                raise LLMError(f"{ep.name}: unknown kind {ep.kind!r}")
            t0 = time.monotonic()
            try:
                text, pt, ct, cost = getattr(self, method)(ep, messages, json_schema, max_tokens, temperature)
            except _Retryable as exc:
                last = exc
                continue
            except (OSError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
                # OSError covers URLError, timeouts and connection resets.
                last = exc
                continue
            secs = time.monotonic() - t0
            if cost is None:
                cost = _cost(ep, pt, ct)
            res = Result(text, ep.model, ep.name, pt, ct, float(cost), secs, i > 0)
            self._log(res)
            if self.budget:
                self.budget.charge(res)
            return res
        raise LLMError(f"all endpoints failed: {type(last).__name__}: {last}")

    def _log(self, r: Result) -> None:
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "endpoint": r.endpoint, "model": r.model,
                "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                "cost_usd": round(r.cost_usd, 6), "seconds": round(r.seconds, 3), "fell_back": r.fell_back}
        if self.job:
            line["job"] = self.job
        try:
            self.usage_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.usage_log, "a") as f:
                f.write(json.dumps(line) + "\n")
        except OSError:
            pass  # a full disk must not lose a paid result


def load_endpoints(path: Path | None = None) -> list[Endpoint]:
    p = Path(path) if path else jobs_dir() / "endpoints.json"
    data = json.loads(p.read_text())
    items = data["endpoints"] if isinstance(data, dict) else data
    fields = {f.name for f in dataclasses.fields(Endpoint)}
    return [Endpoint(**{k: v for k, v in it.items() if k in fields}) for it in items]
