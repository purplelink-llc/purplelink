"""Blender scene for the racer's background loop: a four-lane night skyway that crosses a causeway over dark water, runs under lit gantries
and threads a canyon of towers, then joins itself after 30 s. Run by build_loop.sh, never imported by the video code:

    Blender -b --factory-startup --python racer_highway.py -- --assets DIR --out DIR --raw DIR [--frames 0-900] [--check] [--save-blend F]

Every frame is rendered at 1280x720 with a transparent sky and a depth pass, fogged by depth, averaged 4x4 to the 320x180 art grid and
saved as out/fNNNN.npz (premultiplied linear rgb, alpha, depth code); the EXR is deleted at once. Frames already in out/ are skipped, so
a crashed run resumes. The sky, planet, stars, glow and palette are added afterwards by bgloop.py.

Everything that repeats is built once in the "period" collection (one period of road and scenery, forward 0..L) and instanced at -L, 0
and +L, so frame 900 sees exactly what frame 0 saw, moved by L. Nothing in the scene animates on its own: no particles, physics or motion
blur, so the camera is the only thing that changes between frames.

Models: Kenney City Kit Commercial and City Kit Roads (CC0). Materials: ambientCG Concrete034, Facade001, MetalPlates006 (CC0). Lighting:
Poly Haven rogland_clear_night (CC0). See assets.json.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skyway_geom as G  # noqa: E402

SEED = 313
KC = "kenney/city-kit-commercial/x/Models/GLB format"
KR = "kenney/city-kit-roads/x/Models/GLB format"
NV = 12 * round(G.S / 24)          # road UV: V runs 0..NV over one period (about 2 m a unit); every pattern's period divides NV
N_POSTS = 36                       # light posts a period (about 50 m apart), alternating sides
N_PILLARS = 30


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--assets", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--raw", default="")
    p.add_argument("--frames", default="0-900")
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--check", action="store_true")
    p.add_argument("--save-blend", default="")
    return p.parse_args(a)


# ---------------------------------------------------------------- materials
def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return nt, out


def _img(nt, path, colour=True, box=False, scale=1.0, coord="UV"):
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    if not colour:
        tex.image.colorspace_settings.name = "Non-Color"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object" if box else coord], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    if box:
        tex.projection = "BOX"
        tex.projection_blend = 0.2
    return tex


def _math(nt, op, a, b=None, c=None):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    for i, x in enumerate((a, b, c)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            m.inputs[i].default_value = x
        else:
            nt.links.new(x, m.inputs[i])
    return m.outputs[0]


def _xyz(nt, space="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs[space], sep.inputs[0])
    return sep.outputs[0], sep.outputs[1], sep.outputs[2]


def _emit_mix(nt, out, bsdf, colour_socket, strength):
    """Principled BSDF with its emission colour and strength wired."""
    if colour_socket is not None:
        nt.links.new(colour_socket, bsdf.inputs["Emission Color"])
    if isinstance(strength, (int, float)):
        bsdf.inputs["Emission Strength"].default_value = strength
    else:
        nt.links.new(strength, bsdf.inputs["Emission Strength"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])


def mat_road(assets):
    """Wet violet concrete with lane dashes, solid inner edge lines; the kerbs are a separate material. UV: U lateral metres, V 0..NV."""
    m = bpy.data.materials.new("road")
    nt, out = _nodes(m)
    c = os.path.join(assets, "ambientcg/Concrete034/x/Concrete034_1K-JPG_Color.jpg")
    r = os.path.join(assets, "ambientcg/Concrete034/x/Concrete034_1K-JPG_Roughness.jpg")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs[0], sep.outputs[1]
    # concrete tiles every 4 V units (8 m) along and 8 m across: V scale 1/4 keeps it periodic, as NV is a multiple of 12
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", u, 1 / 8.0), comb.inputs[0])
    nt.links.new(_math(nt, "MULTIPLY", v, 1 / 4.0), comb.inputs[1])
    tcol = nt.nodes.new("ShaderNodeTexImage")
    tcol.image = bpy.data.images.load(c, check_existing=True)
    trou = nt.nodes.new("ShaderNodeTexImage")
    trou.image = bpy.data.images.load(r, check_existing=True)
    trou.image.colorspace_settings.name = "Non-Color"
    nt.links.new(comb.outputs[0], tcol.inputs[0])
    nt.links.new(comb.outputs[0], trou.inputs[0])
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1.0
    nt.links.new(tcol.outputs[0], tint.inputs[6])
    tint.inputs[7].default_value = (0.045, 0.035, 0.085, 1)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(tint.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(_math(nt, "MULTIPLY_ADD", trou.outputs[0], 0.45, 0.08), bsdf.inputs["Roughness"])   # wet: mostly glossy
    au = _math(nt, "ABSOLUTE", u)
    # centre dashes: |u| < 0.12 and V mod 6 < 2.5 (5 m dash, 12 m period); lane lines at |u| = LANE, same rhythm
    ph = _math(nt, "LESS_THAN", _math(nt, "FLOORED_MODULO", v, 6.0), 2.5)
    centre = _math(nt, "MULTIPLY", _math(nt, "LESS_THAN", au, 0.12), ph)
    lane = _math(nt, "MULTIPLY", _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", au, G.LANE)), 0.08), ph)
    edge = _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", au, G.ROAD_HW - 0.2)), 0.1)
    yellow = nt.nodes.new("ShaderNodeMix")
    yellow.data_type = "RGBA"
    nt.links.new(centre, yellow.inputs[0])
    yellow.inputs[6].default_value = (0.55, 0.5, 0.75, 1)                # lane and edge lines: pale violet
    yellow.inputs[7].default_value = (1.0, 0.7, 0.18, 1)                 # centre dashes: amber
    strength = _math(nt, "MULTIPLY", _math(nt, "MAXIMUM", _math(nt, "MAXIMUM", centre, lane), edge), 1.6)
    _emit_mix(nt, out, bsdf, yellow.outputs[2], strength)
    return m


def mat_kerb():
    """Magenta and white stripes, 2 m each (V period 2 units = 4 m), faintly lit."""
    m = bpy.data.materials.new("kerb")
    nt, out = _nodes(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    ph = _math(nt, "LESS_THAN", _math(nt, "FLOORED_MODULO", sep.outputs[1], 2.0), 1.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(ph, mix.inputs[0])
    mix.inputs[6].default_value = (0.85, 0.85, 1.0, 1)
    mix.inputs[7].default_value = (1.0, 0.08, 0.45, 1)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.4
    _emit_mix(nt, out, bsdf, mix.outputs[2], 0.9)
    return m


def mat_metal(assets, name="metal", tint=(0.35, 0.33, 0.45)):
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    base = os.path.join(assets, "ambientcg/MetalPlates006/x/MetalPlates006_1K-JPG_")
    col = _img(nt, base + "Color.jpg", box=True, scale=0.25)
    rou = _img(nt, base + "Roughness.jpg", colour=False, box=True, scale=0.25)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(col.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (*tint, 1)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(rou.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = 0.8
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def mat_rail():
    """The guard rail: dark metal with a cyan light every 8 m (V period 4) and a faint glowing top line."""
    m = bpy.data.materials.new("rail")
    nt, out = _nodes(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    dot = _math(nt, "LESS_THAN", _math(nt, "FLOORED_MODULO", sep.outputs[1], 4.0), 0.35)
    top = _math(nt, "GREATER_THAN", sep.outputs[0], 0.8)                  # U across the rail's height, 0..1
    s = _math(nt, "ADD", _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", dot, _math(nt, "GREATER_THAN", sep.outputs[0], 0.35)), 9.0),
              _math(nt, "MULTIPLY", top, 0.8))
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.03, 0.03, 0.05, 1)
    bsdf.inputs["Metallic"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Emission Color"].default_value = (0.25, 0.9, 1.0, 1)
    _emit_mix(nt, out, bsdf, None, s)
    return m


def mat_emit(name, colour, strength):
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*colour, 1)
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def mat_ground():
    """Dark ground with the racer's glowing violet grid: lines every 40 m across and every L/44 (40 m) along, so the grid repeats with
    the period. Object coordinates: the ground lives in the period collection, so every copy shows the same grid."""
    m = bpy.data.materials.new("ground")
    nt, out = _nodes(m)
    x, y, _ = _xyz(nt)
    def line(c, period):
        f = _math(nt, "FLOORED_MODULO", c, period)
        return _math(nt, "LESS_THAN", _math(nt, "MINIMUM", f, _math(nt, "SUBTRACT", period, f)), 0.35)
    g = _math(nt, "MAXIMUM", line(x, 40.0), line(y, G.L / 44))
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.012, 0.006, 0.03, 1)
    bsdf.inputs["Roughness"].default_value = 0.6
    bsdf.inputs["Emission Color"].default_value = (0.32, 0.06, 0.95, 1)
    _emit_mix(nt, out, bsdf, None, _math(nt, "MULTIPLY", g, 2.2))
    return m


def mat_water():
    """Black glossy water with ripples made of sines whose wavelengths along Y divide L, so the water joins at the seam too."""
    m = bpy.data.materials.new("water")
    nt, out = _nodes(m)
    x, y, _ = _xyz(nt)
    k1, k2 = 2 * math.pi * 440 / G.L, 2 * math.pi * 170 / G.L
    h = _math(nt, "ADD", _math(nt, "SINE", _math(nt, "MULTIPLY_ADD", y, k1, _math(nt, "MULTIPLY", x, 0.31))),
              _math(nt, "MULTIPLY", _math(nt, "SINE", _math(nt, "MULTIPLY_ADD", y, k2, _math(nt, "MULTIPLY", x, -0.53))), 0.6))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    nt.links.new(h, bump.inputs["Height"])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.004, 0.003, 0.012, 1)
    bsdf.inputs["Roughness"].default_value = 0.06
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def mat_tower(assets, src_image, lit=(1.0, 0.72, 0.4), lit2=(0.55, 0.38, 1.0), density=0.2, win=(0.075, 0.1), strength=5.0):
    """Night version of a Kenney building: its own colour map darkened and textured with ambientCG Facade001, plus lit windows laid on the
    walls in the model's own units (a lit or dark window chosen by a hash of its cell and the object, so every copy matches)."""
    m = bpy.data.materials.new("tower")
    nt, out = _nodes(m)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    base = nt.nodes.new("ShaderNodeTexImage")
    base.image = src_image
    fac = _img(nt, os.path.join(assets, "ambientcg/Facade001/x/Facade001_1K-JPG_Color.jpg"), box=True, scale=1.6)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(base.outputs[0], mix.inputs[6])
    nt.links.new(fac.outputs[0], mix.inputs[7])
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    dark.inputs[0].default_value = 1.0
    nt.links.new(mix.outputs[2], dark.inputs[6])
    dark.inputs[7].default_value = (0.22, 0.2, 0.32, 1)
    nt.links.new(dark.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45
    # windows on walls only (normal mostly horizontal); across = x + y in object units, up = z
    x, y, z = _xyz(nt)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    wall = _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", sepn.outputs[2]), 0.4)
    across = _math(nt, "ADD", x, y)
    cu = _math(nt, "FLOOR", _math(nt, "DIVIDE", across, win[0]))
    cz = _math(nt, "FLOOR", _math(nt, "DIVIDE", z, win[1]))
    fu = _math(nt, "FRACT", _math(nt, "DIVIDE", across, win[0]))
    fz = _math(nt, "FRACT", _math(nt, "DIVIDE", z, win[1]))
    shape = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", fu, 0.22), _math(nt, "LESS_THAN", fu, 0.78)),
                  _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", fz, 0.3), _math(nt, "LESS_THAN", fz, 0.75)))
    # the per-object seed is a custom property set by Kit.place, not Object Info > Random: Random is hashed with the collection
    # instance, so the copies at 0 and +L would light different windows and the loop would not join
    oi = nt.nodes.new("ShaderNodeAttribute")
    oi.attribute_type = "OBJECT"
    oi.attribute_name = "wseed"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(cu, comb.inputs[0])
    nt.links.new(cz, comb.inputs[1])
    nt.links.new(_math(nt, "MULTIPLY", oi.outputs["Fac"], 0.97), comb.inputs[2])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    nt.links.new(comb.outputs[0], wn.inputs["Vector"])
    on = _math(nt, "LESS_THAN", wn.outputs["Value"], density)
    hue = nt.nodes.new("ShaderNodeMix")
    hue.data_type = "RGBA"
    nt.links.new(_math(nt, "GREATER_THAN", wn.outputs["Color"], 0.8), hue.inputs[0])
    hue.inputs[6].default_value = (*lit, 1)
    hue.inputs[7].default_value = (*lit2, 1)
    s = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", on, shape), wall), strength)
    _emit_mix(nt, out, bsdf, hue.outputs[2], s)
    return m


# ---------------------------------------------------------------- geometry
def mesh_obj(name, verts, faces, coll, uvs=None, mat_index=None, mats=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(map(int, f)) for f in faces])
    if uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        loop_uv = np.zeros((len(me.loops), 2), dtype=np.float32)
        vi = np.zeros(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", vi)
        loop_uv[:] = np.asarray(uvs, dtype=np.float32)[vi]
        uv.data.foreach_set("uv", loop_uv.ravel())
    for m in mats:
        me.materials.append(m)
    if mat_index is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_index, dtype=np.int32))
    me.validate()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def road_strip(coll, mats):
    """One period of road: kerb, four lanes, kerb, as one mesh along the centre line from s = 0 to S, with UV U = lateral metres and
    V = 0..NV. Its two ends sit exactly on the period boundary, so the copies at -L and +L meet it edge to edge."""
    n = 1800
    s = np.linspace(0.0, G.S, n + 1)
    p = G.point(s)
    hd = G.heading(s)
    nx, ny = np.cos(hd), -np.sin(hd)
    lat = np.array([-G.EDGE, -G.ROAD_HW, G.ROAD_HW, G.EDGE])
    verts, uvs = [], []
    for i in range(n + 1):
        for a in lat:
            verts.append((p[i, 0] + nx[i] * a, p[i, 1] + ny[i] * a, 0.0))
            uvs.append((a, s[i] / G.S * NV))
    k = len(lat)
    faces, mi = [], []
    for i in range(n):
        for j in range(k - 1):
            a0, a1 = i * k + j, i * k + j + 1
            b0, b1 = a0 + k, a1 + k
            faces.append((a0, a1, b1, b0))
            mi.append(0 if j == 1 else 1)
    return mesh_obj("road", verts, faces, coll, uvs, mi, mats)


