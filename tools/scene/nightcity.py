"""Night city seen through the study's side window: lit facades, a street far below, a dark sky.

Everything sits in the ``exterior`` collection (backdrop only). Buildings are batched boxes; the lit
windows come from one emissive facade material, so the geometry stays a few thousand faces.
"""
from __future__ import annotations

import math
import random

import bpy
import numpy as np
from mathutils import Vector

import blib as B
import stage
from blib import srgb
from exterior import Batch

STYLES = {
    # the study on the fourth floor, late at night
    "night": {"ground": -11.0, "lit_from": 0.62, "emit": 2.6, "near_h": (5, 10), "far_h": (8, 24), "street": 6.0,
              "walls": ("#3a4048", "#454b54", "#2f353d", "#4d4a48", "#3f444c"), "ground_col": "#15181d"},
    # the game room on the third floor of an old estate, just before sunset
    "dusk": {"ground": -7.5, "lit_from": 0.9, "emit": 1.4, "near_h": (6, 11), "far_h": (12, 30), "street": 0.0,
             "walls": ("#d8cdb8", "#cbbfa8", "#e2d8c6", "#c9b49a", "#bfb6a8"), "ground_col": "#6d6458"},
}
S = STYLES["night"]


def desk_to_world(x, y, z=0.0):
    (ox, oy, _), yaw = stage.DESK_ROOT
    a = math.radians(yaw)
    return Vector((ox + x * math.cos(a) - y * math.sin(a), oy + x * math.sin(a) + y * math.cos(a), z))


def outward():
    """Unit vector out of the window (desk frame -X) and the along-wall direction (desk frame +Y)."""
    o = desk_to_world(0, 0)
    return (desk_to_world(-1, 0) - o).normalized(), (desk_to_world(0, 1) - o).normalized()


def MOON_DIR():
    out, along = outward()
    return (out * 0.82 + along * 0.4 + Vector((0, 0, 0.13))).normalized()


