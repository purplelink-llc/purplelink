#!/usr/bin/env python3
"""Cost console page: inline data.json into page.html and write one self-contained index.html.

  build_page.py [--data PATH] [--out PATH]

The page holds session titles and short tool previews, so it is written mode 0600 next to the data, outside the
repo, and published only as a private artifact.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.expanduser("~"), ".purplelink", "cost-console")
MAX_BYTES = 8_000_000  # the Artifact limit is 16 MB; stay well under it


def render(data):
    with open(os.path.join(HERE, "page.html")) as fh:
        template = fh.read()
    # "</" inside the JSON would end the <script> element early
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    if "/*__DATA__*/" not in template:
        raise SystemExit("page.html has lost its /*__DATA__*/ placeholder")
    return template.replace("/*__DATA__*/", blob)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=os.path.join(OUT_DIR, "data.json"))
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "index.html"))
    a = ap.parse_args(argv)
    with open(a.data) as fh:
        html = render(json.load(fh))
    size = len(html.encode())
    if size > MAX_BYTES:
        print(f"page is {size / 1e6:.1f} MB, over the {MAX_BYTES / 1e6:.0f} MB budget; lower REPLAY_TOP in parse.py",
              file=sys.stderr)
        return 1
    tmp = a.out + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(html)
    os.replace(tmp, a.out)
    print(f"page: {a.out} ({size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
