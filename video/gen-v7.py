#!/usr/bin/env python3
"""RubbleFront trailer v7: the story cut. Cinematic plates (the game's own art with the interface hidden, slow camera moves,
letterbox) tell the arc: you hold an outpost, the war is out there, every fight is turn by turn with odds, each run is a new road,
the fallen stay fallen, what comes home builds the base, and the war gets bigger.
Cut points come from the capture logs as in v6: flash, shake and slow-motion only where the game log says "destroyed".
Clips: build/trailer/v7/clips (cine captures, batch-v7.sh) and v6/clips (HUD proof shots). Run: python3 gen-v7.py [open]"""
import copy, json, math, re, sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "storyboards"
FL = Path("/Volumes/Extreme SSD/RubbleFront/build/trailer")
END_LINES = ["Spring 2027", "rubblefront.com", "A Purplelink LLC game"]
IMPACT = 0.68     # seconds from the Fire press to the hit on screen (v6, measured on s_c and t_c)
IMPACT_B = 0.65   # --blast captures (v6)
IMPACT_CLIP = {"a_open": 0.76}   # v7 a_open measured frame by frame: the burst starts 22-23 frames after Fire (the Bazooka round is slower)
STRIKE_HIT = 3.2  # v6 s_e / t_e: the artillery lands 3.2 s into the clip
FLASH = lambda at: [{"at": round(at, 3), "dur": 0.07, "amp": 0.85, "color": "#fff6e6", "sfx": "hit"}]
SHAKE = lambda at, amp=16: [{"at": round(at, 3), "amp": amp, "dur": 0.35, "zoom": 0.03}]
WHIP = {"kind": "whip"}
BAR = 112          # letterbox bar height (px of 1080): the picture inside is about 2.4:1


def log_path(clip):
    for sub in ("v7", "v6"):
        f = FL / sub / "raw" / f"{clip}.log"
        if f.exists():
            return f
    return None


def parse(clip):
    """-> [{fire: s, text: first fire log line}] from the capture log (frame / 30 = seconds in the clip)."""
    f = log_path(clip)
    shots, cur = [], None
    if f is None:
        return shots
    for l in f.read_text(errors="ignore").splitlines():
        m = re.match(r"MARK fire frame (\d+)", l)
        if m:
            cur = {"fire": int(m.group(1)) / 30.0, "text": ""}
            shots.append(cur)
        elif l.startswith("LOG ") and cur is not None and not cur["text"] and " fires at " in l:
            cur["text"] = l[4:]
    return shots


def mark(clip, name):
    f = log_path(clip)
    for l in f.read_text(errors="ignore").splitlines():
        m = re.match(rf"MARK {name} frame (\d+)", l)
        if m:
            return int(m.group(1)) / 30.0
    raise KeyError(f"{clip}: no mark {name}")


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


def story(text, at=0.15, dur=2.0, **kw):
    """The narrative line: calm, lower third, no slam sound."""
    return card(text, at, dur, pos="story", sfx=False, **kw)


def S(clip, src, dur, **kw):
    d = {"clip": clip, "in": round(max(0.0, src), 3), "dur": round(dur, 3), "v": {"cx": 960, "cy": 540, "s": 1.0}}
    d.update(kw)
    return d


def plate(clip, src=0.4, dur=2.0, **kw):
    """A cine plate (no action): starts after the cine mark, with the grade and a little push of our own on top of the camera's."""
    kw.setdefault("grade", "cine")
    kw.setdefault("vig", 0.5)
    return S(clip, mark(clip, "cine") + src, dur, **kw)


def _impact(d, imp, kill, slow=True):
    if kill:
        d["flash"] = FLASH(imp)
        d["shake"] = SHAKE(imp)
        if slow:
            d["slow"] = [{"at": round(imp - 0.02, 3), "dur": 0.42, "speed": 0.4}]
    return d


