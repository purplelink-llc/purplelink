"""Blender scene for the Publication suite film (Cycles, 15 s at 30 fps).

One manuscript on a dark desk. A scan line reads the page, highlights land on the three sentences Paper Review flags,
the finding cards rise, the highlights turn to Revision Review's statuses, then the response letter slides in and the
Response Review tracker rises. Textures come from make_textures.py.

    Blender -b -P tools/publication-film/build_scene.py -- TEX_DIR OUT.blend
"""

import json
import math
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
TEX = Path(argv[0])
OUT = Path(argv[1])
LAYOUT = json.loads((TEX / "layout.json").read_text())

FPS, END = 30, 450
PAGE_H = 1.1
PAGE_W = PAGE_H * LAYOUT["page"][0] / LAYOUT["page"][1]
CARD_W = 0.36
CARD_TILT = math.radians(52)  # card faces the camera's mean elevation

PURPLE = (0.55, 0.22, 0.95, 1)
OK = (0.25, 0.75, 0.42, 1)
PART = (0.95, 0.68, 0.18, 1)
NO = (0.95, 0.28, 0.22, 1)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, END


# ------------------------------------------------------------------ helpers

def key(target, path, frame, value, index=-1):
    setattr(target, path, value) if index < 0 else getattr(target, path).__setitem__(index, value)
    target.keyframe_insert(path, frame=frame, index=index)


def key_socket(socket, frame, value):
    socket.default_value = value
    socket.keyframe_insert("default_value", frame=frame)


def plane(name, w, h, loc, rot=(0, 0, 0), cuts=0):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (w, h, 1)
    # Scale only: the operator applies location and rotation too by default, which bakes the start pose into the
    # mesh and makes every later location key an offset on top of it.
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if cuts:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def paper_mat(name, image):
    m, nt, out = new_mat(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(TEX / image))
    tex.interpolation = "Cubic"
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    tone = nt.nodes.new("ShaderNodeMix")
    tone.data_type = "RGBA"
    tone.blend_type = "MULTIPLY"
    tone.inputs["Factor"].default_value = 1.0
    tone.inputs["B"].default_value = (0.78, 0.76, 0.74, 1)  # paper albedo, not a white light source
    nt.links.new(tex.outputs["Color"], tone.inputs["A"])
    nt.links.new(tone.outputs["Result"], bsdf.inputs["Base Color"])
    # A faint paper grain in the bump so the sheet reads as a physical object under the raking key light.
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 900
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def fade_mat(name, image=None, colour=PURPLE, strength=1.0):
    """Emission panel mixed with transparency by a keyable Fade value. Returns (material, fade socket, colour socket)."""
    m, nt, out = new_mat(name)
    fade = nt.nodes.new("ShaderNodeValue")
    fade.name = "Fade"
    fade.outputs[0].default_value = 0.0
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(fade.outputs[0], mul.inputs[0])
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(TEX / image))
        tex.interpolation = "Cubic"
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(tex.outputs["Alpha"], mul.inputs[1])
        colour_socket = None
    else:
        em.inputs["Color"].default_value = colour
        mul.inputs[1].default_value = 1.0
        colour_socket = em.inputs["Color"]
    nt.links.new(mul.outputs[0], mix.inputs["Fac"])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m, fade.outputs[0], colour_socket


def page_to_world(u, v, z=0.0):
    return ((u - 0.5) * PAGE_W, (0.5 - v) * PAGE_H, z)


# ------------------------------------------------------------------ set

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.002, 0.007, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

desk = plane("Desk", 12, 12, (0, 0, -0.004))
m, nt, out = new_mat("Desk")
b = nt.nodes.new("ShaderNodeBsdfPrincipled")
b.inputs["Base Color"].default_value = (0.010, 0.007, 0.015, 1)
b.inputs["Roughness"].default_value = 0.58
b.inputs["Coat Weight"].default_value = 0.25
nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
desk.data.materials.append(m)

