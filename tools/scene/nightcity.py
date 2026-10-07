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

GROUND = -11.0           # the study is on the fourth floor


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
    key = "night_facade"
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
    el[1].position, el[1].color = 0.62, (*srgb("#ffc98a"), 1)
    c2 = el.new(0.86)
    c2.color = (*srgb("#cfe2ff"), 1)
    c3 = el.new(0.95)
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
    p.inputs["Emission Strength"].default_value = 2.6
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


WALLS = [srgb(c) for c in ("#3a4048", "#454b54", "#2f353d", "#4d4a48", "#3f444c")]


def build(seed=5):
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
    dark.box(cx - 900, cy - 900, GROUND - 1, cx + 900, cy + 900, GROUND, srgb("#15181d"))
    for d in (16.0, 70.0, 150.0):
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
            tower(x, y, w, dd, rng.uniform(5, 10))
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
            h = rng.uniform(8, 24) * (1 + 2.6 * max(0.0, (d - 150) / 450)) * (2.0 if rng.random() < 0.06 else 1)
            tower(x, y, w, dd, h)
    blocks.build()
    dark.build()
    glow.build()

    # moon, low over the skyline on the visible side of the window
    moon = B.mat_emit("moon", srgb("#f3eedf"), 6.0)
    p = win + MOON_DIR() * 900
    B.superellipsoid("moon", (16, 16, 16), tuple(p), (0, 0, 0), material=moon, e=1.0, nu=24, nv=12)


def build_world():
    """Night sky: city glow at the horizon fading to deep navy, a faint star field for camera rays only."""
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
    el[0].position, el[0].color = 0.0, (*srgb("#4a4a5c"), 1)
    el[1].position, el[1].color = 1.0, (*srgb("#070a16"), 1)
    mid = el.new(0.22)
    mid.color = (*srgb("#1a2238"), 1)
    nt.links.new(gz.outputs[0], grad.inputs["Fac"])
    stars = nt.nodes.new("ShaderNodeTexVoronoi")
    stars.inputs["Scale"].default_value = 260
    nt.links.new(tc.outputs["Generated"], stars.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeMapRange")
    sr.inputs["From Min"].default_value = 0.06
    sr.inputs["From Max"].default_value = 0.0
    sr.inputs["To Max"].default_value = 0.6
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
    amb.inputs["B"].default_value = (*srgb("#0d1426"), 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    pick = nt.nodes.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    nt.links.new(lp.outputs["Is Camera Ray"], pick.inputs["Factor"])
    nt.links.new(amb.outputs["Result"], pick.inputs["A"])
    nt.links.new(sadd.outputs["Result"], pick.inputs["B"])
    nt.links.new(pick.outputs["Result"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return w
