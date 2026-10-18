"""One thin HTTP layer so adapters can be tested with a fake. Uses urllib only."""
from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Resp:
    status: int
    body: bytes = b""
    headers: dict | None = None

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8") or "null")
        except (ValueError, UnicodeDecodeError):
            return None

    def header(self, name: str, default: str = "") -> str:
        for k, v in (self.headers or {}).items():
            if k.lower() == name.lower():
                return str(v)
        return default

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----plsocial" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (fname, data, ctype) in files.items():
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n").encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class Http:
    """request(method, url, headers=None, json_body=None, form=None, data=None) -> Resp. Never raises on HTTP errors."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict | None = None, json_body=None,
                form: dict | None = None, data: bytes | None = None) -> Resp:
        h = dict(headers or {})
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            h.setdefault("Content-Type", "application/json")
        elif form is not None:
            from urllib.parse import urlencode
            body = urlencode(form).encode()
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        h.setdefault("User-Agent", "purplelink-social/1.0 (+https://purplelink.llc)")
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return Resp(r.status, r.read(), dict(r.headers))
        except urllib.error.HTTPError as e:
            return Resp(e.code, e.read() or b"", dict(e.headers or {}))
        except (urllib.error.URLError, TimeoutError, OSError):
            return Resp(0, b"")
