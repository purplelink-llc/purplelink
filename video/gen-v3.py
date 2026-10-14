#!/usr/bin/env python3
"""RubbleFront trailer v3 storyboards (main, 30 s, 15 s vertical) from one shot library. Clip times below are seconds into the captured
clip (frame / 30). HUD stays on; the compact hit-chance bubble is the number. Run: python3 gen-v3.py"""
import json, copy
from pathlib import Path

OUT = Path(__file__).parent / "storyboards"
END_LINES = ["Spring 2027", "rubblefront.com", "A Purplelink LLC game"]


def card(text, at=0.0, dur=2.0, pos="bottom", **kw):
    c = {"text": text, "at": at, "dur": dur, "pos": pos}
    c.update(kw)
    return c


def hitfx(at, amp=0.55, shake=14, kind="hit"):
    return {"flash": [{"at": at, "dur": 0.2, "amp": amp, "color": "#fff4e0", "sfx": kind}], "shake": [{"at": at, "amp": shake, "dur": 0.4, "zoom": 0.03}]}


def freeze(at, fr=4):
    return {"at": at, "dur": fr / 30, "speed": 0}


def S(clip, src, dur, fx=None, v=None, **kw):
    d = {"clip": clip, "in": src, "dur": dur, "v": v or {"cx": 800, "cy": 450, "s": 1.0}}
    d.update(kw)
    if fx:
        for k, val in fx.items():
            d[k] = d.get(k, []) + val
    return d


HUDV = {"cx": 800, "cy": 450, "s": 1.0}
MENUV = {"cx": 1000, "cy": 540, "s": 0.95}
END = lambda d: {"type": "end", "dur": d, "lines": END_LINES}


def A(dur=2.5):  # cold open: lineup, genre card
    return S("h_aim", 1.2, dur, punch={"from": 1.0, "to": 1.1}, cards=[card("TURN-BASED\n*TACTICS.*", 0.2, 2.2, pos="top", size=92)],
             hits=[{"at": t, "kind": "tick", "gain_db": -4} for t in (0.5, 1.0, 1.5, 2.0)])


def B(dur=1.5):
    return S("h_aim", 3.7, dur, fx=hitfx(0.4, 0.7, 18, "boom"), slow=[{"at": 0.4, "dur": 0.15, "speed": 0.5}, freeze(0.55, 4)], cards=[card("EVERY SHOT HAS *ODDS.*", 0.1, 1.4)])


def C(dur=2.0):
    return S("h_flankkill", 2.7, dur, fx=hitfx(1.0, 0.7, 20, "boom"), cards=[card("FLANK FOR\nTHE *KILL.*", 0.0, 1.9)])


def D(dur=2.0):
    return S("h_cover", 2.2, dur, fx=hitfx(0.85, 0.7, 20, "boom"), slow=[{"at": 0.8, "dur": 0.45, "speed": 0.45}], cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 0.0, 2.0)])


def E(dur=2.0):
    return S("h_combo", 2.4, dur, fx=hitfx(0.9, 0.5, 14), cards=[card("COVER DOWN.\n*THEN KILL.*", 0.0, 2.0)])


def F(dur=2.0):
    return S("h_combo", 8.0, dur, fx=hitfx(1.0, 0.7, 20, "boom"), slow=[{"at": 0.8, "dur": 0.4, "speed": 0.5}])


def G(dur=2.5):
    return S("h_ow", 4.6, dur, cards=[card("HOLD. WAIT.\n*AMBUSH.*", 0.0, 2.4)])


def H(dur=2.0):
    return S("h_ow", 9.2, dur, fx=hitfx(0.6, 0.6, 16, "boom"), slow=[{"at": 0.5, "dur": 0.4, "speed": 0.5}])


def I(dur=2.0):
    return S("h_massive", 11.0, dur, v={"cx": 700, "cy": 540, "s": 1.0}, cards=[card("BOARDS UP TO\n*18 BY 14.*", 0.1, 1.9)])


def J(dur=3.0):
    return S("h_titan", 2.4, dur, cards=[card("PRAY THE *78%*\nHOLDS.", 0.0, 2.4)])


def K(dur=2.5):
    return S("h_titan", 7.5, dur, fx=hitfx(0.8, 0.8, 22, "boom"), slow=[{"at": 0.8, "dur": 0.15, "speed": 0.5}, freeze(0.95, 4)])