def shot(clip, i, pre, post, cards=None, slow=True, blast=False, **kw):
    s = info(clip, i)
    imp = pre + IMPACT_CLIP.get(clip, IMPACT_B if blast else IMPACT)
    d = S(clip, s["fire"] - pre, pre + post, **kw)
    _impact(d, imp, s["kill"], slow)
    if not s["kill"] and not s["miss"]:
        d["hits"] = [{"at": round(imp, 3), "kind": "tick", "gain_db": 0}]
    if cards:
        d["cards"] = cards
    d["_kill"], d["_miss"], d["_impact"], d["_log"] = s["kill"], s["miss"], imp, s["text"]
    return d


def strike(clip, pre, post, hit=STRIKE_HIT, cards=None, **kw):
    """Artillery: the log has no "destroyed" line, so a boom only (no flash, shake or slow-motion)."""
    d = S(clip, hit - pre, pre + post, **kw)
    d["hits"] = [{"at": round(pre, 3), "kind": "boom", "gain_db": 0}]
    if cards:
        d["cards"] = cards
    d["_kill"] = False
    return d


def kclip(clip, impact_src, dur=0.9, lead=0.3):
    return S(clip, impact_src - lead, dur, hits=[{"at": lead, "kind": "hit", "gain_db": -3}])


def fit(d, dur):
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
        tag = "K" if x.get("_kill") else ("m" if x.get("_miss") else " ")
        print(f"   {i:2d} {t:6.2f} {x['dur']:5.2f} {tag} {x.get('clip', x.get('type')):12s} in={x.get('in', '')} {cs}")
        t += x["dur"]


def clean(sc):
    for x in sc:
        for k in [k for k in x if k.startswith("_")]:
            x.pop(k)
    return sc


def write(name, outputs, scenes, fmt, music, env, syn, bars=None, poster=None, crf=16):
    d = {"id": name, "outputs": outputs, "formats": [fmt], "crf": crf, "sfxDb": -6, "music": music, "synth": syn, "scenes": clean(scenes),
         "wishlistText": "Wishlist on Steam"}
    if env:
        d["musicEnv"] = env
    if bars:
        d["bars"] = bars
    if poster:
        d["poster"] = poster
    (OUT / f"{name}.json").write_text(json.dumps(d, indent=1))


def music_cfg(t_kill1, t_loop, t_logo, fade=3.5, fin0=None, t_end=None, intro_db=-9):
    """v6 music plan: low track until the first kill, mid + drive from it, a build to the logo, high + drive after it."""
    m = [{"file": "battle_low.ogg", "in": 44.0, "t": 0.0, "dur": t_kill1 + 0.4, "gain_db": intro_db, "fade_in": 1.0, "fade_out": 0.3}]

    def seg(f, a, b, g=0.0, fo=0.25):
        m.append({"file": f, "in": a - t_kill1, "t": a, "dur": b - a, "gain_db": g, "fade_in": 0.02, "fade_out": fo})
    seg("battle_mid.ogg", t_kill1, t_logo, 0.0, 0.02)
    seg("battle_mid_drive.ogg", t_kill1, t_loop, 2.0)
    seg("battle_high.ogg", t_logo, t_logo + 100, 3.0, fade)
    seg("battle_high_drive.ogg", t_logo, t_logo + 100, 5.0, fade)
    b0 = max(t_kill1 + 4.0, t_logo - 8.0)
    env = [{"t": 0, "db": 0}, {"t": b0, "db": -11}, {"t": t_logo - 0.34, "db": -3}, {"t": t_logo - 0.3, "db": -14}, {"t": t_logo - 0.02, "db": -14},
           {"t": t_logo, "db": 7}, {"t": t_logo + 1.8, "db": -1}]
    syn = [{"t": t_kill1, "kind": "riser", "dur": 2.4, "gain_db": -3}, {"t": t_logo - 0.04, "kind": "riser", "dur": t_logo - 0.04 - b0, "gain_db": -14}]
    if fin0:
        env += [{"t": fin0 - 0.05, "db": 0}, {"t": fin0 + 1.0, "db": 4.0}]
        if t_end:
            syn.append({"t": t_end, "kind": "riser", "dur": t_end - fin0, "gain_db": -8})
    return m, env, syn


