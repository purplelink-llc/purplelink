"""A once-a-minute record of the path to YouTube's ingest server, so that when the stream drops the log can say whether it was our
network or theirs.

Each probe times a DNS lookup and a TCP connect to the ingest host, and reads the container's own TCP retransmit counters. It logs
only what is unusual (a failed or slow probe, a burst of retransmits), one summary line an hour, and, on request, the last few
minutes, which stream.py asks for the moment the pipeline stops:

    network before the drop: last 5 min, 5 probes, 0 failed, connect 3-4 ms, retransmits 0.00%

It makes ordinary short TCP connections to the same host the stream already uses and sends nothing.
"""
from __future__ import annotations

import socket
import threading
import time
from collections import deque
from typing import Callable
from urllib.parse import urlparse

SLOW_MS = 250.0                  # a connect slower than this is worth a line (healthy is 3 ms from this server)
EVERY = 60.0
TIMEOUT = 5.0


def ingest_endpoint(url: str) -> tuple[str, int]:
    """The host and port of an rtmp(s) URL, never the path (the path ends in the stream key)."""
    u = urlparse(url)
    return u.hostname or "a.rtmp.youtube.com", u.port or (443 if u.scheme == "rtmps" else 1935)


def tcp_counters(path: str = "/proc/net/snmp") -> tuple[int, int] | None:
    """(segments sent, segments retransmitted) for this network namespace, or None where /proc has no such file."""
    try:
        rows = [l.split() for l in open(path).read().splitlines() if l.startswith("Tcp:")]
        head, vals = rows[0], rows[1]
        return int(vals[head.index("OutSegs")]), int(vals[head.index("RetransSegs")])
    except (OSError, ValueError, IndexError):
        return None


class NetWatch:
    def __init__(self, host: str, port: int, log: Callable[[str], None] = print, every: float = EVERY):
        self.host, self.port, self.log, self.every = host, port, log, every
        self.samples: deque = deque(maxlen=240)                  # (time, dns_ms, connect_ms or None, error or None, out, retrans)
        self._hour: list = []
        self._last_summary = time.time()

    def probe(self) -> tuple:
        t0 = time.time()
        dns = connect = err = None
        try:
            addr = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)[0][4]
            dns = (time.time() - t0) * 1000
            t1 = time.time()
            with socket.create_connection(addr[:2], timeout=TIMEOUT):
                connect = (time.time() - t1) * 1000
        except OSError as e:
            err = f"{type(e).__name__}: {str(e)[:60]}"
        c = tcp_counters()
        return (time.time(), dns, connect, err, c[0] if c else None, c[1] if c else None)

    def record(self, s: tuple) -> None:
        self.samples.append(s)
        self._hour.append(s)
        _, dns, connect, err, *_ = s
        if err:
            self.log(f"network: probe to {self.host}:{self.port} failed ({err})")
        elif connect is not None and connect > SLOW_MS:
            self.log(f"network: slow connect to {self.host}: {connect:.0f} ms (dns {dns:.0f} ms)")
        if time.time() - self._last_summary >= 3600:
            self.log("network, last hour: " + self.describe(self._hour))
            self._hour, self._last_summary = [], time.time()

    @staticmethod
    def describe(samples) -> str:
        if not samples:
            return "no probes yet"
        ok = [s[2] for s in samples if s[2] is not None]
        failed = len(samples) - len(ok)
        rtt = f"connect {min(ok):.0f}-{max(ok):.0f} ms" if ok else "no successful connect"
        out_d = (samples[-1][4] or 0) - (samples[0][4] or 0)
        re_d = (samples[-1][5] or 0) - (samples[0][5] or 0)
        rt = f", retransmits {100.0 * re_d / out_d:.2f}% of {out_d} segments" if out_d > 0 and samples[0][4] is not None else ""
        return f"{len(samples)} probes, {failed} failed, {rtt}{rt}"

    def summary(self, seconds: float = 300.0) -> str:
        now = time.time()
        recent = [s for s in self.samples if now - s[0] <= seconds]
        return f"last {seconds / 60:.0f} min, " + self.describe(recent)

    def run(self, cancel: threading.Event) -> None:
        while not cancel.is_set():
            try:
                self.record(self.probe())
            except Exception as e:  # noqa: BLE001 - a diagnostic must never be what breaks the stream
                self.log(f"network watch error: {type(e).__name__}")
            if cancel.wait(self.every):
                return
