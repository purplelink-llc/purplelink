#!/usr/bin/env bash
# RubbleFront trailer v7: cinematic plates (no interface, slow camera moves) plus the story's proof shots.
# --cine hides the HUD, badges, tags and dice; the game's aim card (odds) stays. --dolly=Z,VX,VY moves the camera per second.
set -u
cd "$(dirname "$0")"
export WDOG=300
A="--hud4 --ui=1.35 --win=1920x1080"
run() { echo "== $1"; ./cap-v7.sh "$@" 2>&1 | tail -1 | cut -c1-60; }
# weather and biome plates (no action)
run p_snow v $A --cine --scene=a --seed=3 --biome=snow --wx=winter --dolly=0.03,10,0 --hold=6
run p_desert v $A --cine --scene=d --seed=3 --biome=desert --wx=sandstorm --dolly=0.03,-10,0 --hold=6
run p_rain v $A --cine --scene=f --seed=6 --biome=grassland --wx=autumn_rain --dolly=0.03,0,6 --hold=6
run p_night v $A --cine --scene=c --seed=5 --biome=ruins --wx=night --dolly=0.03,8,0 --hold=6
run p_fog v $A --cine --scene=f --seed=6 --biome=grassland --wx=fog --dolly=0.03,-6,4 --hold=6
# cinematic fights (the game log decides every flash)
run a_open v $A --cine --scene=a --seed=9 --blast --dolly=0.02,6,0
run a_b v $A --cine --scene=b --seed=1 --dolly=0.015,4,0
run a_d v $A --cine --scene=d --seed=16 --dolly=0.015,-4,0
run a_e v $A --cine --scene=e --seed=1 --dolly=0.015,0,3
run a_f v $A --cine --scene=f --seed=13 --dolly=0.015,4,0
run a_g1 v $A --cine --scene=g1 --seed=11 --dolly=0.02,0,0
run a_g3 v $A --cine --scene=g3 --seed=11 --dolly=0.02,0,0
run a_snow v $A --cine --scene=a --seed=3 --biome=snow --wx=winter --dolly=0.015,6,0
run a_night v $A --cine --scene=c --seed=5 --biome=ruins --wx=night --dolly=0.015,4,0
run a_desert v $A --cine --scene=d --seed=3 --biome=desert --wx=sandstorm --dolly=0.015,-4,0
# the outpost
run h_est cine_hub --ui=1.35 --win=1920x1080 --cine --look=5,5,0.5 --dolly=0.04,0,0 --hold=6
run h_l1 c_hub_l1 --ui=1.35 --win=1920x1080 --cine --look=3,3,0.5
run h_l3 c_hub_l3 --ui=1.35 --win=1920x1080 --cine --look=3,3,0.5
# the run (menus, kept short in the edit)
run m_roster c_roster --ui=1.35 --win=1920x1080
run m_runmap c_runmap --ui=1.35 --win=1920x1080
run m_boss boss $A
echo BATCHDONE
