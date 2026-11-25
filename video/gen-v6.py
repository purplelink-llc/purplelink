#!/usr/bin/env python3
"""RubbleFront trailer v6 storyboards (main, 30 s, 15 s vertical), cut from the 2026-11-25 captures of the redesigned game.
Cut points come from the capture logs: each clip's fire marks (frame / 30 = seconds) and the game's own log lines (hit, miss, destroyed),
so flash, shake and slow-motion sit only on real kills. The k_* helper captures keep fire marks but no game log, so they get a hit
sound and never a flash. Run: python3 gen-v6.py"""
import json, re, math
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "storyboards"
FL = Path("/Volumes/Extreme SSD/RubbleFront/build/trailer")
END_LINES = ["Spring 2027", "rubblefront.com", "A Purplelink LLC game"]
IMPACT = 0.68     # v6: seconds from the Fire press to the hit (and the death burst) on screen; measured on s_c and t_c
IMPACT_B = 0.65   # v6 --blast captures: the explosion plays about 0.65 s after Fire (measured on o_a)
STRIKE_HIT = 3.2  # s_e and t_e: the artillery explosions land 3.2 s into the clip (rout counter 7 -> 2 in the HUD)
FLASH = lambda at: [{"at": round(at, 3), "dur": 0.07, "amp": 0.85, "color": "#fff6e6", "sfx": "hit"}]
SHAKE = lambda at, amp=16: [{"at": round(at, 3), "amp": amp, "dur": 0.35, "zoom": 0.03}]
WHIP = {"kind": "whip"}


def parse(clip, sub="v6"):
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
    c = {"text": text, "at": at, "dur": dur, "pos": pos, "sfxDb": -4.5}
    c.update(kw)
    return c


def S(clip, src, dur, **kw):
    d = {"clip": clip, "in": round(max(0.0, src), 3), "dur": round(dur, 3), "v": {"cx": 960, "cy": 540, "s": 1.0}}
    d.update(kw)
    return d


def _impact(d, imp, kill, slow=True):
    if kill:
        d["flash"] = FLASH(imp)
        d["shake"] = SHAKE(imp)
        if slow:
            d["slow"] = [{"at": round(imp - 0.02, 3), "dur": 0.42, "speed": 0.4}]
    return d


def shot(clip, i, pre, post, cards=None, slow=True, blast=False, **kw):
    """One fired shot: `pre` seconds of lineup before Fire, `post` after. Flash, shake and slow-motion only if the game's log says destroyed."""
    s = info(clip, i)
    imp = pre + (IMPACT_B if blast else IMPACT)
    d = S(clip, s["fire"] - pre, pre + post, **kw)
    _impact(d, imp, s["kill"], slow)
    if not s["kill"] and not s["miss"]:
        d["hits"] = [{"at": round(imp, 3), "kind": "tick", "gain_db": 0}]
    if cards:
        d["cards"] = cards
    d["_kill"], d["_miss"], d["_impact"] = s["kill"], s["miss"], imp
    return d


def strike(clip, pre, post, cards=None, **kw):
    d = S(clip, STRIKE_HIT - pre, pre + post, **kw)
    d["flash"] = FLASH(pre)
    d["shake"] = SHAKE(pre, 20)
    d["slow"] = [{"at": round(pre - 0.02, 3), "dur": 0.5, "speed": 0.4}]
    if cards:
        d["cards"] = cards
    d["_kill"] = True
    return d


def kclip(clip, impact_src, dur=0.9, lead=0.3):
    """A helper capture with no game log: cut so the hit lands `lead` s in, with a hit sound, never a flash."""
    return S(clip, impact_src - lead, dur, hits=[{"at": lead, "kind": "hit", "gain_db": -3}])


def fit(d, dur):
    """Shorten a shot to `dur` by trimming the lineup from the start; flash, shake, slow and hits move with it."""
    cut = d["dur"] - dur
    if cut > 0:
        d["in"] = round(d["in"] + cut, 3)
        for k in ("flash", "shake", "slow", "hits", "cards"):
            for e in d.get(k, []):
                e["at"] = round(e["at"] - cut, 3)
            if k in d:
                d[k] = [e for e in d[k] if e["at"] >= 0]
    d["dur"] = round(dur, 3)
    return d


