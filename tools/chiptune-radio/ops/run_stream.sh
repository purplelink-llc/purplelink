#!/bin/bash
# Starts the live stream. The RTMP URL with the stream key lives in ~/.config/purplelink/stream.env as STREAM_URL=rtmp://...
# (chmod 600). The key is never printed or logged.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . "$HOME/.config/purplelink/stream.env"; set +a
exec python3.12 stream.py --live
