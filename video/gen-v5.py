#!/usr/bin/env python3
"""RubbleFront trailer v5 storyboards (main, 30 s, 15 s vertical). Cut points come from the capture logs: each clip's fire marks
(frame / 30 = seconds) and the game's own log lines (hit, miss, destroyed), so a flash, a shake and a slow-motion beat are only placed on
real kills. Run: python3 gen-v5.py"""
import json, re, math
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "storyboards"
FL = Path("/Volumes/Extreme SSD/Frontlink/build/trailer")
END_LINES = ["Spring 2027", "rubblefront.com", "A Purplelink LLC game"]
IMPACT = 0.42   # seconds from the Fire press to the hit landing on screen


def parse(clip, sub="v5"):
    """-> list of {fire: seconds, text: first log line of that shot} for the clip's capture."""
    f = FL / sub / "raw" / f"{clip}.log"
    if not f.exists():
        return []
    shots, cur = [], None
    for l in f.read_text(errors="ignore").splitlines():
        m = re.match(r"MARK fire frame (\d+)", l)
        if m:
            cur = {"fire": int(m.group(1)) / 30.0, "text": ""}
            shots.append(cur)
        elif l.startswith("LOG ") and cur is not None and not cur["text"] and " fires at " in l:
            cur["text"] = l[4:]
    return shots


def info(clip, i):
    s = parse(clip)[i]
    t = s["text"]
    s["kill"] = "destroyed" in t.split("It fires back")[0]
    s["miss"] = ": miss" in t
    return s


def card(text, at=0.0, dur=2.0, pos="bottom", **kw):
    c = {"text": text, "at": at, "dur": dur, "pos": pos}
    c.update(kw)
    return c


def S(clip, src, dur, **kw):
    d = {"clip": clip, "in": round(max(0.0, src), 3), "dur": round(dur, 3), "v": {"cx": 960, "cy": 540, "s": 1.0}}
    d.update(kw)
    return d


def shot(clip, i, pre, post, cards=None, slow=True, **kw):
    """One fired shot: `pre` seconds of lineup (bubble) before Fire, `post` after. Flash, shake and slow-motion only if the game's log says destroyed."""
    s = info(clip, i)
    imp = pre + IMPACT
    d = S(clip, s["fire"] - pre, pre + post, **kw)
    if s["kill"]:
        d["flash"] = [{"at": imp, "dur": 0.07, "amp": 0.85, "color": "#fff6e6", "sfx": "hit"}]
        d["shake"] = [{"at": imp, "amp": 16, "dur": 0.35, "zoom": 0.03}]
        if slow:
            d["slow"] = [{"at": imp - 0.02, "dur": 0.42, "speed": 0.4}]
    elif not s["miss"]:
        d["hits"] = [{"at": imp, "kind": "tick", "gain_db": 0}]
    if cards:
        d["cards"] = cards
    d["_kill"] = s["kill"]
    d["_miss"] = s["miss"]
    d["_text"] = s["text"]
    d["_impact"] = imp
    return d


BLACK = None
END = lambda d: {"type": "end", "dur": d, "lines": END_LINES}


def strike(clip, pre, post, cards=None):
    d = S(clip, 2.9 + 0.4 - pre, pre + post)   # explosion lands about 0.4 s after the strike is confirmed (about 2.9 s into the clip)
    d["flash"] = [{"at": pre, "dur": 0.07, "amp": 0.85, "color": "#fff6e6", "sfx": "hit"}]
    d["shake"] = [{"at": pre, "amp": 20, "dur": 0.4, "zoom": 0.035}]
    d["slow"] = [{"at": pre - 0.02, "dur": 0.42, "speed": 0.4}]
    if cards:
        d["cards"] = cards
    return d


def timeline(sc, label):
    t = 0.0
    rows = []
    for i, x in enumerate(sc):
        rows.append((i, round(t, 2), round(x["dur"], 2), x.get("clip", x.get("type"))))
        t += x["dur"]
    print(label, "total", round(t, 2), "scenes", len(sc))
    return t, rows


def clean(sc):
    for x in sc:
        for k in [k for k in x if k.startswith("_")]:
            x.pop(k)
    return sc


def logo_time(sc):
    t = 0.0
    for x in sc:
        if x.get("logo"):
            return t + x["logo"]["at"]
        t += x["dur"]


