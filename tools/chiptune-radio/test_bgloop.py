"""Checks for the pre-rendered background loops: python3.12 -m pytest -q test_bgloop.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import bgloop
import longform as lf
import themes

sys.path.insert(0, str(Path(__file__).resolve().parent / "blender"))
import skyway_geom as G  # noqa: E402

N = 6


def make_loop(root: Path, name: str = "racer-highway-v1") -> Path:
    pal = np.array(bgloop.SEED_COLOURS + [(20 + 5 * i, 10, 40 + 3 * i) for i in range(bgloop.PALETTE_SIZE - len(bgloop.SEED_COLOURS))], dtype=np.uint8)
    rng = np.random.default_rng(1)
    idx = rng.integers(0, len(pal), (N, G.H, G.W)).astype(np.uint8)
    depth = np.full((N, G.H, G.W), 120, dtype=np.uint8)
    depth[:, :70] = G.DEPTH_SKY
    rows = [G.road_rows(n * G.FRAMES // N) for n in range(N)]
    bend = bgloop.smooth_bend(G.bends())[:: G.FRAMES // N][:N]
    bgloop.write_loop(root / name, idx, pal, depth, np.stack([r[0] for r in rows]), np.stack([r[1] for r in rows]), np.stack([r[2] for r in rows]),
                      bend, G.horizon_row(), {"seam_rms": 0.0, "test": True})
    return root / name


@pytest.fixture
def loop_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENT_LOOPS", str(tmp_path))
    monkeypatch.delenv("AMBIENT_BG", raising=False)
    bgloop._CACHE.clear()
    make_loop(tmp_path)
    yield tmp_path
    bgloop._CACHE.clear()


def test_the_road_repeats_exactly_once_a_loop():
    (x0, y0, _), yaw0 = G.camera(0)
    (x9, y9, _), yaw9 = G.camera(G.FRAMES)
    assert abs(x9 - x0) < 1e-6 and abs(y9 - y0 - G.L) < 1e-6 and abs(yaw9 - yaw0) < 1e-9
    assert 74 < G.horizon_row() < 78
    cx, hw, dz = G.road_rows(0)
    assert np.isnan(cx[:70]).all() and np.isfinite(cx[100:]).all()
    assert (np.diff(hw[100:]) > 0).all() and (np.diff(dz[100:]) < 0).all()     # wider and nearer towards the bottom
    b = bgloop.smooth_bend(G.bends())
    assert len(b) == G.FRAMES and np.abs(b).max() <= 1.0
    assert abs(float(b[0]) - float(b[-1])) < 0.05                               # the smoothing wraps round, so the lean has no seam either


def test_depth_codes_round_trip_and_mark_the_sky():
    d = np.array([0.5, 3.0, 40.0, 900.0, np.inf])
    q = G.depth_code(d)
    assert q[-1] == G.DEPTH_SKY and (q[:-1] < G.DEPTH_SKY).all()
    back = G.depth_of_code(q)
    assert np.isinf(back[-1]) and np.allclose(back[:-1], d[:-1], rtol=0.03)
    assert np.allclose(G.tone(G.untone(np.array([0.01, 0.2, 0.7]))), [0.01, 0.2, 0.7])


def test_the_sky_repeats_with_the_loop():
    sky = bgloop.Sky()
    assert np.array_equal(sky.frame(0), sky.frame(G.FRAMES))
    assert not np.array_equal(sky.frame(0), sky.frame(200))                    # the stars slide as the camera turns


def test_palette_keeps_the_racer_colours_and_quantises_to_them():
    rng = np.random.default_rng(0)
    pix = rng.integers(0, 256, (2000, 3)).astype(np.uint8)
    pal = bgloop.build_palette(pix)
    assert pal.shape == (bgloop.PALETTE_SIZE, 3)
    assert {tuple(c) for c in bgloop.SEED_COLOURS} <= {tuple(int(v) for v in c) for c in pal}
    img = rng.uniform(0, 255, (8, 12, 3))
    idx = bgloop.quantise(img, pal, bgloop.srgb8_to_oklab(pal.astype(float)), bgloop.palette_step(pal))
    assert idx.shape == (8, 12) and idx.max() < len(pal)
    assert bgloop.snap((255, 60, 150), pal) == (255, 60, 150)


def test_load_checks_the_hash_and_caches(loop_root):
    lp = bgloop.load("racer-highway-v1")
    assert lp.frames == N and lp.rgb(N + 1).shape == (G.H, G.W, 3)
    assert bgloop.load("racer-highway-v1") is lp
    assert lp.sky(0)[:70].all() and not lp.sky(0)[100:].any()
    bgloop._CACHE.clear()
    man = json.loads((loop_root / "racer-highway-v1" / "manifest.json").read_text())
    man["sha256"] = "0" * 64
    (loop_root / "racer-highway-v1" / "manifest.json").write_text(json.dumps(man))
    with pytest.raises(ValueError):
        bgloop.load("racer-highway-v1")


def test_racer_on_a_loop_draws_only_palette_colours(loop_root):
    th = themes.get("racer")(seed=3, seconds=3600, options={})
    assert th.loop is not None and th.background.startswith("racer-highway-v1@")
    pal = {tuple(int(v) for v in c) for c in th.loop.palette}
    times = [10.0] + [e[0] + e[2] * 0.5 for e in th.events[:12]]                # some inside a boost, a rival and a shooting star
    kinds = {e[1] for e in th.events[:12]}
    assert {"boost", "rival"} <= kinds
    for t in times:
        im = th.frame(t)
        assert im.size == (G.W, G.H) and im.mode == "RGB"
        cols = {tuple(c) for c in np.asarray(im).reshape(-1, 3)}
        assert cols <= pal, f"t={t}: {len(cols - pal)} colours outside the palette"
    a, b = np.asarray(th.frame(10.0)), np.asarray(th.frame(10.0 + N / 30))
    assert np.array_equal(a[:130], b[:130])                                     # the loop has come round; only the craft's bob differs


def test_code_background_is_unchanged_by_the_loop(loop_root, monkeypatch):
    monkeypatch.setenv("AMBIENT_BG", "code")
    th = themes.get("racer")(seed=3, seconds=600)
    assert th.loop is None and th.background == "code"
    th2 = themes.get("racer")(seed=3, seconds=600, options={"bg": "code"})
    assert th.frame(42.0).tobytes() == th2.frame(42.0).tobytes()


def test_longform_reads_the_switch_once_and_refuses_what_does_not_apply(loop_root, tmp_path):
    out = tmp_path / "f.png"
    lf.main(["--theme", "racer", "--seconds", "60", "--no-music", "--preview-frame", "5", "--out", str(out)])
    assert Image.open(out).size == lf.VIDEO_SIZE
    with pytest.raises(SystemExit, match="loop-min"):
        lf.main(["--theme", "racer", "--hours", "1", "--loop-min", "10", "--out", str(tmp_path / "x.mp4")])
    lf.main(["--theme", "campfire", "--seconds", "60", "--no-music", "--preview-frame", "5", "--out", str(out)])   # other themes never look


def test_a_missing_loop_stops_before_any_work(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENT_LOOPS", str(tmp_path / "none"))
    monkeypatch.delenv("AMBIENT_BG", raising=False)
    bgloop._CACHE.clear()
    with pytest.raises(SystemExit, match="not built"):
        lf.main(["--theme", "racer", "--seconds", "60", "--out", str(tmp_path / "x.mp4")])
    assert not (tmp_path / "x.mp4.work").exists()


def test_thumbnail_tool_uses_the_loop(loop_root, tmp_path):
    import longform_pub as pub
    p = pub.make_thumbnail("racer", 3600, 3, tmp_path / "t.png", {}, music=False)
    assert Path(p).exists()
