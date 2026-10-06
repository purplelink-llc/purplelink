#!/bin/bash
# Put the Purplelink live-broadcast token on the server so broadcast.py can open each new broadcast.
#   bash ops/push-live-token.sh
# Reads the OAuth token (scope youtube.force-ssl, made with the consent flow for the Purplelink channel)
# from ~/.tiktok_pipeline/youtube_live_purplelink.json and writes it as one line, YT_LIVE_TOKEN_JSON='{...}',
# into /opt/chiptune-radio/stream.env on the server (chmod 600, replacing any earlier copy). The token travels
# over SSH on stdin and is never printed. Run ops/deploy-vps.sh afterwards to restart the stream with it.
# HOST comes from ~/.config/purplelink/stream-host (one line, root@<ip>).
set -euo pipefail
HOST=$(head -1 "$HOME/.config/purplelink/stream-host")
KEY="$HOME/.ssh/chiptune_radio_ed25519"
TOKEN="${YT_LIVE_TOKEN_FILE:-$HOME/.tiktok_pipeline/youtube_live_purplelink.json}"
[ -r "$TOKEN" ] || { echo "no token at $TOKEN" >&2; exit 1; }
python3 - "$TOKEN" <<'PY' | ssh -i "$KEY" -o IdentitiesOnly=yes "$HOST" \
  'cd /opt/chiptune-radio && umask 077 && { grep -v "^YT_LIVE_TOKEN_JSON=" stream.env > stream.env.new; cat >> stream.env.new; mv stream.env.new stream.env; chmod 600 stream.env; } && echo "stream.env updated: $(wc -l < stream.env) lines, mode $(stat -c %a stream.env), keys: $(cut -d= -f1 stream.env | tr "\n" " ")"'
import json, sys
t = json.load(open(sys.argv[1]))
print("YT_LIVE_TOKEN_JSON='" + json.dumps(t, separators=(",", ":")) + "'")
PY
