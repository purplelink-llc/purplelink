#!/usr/bin/env python3
"""Writes storyboards/rubblefront-v2.md (the shot list table) from storyboards/rubblefront-v2.json."""
import json
from pathlib import Path
D = Path(__file__).parent / "storyboards"
SHOWS = {
    "c_odds": "Tank lines up a shot at an infantry behind a wall; the game's hit-chance card shows 66 percent; the shot hits",
    "c_flank": "The same shot from the side: the card goes from 66 to 78 percent (a flank counts half the cover); the shot",
    "c_cover": "A worn wall (staged at 2 hit points) is shot to rubble under the infantry",
    "c_rubble": "Tank and bazooka shots at an enemy tank; the last one destroys it",
    "c_ow": "A tank on overwatch; the enemy walks in and takes the reaction shots (63 and 90 percent), one tank is destroyed",
    "c_massive": "A massive board (18 by 14): the player's army, the enemy base",
    "c_titan": "An Endless titan (heavy tank, 30 hp): 78 percent shot misses, the next is a critical hit for 23",
    "c_weather": "Four boards in winter, sandstorm, autumn rain and night, with the game's own weather effects",
    "c_runmap": "The branching run map after the first battle (pans along the route)",
    "c_spoils": "After a town capture: Spoils of war, choose one of three rewards",
    "c_loot": "Field upgrade: choose one of three after a fight",
    "c_hub_l1": "The outpost with every building at level 1 (test profile)",
    "c_hub_l3": "The same outpost at level 3 (test profile)",
    "c_outpost": "The outpost: a Radar and a Motor Pool finish building as days pass",
    "c_roster": "The roster: named soldiers with levels, one wounded, one fallen",
    "endless": "Endless: the Threat panel with its Mutators (clip from the v1 capture)",
    "daily": "The Daily challenge screen (clip from the v1 capture)",
    "c_snow": "One shot in snow", "c_desert": "One shot in a sandstorm", "c_night": "One shot at night in ruins",
    "c_strike": "An artillery strike from the Spoils card lands",
    "black": "Black beat (music drops out, riser)", "logo": "RUBBLEFRONT logo slam (boom)", "end": "End card: Spring 2027, rubblefront.com, A Purplelink LLC game",
}
for name, title in (("rubblefront-v2", "Main trailer"), ("rubblefront-v2-30s", "30 s cut"), ("rubblefront-v2-15s", "15 s vertical cut (9:16)")):
    sb = json.loads((D / f"{name}.json").read_text())
    t = 0.0
    rows = []
    for i, s in enumerate(sb["scenes"]):
        k = s.get("clip") or s.get("type")
        cards = " / ".join(c["text"].replace("\n", " ").replace("*", "") for c in s.get("cards", []))
        fx = []
        if s.get("slow"): fx.append("slow-mo/freeze")
        if s.get("shake"): fx.append("shake")
        if s.get("flash"): fx.append("flash")
        rows.append(f"| {i} | {t:5.2f} | {s['dur']:.2f} | `{k}` @{s.get('in', '')} | {SHOWS.get(k, '')} | {cards} | {', '.join(fx)} |")
        t += s["dur"]
    md = [f"## {title} ({t:.1f} s)", "", "| # | start | dur | clip | shows | text | edit |", "|---|---|---|---|---|---|---|", *rows, ""]
    (D / f"{name}.table.md").write_text("\n".join(md))
