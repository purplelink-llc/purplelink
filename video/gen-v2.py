#!/usr/bin/env python3
"""Writes the RubbleFront v2 storyboards (main 16:9, 30 s 16:9, 15 s 9:16) from one shot library.
Cuts sit on the music's 120 bpm grid (a beat is 0.5 s, a bar 2 s). The music starts at t = 3 s so its downbeats fall on odd seconds."""
import json, copy
from pathlib import Path

OUTDIR = Path(__file__).parent / "storyboards"
CARDS_END = ["Spring 2027", "rubblefront.com", "A Purplelink LLC game"]


def card(text, at=0.0, dur=None, pos="low", **kw):
    c = {"text": text, "at": at, "pos": pos}
    if dur:
        c["dur"] = dur
    c.update(kw)
    return c


def hitfx(at, amp=0.8, shake=20, kind="hit", color="#fff4e0"):
    return {"flash": [{"at": at, "dur": 0.24, "amp": amp, "color": color, "sfx": kind}], "shake": [{"at": at, "amp": shake, "dur": 0.45, "zoom": 0.04}]}


def merge(d, extra):
    for k, v in extra.items():
        d[k] = d.get(k, []) + v
    return d


def freeze(at, frames=4):
    return {"at": at, "dur": frames / 30, "speed": 0}


def S(clip, src, dur, fx=None, **kw):
    d = {"clip": clip, "in": src, "dur": dur}
    d.update(kw)
    if fx:
        merge(d, fx)
    return d


# ---- shot library: each returns a scene; `v` is the 9:16 window, `crop` the 16:9 punch-in ---------------------------------------
def odds_push(dur=2.4):
    return S("c_odds", 2.3, dur, punch={"from": 1.0, "to": 1.24}, crop={"x": 0.42, "y": 0.45, "s": 1.0}, v={"x": 0.08, "y": 0.5, "s": 1.0, "fit": {"z": 1.5, "x": 0.0, "y": 0.25}},
             hits=[{"at": t, "kind": "tick", "gain_db": -4} for t in (0.5, 1.0, 1.5, 2.0)])


def odds_hit():
    return S("c_odds", 5.15, 1.6, fx=hitfx(0.6, 0.95, 26, "boom"), slow=[{"at": 0.2, "dur": 0.3, "speed": 0.5}, freeze(0.6, 4)],
             crop={"x": 0.45, "y": 0.5, "s": 1.2}, v={"x": 0.58, "y": 0.5, "s": 1.0})


def flank_front(dur=1.0, **kw):
    return S("c_flank", 2.7, dur, punch={"from": 1.0, "to": 1.1}, crop={"x": 0.3, "y": 0.3, "s": 1.0}, v={"x": 0.08, "y": 0.5, "s": 1.0, "fit": {"z": 1.5, "x": 0.0, "y": 0.25}}, **kw)


def flank_side(dur=1.0, **kw):
    return S("c_flank", 5.4, dur, punch={"from": 1.0, "to": 1.1}, crop={"x": 0.3, "y": 0.3, "s": 1.0}, v={"x": 0.08, "y": 0.5, "s": 1.0, "fit": {"z": 1.5, "x": 0.0, "y": 0.25}}, **kw)


