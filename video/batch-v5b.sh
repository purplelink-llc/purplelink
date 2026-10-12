#!/usr/bin/env bash
cd "$(dirname "$0")"
A="--hud4 --ui=1.7"
run() { echo "== $1"; ./cap-v5.sh "$@" 2>&1 | tail -2 | cut -c1-160; }
run t_a v $A --scene=a --seed=3 --biome=snow --wx=winter
run t_c v $A --scene=c --seed=5 --biome=ruins --wx=none
run t_d v $A --scene=d --seed=3 --biome=desert --wx=none
run t_e v $A --scene=e --seed=2 --biome=desert --wx=none
run t_f v $A --scene=f --seed=6 --biome=grassland --wx=fog
echo BATCHDONE
