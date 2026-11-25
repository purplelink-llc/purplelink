#!/usr/bin/env bash
# RubbleFront trailer v6: capture every clip from the current game (after the 2026-11 redesigns).
# 16:9 runs pass --win=1920x1080: on the built-in display alone the window is squeezed to 1280x1440 unless it is resized in code.
set -u
cd "$(dirname "$0")"
export WDOG=420
A="--hud4 --ui=1.35 --win=1920x1080"
run() { echo "== $1"; ./cap-v6.sh "$@" 2>&1 | tail -1 | cut -c1-60; }
run o_a v $A --scene=a --seed=9 --blast
run s_a v $A --scene=a --seed=9
run s_b v $A --scene=b --seed=1
run s_c v $A --scene=c --seed=1
run s_d v $A --scene=d --seed=16
run s_e v $A --scene=e --seed=1
run s_f v $A --scene=f --seed=13
run s_g1 v $A --scene=g1 --seed=11
run s_g3 v $A --scene=g3 --seed=11
run t_a v $A --scene=a --seed=3 --biome=snow --wx=winter
run t_c v $A --scene=c --seed=5 --biome=ruins --wx=none
run t_d v $A --scene=d --seed=3 --biome=desert --wx=none
run t_e v $A --scene=e --seed=2 --biome=desert --wx=none
run t_f v $A --scene=f --seed=6 --biome=grassland --wx=fog
run k_spoils h_spoils $A
run k_hub h_hub --ui=1.35 --win=1920x1080
run h_runmap h_runmap $A
run k_massive h_massive $A
run k_strike h_strike $A
run k_combo h_combo $A
run k_desert_combo h_combo $A --biome=desert --seed=9
run k_snow_ow h_ow_snow $A
run k_ruins_cover h_cover $A --biome=ruins --seed=11
run k_ruins_aim h_aim $A --biome=ruins --seed=13
run k_snow_flank h_flankkill $A --biome=snow --seed=7
run k_titan h_titan $A
run k_ow h_ow $A
# portrait (9:16): the window is resized in code; macOS caps it at 1790 tall
export WDOG=300 RES=1024x1790
V="--hud4 --ui=1.4 --win=1024x1790 --botpad=480 --zoom=1.7"
run v2_ob v $V --scene=a --seed=9 --blast
run v2_g1 v $V --scene=g1 --seed=11
run v2_g3 v $V --scene=g3 --seed=11
run v2_a v $V --scene=a --seed=9
echo BATCHDONE