def rail_strip(coll, side, mat, height=0.9):
    n = 1800
    s = np.linspace(0.0, G.S, n + 1)
    p = G.point(s)
    hd = G.heading(s)
    nx, ny = np.cos(hd), -np.sin(hd)
    a = side * (G.EDGE + 0.45)
    verts, uvs, faces = [], [], []
    for i in range(n + 1):
        x, y = p[i, 0] + nx[i] * a, p[i, 1] + ny[i] * a
        verts += [(x, y, 0.0), (x, y, height)]
        uvs += [(0.0, s[i] / G.S * NV), (1.0, s[i] / G.S * NV)]
    for i in range(n):
        a0 = 2 * i
        faces.append((a0, a0 + 2, a0 + 3, a0 + 1) if side > 0 else (a0, a0 + 1, a0 + 3, a0 + 2))
    return mesh_obj(f"rail{side:+d}", verts, faces, coll, uvs, None, [mat])


def box(name, coll, cx, cy, cz, sx, sy, sz, rot=0.0, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (sx, sy, sz)
    ob.rotation_euler = (0, 0, rot)
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


class Kit:
    """Kenney models imported once each and kept as hidden templates; place() links a new object to the template's mesh."""

    def __init__(self, assets, store):
        self.assets, self.store, self.meshes = assets, store, {}

    def mesh(self, rel):
        if rel not in self.meshes:
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=os.path.join(self.assets, rel))
            new = [o for o in bpy.data.objects if o not in before]
            ob = [o for o in new if o.type == "MESH"][0]
            me = ob.data
            for o in new:
                bpy.data.objects.remove(o)
            self.meshes[rel] = me
        return self.meshes[rel]

    def place(self, rel, coll, loc, rot_z, scale, material=None):
        me = self.mesh(rel)
        ob = bpy.data.objects.new(os.path.basename(rel), me)
        ob.location = loc
        ob.rotation_euler = (0, 0, rot_z)
        ob.scale = (scale, scale, scale)
        self.placed = getattr(self, "placed", 0) + 1
        ob["wseed"] = float(self.placed)          # fixed per object, the same in every instanced copy (see the window shader)
        if material is not None:
            ob.material_slots[0].link = "OBJECT"
            ob.material_slots[0].material = material
        coll.objects.link(ob)
        return ob


