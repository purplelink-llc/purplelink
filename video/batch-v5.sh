#!/usr/bin/env bash
cd "$(dirname "$0")"
A="--hud4 --ui=1.7"
run() { echo "== $1"; ./cap-v5.sh "$@" 2>&1 | tail -2 | cut -c1-160; }

run s_a v $A --scene=a --seed=9
run s_c v $A --scene=c --seed=1
run s_d v $A --scene=d --seed=16
run s_b v $A --scene=b --seed=1
run s_f v $A --scene=f --seed=13
run s_e v $A --scene=e --seed=1
run s_g1 v $A --scene=g1 --seed=11
run s_g3 v $A --scene=g3 --seed=11
echo BATCHDONE