def bars_for(sc, on):
    """Letterbox keyframes: bars on scenes whose index is in `on`, off elsewhere; 0.35 s eases at each change."""
    keys, t, prev = [], 0.0, None
    for i, x in enumerate(sc):
        v = BAR if i in on else 0
        if v != prev:
            if prev is None:
                keys.append({"t": 0.0, "v": v})
            else:
                keys += [{"t": round(t - 0.01, 3), "v": prev}, {"t": round(t + 0.35, 3), "v": v}]
            prev = v
        t += x["dur"]
    return keys


# ================================================================== the story
def act_open():
    """0-3 s: the genre line over a snow plate, then the first kill (the drop)."""
    a = plate("p_snow", 0.3, 1.5, title={"text": "Turn-based tactics", "sub": "Roguelike", "at": 0.0, "dur": 1.5, "y": 175},
              hits=[{"at": t, "kind": "tick", "gain_db": -6} for t in (0.5, 1.0)])
    b = shot("a_open", 0, 0.75, 1.05, blast=True, glint=WHIP, grade="cine")      # log: Tank 78%, destroyed (aim card shows 78%)
    return [a, b]


def act_base():
    """The outpost: an establishing push across the base."""
    return [plate("h_est", 0.5, 3.2, cards=[story("You hold a *forward outpost.*", 0.25, 2.8)])]


def act_war():
    """The world past the wire: four places, four weathers."""
    return [plate("p_desert", 0.4, 1.9, cards=[story("Past the wire, *the front.*", 0.15, 3.4)]),
            plate("p_night", 0.6, 1.5, grade="lift", vig=0.3),
            plate("p_rain", 0.4, 1.25, grade="cold"),
            plate("p_fog", 0.6, 1.15, grade="cold")]


def act_fight():
    """How a fight works: turn by turn, odds on every shot, cover breaks, heavies take focus, ambushes, artillery."""
    L = []
    L.append(shot("a_open", 1, 1.0, 1.75, blast=True, grade="cine", cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 1.45, 1.2)]))   # walls reduced to rubble
    L.append(shot("t_c", 0, 1.15, 0.85, glint=WHIP, crop={"x": 0.5, "y": 0.42, "s": 1.12},
                  cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.95)]))     # v6 HUD shot: the hit bubble, 73%, hit for 8
    d = [shot("a_d", 0, 1.1, 0.75, grade="cine", cards=[card("ONE HEAVY TANK.\n*FOUR SHOTS.*", 0.0, 1.8)]),
         shot("a_d", 1, 0.45, 0.85, grade="cine"),
         shot("a_d", 2, 0.3, 0.95, grade="cine"),
         shot("a_d", 3, 0.45, 1.8, grade="cine")]
    L += d
    # a_b: three units go on overwatch, the enemy walks in. Log: Tank 59% from overwatch, destroyed (hit on screen at 7.15 s of the clip,
    # checked frame by frame); Infantry 51% at the Scout, destroyed (9.6 s). Same events and frames as v6 s_b.
    amb = S("a_b", 4.3, 1.6, grade="cine", glint=WHIP, cards=[card("SET AN\n*AMBUSH.*", 0.1, 1.45)])
    hit = _impact(S("a_b", 6.45, 1.55, grade="cine"), 0.7, True)
    hit["_kill"], hit["_impact"] = True, 0.7
    L += [amb, hit]
    L.append(strike("s_e", 1.1, 1.4, glint=WHIP, cards=[card("CALL IN\n*ARTILLERY.*", 0.0, 1.05)]))
    return L