def write(name, id_, outputs, scenes, fmt, music, env, syn, poster=None, crf=16):
    d = {"id": id_, "outputs": outputs, "formats": [fmt], "crf": crf, "sfxDb": -6, "music": music, "synth": syn, "scenes": clean(scenes), "wishlistText": "Wishlist on Steam"}
    if env:
        d["musicEnv"] = env
    if poster:
        d["poster"] = poster
    (OUT / f"{name}.json").write_text(json.dumps(d, indent=1))


def music_cfg(t_kill1, t_loop, t_logo, fade=3.5):
    """Escalation: low track and ticks until the first kill; mid + drive from the kill (drop 1); a build (riser, mid kept) under the run loop;
    a short dip and a boom at the logo (drop 2, high + drive); then the fastest cuts on high + drive. Everything is on the 120 bpm bar grid
    (the music files start at t_kill1, so downbeats fall on kill1 + 2k)."""
    m = [{"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": t_kill1 + 0.4, "gain_db": -6, "fade_in": 1.2, "fade_out": 0.3}]

    def seg(f, a, b, g=0.0, fo=0.25):
        m.append({"file": f, "in": a - t_kill1, "t": a, "dur": b - a, "gain_db": g, "fade_in": 0.02, "fade_out": fo})
    seg("battle_mid.ogg", t_kill1, t_logo - 0.4)
    seg("battle_mid_drive.ogg", t_kill1, t_loop, 2.0)
    seg("battle_high.ogg", t_logo, t_logo + 100, 0.0, fade)
    seg("battle_high_drive.ogg", t_logo, t_logo + 100, 2.0, fade)
    b0 = max(t_kill1 + 4.0, t_logo - 8.0)     # the build: the mid stem rises from -3 dB to +2 dB over the last 8 s before the slam, with a riser
    env = [{"t": 0, "db": 0}, {"t": b0, "db": -3}, {"t": t_logo - 0.45, "db": 2}, {"t": t_logo - 0.4, "db": -40}, {"t": t_logo - 0.03, "db": -40}, {"t": t_logo, "db": 0}]
    syn = [{"t": t_kill1, "kind": "riser", "dur": 2.4, "gain_db": -3}, {"t": t_logo - 0.4, "kind": "riser", "dur": t_logo - 0.4 - b0, "gain_db": -3}, {"t": t_logo, "kind": "boom", "gain_db": 6}]
    return m, env, syn


# ================================================================== shot library
def ow_kill(src, dur, impact, cards=None):
    d = S("s_b", src, dur)
    d["flash"] = [{"at": impact, "dur": 0.07, "amp": 0.85, "color": "#fff6e6", "sfx": "hit"}]
    d["shake"] = [{"at": impact, "amp": 16, "dur": 0.35, "zoom": 0.03}]
    d["slow"] = [{"at": impact - 0.02, "dur": 0.42, "speed": 0.4}]
    if cards:
        d["cards"] = cards
    return d


def loop_scenes():
    sp = lambda src, dur, **kw: S("k_spoils", src, dur, **kw)
    L = [
        sp(1.7, 1.3, cards=[card("TAKE A TOWN.\n*PICK ONE OF THREE.*", 0.0, 1.25)]),
        sp(3.3, 0.9, crop={"x": 0.5, "y": 0.45, "s": 1.18}),
        sp(6.1, 0.5),
        sp(7.2, 2.0, insets=[{"clip": "h_runmap", "src": 0.8, "at": 0.15, "dur": 1.8, "crop": {"x": 70, "y": 165, "w": 1210, "h": 690}, "x": 40, "y": 140, "w": 900}],
           cards=[card("THE MAP\n*BRANCHES.*", 0.0, 2.0, pos="bottom")]),
        S("k_hub", 3.0, 2.8, crop={"x": 0.5, "y": 0.0, "s": 1.22}, cards=[card("SPEND SALVAGE\nON *BUILDINGS.*", 0.0, 1.4), card("NEW BUILDINGS.\n*NEW UNITS.*", 1.4, 1.4)]),
    ]
    return L


