#!/bin/bash
# Push the current code to the server and restart the stream (about 20 seconds of dead air, then YouTube reconnects).
#   bash ops/deploy-vps.sh            deploy and restart
#   bash ops/deploy-vps.sh logs       follow the stream log
#   bash ops/deploy-vps.sh status     container state, CPU, steal time
# HOST comes from ~/.config/purplelink/stream-host (one line, e.g. root@203.0.113.7).
set -euo pipefail
HOST=$(head -1 "$HOME/.config/purplelink/stream-host")
cd "$(dirname "$0")/.."
case "${1:-deploy}" in
  logs)   exec ssh "$HOST" 'cd /opt/chiptune-radio && docker compose logs -f --tail 50' ;;
  status) exec ssh "$HOST" 'cd /opt/chiptune-radio && docker compose ps && docker stats --no-stream && top -bn1 | sed -n "3p"' ;;
  deploy)
    rsync -az --delete --exclude 'out*' --exclude __pycache__ --exclude .pytest_cache --exclude stream.env ./ "$HOST:/opt/chiptune-radio/"
    ssh "$HOST" 'cd /opt/chiptune-radio && docker compose up -d --build && docker image prune -f >/dev/null' ;;
esac