# A short stack of earlier drafts under the top page, each turned a little.
blank = paper_mat("Blank", "page_letter.png")
for i, (dx, dy, rz) in enumerate([(0.012, -0.01, -2.2), (-0.01, 0.006, 1.6), (0.004, 0.012, -0.8)]):
    s = plane(f"Sheet{i}", PAGE_W, PAGE_H, (dx, dy, -0.0032 + i * 0.0009), (0, 0, math.radians(rz)))
    s.data.materials.append(blank)

page = plane("Manuscript", PAGE_W, PAGE_H, (0, 0, 0), cuts=24)
page.data.materials.append(paper_mat("Manuscript", "page_manuscript.png"))
def curl(ob):
    # Paper thickness only. A Simple Deform bend pivots on the object origin, so on the letter (which slides in
    # from 1.6 m away) it stood the sheet on edge; the noise bump in paper_mat carries the surface instead.
    ob.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.0007


curl(page)

letter = plane("Letter", PAGE_W, PAGE_H, (1.6, 0.05, 0.004), (0, 0, math.radians(-9)), cuts=12)
letter.data.materials.append(paper_mat("Letter", "page_letter.png"))
curl(letter)

# ------------------------------------------------------------------ beat 1: the scan and the highlights

SCAN_IN, SCAN_OUT = 34, 118
scan = plane("Scan", PAGE_W * 1.04, 0.006, (0, PAGE_H / 2, 0.003))
sm, sfade, _ = fade_mat("Scan", colour=(0.78, 0.6, 1.0, 1), strength=7.0)
scan.data.materials.append(sm)
key(scan, "location", SCAN_IN, (0, PAGE_H / 2 - 0.02, 0.003))
key(scan, "location", SCAN_OUT, (0, PAGE_H / 2 - 0.66, 0.003))
key_socket(sfade, SCAN_IN - 6, 0.0)
key_socket(sfade, SCAN_IN + 4, 1.0)
key_socket(sfade, SCAN_OUT - 8, 1.0)
key_socket(sfade, SCAN_OUT, 0.0)

REVISE = 236  # the highlights take Revision Review's statuses
STATUS = {1: OK, 2: PART, 3: NO}
for i, h in enumerate(LAYOUT["highlights"]):
    cx, cy, _ = page_to_world((h["u0"] + h["u1"]) / 2, (h["v0"] + h["v1"]) / 2)
    hp = plane(f"HL{i}", (h["u1"] - h["u0"]) * PAGE_W, (h["v1"] - h["v0"]) * PAGE_H, (cx, cy, 0.0012))
    hm, hfade, hcol = fade_mat(f"HL{i}", colour=PURPLE, strength=1.6)
    hp.data.materials.append(hm)
    # The highlight lands the moment the scan line passes it.
    t = SCAN_IN + (PAGE_H / 2 - 0.02 - cy) / 0.64 * (SCAN_OUT - SCAN_IN)
    t = int(round(t)) + 2
    key_socket(hfade, t, 0.0)
    key_socket(hfade, t + 8, 0.55)
    key_socket(hfade, 300, 0.55)
    key_socket(hfade, 312, 0.0)
    key_socket(hcol, REVISE, PURPLE)
    key_socket(hcol, REVISE + 12, STATUS[h["id"]])