def build_main():
    sc = []
    sc.append(shot("s_a", 0, 2.58, 0.9, cards=[card("TURN-BASED\n*TACTICS.*", 0.2, 2.0, pos="top", size=92, sfxDb=-3)],
                   hits=None, slow=False))
    sc[-1]["hits"] = [{"at": t, "kind": "tick", "gain_db": -4} for t in (0.5, 1.0, 1.5, 2.0, 2.5)]
    sc.append(shot("s_a", 1, 0.6, 1.7, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 0.0, 2.2)]))
    sc.append(shot("s_a", 2, 0.5, 1.6, cards=[card("EVERY SHOT HAS *ODDS.*", 0.0, 1.8)]))
    sc.append(shot("s_c", 0, 1.1, 1.2, cards=[card("FLANK FOR\nTHE *KILL.*", 0.0, 2.2)]))
    sc.append(shot("s_c", 1, 0.5, 1.5))
    sc.append(shot("s_d", 0, 1.5, 1.0, cards=[card("ONE TITAN.\n*FOUR SHOTS.*", 0.0, 2.4)]))
    sc.append(shot("s_d", 1, 0.4, 1.1))
    sc.append(shot("s_d", 2, 0.3, 1.0))
    sc.append(shot("s_d", 3, 0.5, 1.8))
    loop_start = sum(x["dur"] for x in sc)
    sc += loop_scenes()
    sc.append(shot("s_g1", 0, 1.6, 1.1, cards=[card("EARLY *SQUAD.*", 0.0, 2.5)]))
    sc.append(shot("s_g3", 0, 1.6, 1.1, cards=[card("UPGRADED *SQUAD.*", 0.0, 2.5)]))
    # land the logo on an odd second (the music's downbeats): pad the last "run three" shot
    t = sum(x["dur"] for x in sc)
    want = math.ceil(t + 1.5 - 1.0 + 0.0001)
    if (want % 2) == 0:
        want += 1
    sc[-1]["dur"] = round(sc[-1]["dur"] + (want - 1.5 - t), 3)
    e = strike("s_e", 1.5, 1.2)
    e["logo"] = {"at": 1.5, "dur": 1.0}
    sc.append(e)
    t_logo = sum(x["dur"] for x in sc[:-1]) + 1.5
    sc.append(ow_kill(6.4, 2.6, 1.25, [card("HOLD. WAIT.\n*AMBUSH.*", 0.0, 2.6)]))
    sc.append(S("k_massive", 6.0, 1.8, cards=[card("BOARDS UP TO\n*18 BY 14 TILES.*", 0.0, 1.7)]))
    sc.append(shot("s_f", 1, 1.3, 1.0, cards=[card("SOMETIMES\nIT *MISSES.*", 0.0, 2.2)]))
    chain = [ow_kill(12.9, 1.0, 0.5), shot("t_a", 0, .3, .7), shot("t_a", 1, .3, .6), shot("t_a", 2, .3, .55),
             shot("t_c", 0, .35, .6), shot("t_c", 1, .3, .5), shot("t_d", 1, .3, .5), shot("t_d", 3, .3, .55), shot("s_f", 0, .3, .6),
             strike("t_e", .3, .5), shot("t_f", 1, .25, .5), shot("t_d", 0, .4, .6), shot("t_f", 0, .4, .6)]
    keep = {0, 3, 7, 9}      # the strongest kills keep flash, shake and slow-motion; the rest are plain cuts
    for i, d in enumerate(chain):
        if i not in keep:
            for k in ("flash", "shake", "slow"):
                d.pop(k, None)
    sc += chain
    sc.append(S("t_e", 4.6, 2.0, punch={"from": 1.0, "to": 1.05}, cards=[card("ONE MORE *RUN.*", 0.4, 1.5, pos="mid", size=150, sfx=False)]))
    sc.append(END(4.0)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 0}]
    return sc, loop_start, t_logo


main, loop_start, t_logo = build_main()
tot, rows = timeline(main, "main")
print("loop start", round(loop_start, 2), "logo", round(t_logo, 2))
for r in rows:
    print("  ", r)
m, env, syn = music_cfg(3.0, loop_start, t_logo)
write("rubblefront-v5", "rubblefront-v5", {"16x9": "rubblefront-trailer-v5-16x9.mp4"}, main, "16x9", m, env, syn, poster={"file": "rubblefront-poster-v5.png", "at": 3.3})