def act_run():
    """The roguelike loop, told plainly: a new road each run, spoils, the fallen stay fallen, the rest come home and build."""
    L = [S("m_runmap", 0.6, 2.0, crop={"x": 0.47, "y": 0.4, "s": 1.22, "to": {"x": 0.5, "y": 0.4, "s": 1.36}}, glint=WHIP,
           cards=[story("Every run, *a new road* to the front.", 0.1, 1.85)]),
         S("k_spoils", 2.95, 1.5, crop={"x": 0.5, "y": 0.52, "s": 1.14}, cards=[story("Win, and take *the spoils.*", 0.05, 1.4)]),
         # the roster proves named soldiers with their own health and rank; the one fallen card is half off screen, so no permadeath claim
         S("m_roster", 0.5, 1.7, crop={"x": 0.5, "y": 0.36, "s": 1.25, "to": {"x": 0.5, "y": 0.36, "s": 1.34}},
           cards=[story("Every soldier has *a name.*", 0.1, 1.55)]),
         S("h_l1", mark("h_l1", "go") + 1.45, 2.0, grade="cine", vig=0.5, cards=[story("Bring them home, *and build.*", 0.1, 2.9)]),
         # the outpost grows: level 1 and level 3 cut at the same moment of the same scripted camera move (a true before/after)
         S("h_l3", mark("h_l3", "go") + 1.45, 2.0, grade="cine", vig=0.5, glint=WHIP),
         S("k_massive", 4.15, 2.4, crop={"x": 0.42, "y": 0.52, "s": 1.08}, hits=[{"at": 1.05, "kind": "tick", "gain_db": 0}],
           cards=[card("FIELD\n*AN ARMY.*", 0.0, 0.9, pos="top")])]
    return L