def L(dur=2.0, logo=True):
    d = S("h_titan", 16.7, dur, fx=hitfx(0.7, 0.9, 26, "boom"), slow=[{"at": 0.7, "dur": 0.5, "speed": 0.4}])
    if logo:
        d["logo"] = {"at": 1.0, "dur": 1.0}
    return d


def Mm(dur=1.5):
    return S("h_spoils", 1.0, dur, cards=[card("WIN THE *BATTLE.*", 0.0, 1.5)])


def Nn(dur=2.0):
    return S("h_loot", 0.8, dur, v={"cx": 900, "cy": 330, "s": 1.0}, cards=[card("PICK ONE OF\n*THREE.*", 0.0, 2.0)])


def O(dur=2.5):
    return S("h_runmap", 0.8, dur, v={"cx": 700, "cy": 330, "s": 1.0}, cards=[card("THE MAP\n*BRANCHES.*", 0.0, 2.4)])


def P(dur=3.0):
    return S("h_hub", 0.8, dur, v={"cx": 1150, "cy": 480, "s": 0.9}, cards=[card("SPEND SALVAGE\nON *BUILDINGS.*", 0.0, 3.0, full=True)])


def Q(dur=3.0):
    return S("h_hub", 5.0, dur, v={"cx": 1150, "cy": 480, "s": 0.9}, cards=[card("THE NEXT RUN\nSTARTS *STRONGER.*", 0.0, 3.0, full=True)])


def fogs(dur=2.0):
    return S("h_fog", 2.4, dur, fx=hitfx(0.9, 0.5, 14), cards=[card("FOG CHANGES\nTHE *ODDS.*", 0.0, 2.0)])


def snow_ow(dur=2.5):
    return S("h_ow_snow", 4.8, dur, fx=hitfx(1.5, 0.5, 14))


def desert(dur=1.5, cards=True):
    return S("h_desert", 2.4, dur, fx=hitfx(0.9, 0.5, 14), cards=[card("FOUR *BIOMES.*\nREAL WEATHER.", 0.0, 3.0, span=True)] if cards else None)


def night(dur=1.5):
    return S("h_snow", 2.4, dur, fx=hitfx(0.9, 0.5, 14))


def strike(dur=2.0):
    return S("h_strike", 1.4, dur, fx=hitfx(1.6, 0.8, 22, "boom"), cards=[card("CALL IN\n*ARTILLERY.*", 0.0, 2.0)])


def titan2(dur=1.5):
    return S("h_titan", 12.3, dur, fx=hitfx(0.5, 0.5, 14))


def quick():
    out = [
        S("h_cover", 2.9, 1.0, fx=hitfx(0.3, 0.6, 16, "boom")),
        S("h_titan", 8.1, 1.0, fx=hitfx(0.3, 0.6, 16, "boom")),
        S("h_flankkill", 3.4, 1.0, fx=hitfx(0.4, 0.6, 16, "boom")),
        S("h_ow", 10.0, 0.75, fx=hitfx(0.2, 0.6, 16, "boom")),
        S("h_ow_snow", 8.6, 0.75, fx=hitfx(0.2, 0.6, 16, "boom")),
        S("h_desert", 3.1, 0.5, fx=hitfx(0.1, 0.6, 16, "boom")),
        S("h_combo", 8.6, 0.5, fx=hitfx(0.1, 0.6, 16, "boom")),
        S("h_snow", 3.1, 0.5, fx=hitfx(0.1, 0.6, 16, "boom")),
        S("h_strike", 3.1, 0.5, fx=hitfx(0.1, 0.6, 16, "boom")),
    ]
    return out


def beauty(dur=3.0):
    return S("h_massive", 12.0, dur, punch={"from": 1.0, "to": 1.06}, v={"cx": 700, "cy": 540, "s": 1.0}, cards=[card("ONE MORE *RUN.*", dur - 1.5, 1.5, pos="mid", full=True, size=150, sfx="boom")])


def timeline(sc, label):
    t = 0
    rows = []
    for i, x in enumerate(sc):
        rows.append((i, t, x["dur"], x.get("clip", x.get("type"))))
        t += x["dur"]
    print(label, "total", round(t, 2), "scenes", len(sc))
    return t, rows


def logo_time(sc):
    t = 0
    for x in sc:
        if x.get("logo"):
            return t + x["logo"]["at"]
        t += x["dur"]