def calm(d):
    for k in ("flash", "shake", "slow"):
        d.pop(k, None)
    return d


END = lambda d: {"type": "end", "dur": d, "lines": END_LINES}
tot = lambda sc: sum(x["dur"] for x in sc)


def timeline(sc, label):
    t = 0.0
    print(label, "total", round(tot(sc), 2), "scenes", len(sc))
    for i, x in enumerate(sc):
        cs = " / ".join(c["text"].replace("\n", " ") for c in x.get("cards", []))
        print(f"   {i:2d} {t:6.2f} {x['dur']:5.2f} {x.get('clip', x.get('type')):15s} in={x.get('in', '')} {cs}")
        t += x["dur"]


def clean(sc):
    for x in sc:
        for k in [k for k in x if k.startswith("_")]:
            x.pop(k)
    return sc


def write(name, outputs, scenes, fmt, music, env, syn, poster=None, crf=16):
    d = {"id": name, "outputs": outputs, "formats": [fmt], "crf": crf, "sfxDb": -6, "music": music, "synth": syn, "scenes": clean(scenes),
         "wishlistText": "Wishlist on Steam"}
    if env:
        d["musicEnv"] = env
    if poster:
        d["poster"] = poster
    (OUT / f"{name}.json").write_text(json.dumps(d, indent=1))


def music_cfg(t_kill1, t_loop, t_logo, fade=3.5, fin0=None, t_end=None):
    """Quiet low track and ticks until the first kill; mid + drive from the kill (drop 1); a build under the run loop; a dip and a boom at
    the logo (drop 2, high + drive); the fastest cuts on high + drive. On the 120 bpm grid: downbeats fall on kill1 + 2k."""
    m = [{"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": t_kill1 + 0.4, "gain_db": -9, "fade_in": 1.0, "fade_out": 0.3}]

    def seg(f, a, b, g=0.0, fo=0.25):
        m.append({"file": f, "in": a - t_kill1, "t": a, "dur": b - a, "gain_db": g, "fade_in": 0.02, "fade_out": fo})
    seg("battle_mid.ogg", t_kill1, t_logo, 0.0, 0.02)
    seg("battle_mid_drive.ogg", t_kill1, t_loop, 2.0)
    seg("battle_high.ogg", t_logo, t_logo + 100, 3.0, fade)
    seg("battle_high_drive.ogg", t_logo, t_logo + 100, 5.0, fade)
    b0 = max(t_kill1 + 4.0, t_logo - 8.0)
    env = [{"t": 0, "db": 0}, {"t": b0, "db": -11}, {"t": t_logo - 0.34, "db": -3}, {"t": t_logo - 0.3, "db": -12}, {"t": t_logo - 0.02, "db": -12},
           {"t": t_logo, "db": 6}, {"t": t_logo + 1.8, "db": -1}]
    syn = [{"t": t_kill1, "kind": "riser", "dur": 2.4, "gain_db": -3}, {"t": t_logo - 0.04, "kind": "riser", "dur": t_logo - 0.04 - b0, "gain_db": -14}]
    if fin0:
        env += [{"t": fin0 - 0.05, "db": 0}, {"t": fin0 + 1.0, "db": 4.0}]
        if t_end:
            syn.append({"t": t_end, "kind": "riser", "dur": t_end - fin0, "gain_db": -8})
    return m, env, syn


# ================================================================== shot library
def opening(title_dur=1.3, push=1.25):
    """The camera's own push-in from the whole board to the fight, slowed, under the genre title; then a whip into the first kill."""
    a = S("o_a", 0.07, push, slow=[{"at": 0.0, "dur": push, "speed": 0.6}],     # frame 0 of the capture is black; start on frame 2
          title={"text": "Turn-based tactics", "at": 0.0, "dur": title_dur},
          hits=[{"at": t, "kind": "tick", "gain_db": -6} for t in (0.5, 1.0, 1.5) if t < push])
    b = shot("o_a", 0, 0.95, 1.05, blast=True, glint=WHIP)        # log: Tank 78%, destroyed (and the walls are damaged)
    return [a, b]