# ================================================================== 30 s
def build_30():
    sc = [shot("s_a", 0, 2.58, 0.9, cards=[card("TURN-BASED\n*TACTICS.*", 0.2, 2.0, pos="top", size=92, sfxDb=-3)], slow=False)]
    sc[-1]["hits"] = [{"at": t, "kind": "tick", "gain_db": -4} for t in (0.5, 1.0, 1.5, 2.0, 2.5)]
    sc.append(shot("s_a", 1, 0.6, 1.5, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 0.0, 2.0)]))
    sc.append(shot("s_c", 1, 0.9, 1.1, cards=[card("FLANK FOR\nTHE *KILL.*", 0.0, 2.0)]))
    sc.append(S("k_spoils", 3.3, 0.9, cards=[card("PICK ONE\nOF *THREE.*", 0.0, 1.0)]))
    sc.append(S("k_hub", 3.0, 1.6, crop={"x": 0.5, "y": 0.0, "s": 1.22}, cards=[card("SPEND SALVAGE\nON *BUILDINGS.*", 0.0, 1.6)]))
    sc.append(shot("s_g1", 0, 1.2, 0.8, cards=[card("EARLY *SQUAD.*", 0.0, 1.6)]))
    sc.append(shot("s_g3", 0, 1.2, 0.8, cards=[card("UPGRADED *SQUAD.*", 0.0, 1.6)]))
    t = sum(x["dur"] for x in sc)
    want = math.ceil(t + 1.5)
    if want % 2 == 0:
        want += 1
    sc[-1]["dur"] = round(sc[-1]["dur"] + (want - 1.5 - t), 3)
    e = strike("s_e", 1.5, 1.0)
    e["logo"] = {"at": 1.5, "dur": 1.0}
    sc.append(e)
    t_logo = sum(x["dur"] for x in sc[:-1]) + 1.5
    sc.append(ow_kill(6.4, 2.2, 1.25, [card("HOLD. WAIT.\n*AMBUSH.*", 0.0, 2.2)]))
    for a in (shot("t_a", 0, .3, .7), shot("t_c", 1, .3, .6), strike("t_e", .3, .5), shot("t_f", 1, .25, .5)):
        sc.append(a)
    sc.append(S("t_e", 4.6, 2.2, punch={"from": 1.0, "to": 1.05}, cards=[card("ONE MORE *RUN.*", 0.4, 1.5, pos="mid", size=150, sfx=False)]))
    sc.append(END(3.2)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 0}]
    return sc, t_logo


s30, t30 = build_30()
tot30, rows30 = timeline(s30, "30s")
print("logo", t30)
m, env, syn = music_cfg(3.0, sum(x["dur"] for x in s30[:5]), t30, 3.0)
write("rubblefront-v5-30s", "rubblefront-v5-30s", {"16x9": "rubblefront-trailer-v5-30s-16x9.mp4"}, s30, "16x9", m, env, syn)


# ================================================================== 15 s vertical (full-frame 1080x1920 captures, action centred above a caption strip)
def vshot(clip, i, pre, post, cards=None, **kw):
    d = shot(clip, i, pre, post, cards=cards, **kw)
    d["vclip"] = clip
    return d


def build_15():
    sc = [vshot("v_a", 0, 1.6, 0.9, cards=[card("TURN-BASED\n*TACTICS.*", 0.1, 2.3)], slow=False)]
    sc[-1]["hits"] = [{"at": t, "kind": "tick", "gain_db": -4} for t in (0.4, 0.9, 1.4)]
    sc.append(vshot("v_a", 1, 0.5, 1.4, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 0.0, 1.9)]))
    sc.append(vshot("v_a", 2, 0.5, 1.2, cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.7)]))
    d = vshot("v_g1", 0, 0.9, 0.7, cards=[card("EARLY *SQUAD.*", 0.0, 1.6)])
    sc.append(d)
    sc.append(vshot("v_g3", 0, 0.9, 0.7, cards=[card("UPGRADED *SQUAD.*", 0.0, 1.6)]))
    e = strike("v_e", 1.2, 1.1)
    e["vclip"] = "v_e"
    e["logo"] = {"at": 1.2, "dur": 1.0}
    sc.append(e)
    sc.append(vshot("v_a", 0, 0.3, 0.6, cards=[card("ONE MORE *RUN.*", 0.0, 0.9, pos="bottom")]))
    sc.append(END(2.5)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 0}]
    return sc


v15 = build_15()
tot15, _ = timeline(v15, "15s")
lt15 = sum(x["dur"] for x in v15[:5]) + 1.2
m, env, syn = music_cfg(1.5, sum(x["dur"] for x in v15[:3]), lt15, 2.0)
write("rubblefront-v5-15s", "rubblefront-v5-15s", {"9x16": "rubblefront-trailer-v5-15s-9x16.mp4"}, v15, "9x16", m, env, syn, crf=17)