def music_cfg(total, lt, loop_end, fade=3.5):
    m = [{"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": 3.4, "gain_db": -6, "fade_in": 1.2, "fade_out": 0.3}]

    def seg(f, t0, t1, g=0.0, fo=0.25):
        m.append({"file": f, "in": t0 - 3.0, "t": t0, "dur": t1 - t0, "gain_db": g, "fade_in": 0.02, "fade_out": fo})
    seg("battle_mid.ogg", 3.0, lt - 0.4)
    seg("battle_mid_drive.ogg", 3.0, lt - 0.4, 2.0)
    seg("battle_high.ogg", lt, lt + 3.0)
    seg("battle_high_drive.ogg", lt, lt + 3.0, 2.0)
    loop_end = max(loop_end, lt + 3.0)
    if loop_end > lt + 3.0:
        seg("battle_mid.ogg", lt + 3.0, loop_end)
    m.append({"file": "battle_high.ogg", "in": loop_end - 3.0, "t": loop_end, "dur": 100, "gain_db": 0, "fade_in": 0.05, "fade_out": fade})
    m.append({"file": "battle_high_drive.ogg", "in": loop_end - 3.0, "t": loop_end, "dur": 100, "gain_db": 2, "fade_in": 0.05, "fade_out": fade})
    env = [{"t": 0, "db": 0}, {"t": lt - 0.4, "db": 0}, {"t": lt - 0.35, "db": -40}, {"t": lt - 0.03, "db": -40}, {"t": lt, "db": 0}]
    syn = [{"t": 3.0, "kind": "riser", "dur": 2.8, "gain_db": -2}, {"t": lt, "kind": "riser", "dur": 0.9, "gain_db": 0}]
    return m, env, syn


def write(name, id_, outputs, scenes, fmt, music, env, syn, poster=None, crf=16):
    d = {"id": id_, "outputs": outputs, "formats": [fmt], "crf": crf, "sfxDb": -6, "music": music, "synth": syn, "scenes": scenes, "wishlistText": "Wishlist on Steam"}
    if env:
        d["musicEnv"] = env
    if poster:
        d["poster"] = poster
    (OUT / f"{name}.json").write_text(json.dumps(d, indent=1))


# ----------------------------------------------------------------- MAIN
main = [A(), B(), C(), D(), E(), F(), G(), H(), I(), J(), K(), L()]
main += [Mm(), Nn(), O(), P(), Q()]
main += [fogs(), snow_ow(), desert(1.5), night(1.5), strike()]
main += [titan2()]
main += quick()
main += [beauty(3.0), END(4.0)]
tot, rows = timeline(main, "main")
lt = logo_time(main)
loop_end = sum(x["dur"] for x in main[:17])
print("logo at", lt, "loop ends", loop_end)
m, env, syn = music_cfg(tot, lt, sum(x["dur"] for x in main[:17]))
write("rubblefront-v3", "rubblefront-v3", {"16x9": "rubblefront-trailer-v3-16x9.mp4"}, main, "16x9", m, env, syn, poster={"file": "rubblefront-poster-v3.png", "at": 22.6})
for r in rows:
    print(r)

# ----------------------------------------------------------------- 30 s
s30 = [A(2.5), B(1.5), D(2.0), G(2.0), H(1.5), K(1.5), L(2.0)]
s30 += [Nn(1.5), O(1.5), P(2.0), Q(2.0)]
s30 += [fogs(1.5)]
q = quick()
s30 += [q[1], q[3], q[5], q[6]]
s30 += [beauty(2.5), END(3.25)]
tot30, _ = timeline(s30, "30s")
lt30 = logo_time(s30)
loop30 = 2.5 + 1.5 + 2.0 + 2.0 + 1.5 + 1.5 + 2.0 + 1.5 + 1.5 + 2.0 + 2.0
m, env, syn = music_cfg(tot30, lt30, loop30, 3.0)
write("rubblefront-v3-30s", "rubblefront-v3-30s", {"16x9": "rubblefront-trailer-v3-30s-16x9.mp4"}, s30, "16x9", m, env, syn)

# ----------------------------------------------------------------- 15 s vertical
def vcard(sc):
    for c in sc.get("cards", []):
        c["vsize"] = 78
    return sc


v15 = [A(2.0), B(1.5), D(1.5), G(1.5), K(1.5), L(2.0), P(1.5), beauty(1.5), END(2.0)]
tot15, _ = timeline(v15, "15s")
lt15 = logo_time(v15)
m, env, syn = music_cfg(tot15, lt15, 11.0, 2.0)
write("rubblefront-v3-15s", "rubblefront-v3-15s", {"9x16": "rubblefront-trailer-v3-15s-9x16.mp4"}, v15, "9x16", m, env, syn, crf=17)