def flank_hit(dur=1.0):
    return S("c_flank", 7.15, dur, fx=hitfx(0.55, 0.6, 16), crop={"x": 0.45, "y": 0.5, "s": 1.15}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def cover_shot(dur=1.0, **kw):
    return S("c_cover", 4.75, dur, fx=hitfx(0.5, 0.6, 16), crop={"x": 0.4, "y": 0.5, "s": 1.1}, v={"x": 0.45, "y": 0.5, "s": 1.0}, **kw)


def cover_rubble(dur=1.0):
    return S("c_cover", 5.5, dur, crop={"x": 0.4, "y": 0.55, "s": 1.15}, v={"x": 0.45, "y": 0.5, "s": 1.0})


def rubble_hit(dur=1.0):
    return S("c_rubble", 7.7, dur, fx=hitfx(0.25, 0.55, 14), crop={"x": 0.45, "y": 0.5, "s": 1.1}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def rubble_kill(dur=1.0):
    return S("c_rubble", 8.15, dur, fx=hitfx(0.2, 0.8, 24, "boom"), slow=[{"at": 0.12, "dur": 0.5, "speed": 0.5}], crop={"x": 0.45, "y": 0.5, "s": 1.2}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def ow_walk(dur=1.5, **kw):
    return S("c_ow", 5.0, dur, crop={"x": 0.4, "y": 0.5, "s": 1.1}, v={"x": 0.4, "y": 0.5, "s": 1.0}, **kw)


def ow_hit(dur=1.0):
    return S("c_ow", 6.2, dur, fx=hitfx(0.35, 0.6, 16), crop={"x": 0.45, "y": 0.5, "s": 1.15}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def ow_boom(dur=1.5, **kw):
    return S("c_ow", 8.8, dur, fx=hitfx(0.2, 0.9, 26, "boom"), slow=[{"at": 0.15, "dur": 0.4, "speed": 0.45}], crop={"x": 0.5, "y": 0.5, "s": 1.2}, v={"x": 0.5, "y": 0.5, "s": 1.0}, **kw)


def titan_card(dur=1.0, **kw):
    return S("c_titan", 2.8, dur, crop={"x": 0.4, "y": 0.4, "s": 1.1}, v={"x": 0.35, "y": 0.5, "s": 1.0}, **kw)


def titan_miss(dur=1.0, **kw):
    return S("c_titan", 3.5, dur, crop={"x": 0.5, "y": 0.5, "s": 1.1}, v={"x": 0.5, "y": 0.5, "s": 1.0}, **kw)


def titan_crit(dur=1.0):
    return S("c_titan", 4.85, dur, fx=hitfx(0.5, 1.0, 32, "boom"), slow=[{"at": 0.2, "dur": 0.2, "speed": 0.5}, freeze(0.5, 5)], crop={"x": 0.5, "y": 0.5, "s": 1.15}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def massive_a(dur=1.0, **kw):
    return S("c_massive", 0.1, dur, punch={"from": 1.0, "to": 1.12}, v={"x": 0.3, "y": 0.6, "s": 1.0}, **kw)


def massive_b(dur=1.0):
    return S("c_massive", 1.0, dur, punch={"from": 1.05, "to": 1.2}, v={"x": 0.55, "y": 0.4, "s": 1.0})


def runmap(dur=2.0, **kw):
    return S("c_runmap", 0.6, dur, dim=0.62, crop={"x": 0.12, "y": 0.34, "s": 1.7, "to": {"x": 0.36, "y": 0.34, "s": 1.7}}, v={"x": 0.2, "y": 0.3, "s": 1.5}, **kw)


def spoils(dur=2.0, **kw):
    return S("c_spoils", 5.2, dur, dim=0.62, crop={"x": 0.5, "y": 0.4, "s": 1.0}, punch={"from": 1.0, "to": 1.07}, v={"x": 0.5, "y": 0.45, "s": 1.4}, **kw)


def loot(dur=1.5, **kw):
    return S("c_loot", 0.8, dur, dim=0.35, crop={"x": 0.5, "y": 0.4, "s": 1.0}, punch={"from": 1.0, "to": 1.06}, v={"x": 0.5, "y": 0.3, "s": 1.7}, **kw)


def hub1(dur=2.0, **kw):
    return S("c_hub_l1", 1.8, dur, punch={"from": 1.0, "to": 1.1}, v={"x": 0.5, "y": 0.5, "s": 1.0}, **kw)


def hub3(dur=2.0, **kw):
    return S("c_hub_l3", 1.8, dur, fx={"flash": [{"at": 0.0, "dur": 0.3, "amp": 0.6, "color": "#fff4e0", "sfx": "hit"}]}, punch={"from": 1.0, "to": 1.1}, v={"x": 0.5, "y": 0.5, "s": 1.0}, **kw)


def outpost(dur=2.5, **kw):
    return S("c_outpost", 3.2, dur, punch={"from": 1.0, "to": 1.1}, v={"x": 0.5, "y": 0.5, "s": 1.0}, **kw)


def roster(dur=2.0, **kw):
    return S("c_roster", 0.8, dur, dim=0.62, crop={"x": 0.28, "y": 0.4, "s": 1.3}, v={"x": 0.15, "y": 0.3, "s": 1.4}, **kw)


def endless(dur=1.5, **kw):
    return S("endless", 4.0, dur, dim=0.62, crop={"x": 0.5, "y": 0.5, "s": 1.25}, punch={"from": 1.0, "to": 1.07}, v={"x": 0.5, "y": 0.4, "s": 1.6}, **kw)


def daily(dur=1.0, **kw):
    return S("daily", 1.0, dur, dim=0.65, crop={"x": 0.5, "y": 0.5, "s": 1.3}, v={"x": 0.5, "y": 0.5, "s": 1.6}, **kw)


def weather4(each=0.75, sizes=150):
    out = []
    for src, word in ((0.7, "SNOW."), (3.3, "SAND."), (5.9, "RAIN."), (8.6, "NIGHT.")):
        out.append(S("c_weather", src, each, fx={"flash": [{"at": 0.0, "dur": 0.15, "amp": 0.35, "color": "#ffffff", "sfx": "slam"}]},
                     cards=[card(word, 0.0, each - 0.05, size=sizes, sfx=False)], punch={"from": 1.0, "to": 1.08}, v={"x": 0.45, "y": 0.5, "s": 1.0}))
    return out


def fights(n=3):
    out = []
    for name, src in (("c_snow", 3.0), ("c_desert", 2.95), ("c_night", 2.85))[:n]:
        out.append(S(name, src, 1.0, fx=hitfx(0.4, 0.6, 16), crop={"x": 0.4, "y": 0.5, "s": 1.15}, v={"x": 0.38, "y": 0.5, "s": 1.0}))
    return out


def strike(dur=1.0):
    return S("c_strike", 5.6, dur, fx=hitfx(0.2, 0.8, 22, "boom"), crop={"x": 0.45, "y": 0.45, "s": 1.2}, v={"x": 0.5, "y": 0.5, "s": 1.0})


def titan_more(src, dur=1.0):
    return S("c_titan", src, dur, fx=hitfx(0.3, 0.7, 20, "boom"), crop={"x": 0.5, "y": 0.5, "s": 1.15}, v={"x": 0.4, "y": 0.5, "s": 1.0})


def titan_kill(dur=1.5):
    return S("c_titan", 16.4, dur, fx=hitfx(0.6, 0.9, 26, "boom"), slow=[{"at": 0.45, "dur": 0.4, "speed": 0.5}], crop={"x": 0.45, "y": 0.5, "s": 1.2}, v={"x": 0.45, "y": 0.5, "s": 1.0})


def beauty(dur=2.2):
    return S("c_weather", 5.9, dur, punch={"from": 1.0, "to": 1.06}, cards=[card("ONE MORE *RUN.*", dur - 1.2, 1.2, pos="mid", size=170, sfx="boom")], v={"x": 0.45, "y": 0.5, "s": 1.0})


def quick():
    """Four half-second hits in a row, cut on the beat."""
    a = odds_hit(); a.update({"in": 5.3, "dur": 0.5, "slow": [], "flash": [{"at": 0.3, "dur": 0.2, "amp": 0.8, "color": "#fff4e0", "sfx": "hit"}], "shake": [{"at": 0.3, "amp": 22, "dur": 0.3, "zoom": 0.04}]})
    b = ow_boom(); b.update({"in": 8.85, "dur": 0.5, "slow": [], "flash": [{"at": 0.15, "dur": 0.2, "amp": 0.8, "color": "#fff4e0", "sfx": "hit"}], "shake": [{"at": 0.15, "amp": 22, "dur": 0.3, "zoom": 0.04}]})
    cc = S("c_titan", 4.75, 0.5, fx=hitfx(0.25, 0.8, 22), crop={"x": 0.5, "y": 0.5, "s": 1.15}, v={"x": 0.4, "y": 0.5, "s": 1.0})
    d = rubble_kill(); d.update({"in": 8.3, "dur": 0.5, "slow": [], "flash": [{"at": 0.1, "dur": 0.2, "amp": 0.8, "color": "#fff4e0", "sfx": "hit"}], "shake": [{"at": 0.1, "amp": 22, "dur": 0.3, "zoom": 0.04}]})
    return [a, b, cc, d]


BLACK = lambda d: {"type": "black", "dur": d}
LOGO = lambda d: {"type": "logo", "dur": d}
END = lambda d: {"type": "end", "dur": d, "lines": CARDS_END}


def timeline(scenes, label):
    t = 0
    print(label)
    for i, x in enumerate(scenes):
        print(f"  {i:2d} t={t:6.2f} dur={x['dur']:.2f} {x.get('clip', x.get('type'))}")
        t += x["dur"]
    print("  total", t)
    return t


# ------------------------------------------------------------------ MAIN
def c(text, **kw):
    return [card(text, **kw)]


main = []
main += [odds_push(), odds_hit()]
main += [flank_front(), flank_side(cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 2.0, pos="lowright", size=112)]), flank_hit()]
main += [cover_shot(cards=c("BLOW A HOLE\nIN THEIR *COVER.*", dur=2.2)), cover_rubble(), rubble_hit(), rubble_kill()]
main += [ow_walk(2.0, cards=c("HOLD. WAIT.\n*AMBUSH.*", dur=2.6)), ow_hit(), ow_boom(1.0)]
main += [massive_a(cards=c("BOARDS UP TO\n*18 BY 14.*", dur=2.0)), massive_b()]
main += [titan_card(cards=c("PRAY THE *78%*\nHOLDS.", dur=2.0)), titan_miss(), titan_crit()]
main += [BLACK(1.0), LOGO(2.5)]                                           # t = 20 .. 23: the drop
main += weather4(1.0)                                                     # 23.5 .. 27.5
main += [runmap(cards=c("CHOOSE YOUR\n*ROUTE.*", pos="mid", size=120)), spoils(1.5, cards=c("PICK ONE\nOF *THREE.*", pos="mid", size=120))]
main += [hub1(cards=c("BUILD THE\n*OUTPOST.*", dur=3.5)), hub3(2.5), outpost(3.0)]
main += [roster(cards=c("KEEP YOUR\n*VETERANS* ALIVE.", pos="mid", size=112)), endless(cards=c("GO *DEEPER.*", pos="mid", size=130)), daily(cards=c("A NEW BATTLE\nEVERY *DAY.*", pos="mid", size=112))]
main += [massive_a(1.0)] + fights(3) + [strike(), titan_kill()]
main += quick()

main += [beauty(2.7), END(6.0)]
timeline(main, "main")

MAIN = {
    "id": "rubblefront-v2",
    "outputs": {"16x9": "rubblefront-trailer-v2-16x9.mp4"},
    "poster": {"file": "rubblefront-poster-v2.png", "at": 3.1},
    "formats": ["16x9"],
    "crf": 16,
    "sfxDb": -6,
    "music": [],      # filled below from the section list
    "scenes": main,
}


def music_for(total, logo_t, end_t):
    """Intro, mid section, silence for the drop, then low (loop), mid, high with the drive stem; all on one running bar position."""
    m = []

    def seg(f, t0, t1, g=0.0, fi=0.03, fo=0.3):
        m.append({"file": f, "in": t0 - 3.0, "t": t0, "dur": t1 - t0, "gain_db": g, "fade_in": fi, "fade_out": fo})
    m.append({"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": 3.4, "gain_db": -6, "fade_in": 1.2, "fade_out": 0.3})
    seg("battle_mid.ogg", 3.0, logo_t - 1.0)
    seg("battle_mid_drive.ogg", 3.0, logo_t - 1.0, 2.0)
    return m


# 120 bpm music: low base (intro), mid + drive (fights), silence, high + drive at the logo and through the weather montage,
# then mid for the loop, high + drive for the finale.
LOGO_T = 21.0
MAIN["music"] = [
    {"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": 3.4, "gain_db": -6, "fade_in": 1.2, "fade_out": 0.3},
    {"file": "battle_mid.ogg", "in": 0.0, "t": 3.0, "dur": 17.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 0.4},
    {"file": "battle_mid_drive.ogg", "in": 0.0, "t": 3.0, "dur": 17.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 0.4},
    {"file": "battle_high.ogg", "in": 18.0, "t": 21.0, "dur": 8.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 0.3},
    {"file": "battle_high_drive.ogg", "in": 18.0, "t": 21.0, "dur": 8.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 0.3},
    {"file": "battle_mid.ogg", "in": 26.0, "t": 29.0, "dur": 14.0, "gain_db": 0, "fade_in": 0.05, "fade_out": 0.3},
    {"file": "battle_mid_drive.ogg", "in": 38.0, "t": 41.0, "dur": 4.0, "gain_db": 2, "fade_in": 0.05, "fade_out": 0.3},
    {"file": "battle_high.ogg", "in": 42.0, "t": 45.0, "dur": 100.0, "gain_db": 0, "fade_in": 0.05, "fade_out": 3.5},
    {"file": "battle_high_drive.ogg", "in": 42.0, "t": 45.0, "dur": 100.0, "gain_db": 2, "fade_in": 0.05, "fade_out": 3.5},
]
MAIN["musicEnv"] = [{"t": 0, "db": 0}, {"t": 19.9, "db": 0}, {"t": 20.0, "db": -40}, {"t": 20.95, "db": -40}, {"t": 21.0, "db": 0}, {"t": 52.4, "db": 0}, {"t": 52.5, "db": -40}, {"t": 52.95, "db": -40}, {"t": 53.0, "db": 0}]
MAIN["synth"] = [{"t": 3.0, "kind": "riser", "dur": 2.8, "gain_db": -2}, {"t": 21.0, "kind": "riser", "dur": 1.0, "gain_db": 0}, {"t": 53.0, "kind": "riser", "dur": 0.9, "gain_db": -1}]
(OUTDIR / "rubblefront-v2.json").write_text(json.dumps(MAIN, indent=1))


# ------------------------------------------------------------------ 30 s (16:9)
def sub(d, **kw):
    d = copy.deepcopy(d)
    d.update(kw)
    return d


s30 = [odds_push(), odds_hit()]
s30 += [flank_side(cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 2.0, pos="lowright", size=112)]), flank_hit()]
s30 += [cover_shot(cards=c("BLOW A HOLE\nIN THEIR *COVER.*", dur=2.0)), rubble_kill()]
s30 += [ow_walk(1.5, cards=c("HOLD. WAIT.\n*AMBUSH.*", dur=2.4)), ow_boom(1.0)]
s30 += [titan_miss(1.0, cards=c("PRAY THE *78%*\nHOLDS.", dur=2.0)), titan_crit()]
s30 += [BLACK(0.5), LOGO(1.5)]
s30 += weather4(0.75, 150)
s30 += [hub1(1.5, cards=c("BUILD THE\n*OUTPOST.*", dur=3.0)), hub3(1.5)]
s30 += [runmap(1.5, cards=c("CHOOSE YOUR\n*ROUTE.*", pos="mid", size=120))]
s30 += quick()
s30 += [beauty(2.2), END(3.8)]
timeline(s30, "30 s")
T30_LOGO = 13.0
S30 = {
    "id": "rubblefront-v2-30s", "outputs": {"16x9": "rubblefront-trailer-v2-30s-16x9.mp4"}, "formats": ["16x9"], "crf": 16, "sfxDb": -6,
    "music": [
        {"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": 3.4, "gain_db": -6, "fade_in": 1.2, "fade_out": 0.3},
        {"file": "battle_mid.ogg", "in": 0.0, "t": 3.0, "dur": 9.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 0.3},
        {"file": "battle_mid_drive.ogg", "in": 0.0, "t": 3.0, "dur": 9.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 0.3},
        {"file": "battle_high.ogg", "in": 10.0, "t": 13.0, "dur": 100.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 3.0},
        {"file": "battle_high_drive.ogg", "in": 10.0, "t": 13.0, "dur": 100.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 3.0},
    ],
    "musicEnv": [{"t": 0, "db": 0}, {"t": 11.9, "db": 0}, {"t": 12.0, "db": -40}, {"t": 12.95, "db": -40}, {"t": 13.0, "db": 0}],
    "synth": [{"t": 3.0, "kind": "riser", "dur": 2.8, "gain_db": -2}, {"t": 13.0, "kind": "riser", "dur": 1.0, "gain_db": 0}],
    "scenes": s30,
}
(OUTDIR / "rubblefront-v2-30s.json").write_text(json.dumps(S30, indent=1))

# ------------------------------------------------------------------ 15 s (9:16)
o = S("c_odds", 3.2, 0.9, punch={"from": 1.0, "to": 1.15}, v={"x": 0.1, "y": 0.5, "s": 1.0, "fit": {"z": 1.5, "x": 0.0, "y": 0.25}}, hits=[{"at": 0.4, "kind": "tick", "gain_db": -4}, {"at": 0.65, "kind": "tick", "gain_db": -2}])
oh = sub(odds_hit(), dur=1.1)
v15 = [o, oh]
v15 += [sub(flank_side(1.0, cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.9)])), flank_hit()]
v15 += [cover_shot(1.0, cards=c("BLOW A HOLE\nIN THEIR *COVER.*", dur=1.9)), rubble_kill()]
v15 += [sub(ow_boom(1.0), cards=c("HOLD. WAIT.\n*AMBUSH.*", dur=1.2))]
v15 += [titan_miss(0.75, cards=c("PRAY THE *78%*\nHOLDS.", dur=1.7)), titan_crit()]
v15 += [hub1(1.0, cards=c("BUILD THE\n*OUTPOST.*", dur=2.0)), hub3(1.0)]
v15 += [beauty(1.5)]
v15 += [END(2.75)]
timeline(v15, "15 s vertical")
S15 = {
    "id": "rubblefront-v2-15s", "outputs": {"9x16": "rubblefront-trailer-v2-15s-9x16.mp4"}, "formats": ["9x16"], "crf": 17, "sfxDb": -6,
    "music": [
        {"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": 1.9, "gain_db": -6, "fade_in": 0.6, "fade_out": 0.2},
        {"file": "battle_mid.ogg", "in": 0.0, "t": 1.5, "dur": 8.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 0.3},
        {"file": "battle_mid_drive.ogg", "in": 0.0, "t": 1.5, "dur": 8.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 0.3},
        {"file": "battle_high.ogg", "in": 8.0, "t": 9.5, "dur": 100.0, "gain_db": 0, "fade_in": 0.02, "fade_out": 2.0},
        {"file": "battle_high_drive.ogg", "in": 8.0, "t": 9.5, "dur": 100.0, "gain_db": 2, "fade_in": 0.02, "fade_out": 2.0},
    ],
    "synth": [{"t": 1.5, "kind": "riser", "dur": 1.4, "gain_db": -2}],
    "scenes": v15,
}
(OUTDIR / "rubblefront-v2-15s.json").write_text(json.dumps(S15, indent=1))