def facade_mat():
    """Dark facade; a world-space grid of windows, about a third of them lit warm or cool. Roofs stay dark."""
    key = f"facade_{S['lit_from']}"
    if key in B._mats:
        return B._mats[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.7
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "vcol"
    nt.links.new(attr.outputs["Color"], p.inputs["Base Color"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(add.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 2.4
    br.inputs["Row Height"].default_value = 3.1
    br.inputs["Mortar Size"].default_value = 0.75
    br.inputs["Mortar Smooth"].default_value = 0.05
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (0, 0, 0, 1)
    br.inputs["Color2"].default_value = (1, 1, 1, 1)
    nt.links.new(comb.outputs[0], br.inputs["Vector"])
    # per-window random value -> lit (warm / cool) or dark
    lit = nt.nodes.new("ShaderNodeValToRGB")
    lit.color_ramp.interpolation = "CONSTANT"
    el = lit.color_ramp.elements
    el[0].position, el[0].color = 0.0, (0, 0, 0, 1)
    lo = S["lit_from"]
    el[1].position, el[1].color = lo, (*srgb("#ffc98a"), 1)
    c2 = el.new(lo + (1 - lo) * 0.63)
    c2.color = (*srgb("#cfe2ff"), 1)
    c3 = el.new(lo + (1 - lo) * 0.87)
    c3.color = (*srgb("#ffe7c2"), 1)
    nt.links.new(br.outputs["Color"], lit.inputs["Fac"])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(br.outputs["Fac"], inv.inputs[1])
    # no windows on roofs
    nz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nz.inputs[0])
    absz = nt.nodes.new("ShaderNodeMath")
    absz.operation = "ABSOLUTE"
    nt.links.new(nz.outputs["Z"], absz.inputs[0])
    side = nt.nodes.new("ShaderNodeMath")
    side.operation = "LESS_THAN"
    side.inputs[1].default_value = 0.5
    nt.links.new(absz.outputs[0], side.inputs[0])
    mask = nt.nodes.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    nt.links.new(inv.outputs[0], mask.inputs[0])
    nt.links.new(side.outputs[0], mask.inputs[1])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(lit.outputs["Color"], mul.inputs["A"])
    comb2 = nt.nodes.new("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        nt.links.new(mask.outputs[0], comb2.inputs[k])
    nt.links.new(comb2.outputs[0], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = S["emit"]
    B._mats[key] = m
    return m


def plain_mat(name, rough=0.8, emit=0.0):
    key = f"night_{name}"
    if key in B._mats:
        return B._mats[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = rough
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "vcol"
    nt.links.new(a.outputs["Color"], p.inputs["Base Color"])
    if emit:
        nt.links.new(a.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = emit
    B._mats[key] = m
    return m


def build(seed=5, style="night", sky_disc=None):
    """``sky_disc`` = (direction, colour, strength, size): the moon at night, the setting sun at dusk."""
    global S
    S = STYLES[style]
    GROUND = S["ground"]
    WALLS = [srgb(c) for c in S["walls"]]
    B.use_collection("exterior")
    rng = random.Random(seed)
    out, along = outward()
    win = desk_to_world(-1.3, 0.0, 1.6)
    up = Vector((0, 0, 1))

    def at(d, s):
        """Ground point d metres out from the window and s metres along the wall."""
        p = win + out * d + along * s
        return p.x, p.y

    blocks = Batch("night_blocks", facade_mat())
    dark = Batch("night_ground", plain_mat("ground", 0.9))
    glow = Batch("night_lights", plain_mat("lights", 0.5, emit=6.0))

    # ground and streets
    x0, y0 = at(-5, -400)
    cx, cy = at(400, 0)
    dark.box(cx - 900, cy - 900, GROUND - 1, cx + 900, cy + 900, GROUND, srgb(S["ground_col"]))
    for d in ((16.0, 70.0, 150.0) if S["street"] else ()):
        ax, ay = at(d, -260)
        bx, by = at(d, 260)
        n = int(520 / 9)
        for k in range(n + 1):
            t = k / n
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            glow.box(px - 0.25, py - 0.25, GROUND + 6.0, px + 0.25, py + 0.25, GROUND + 6.5, srgb("#ffbf78"))

    placed = []

    def free(x, y, w, d):
        return all(abs(x - px) > (w + pw) / 2 + 3 or abs(y - py) > (d + pd) / 2 + 3 for px, py, pw, pd in placed)

    def tower(x, y, w, d, h):
        col = np.array(rng.choice(WALLS))
        blocks.box(x - w / 2, y - d / 2, GROUND - 1, x + w / 2, y + d / 2, GROUND + h, col)
        if rng.random() < 0.35:
            blocks.box(x - w / 4, y - d / 4, GROUND + h, x + w / 4, y + d / 4, GROUND + h + rng.uniform(2, 5),
                       col * 0.8)
        if h > 45 and rng.random() < 0.6:
            glow.box(x - 0.4, y - 0.4, GROUND + h + 4.5, x + 0.4, y + 0.4, GROUND + h + 5.3, srgb("#ff5a4a"))

    # near band: low housing across the street, roofs below the window so the skyline shows over them
    for _ in range(300):
        if len(placed) >= 26:
            break
        d, s = rng.uniform(26, 70), rng.uniform(-90, 90)
        x, y = at(d, s)
        w, dd = rng.uniform(12, 22), rng.uniform(10, 16)
        if free(x, y, w, dd):
            placed.append((x, y, w, dd))
            tower(x, y, w, dd, rng.uniform(*S["near_h"]))
    # middle and far bands: taller and denser toward a skyline
    for _ in range(2500):
        if len(placed) >= 240:
            break
        d = rng.uniform(80, 600)
        s = rng.uniform(-1.1, 1.1) * d
        x, y = at(d, s)
        w, dd = rng.uniform(14, 34), rng.uniform(14, 30)
        if free(x, y, w, dd):
            placed.append((x, y, w, dd))
            h = rng.uniform(*S["far_h"]) * (1 + 2.6 * max(0.0, (d - 150) / 450)) * (2.0 if rng.random() < 0.06 else 1)
            tower(x, y, w, dd, h)
    blocks.build()
    dark.build()
    glow.build()

    dirn, col, strength, size = sky_disc or (MOON_DIR(), "#f3eedf", 6.0, 16)
    p = win + dirn * 900
    B.superellipsoid("sky_disc", (size,) * 3, tuple(p), (0, 0, 0), material=B.mat_emit(f"disc_{col}", srgb(col), strength),
                     e=1.0, nu=24, nv=12).visible_shadow = False


SKIES = {
    # horizon, lower sky, zenith, ambient seen by everything but camera rays, star strength
    "night": ("#4a4a5c", "#1a2238", "#070a16", "#0d1426", 0.6),
    "dusk": ("#ffb07a", "#e89a9a", "#5d7fc4", "#7a6c66", 0.0),
    # 出发: one clear sky per destination
    "nagoya": ("#e9e4da", "#a8c6e4", "#4f88c9", "#8d9cb0", 0.0),
    "tbilisi": ("#f0e2cc", "#b9cbe0", "#5a8cc8", "#9a9fae", 0.0),
    "batumi": ("#e6ecef", "#a9cbe6", "#4a86c8", "#8fa2b6", 0.0),
    "sayram": ("#dfeaf2", "#8cbde8", "#2c6cc4", "#8ea6c4", 0.0),
    "doha": ("#f2e3cc", "#dcd6c8", "#93b2cc", "#b0a796", 0.0),
    "hokkaido": ("#e8eef2", "#a8cdeb", "#4f8fd6", "#90a6bf", 0.0),
    "fukuoka": ("#e9e6de", "#acc9e4", "#4e88c9", "#8d9cb0", 0.0),
    "dalian": ("#e4e9ec", "#a6c4e0", "#5288c4", "#8c9bb0", 0.0),
    "changsha": ("#ece2d2", "#c6ccd0", "#7c9cc0", "#9c9a98", 0.0),
    "harbin": ("#8ea4d8", "#3c5294", "#121a46", "#4c5a88", 0.4),
}


def build_world(style="night"):
    """Gradient sky for camera rays (city glow at night, sunset at dusk) and a flat ambient for lighting."""
    hz_c, mid_c, top_c, amb_c, star = SKIES[style]
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    gz = nt.nodes.new("ShaderNodeMapRange")
    gz.inputs["From Min"].default_value = -0.02
    gz.inputs["From Max"].default_value = 0.5
    nt.links.new(sep.outputs["Z"], gz.inputs["Value"])
    grad = nt.nodes.new("ShaderNodeValToRGB")
    el = grad.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*srgb(hz_c), 1)
    el[1].position, el[1].color = 1.0, (*srgb(top_c), 1)
    mid = el.new(0.22)
    mid.color = (*srgb(mid_c), 1)
    nt.links.new(gz.outputs[0], grad.inputs["Fac"])
    stars = nt.nodes.new("ShaderNodeTexVoronoi")
    stars.inputs["Scale"].default_value = 260
    nt.links.new(tc.outputs["Generated"], stars.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeMapRange")
    sr.inputs["From Min"].default_value = 0.06
    sr.inputs["From Max"].default_value = 0.0
    sr.inputs["To Max"].default_value = star
    nt.links.new(stars.outputs["Distance"], sr.inputs["Value"])
    hz = nt.nodes.new("ShaderNodeMapRange")
    hz.inputs["From Min"].default_value = 0.08
    hz.inputs["From Max"].default_value = 0.3
    nt.links.new(sep.outputs["Z"], hz.inputs["Value"])
    smul = nt.nodes.new("ShaderNodeMath")
    smul.operation = "MULTIPLY"
    nt.links.new(sr.outputs[0], smul.inputs[0])
    nt.links.new(hz.outputs[0], smul.inputs[1])
    sadd = nt.nodes.new("ShaderNodeMix")
    sadd.data_type = "RGBA"
    sadd.blend_type = "ADD"
    nt.links.new(smul.outputs[0], sadd.inputs["Factor"])
    nt.links.new(grad.outputs["Color"], sadd.inputs["A"])
    sadd.inputs["B"].default_value = (1, 1, 1, 1)
    amb = nt.nodes.new("ShaderNodeMix")
    amb.name = "amb_sky"
    amb.data_type = "RGBA"
    amb.inputs["Factor"].default_value = 1.0
    amb.inputs["B"].default_value = (*srgb(amb_c), 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    pick = nt.nodes.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    nt.links.new(lp.outputs["Is Camera Ray"], pick.inputs["Factor"])
    nt.links.new(amb.outputs["Result"], pick.inputs["A"])
    nt.links.new(sadd.outputs["Result"], pick.inputs["B"])
    nt.links.new(pick.outputs["Result"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return w
