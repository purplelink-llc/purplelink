#!/usr/bin/env bash
cd "$(dirname "$0")"
export WDOG=300 RES=1024x1790
V="--hud4 --ui=1.4 --win=1024x1790 --botpad=480 --zoom=1.7"
run() { echo "== $1"; ./cap-v5.sh "$@" 2>&1 | tail -1 | cut -c1-60; }
run v2_g1 v $V --scene=g1 --seed=11
run v2_g3 v $V --scene=g3 --seed=11
run v2_a v $V --scene=a --seed=9
echo BATCHDONE