def clear_of_road(x, y, half, margin):
    """True when a footprint of half-size `half` centred at (x, y) keeps `margin` metres from the road edge everywhere along it."""
    vs = np.linspace(y - half, y + half, 9)
    return bool(np.all(np.abs(x - G.centre_x(vs)) > G.EDGE + margin + half))


def build(assets):
    rng = random.Random(SEED)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    scn = bpy.context.scene
    period = bpy.data.collections.new("period")
    scn.collection.children.link(period)
    static = bpy.data.collections.new("static")
    scn.collection.children.link(static)
    kit_store = bpy.data.collections.new("kit")
    scn.collection.children.link(kit_store)
    kit = Kit(assets, kit_store)

    road_m, kerb_m = mat_road(assets), mat_kerb()
    metal = mat_metal(assets)
    rail_m = mat_rail()
    road_strip(period, [road_m, kerb_m])
    rail_strip(period, -1, rail_m)
    rail_strip(period, +1, rail_m)

    # the ground of the gantry run and the canyon (the causeway crosses water instead)
    g0, g1 = G.SECTIONS["gantry"][0] * G.L, G.L
    mesh_obj("ground", [(-3000, g0, -0.35), (3000, g0, -0.35), (3000, g1, -0.35), (-3000, g1, -0.35)], [(0, 1, 2, 3)], period, None, None,
             [mat_ground()])
    # one big water plane under everything: its ripples repeat with L, so it need not be copied
    mesh_obj("water", [(-4000, -G.L - 400, -6.5), (4000, -G.L - 400, -6.5), (4000, 2 * G.L + G.FAR + 400, -6.5),
                       (-4000, 2 * G.L + G.FAR + 400, -6.5)], [(0, 1, 2, 3)], static, None, None, [mat_water()])

    # light posts: every S / N_POSTS metres of road, alternating sides, the arm reaching over the road, a lamp and a light at its tip
    lamp_warm = mat_emit("lamp", (1.0, 0.82, 0.6), 30.0)
    lamp_cyan = mat_emit("lamp_c", (0.35, 0.95, 1.0), 30.0)
    for i in range(N_POSTS):
        s = G.S * (i + 0.5) / N_POSTS
        side = 1 if i % 2 else -1
        (x, y), hd = G.point(s), float(G.heading(s))
        nx, ny = math.cos(hd), -math.sin(hd)
        a = side * (G.EDGE + 0.9)
        px_, py_ = x + nx * a, y + ny * a
        # the model's arm points along local +Y; turn it to point across the road, towards the centre
        # (rotating by t about Z sends local +Y to (-sin t, cos t); we want it along -side * (nx, ny))
        rot = math.atan2(side * nx, -side * ny)
        kit.place(f"{KR}/light-curved.glb", period, (px_, py_, 0.0), rot, 13.0, metal)
        tipx, tipy = px_ - nx * side * 2.5, py_ - ny * side * 2.5
        warm = (i // 2) % 3 != 2
        box(f"lamp{i}", period, tipx, tipy, 8.45, 1.1, 0.5, 0.18, -hd, lamp_warm if warm else lamp_cyan)
        ld = bpy.data.lights.new(f"post{i}", "POINT")
        ld.energy = 2600.0
        ld.color = (1.0, 0.8, 0.6) if warm else (0.4, 0.9, 1.0)
        ld.shadow_soft_size = 0.4
        ld.use_shadow = False
        lo = bpy.data.objects.new(f"post{i}", ld)
        lo.location = (tipx, tipy, 8.0)
        period.objects.link(lo)

    # causeway pillars under the deck, and a deck slab so the road reads as a bridge from the side
    deck_m = mat_metal(assets, "deck", (0.12, 0.11, 0.17))
    c0, c1 = G.SECTIONS["causeway"]
    for i in range(N_PILLARS):
        s = G.S * (i + 0.5) / N_PILLARS
        (x, y) = G.point(s)
        if not (c0 * G.L <= y < c1 * G.L):
            continue
        hd = float(G.heading(s))
        for side in (-1, 1):
            a = side * (G.EDGE - 1.2)
            kit.place(f"{KR}/bridge-pillar-wide.glb", period, (x + math.cos(hd) * a, y - math.sin(hd) * a, -7.0), -hd, 14.0, deck_m)
    n = 600
    s = np.linspace(0, G.S, n + 1)
    p = G.point(s)
    hd = G.heading(s)
    nx, ny = np.cos(hd), -np.sin(hd)
    verts, faces = [], []
    for i in range(n + 1):
        for a, z in ((-G.EDGE - 0.6, -0.02), (-G.EDGE - 0.6, -1.1), (G.EDGE + 0.6, -1.1), (G.EDGE + 0.6, -0.02)):
            verts.append((p[i, 0] + nx[i] * a, p[i, 1] + ny[i] * a, z))
    for i in range(n):
        for j in range(3):
            a0, a1 = i * 4 + j, i * 4 + j + 1
            faces.append((a0, a0 + 4, a1 + 4, a1))
    mesh_obj("deck", verts, faces, period, None, None, [deck_m])

    # gantries: a lit arch every 40 m through the gantry run, legs well outside the rails, alternating magenta and cyan
    gm, gc = mat_emit("gantry_m", (1.0, 0.12, 0.55), 14.0), mat_emit("gantry_c", (0.2, 0.9, 1.0), 14.0)
    a0, a1 = G.SECTIONS["gantry"]
    sg0, sg1 = float(G.s_of_v(a0 * G.L)), float(G.s_of_v(a1 * G.L))
    ng = int((sg1 - sg0) // 40)
    for i in range(ng + 1):
        s = sg0 + i * (sg1 - sg0) / ng
        (x, y), h = G.point(s), float(G.heading(s))
        nx, ny = math.cos(h), -math.sin(h)
        span, top = G.EDGE + 3.2, 9.5
        em = gm if i % 2 else gc
        for side in (-1, 1):
            box(f"gleg{i}{side}", period, x + nx * span * side, y + ny * span * side, top / 2, 0.8, 0.8, top, -h, metal)
            box(f"gstrip{i}{side}", period, x + nx * (span - 0.45) * side, y + ny * (span - 0.45) * side, top / 2, 0.12, 0.3, top - 0.6,
                -h, em)
        box(f"gbeam{i}", period, x, y, top, 2 * span + 0.8, 1.0, 0.9, -h, metal)
        box(f"gglow{i}", period, x, y, top - 0.5, 2 * span - 0.4, 0.25, 0.12, -h, em)
        ld = bpy.data.lights.new(f"gl{i}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 2 * span - 2, 0.6
        ld.energy = 9000.0
        ld.color = (1.0, 0.25, 0.65) if i % 2 else (0.3, 0.9, 1.0)
        ld.use_shadow = False
        lo = bpy.data.objects.new(f"gl{i}", ld)
        lo.location = (x, y, top - 0.8)
        lo.rotation_euler = (0, 0, -h)
        period.objects.link(lo)

    # buildings. Night materials are made per source mesh, once.
    tower_mats = {}

    def tower_mat(rel):
        if rel not in tower_mats:
            me = kit.mesh(rel)
            img = None
            for node in me.materials[0].node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    img = node.image
            tower_mats[rel] = mat_tower(assets, img)
        return tower_mats[rel]

    sky_ = [f"{KC}/building-skyscraper-{c}.glb" for c in "abcde"]
    mid_ = [f"{KC}/building-{c}.glb" for c in "abcdefghijklmn"]
    low_ = [f"{KC}/low-detail-building-{c}.glb" for c in "abcdefghijklmn"] + [f"{KC}/low-detail-building-wide-{c}.glb" for c in "ab"]

    def put(rel, x, y, scale, rot=None):
        kit.place(rel, period, (x, y, -0.35), rng.uniform(0, 2 * math.pi) if rot is None else rot, scale, tower_mat(rel))

    # the canyon: towers close on both sides, then a second row
    cs0, cs1 = G.SECTIONS["canyon"]
    y = cs0 * G.L + 10
    while y < cs1 * G.L - 15:
        for side in (-1, 1):
            rel = rng.choice(sky_)
            sc = rng.uniform(24, 34)
            half = 0.7 * sc
            for _ in range(6):
                x = float(G.centre_x(y)) + side * (G.EDGE + 6 + half + rng.uniform(0, 14))
                if clear_of_road(x, y, half, 4.0):
                    put(rel, x, y, sc, rng.choice((0, math.pi / 2, math.pi, -math.pi / 2)))
                    break
            if rng.random() < 0.8:
                rel2 = rng.choice(sky_ + mid_)
                sc2 = rng.uniform(26, 40) if rel2 in sky_ else rng.uniform(40, 70)
                x2 = float(G.centre_x(y)) + side * rng.uniform(75, 170)
                put(rel2, x2, y + rng.uniform(-15, 15), sc2)
        y += rng.uniform(30, 44)
    # mid-distance blocks along the gantry run
    y = G.SECTIONS["gantry"][0] * G.L
    while y < G.SECTIONS["gantry"][1] * G.L:
        for side in (-1, 1):
            if rng.random() < 0.7:
                rel = rng.choice(mid_)
                sc = rng.uniform(20, 35)
                x = float(G.centre_x(y)) + side * rng.uniform(60, 160)
                if clear_of_road(x, y, 0.6 * sc, 8):
                    put(rel, x, y, sc)
        y += rng.uniform(25, 45)
    # the far skyline, all the way round, seen across the water
    y = 0.0
    while y < G.L:
        for side in (-1, 1):
            if rng.random() < 0.85:
                tall = rng.random() < 0.45
                rel = rng.choice(sky_ if tall else low_)
                sc = rng.uniform(22, 40) if tall else rng.uniform(40, 85)
                put(rel, side * rng.uniform(300, 1100), y, sc)
        y += rng.uniform(30, 60)

    # templates: hide the kit collection; the period collection is excluded and drawn only through its three instances
    for k in (-1, 0, 1):
        e = bpy.data.objects.new(f"period{k:+d}", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = period
        e.location = (0.0, k * G.L, 0.0)
        static.objects.link(e)
    vl = scn.view_layers[0]
    vl.layer_collection.children["period"].exclude = True
    vl.layer_collection.children["kit"].exclude = True

    # lighting: the night HDRI, dim, for the cool ambient light and reflections; a faint moon
    world = bpy.data.worlds.new("night")
    scn.world = world
    world.use_nodes = True
    nt = world.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(assets, "polyhaven/rogland_clear_night/rogland_clear_night_2k.hdr"))
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = 0.6
    wo = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], wo.inputs[0])
    sun = bpy.data.lights.new("moon", "SUN")
    sun.energy = 0.08
    sun.color = (0.6, 0.65, 1.0)
    so = bpy.data.objects.new("moon", sun)
    so.rotation_euler = (math.radians(60), 0, math.radians(30))
    static.objects.link(so)

    cam_d = bpy.data.cameras.new("cam")
    cam_d.sensor_fit = "HORIZONTAL"
    cam_d.angle = G.HFOV
    cam_d.clip_start, cam_d.clip_end = 0.3, G.FAR
    cam = bpy.data.objects.new("cam", cam_d)
    static.objects.link(cam)
    scn.camera = cam
    return cam


def render_settings(samples: int):
    scn = bpy.context.scene
    r = scn.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y, r.resolution_percentage = G.RENDER_W, G.RENDER_H, 100
    r.film_transparent = True
    r.use_motion_blur = False
    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "None"
    e = scn.eevee
    e.taa_render_samples = samples
    for k, v in (("use_raytracing", True), ("use_shadows", True), ("use_gtao", True)):
        if hasattr(e, k):
            setattr(e, k, v)
    s = r.image_settings
    if hasattr(s, "media_type"):
        try:
            s.media_type = "MULTI_LAYER_IMAGE"
        except Exception:
            pass
    s.file_format = "OPEN_EXR_MULTILAYER"
    s.color_depth = "32"
    s.exr_codec = "ZIP"


def set_camera(cam, n: int):
    (x, y, z), yaw = G.camera(n)
    cam.location = (x, y, z)
    cam.rotation_euler = (math.pi / 2 - G.PITCH, 0.0, -yaw)


# ---------------------------------------------------------------- per frame
def read_exr(path):
    """The four channels of a single-layer render, [H, W, 4] float32."""
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise RuntimeError(f"cannot open {path}")
    sp = inp.spec()
    data = np.asarray(inp.read_image(0, 0, 0, sp.nchannels, "float")).reshape(sp.height, sp.width, sp.nchannels)
    names = list(sp.channelnames)
    inp.close()
    order = [next(i for i, n in enumerate(names) if n.endswith("." + c) or n == c) for c in "RGBA"]
    return data[:, :, order]


def mat_depth():
    """Emission of the view-space depth (metres along the camera's axis): rendered as a second pass with this material on everything,
    because Blender 5.2's still-image writer keeps only the combined pass."""
    m = bpy.data.materials.new("depth_pass")
    nt, out = _nodes(m)
    cd = nt.nodes.new("ShaderNodeCameraData")
    e = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(cd.outputs["View Z Depth"], e.inputs[0])
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return read_exr(path)


def shrink(rgb, a, z):
    """Fog by depth at full size, then average 4x4 blocks in linear light; depth is the nearest in each block."""
    z = np.where(a > 0.001, z, np.inf)
    f = G.fog_amount(z)[..., None]
    haze = G.sky_scene_linear(G.RENDER_H)[:, None, :]
    rgb = rgb * (1 - f) + a[..., None] * f * haze
    k = G.RENDER_W // G.W
    rgb_s = rgb.reshape(G.H, k, G.W, k, 3).mean(axis=(1, 3))
    a_s = a.reshape(G.H, k, G.W, k).mean(axis=(1, 3))
    z_s = z.reshape(G.H, k, G.W, k).min(axis=(1, 3))
    return rgb_s.astype(np.float16), a_s.astype(np.float16), G.depth_code(z_s)


def main():
    a = args()
    if a.check:
        n0 = np.array(G.camera(0)[0])
        n9 = np.array(G.camera(G.FRAMES)[0])
        dy = n9 - n0
        print(f"CHECK S={G.S:.2f} m  speed={G.SPEED:.2f} m/s  NV={NV}  camera 900 - camera 0 = {dy.round(6).tolist()} (want [0, {G.L}, 0])")
        print(f"CHECK yaw 0 = {G.camera(0)[1]:.6f}  yaw 900 = {G.camera(G.FRAMES)[1]:.6f}  horizon row = {G.horizon_row():.2f}")
        ok = abs(dy[0]) < 1e-6 and abs(dy[1] - G.L) < 1e-6 and abs(G.camera(0)[1] - G.camera(G.FRAMES)[1]) < 1e-9
        cx, hw, _ = G.road_rows(0)
        print("CHECK road rows (row, centre, half width):", [(r, round(float(cx[r]), 1), round(float(hw[r]), 1)) for r in (80, 100, 140, 179)])
        print("CHECK", "OK" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    t0 = time.time()
    cam = build(a.assets)
    render_settings(a.samples)
    depth_m = mat_depth()
    print(f"BUILD {time.time() - t0:.1f}s objects={len(bpy.data.objects)}", flush=True)
    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=a.save_blend)
    lo, hi = (int(x) for x in a.frames.split("-"))
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.raw, exist_ok=True)
    for n in range(lo, hi + 1):
        dst = os.path.join(a.out, f"f{n:04d}.npz")
        if os.path.exists(dst):
            continue
        t1 = time.time()
        set_camera(cam, n)
        exr = os.path.join(a.raw, f"f{n:04d}.exr")
        scn, vl = bpy.context.scene, bpy.context.scene.view_layers[0]
        beauty = render_to(exr)
        vl.material_override, scn.eevee.taa_render_samples = depth_m, 1
        dep = render_to(exr)
        vl.material_override, scn.eevee.taa_render_samples = None, a.samples
        z = np.where(dep[:, :, 3] > 0.5, dep[:, :, 0] / np.maximum(dep[:, :, 3], 1e-6), np.inf)
        rs, as_, zs = shrink(beauty[:, :, :3], beauty[:, :, 3], z)
        tmp = dst + ".tmp.npz"
        np.savez_compressed(tmp, rgb=rs, alpha=as_, depth=zs)
        os.replace(tmp, dst)
        os.remove(exr)
        print(f"FRAME {n} {time.time() - t1:.2f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
