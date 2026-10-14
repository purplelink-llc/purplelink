#!/usr/bin/env bash
cd "$(dirname "$0")"
A="--hud4 --ui=1.7"
run() { echo "== $1"; ./cap-v5.sh "$@" 2>&1 | tail -2 | cut -c1-160; }
run s_b v $A --scene=b --seed=1
V="--hud4 --ui=1.4 --botpad=440"
export RES=1080x1920
run v_g1 v $V --scene=g1 --seed=11
echo BATCHDONE
