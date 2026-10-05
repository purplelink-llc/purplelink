#!/bin/bash
# One-time setup on a fresh Ubuntu 24.04 VPS (run as root): installs Docker, copies nothing secret.
# Then, from your Mac:  rsync -av --exclude 'out*' --exclude __pycache__ tools/chiptune-radio/ root@HOST:/opt/chiptune-radio/
# and on the server:    cd /opt/chiptune-radio && printf 'STREAM_URL=%s\n' 'rtmp://a.rtmp.youtube.com/live2/KEY' > stream.env && chmod 600 stream.env && docker compose up -d --build
set -euo pipefail
apt-get update && apt-get install -y docker.io docker-compose-v2 rsync ufw
ufw allow OpenSSH && ufw --force enable
mkdir -p /opt/chiptune-radio