def cover():
    return shot("o_a", 1, 0.8, 1.75, blast=True, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 1.5, 1.05)])   # log: walls reduced to rubble


def odds():
    return shot("t_c", 0, 1.15, 0.85, glint=WHIP, crop={"x": 0.5, "y": 0.42, "s": 1.12},
                cards=[card("EVERY SHOT HAS *ODDS.*", 0.0, 1.95)])     # 73%, hit for 8, return fire


def heavy():
    return [shot("s_d", 0, 1.1, 0.75, cards=[card("ONE HEAVY TANK.\n*FOUR SHOTS.*", 0.0, 1.8)]),   # 80% hit for 29
            shot("s_d", 1, 0.45, 0.85),        # 90%: miss
            shot("s_d", 2, 0.3, 0.6),          # 85% hit for 3
            shot("s_d", 3, 0.45, 1.35)]        # 80%, destroyed


def ambush():
    """s_b: three units go on overwatch, the enemy walks in. First reaction shot (Tank 59%, destroyed) lands at 7.2 s of the clip."""
    a = S("s_b", 4.1, 1.9, glint=WHIP, cards=[card("SET AN\n*AMBUSH.*", 0.15, 1.75)])
    b = S("s_b", 6.45, 1.7)
    b["flash"], b["shake"] = FLASH(0.75), SHAKE(0.75)
    b["slow"] = [{"at": 0.73, "dur": 0.42, "speed": 0.4}]
    c = S("s_b", 9.75, 1.25, hits=[{"at": 0.3, "kind": "hit", "gain_db": -3}])   # Infantry 51% from overwatch, destroyed: "Kill 2"
    return [a, b, c]


def run_loop():
    """Win -> spoils (pick one of three from the quartermaster) -> the branching run map -> build the outpost -> a bigger army."""
    L = [S("k_spoils", 1.85, 1.05, glint=WHIP, cards=[card("PICK ONE\n*OF THREE.*", 0.0, 1.05, pos="top", size=72)]),                                                     # the game's own SPOILS OF WAR banner
         S("k_spoils", 2.95, 1.6, crop={"x": 0.5, "y": 0.52, "s": 1.18}),   # the three cards, no caption over the buttons
         S("k_spoils", 7.05, 1.5, insets=[{"clip": "h_runmap", "src": 0.8, "at": 0.1, "dur": 1.4, "crop": {"x": 70, "y": 165, "w": 1210, "h": 690},
                                            "x": 980, "y": 120, "w": 900}], cards=[card("THE MAP\n*BRANCHES.*", 0.0, 1.5, pos="left", size=78, strong=True)]),
         S("k_hub", 0.1, 1.5, cards=[card("BUILD THE\n*OUTPOST.*", 0.0, 1.5, pos="left", size=78, strong=True)]),
         S("k_hub", 5.45, 0.9),                                                                      # "Radar is built and ready"
         S("k_massive", 4.15, 2.6, crop={"x": 0.42, "y": 0.52, "s": 1.08}, hits=[{"at": 1.05, "kind": "tick", "gain_db": 0}],
           cards=[card("GROW THE\n*ARMY.*", 0.0, 0.8, pos="top")])]   # ten blue units on the board, then their next exchange (85%)   # "Can act: 10"
    return L


