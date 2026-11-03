#!/bin/bash
# Cost console: rebuild ~/.purplelink/cost-console/{data.json,index.html} from the transcripts on disk (read-only).
# The one on-demand command; the nightly cost-console-refresh task runs it, then publishes index.html.
#   bash scripts/cost_console/run.sh [--days N]
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/parse.py" "$@"
python3 "$here/build_page.py"
