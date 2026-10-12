#!/usr/bin/env bash
cd "$(dirname "$0")"
run() { echo "== $1"; ./cap-v5.sh "$@" 2>&1 | tail -2 | cut -c1-160; }
export RES=1080x1920
V="--hud4 --ui=1.4 --botpad=440 --zoom=0.8"
run v_g1 v $V --scene=g1 --seed=11
run v_a v $V --scene=a --seed=9
run v_g3 v $V --scene=g3 --seed=11
run v_e v $V --scene=e --seed=1
echo BATCHDONE