def build_main():
    sc = opening()
    t_kill1 = sc[0]["dur"] + sc[1]["_impact"]
    sc.append(cover())
    sc.append(odds())
    sc.append(shot("s_g1", 0, 0.8, 1.3, crop={"x": 0.5, "y": 0.45, "s": 1.1}, cards=[card("CRITICAL\n*HITS.*", 0.75, 1.35)]))   # 66% crit for 9, 1 HP left
    sc += heavy()
    sc += ambush()
    sc.append(shot("t_d", 0, 0.9, 1.6, glint=WHIP, cards=[card("THEY SHOOT\n*BACK.*", 0.85, 1.6)]))   # 68% miss; return fire leaves the Bazooka at 1 HP
    sc.append(shot("s_c", 1, 0.5, 1.2))      # Infantry 85%, destroyed
    sc.append(strike("s_e", 1.1, 1.4, glint=WHIP, cards=[card("CALL IN\n*ARTILLERY.*", 0.0, 1.05)]))
    loop_start = tot(sc)
    sc += run_loop()
    kill = shot("s_a", 2, 0.5, 1.0)        # infantry critical hit, destroyed: the bigger squad back in a fight
    sc.append(kill)
    # the logo lands on a downbeat: an odd number of seconds from 0 (kill1 + 2k with kill1 near 3.25); pad the last loop shot
    t = tot(sc)
    want = math.ceil(t + 1.5)
    if (want - round(t_kill1)) % 2:
        want += 1
    kill["dur"] = round(kill["dur"] + (want - 1.5 - t) + (t_kill1 - round(t_kill1)), 3)
    e = strike("t_e", 1.35, 1.4)     # the blast lands 0.15 s before the logo, so it reads before the slam
    e["logo"] = {"at": 1.5, "dur": 1.15}
    sc.append(e)
    t_logo = tot(sc[:-1]) + 1.5
    sc.append(shot("t_f", 0, 0.75, 1.6, cards=[card("SOMETIMES\nIT *MISSES.*", 0.75, 1.5)]))   # Bazooka 56%: miss, takes 5 back
    fin0 = tot(sc)
    chain = [shot("t_a", 0, .35, .65), kclip("k_desert_combo", 6.83 + IMPACT), shot("t_c", 1, .35, .65), kclip("k_snow_ow", 6.5),
             kclip("k_ruins_cover", 2.7 + IMPACT), shot("s_a", 0, .3, .6), kclip("k_ruins_aim", 3.7 + IMPACT), kclip("k_snow_flank", 3.37 + IMPACT),
             kclip("k_titan", 11.93 + IMPACT), kclip("k_combo", 2.87 + IMPACT)]
    for d, du in zip(chain, [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55]):
        fit(d, du)
    for i, d in enumerate(chain):
        if i not in (0, 2):
            calm(d)
            d.setdefault("hits", [{"at": 0.02, "kind": "hit", "gain_db": -3}])
    last = shot("t_d", 3, 0.4, 2.75, cards=[card("ONE MORE *RUN.*", 1.0, 1.4, pos="mid", size=150, sfx=False)])   # Bazooka 77% crit, Heavy Tank destroyed
    chain.append(last)
    sc += chain
    t_end = tot(sc)
    sc.append(END(4.8)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    return sc, t_kill1, loop_start, t_logo, fin0, t_end


def gen_main():
    main, k1, loop_start, t_logo, fin0, t_end = build_main()
    timeline(main, "main")
    print("kill1", round(k1, 2), "loop", round(loop_start, 2), "logo", round(t_logo, 2), "finale", round(fin0, 2), "end", round(t_end, 2))
    m, env, syn = music_cfg(k1, loop_start, t_logo, fin0=fin0, t_end=t_end)
    import copy
    write("rubblefront-v6", {"16x9": "rubblefront-trailer-v6-16x9.mp4"}, copy.deepcopy(main), "16x9", m, env, syn,
          poster={"file": "rubblefront-poster-v6.png", "at": 3.5})
    wl = copy.deepcopy(main)
    wl[-1]["wishlist"] = True
    write("rubblefront-v6-wishlist", {"16x9": "rubblefront-trailer-v6-wishlist-16x9.mp4"}, wl, "16x9", m, env, syn)


# ================================================================== 30 s
def build_30():
    sc = opening()
    k1 = sc[0]["dur"] + sc[1]["_impact"]
    sc.append(cover())
    sc.append(odds())
    loop0 = tot(sc)
    sc.append(S("k_spoils", 2.95, 1.3, glint=WHIP, crop={"x": 0.5, "y": 0.4, "s": 1.12}, cards=[card("PICK ONE\n*OF THREE.*", 0.05, 1.2, pos="floor", size=72)]))
    hub = S("k_hub", 0.1, 1.3, cards=[card("BUILD THE\n*OUTPOST.*", 0.0, 1.3, pos="left", size=78, strong=True)])
    sc.append(hub)
    sc.append(S("k_massive", 4.15, 1.6, crop={"x": 0.42, "y": 0.52, "s": 1.08}, cards=[card("GROW THE\n*ARMY.*", 0.0, 1.5)]))
    t = tot(sc)
    want = math.ceil(t + 1.5)
    if (want - round(k1)) % 2:
        want += 1
    hub["dur"] = round(hub["dur"] + (want - 1.5 - t) + (k1 - round(k1)), 3)
    e = strike("t_e", 1.35, 1.25)
    e["logo"] = {"at": 1.5, "dur": 1.05}
    sc.append(e)
    t_logo = tot(sc[:-1]) + 1.5
    amb = ambush()[1]
    amb["cards"] = [card("SET AN\n*AMBUSH.*", 0.0, 1.7, sfx=False)]
    sc.append(amb)
    fin0 = tot(sc)
    ch = [shot("t_a", 0, .3, .6), kclip("k_snow_ow", 6.5, .8), kclip("k_desert_combo", 6.83 + IMPACT, .75)]
    for d in ch[1:]:
        calm(d)
    ch.append(shot("t_d", 3, 0.4, 1.9, cards=[card("ONE MORE *RUN.*", 0.9, 1.35, pos="mid", size=150, sfx=False)]))
    sc += ch
    t_end = tot(sc)
    sc.append(END(3.2)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    return sc, k1, loop0, t_logo, fin0, t_end


def gen_30():
    s30, k1, loop0, t_logo, fin0, t_end = build_30()
    timeline(s30, "30s")
    print("logo", round(t_logo, 2))
    m, env, syn = music_cfg(k1, loop0, t_logo, 3.0, fin0=fin0, t_end=t_end)
    write("rubblefront-v6-30s", {"16x9": "rubblefront-trailer-v6-30s-16x9.mp4"}, s30, "16x9", m, env, syn)


# ================================================================== 15 s vertical (1024x1730 portrait captures, drawn undistorted)
def v(d, clip):
    d["vclip"] = clip
    return d


def build_15():
    a = v(S("v2_ob", 0.0, 1.2, slow=[{"at": 0.0, "dur": 1.2, "speed": 0.5}], title={"text": "Turn-based tactics", "at": 0.05, "dur": 1.15},
            hits=[{"at": 0.5, "kind": "tick", "gain_db": -6}]), "v2_ob")
    b = v(shot("v2_ob", 0, 0.9, 1.0, blast=True, glint=WHIP), "v2_ob")
    k1 = a["dur"] + b["_impact"]
    c = v(shot("v2_ob", 1, 0.8, 1.6, blast=True, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 1.35, 1.05)]), "v2_ob")
    g1 = v(shot("v2_g1", 0, 0.9, 0.8, glint=WHIP, cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.7)]), "v2_g1")
    e = v(shot("v2_a", 2, 0.9, 1.4), "v2_a")      # infantry crit, destroyed; the logo sits on the kill
    e["logo"] = {"at": e["_impact"], "dur": 1.1}
    sc = [a, b, c, g1, e]
    t_logo = tot(sc[:-1]) + e["_impact"]
    sc.append(v(shot("v2_a", 0, 0.3, 1.2, slow=False, cards=[card("ONE MORE *RUN.*", 0.1, 1.3, sfx=False)]), "v2_a"))
    t_end = tot(sc)
    sc.append(END(2.6)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    return sc, k1, t_logo, t_end


def gen_15():
    v15, k1, t_logo, t_end = build_15()
    timeline(v15, "15s")
    m, env, syn = music_cfg(k1, k1 + 2.0, t_logo, 2.0)
    write("rubblefront-v6-15s", {"9x16": "rubblefront-trailer-v6-15s-9x16.mp4"}, v15, "9x16", m, env, syn, crf=17)


if __name__ == "__main__":
    gen_main()
    gen_30()
    gen_15()
