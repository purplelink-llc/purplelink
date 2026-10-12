#!/usr/bin/env bash
cd "$(dirname "$0")"
A="--hud4 --ui=1.5"
run() { echo "== $1"; ./cap-v4.sh "$@" 2>&1 | tail -2; }
run k_aim h_aim $A
run k_flank h_flankkill $A
run k_cover h_cover $A
run k_combo h_combo $A
run k_ow h_ow $A
run k_fog h_fog $A --keep=weather
run k_strike h_strike $A
run k_titan h_titan $A --keep=unit
run k_massive h_massive $A
run k_spoils h_spoils $A
run k_hub h_hub --ui=1.5
run k_snow_flank h_flankkill $A --biome=snow --seed=7
run k_desert_combo h_combo $A --biome=desert --seed=9
run k_ruins_cover h_cover $A --biome=ruins --seed=11
run k_snow_ow h_ow_snow $A
run k_desert_aim h_aim $A --biome=desert --seed=9
run k_ruins_aim h_aim $A --biome=ruins --seed=13
echo BATCHDONE