def build_main():
    sc = act_open()
    t_kill1 = sc[0]["dur"] + sc[1]["_impact"]
    sc += act_base()
    sc += act_war()
    war_end = len(sc)
    sc += act_fight()
    loop_start = tot(sc)
    sc += act_run()
    run_end = len(sc)
    kill = shot("s_a", 2, 0.5, 1.0)        # infantry critical hit, destroyed: the bigger squad back in a fight
    sc.append(kill)
    t = tot(sc)
    want = math.ceil(t + 1.5)
    if (want - round(t_kill1)) % 2:
        want += 1
    extra = (want - 1.5 - t) + (t_kill1 - round(t_kill1))
    kill.clear(); kill.update(shot("s_a", 2, 0.5 + extra * 0.6, 1.0 + extra * 0.4))   # pad mostly before the shot: aim-up, not dead air after the hit
    e = strike("t_e", 1.35, 1.4)
    e["logo"] = {"at": 1.5, "dur": 1.15}
    sc.append(e)
    t_logo = tot(sc[:-1]) + 1.5
    fin0 = tot(sc)
    # finale: each cut opens 0.3 s before its impact (fire + 0.68 s), so the hit is always on screen
    hitcut = lambda clip, i, du, **kw: shot(clip, i, 0.3 - IMPACT, du - 0.3 + IMPACT, **kw)
    chain = [hitcut("a_g1", 0, 1.0, grade="cine"), hitcut("a_night", 1, 0.95), hitcut("t_c", 1, 0.9), hitcut("a_snow", 0, 0.85, grade="cine"),
             hitcut("a_f", 0, 0.8, grade="cold"), hitcut("a_snow", 2, 0.75, grade="cine"),
             kclip("k_titan", 11.93 + IMPACT, 0.65), kclip("k_combo", 2.87 + IMPACT, 0.6)]   # a_f: Bazooka 56% hit, return fire (no kill: tick only)
    for d in chain[6:]:
        calm(d)
    last = shot("t_d", 3, 0.4, 2.6, cards=[card("ONE MORE *RUN.*", 1.0, 1.4, pos="mid", size=150, sfx=False)])   # Bazooka 77% crit, Heavy Tank destroyed
    chain.append(last)
    sc += chain
    t_end = tot(sc)
    sc.append(END(4.6)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    # letterbox on the story plates (open, base, war) and the outpost shots of the run act; full frame for the fights and the finale
    on = set(range(0, war_end)) - {1}
    on |= {i for i, x in enumerate(sc) if x.get("clip") in ("h_l1", "h_l3", "m_runmap")}
    return sc, t_kill1, loop_start, t_logo, fin0, t_end, bars_for(sc, on)


def gen_main():
    main, k1, loop_start, t_logo, fin0, t_end, bars = build_main()
    timeline(main, "main")
    print("kill1", round(k1, 2), "loop", round(loop_start, 2), "logo", round(t_logo, 2), "finale", round(fin0, 2), "end", round(t_end, 2))
    m, env, syn = music_cfg(k1, loop_start, t_logo, fin0=fin0, t_end=t_end)
    write("rubblefront-v7", {"16x9": "rubblefront-trailer-v7-16x9.mp4"}, copy.deepcopy(main), "16x9", m, env, syn, bars=bars,
          poster={"file": "rubblefront-poster-v7.png", "at": 5.0})
    wl = copy.deepcopy(main)
    wl[-1]["wishlist"] = "Wishlist on Steam"
    write("rubblefront-v7-wishlist", {"16x9": "rubblefront-trailer-v7-wishlist-16x9.mp4"}, wl, "16x9", m, env, syn, bars=bars)


def gen_open():
    """The early style test: the first ~13 s (open, outpost, the war plates), cut to the end card."""
    sc = act_open()
    k1 = sc[0]["dur"] + sc[1]["_impact"]
    sc += act_base() + act_war()
    n = len(sc)
    sc.append(END(2.4))
    timeline(sc, "open-test")
    m, env, syn = music_cfg(k1, k1 + 8, tot(sc) - 2.4)
    write("rubblefront-v7-open", {"16x9": "rubblefront-v7-open-test.mp4"}, sc, "16x9", m, env, syn, bars=bars_for(sc, set(range(n)) - {1}))


# ================================================================== 30 s: the same story, one beat per act
def build_30():
    sc = act_open()
    t_kill1 = sc[0]["dur"] + sc[1]["_impact"]
    sc.append(plate("h_est", 0.5, 2.1, cards=[story("You hold a *forward outpost.*", 0.15, 1.9)]))
    sc.append(plate("p_desert", 0.4, 1.7, cards=[story("Past the wire, *the front.*", 0.1, 1.55)]))
    bars_n = len(sc)
    loop_start = tot(sc)
    sc.append(shot("t_c", 0, 1.15, 0.85, glint=WHIP, crop={"x": 0.5, "y": 0.42, "s": 1.12}, cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.95)]))
    sc.append(shot("a_open", 1, 1.0, 1.75, blast=True, grade="cine", cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 1.45, 1.2)]))
    sc.append(S("m_runmap", 0.6, 1.8, crop={"x": 0.47, "y": 0.4, "s": 1.22, "to": {"x": 0.5, "y": 0.4, "s": 1.34}}, glint=WHIP,
                cards=[story("Every run, *a new road* to the front.", 0.1, 1.65)]))
    sc.append(S("h_l1", mark("h_l1", "go") + 1.95, 1.2, grade="cine", vig=0.5, cards=[story("Bring them home, *and build.*", 0.1, 2.3)]))
    sc.append(S("h_l3", mark("h_l3", "go") + 1.95, 1.3, grade="cine", vig=0.5, glint=WHIP))
    kill = shot("s_a", 2, 0.5, 1.0)
    sc.append(kill)
    t = tot(sc)
    want = math.ceil(t + 1.5)
    if (want - round(t_kill1)) % 2:
        want += 1
    extra = (want - 1.5 - t) + (t_kill1 - round(t_kill1))
    kill.clear(); kill.update(shot("s_a", 2, 0.5 + extra * 0.6, 1.0 + extra * 0.4))   # pad mostly before the shot: aim-up, not dead air after the hit
    e = strike("t_e", 1.35, 1.3)
    e["logo"] = {"at": 1.5, "dur": 1.05}
    sc.append(e)
    t_logo = tot(sc[:-1]) + 1.5
    fin0 = tot(sc)
    hitcut = lambda clip, i, du, **kw: shot(clip, i, 0.3 - IMPACT, du - 0.3 + IMPACT, **kw)
    sc += [hitcut("a_night", 1, 0.9), hitcut("a_snow", 0, 0.8, grade="cine"), hitcut("a_f", 0, 0.7, grade="cold"),
           shot("t_d", 3, 0.4, 2.1, cards=[card("ONE MORE *RUN.*", 0.9, 1.35, pos="mid", size=150, sfx=False)])]
    t_end = tot(sc)
    sc.append(END(3.2)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    on = set(range(0, bars_n)) - {1}
    on |= {i for i, x in enumerate(sc) if x.get("clip") in ("h_l1", "h_l3", "m_runmap")}
    return sc, t_kill1, loop_start, t_logo, fin0, t_end, bars_for(sc, on)


def gen_30():
    sc, k1, loop_start, t_logo, fin0, t_end, bars = build_30()
    timeline(sc, "30s")
    print("kill1", round(k1, 2), "logo", round(t_logo, 2), "end", round(t_end, 2))
    m, env, syn = music_cfg(k1, loop_start, t_logo, 3.0, fin0=fin0, t_end=t_end)
    write("rubblefront-v7-30s", {"16x9": "rubblefront-trailer-v7-30s-16x9.mp4"}, sc, "16x9", m, env, syn, bars=bars)


# ================================================================== 15 s vertical: v6's portrait fight captures (drawn undistorted) plus the outpost before/after
def vc(d, clip):
    d["vclip"] = clip
    return d


def build_15():
    a = vc(S("v2_ob", 0.0, 1.2, slow=[{"at": 0.0, "dur": 1.2, "speed": 0.5}], title={"text": "Turn-based tactics", "sub": "Roguelike", "at": 0.05, "dur": 1.15, "vy": 1380},
             hits=[{"at": 0.5, "kind": "tick", "gain_db": -6}]), "v2_ob")
    b = vc(shot("v2_ob", 0, 0.9, 1.0, blast=True, glint=WHIP), "v2_ob")
    k1 = a["dur"] + b["_impact"]
    c = vc(shot("v2_ob", 1, 0.8, 1.6, blast=True, cards=[card("BLOW A HOLE IN\nTHEIR *COVER.*", 1.35, 1.05)]), "v2_ob")
    g1 = vc(shot("v2_g1", 0, 0.9, 0.8, glint=WHIP, cards=[card("EVERY SHOT\nHAS *ODDS.*", 0.0, 1.7)]), "v2_g1")
    l1 = S("h_l1", mark("h_l1", "go") + 1.95, 1.1, grade="cine", v={"cx": 900, "cy": 520, "s": 1.0}, cards=[card("COME HOME\nAND *BUILD.*", 0.05, 2.1)])
    l3 = S("h_l3", mark("h_l3", "go") + 1.95, 1.1, grade="cine", v={"cx": 900, "cy": 520, "s": 1.0}, glint=WHIP)
    e = vc(shot("v2_a", 2, 0.9, 1.4), "v2_a")      # infantry crit, destroyed; the logo sits on the kill
    e["logo"] = {"at": e["_impact"], "dur": 1.1}
    sc = [a, b, c, g1, l1, l3, e]
    t_logo = tot(sc[:-1]) + e["_impact"]
    sc.append(vc(shot("v2_a", 0, 0.3, 1.2, slow=False, cards=[card("ONE MORE *RUN.*", 0.1, 1.3, sfx=False)]), "v2_a"))
    t_end = tot(sc)
    sc.append(END(2.6)); sc[-1]["hits"] = [{"at": 0.0, "kind": "boom", "gain_db": 4}]
    return sc, k1, t_logo, t_end


def gen_15():
    sc, k1, t_logo, t_end = build_15()
    timeline(sc, "15s")
    m, env, syn = music_cfg(k1, k1 + 2.0, t_logo, 2.0)
    write("rubblefront-v7-15s", {"9x16": "rubblefront-trailer-v7-15s-9x16.mp4"}, sc, "9x16", m, env, syn, crf=17)


if __name__ == "__main__":
    if sys.argv[1:] == ["open"]:
        gen_open()
    elif sys.argv[1:] == ["30"]:
        gen_30()
    elif sys.argv[1:] == ["15"]:
        gen_15()
    else:
        gen_main()