def card_mat(name, image):
    """A UI panel shown at its designed colours: emission over transparency, so the key light's specular cannot grey it
    out. Alpha is the texture's alpha times a keyable Fade, pushed to opaque so the page never shows through."""
    m, nt, out = new_mat(name)
    fade = nt.nodes.new("ShaderNodeValue")
    fade.outputs[0].default_value = 0.0
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(TEX / image))
    tex.interpolation = "Cubic"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(tex.outputs["Alpha"], mul.inputs[0])
    nt.links.new(fade.outputs[0], mul.inputs[1])
    solid = nt.nodes.new("ShaderNodeMath")  # panel alpha is 238/255; push it to opaque, keep the soft corners
    solid.operation = "MULTIPLY"
    solid.use_clamp = True
    solid.inputs[1].default_value = 1.3
    nt.links.new(mul.outputs[0], solid.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(solid.outputs[0], mix.inputs["Fac"])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m, fade.outputs[0]


def card(name, image, size_px, loc, t_in, t_out, drift=0.0):
    w = CARD_W
    h = CARD_W * size_px[1] / size_px[0]
    c = plane(name, w, h, loc, (CARD_TILT, 0, math.radians(drift)))
    cm, cfade = card_mat(name, image)
    c.data.materials.append(cm)
    x, y, z = loc
    key(c, "location", t_in, (x, y - 0.03, z - 0.02))
    key(c, "location", t_in + 22, (x, y, z))
    key(c, "location", t_out, (x, y + 0.015, z + 0.02))
    key_socket(cfade, t_in, 0.0)
    key_socket(cfade, t_in + 16, 1.0)
    key_socket(cfade, t_out - 10, 1.0)
    key_socket(cfade, t_out, 0.0)
    return c


# ------------------------------------------------------------------ beat 1b: the findings rise

card("Card_f3", "card_f3.png", (760, 210), (0.32, -0.10, 0.08), 128, 226, -2)
card("Card_f2", "card_f2.png", (760, 210), (0.36, -0.04, 0.19), 140, 226, 1)
card("Card_f1", "card_f1.png", (760, 210), (0.40, 0.02, 0.29), 152, 226, -1)

# ------------------------------------------------------------------ beat 2: Revision Review

card("Card_revision", "card_revision.png", (760, 332), (0.34, 0.0, 0.32), 244, 316, 0)

# ------------------------------------------------------------------ beat 3: the response letter and Response Review

key(letter, "location", 300, (1.6, 0.05, 0.004))
key(letter, "location", 338, (0.05, 0.02, 0.004))
key(letter, "rotation_euler", 300, math.radians(-14), index=2)
key(letter, "rotation_euler", 338, math.radians(-4), index=2)
card("Card_response", "card_response.png", (760, 406), (0.38, 0.0, 0.34), 346, 452, 0)

# ------------------------------------------------------------------ light

def area(name, loc, rot, size, energy, colour):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    data.energy = energy
    data.color = colour
    ob = bpy.data.objects.new(name, data)
    ob.location, ob.rotation_euler = loc, [math.radians(a) for a in rot]
    scene.collection.objects.link(ob)
    return ob


key_light = area("Key", (-0.9, -0.5, 1.3), (32, -36, -22), (0.7, 0.5), 34, (1.0, 0.95, 0.9))
key_light.data.spread = math.radians(38)  # a pool of light that falls off into the dark desk
area("Rim", (0.9, 1.3, 0.55), (-68, 30, 0), (1.6, 0.3), 6, (0.62, 0.36, 1.0))
area("Fill", (1.4, -1.2, 0.9), (55, 40, 40), (1.0, 1.0), 6, (0.85, 0.8, 1.0))

# ------------------------------------------------------------------ camera

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 44
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 5.0
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

target = bpy.data.objects.new("Target", None)
scene.collection.objects.link(target)
track = cam.constraints.new("TRACK_TO")
track.target = target
track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
cam_data.dof.focus_object = target

# One slow, continuous dolly with a little lateral parallax: the camera never stops, the beats change under it.
for f, cloc, tloc in [
    (1, (-0.30, -1.55, 1.20), (0.02, 0.06, 0.0)),
    (130, (-0.12, -1.30, 1.04), (0.06, 0.02, 0.03)),
    (240, (0.00, -1.24, 0.98), (0.10, 0.0, 0.05)),
    (340, (0.10, -1.26, 1.00), (0.10, 0.0, 0.05)),
    (450, (0.20, -1.36, 1.08), (0.12, 0.02, 0.05)),
]:
    key(cam, "location", f, cloc)
    key(target, "location", f, tloc)

# ------------------------------------------------------------------ render

scene.render.engine = "CYCLES"
cy = scene.cycles
cy.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
cy.samples = 64
cy.use_denoising = True
cy.max_bounces = 6
cy.transparent_max_bounces = 16
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -0.2

bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("saved", OUT)
