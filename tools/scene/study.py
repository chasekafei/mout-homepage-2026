"""工作: a home study late at night — the desk, the AI Agent core and the career modules wired into it.

Everything is laid out in the desk frame (``stage.DESK_ROOT``): +Y is where the character looks, the
desk stands against the front wall, the side window is on his left. The AI core sits on a low riser
straight ahead; the four earlier industries hang on the wall around it in an arc, oldest at the top,
and one glowing cable runs through them in order before plugging into the core.
"""
from __future__ import annotations

import math
import random

import bpy
import numpy as np

import blib as B
import props_room as P
import stage
from blib import srgb
from stage import DESK_TOP

LEFT_X, RIGHT_X = -1.25, 2.3      # inner wall faces
FRONT_Y, BACK_Y = 0.82, -2.6
CEIL = 2.65
WALL_T = 0.2
WIN_Y0, WIN_Y1, WIN_Z0, WIN_Z1 = -0.45, 0.66, 0.86, 2.3
DESK = (-0.85, 1.3, 0.0, 0.78)     # x0, x1, y0, y1
RISER = (-0.32, 0.72, 0.55, 0.78, DESK_TOP + 0.06)   # x0, x1, y0, y1, top
CORE = (0.06, 0.665)               # core centre on the riser
RING_Z = 1.0
# career modules on an arc around the core (wall-mounted except the newest, which stands on the riser)
ARC_C, ARC_RX, ARC_RZ = (0.06, 1.06), 0.5, 0.45
MODULES = [("gov", 8.0), ("brand", 45.0), ("games", 80.0), ("social", 128.0)]
MOD_SCALE = 1.2

root = None


def arc_point(deg, y=FRONT_Y - 0.01):
    a = math.radians(deg)
    return (ARC_C[0] + ARC_RX * math.sin(a), y, ARC_C[1] + ARC_RZ * math.cos(a))


# ---------------------------------------------------------------- materials

def wall_paint():
    return B.mat_noise("study_wall", srgb("#5b6672"), srgb("#55606b"), scale=7, rough=0.9, detail=3, spec=0.2)


def graphite():
    return B.mat("study_graphite", srgb("#2a2d32"), 0.45, metal=0.3, spec=0.45)


def graphite_dark():
    return B.mat("study_graphite_d", srgb("#1a1c20"), 0.5, spec=0.4)


def walnut():
    return B.mat_noise("study_walnut", srgb("#5a3b27"), srgb("#4a2f1f"), scale=12, rough=0.38, detail=5, spec=0.5)


def cream():
    return B.mat("study_cream", srgb("#ece6da"), 0.5, spec=0.4)


def teal_glow(strength=3.0):
    return B.mat_emit(f"teal_glow_{strength}", srgb("#5ff0d8"), strength)


def red_glow():
    return B.mat_emit("red_glow", srgb("#ff4a3d"), 5.0)


def floor_mat():
    if "study_floor" in B._mats:
        return B._mats["study_floor"]
    m = bpy.data.materials.new("study_floor")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.4
    p.inputs["Specular IOR Level"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.3
    br.inputs["Row Height"].default_value = 0.17
    br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Color1"].default_value = (*srgb("#6b4a33"), 1)
    br.inputs["Color2"].default_value = (*srgb("#5c3f2b"), 1)
    br.inputs["Mortar"].default_value = (*srgb("#3a281b"), 1)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], p.inputs["Base Color"])
    B._mats["study_floor"] = m
    return m


# ---------------------------------------------------------------- shell

def build_shell():
    B.use_collection("room")
    r = root
    wall = wall_paint()
    B.box_minmax("floor", (LEFT_X - 0.1, BACK_Y, -0.1), (RIGHT_X + 0.1, FRONT_Y + 0.1, 0.0), floor_mat(), bevel=0, parent=r)
    B.box_minmax("ceiling", (LEFT_X - WALL_T, BACK_Y, CEIL), (RIGHT_X + WALL_T, FRONT_Y + WALL_T, CEIL + 0.15),
                 B.mat("study_ceiling", srgb("#d9d6cf"), 0.9), bevel=0, parent=r)
    B.box_minmax("wall_front", (LEFT_X - WALL_T, FRONT_Y, 0), (RIGHT_X + WALL_T, FRONT_Y + WALL_T, CEIL), wall, bevel=0,
                 parent=r)
    B.box_minmax("wall_right", (RIGHT_X, BACK_Y, 0), (RIGHT_X + WALL_T, FRONT_Y, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_back", (LEFT_X - WALL_T, BACK_Y - WALL_T, 0), (RIGHT_X + WALL_T, BACK_Y, CEIL), wall, bevel=0,
                 parent=r)
    # left wall with the window
    x0, x1 = LEFT_X - WALL_T, LEFT_X
    B.box_minmax("wall_left_a", (x0, BACK_Y, 0), (x1, WIN_Y0, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_b", (x0, WIN_Y1, 0), (x1, FRONT_Y, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_c", (x0, WIN_Y0, 0), (x1, WIN_Y1, WIN_Z0), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_d", (x0, WIN_Y0, WIN_Z1), (x1, WIN_Y1, CEIL), wall, bevel=0, parent=r)
    fr = graphite_dark()
    B.box_minmax("win_sill", (LEFT_X - 0.08, WIN_Y0 - 0.04, WIN_Z0 - 0.04), (LEFT_X + 0.26, WIN_Y1 + 0.04, WIN_Z0),
                 walnut(), bevel=0.006, parent=r)
    for name, a, b in (("win_frame_l", (x0, WIN_Y0, WIN_Z0), (x1 + 0.02, WIN_Y0 + 0.05, WIN_Z1)),
                       ("win_frame_r", (x0, WIN_Y1 - 0.05, WIN_Z0), (x1 + 0.02, WIN_Y1, WIN_Z1)),
                       ("win_frame_t", (x0, WIN_Y0, WIN_Z1 - 0.05), (x1 + 0.02, WIN_Y1, WIN_Z1)),
                       ("win_mullion", (x0 + 0.05, (WIN_Y0 + WIN_Y1) / 2 - 0.025, WIN_Z0), (x1, (WIN_Y0 + WIN_Y1) / 2 + 0.025, WIN_Z1)),
                       ("win_transom", (x0 + 0.05, WIN_Y0, 1.92), (x1, WIN_Y1, 1.96))):
        B.box_minmax(name, a, b, fr, bevel=0.003, parent=r)
    # linen curtains bunched at both sides
    linen = B.mat_noise("linen", srgb("#b9b2a5"), srgb("#aaa293"), scale=300, rough=0.95, spec=0.15, bump=0.1)
    for k, (y0, y1) in enumerate(((WIN_Y0 - 0.34, WIN_Y0 + 0.06), (WIN_Y1 - 0.04, FRONT_Y - 0.01))):
        n = 5
        for j in range(n):
            y = y0 + (y1 - y0) * (j + 0.5) / n
            B.cylinder(f"curtain{k}_{j}", (y1 - y0) / n * 0.62, WIN_Z1 + 0.25, (LEFT_X + 0.1 + 0.02 * (j % 2), y,
                       (WIN_Z1 + 0.25) / 2 + 0.02), material=linen, verts=12, parent=r)
    B.cylinder("curtain_rod", 0.012, FRONT_Y - WIN_Y0 + 0.4, (LEFT_X + 0.1, (WIN_Y0 - 0.4 + FRONT_Y) / 2, WIN_Z1 + 0.3),
               (90, 0, 0), material=fr, verts=12, parent=r)
    # skirting
    sk = B.mat("skirting", srgb("#3d454e"), 0.6)
    B.box_minmax("skirt_front", (LEFT_X, FRONT_Y - 0.015, 0), (RIGHT_X, FRONT_Y, 0.09), sk, bevel=0.002, parent=r)
    B.box_minmax("skirt_left", (LEFT_X, WIN_Y1, 0), (LEFT_X + 0.015, FRONT_Y, 0.09), sk, bevel=0.002, parent=r)
    # rug under the chair
    rug = B.mat_noise("study_rug", srgb("#2b3542"), srgb("#323d4b"), scale=220, rough=0.95, spec=0.1, bump=0.2)
    B.box_minmax("rug", (-1.0, -1.4, 0.0), (1.1, 0.5, 0.012), rug, bevel=0.004, parent=r)
    B.box_minmax("rug_stripe", (-1.0, -1.2, 0.0), (1.1, -1.12, 0.013), B.mat("rug_teal", srgb("#3f8f86"), 0.95),
                 bevel=0.002, parent=r)


# ---------------------------------------------------------------- desk + chair

def build_desk():
    B.use_collection("desk")
    r = root
    x0, x1, y0, y1 = DESK
    B.box_minmax("desk_top", (x0, y0, DESK_TOP - 0.035), (x1, y1, DESK_TOP), walnut(), bevel=0.006, parent=r)
    g = graphite()
    for k, x in enumerate((x0 + 0.08, x1 - 0.08)):
        B.box_minmax(f"desk_leg{k}", (x - 0.025, y0 + 0.06, 0.03), (x + 0.025, y1 - 0.06, DESK_TOP - 0.035), g,
                     bevel=0.006, parent=r)
        B.box_minmax(f"desk_foot{k}", (x - 0.03, y0 + 0.02, 0.0), (x + 0.03, y1 - 0.02, 0.03), g, bevel=0.006, parent=r)
    B.box_minmax("desk_beam", (x0 + 0.1, y1 - 0.12, DESK_TOP - 0.1), (x1 - 0.1, y1 - 0.08, DESK_TOP - 0.035), g,
                 bevel=0.004, parent=r)
    return r


def build_chair(desk_root):
    """Walnut desk chair with a low curved back so the desk stays visible over his shoulder."""
    B.use_collection("chair")
    ch = stage.chair_frame(desk_root)
    wd = walnut()
    fab = B.mat_noise("chair_fabric", srgb("#5d6670"), srgb("#535b64"), scale=420, rough=0.95, spec=0.2, bump=0.15)
    B.superellipsoid("chair_seat", (0.46, 0.44, 0.06), (0, 0.0, 0.46), (0, 0, 0), material=fab, e=0.3, parent=ch)
    B.box("chair_seat_base", (0.44, 0.42, 0.03), (0, 0, 0.425), material=wd, bevel=0.008, parent=ch)
    segs = []
    for sx in (-1, 1):
        segs.append(((sx * 0.19, 0.17, 0.42), (sx * 0.22, 0.22, 0.0), 0.017))
        segs.append(((sx * 0.19, -0.17, 0.42), (sx * 0.22, -0.24, 0.0), 0.017))
        segs.append(((sx * 0.19, -0.17, 0.42), (sx * 0.2, -0.21, 0.72), 0.014))
    B.tubes("chair_legs", segs, wd, parent=ch, sides=8)
    arc = [(0.22 * math.sin(math.radians(a)), -0.2 - 0.06 * math.cos(math.radians(a)), 0.7) for a in range(-70, 71, 10)]
    B.tubes("chair_back", [(a, b, 0.03) for a, b in zip(arc[:-1], arc[1:])], wd, parent=ch, sides=8)
    return ch


# ---------------------------------------------------------------- desk props

def keyboard(parent, loc):
    """Low-profile keyboard: graphite case, cream keys, teal and red accents."""
    kr = B.empty("kb_root", loc, (0, 0, 0), parent=parent)
    W, D = 0.34, 0.12
    B.box("kb_case", (W, D, 0.018), (0, 0, 0.009), material=graphite(), bevel=0.004, parent=kr)
    keys = {}
    cols, rows = 15, 5
    cream_c, grey_c, teal_c, red_c = srgb("#ece6da"), srgb("#9ea4aa"), srgb("#5ac7b5"), srgb("#e2493f")
    for j in range(rows):
        for i in range(cols):
            c = cream_c
            if i in (0, cols - 1) or j == 0:
                c = grey_c
            if (i, j) == (0, 0):
                c = red_c
            if j == 4 and 4 <= i <= 10:
                c = cream_c
            if (i, j) == (cols - 2, 1):
                c = teal_c
            keys[(i, j, 0)] = c
    B.voxel_mesh("kb_keys", keys, 0.0205, (-W / 2 + 0.016, -D / 2 + 0.017, 0.024), chamfer=0.22, jitter=0.0,
                 scale_z=0.45, parent=kr)
    return kr


def trackpad(parent, loc):
    B.box("trackpad", (0.13, 0.1, 0.006), (loc[0], loc[1], loc[2] + 0.003), material=B.mat("pad_alu", srgb("#b9bcc1"),
          0.3, metal=0.7), bevel=0.003, parent=parent)


def mug(parent, loc):
    r = B.empty("mug_root", loc, (0, 0, 0), parent=parent)
    B.lathe("mug", [(0.0, 0.0), (0.038, 0.0), (0.04, 0.09), (0.036, 0.09), (0.034, 0.012), (0.0, 0.012)],
            material=B.mat("mug_cream", srgb("#e9e3d6"), 0.3, spec=0.6, coat=0.3), segs=32, parent=r)
    B.cylinder("mug_tea", 0.034, 0.002, (0, 0, 0.075), material=B.mat("tea", srgb("#6a3a1c"), 0.1, spec=0.7), verts=24,
               parent=r)
    B.tubes("mug_handle", [((0.038, 0, 0.07), (0.058, 0, 0.06), 0.006), ((0.058, 0, 0.06), (0.058, 0, 0.03), 0.006),
                           ((0.058, 0, 0.03), (0.038, 0, 0.022), 0.006)],
            B.mat("mug_cream", srgb("#e9e3d6"), 0.3, spec=0.6, coat=0.3), parent=r, sides=8)


def desk_lamp(parent, loc, yaw):
    """Graphite task lamp; the shade points down onto the right half of the desk."""
    r = B.empty("lamp_root", loc, (0, 0, yaw), parent=parent)
    g = graphite()
    B.cylinder("lamp_base", 0.075, 0.02, (0, 0, 0.01), material=g, verts=32, bevel=0.004, parent=r)
    a, b, c = (0, 0, 0.02), (0.0, 0.08, 0.36), (0.0, -0.12, 0.5)
    B.tubes("lamp_arm", [(a, b, 0.008), (b, c, 0.008)], g, parent=r, sides=10)
    B.superellipsoid("lamp_joint", (0.025, 0.025, 0.025), b, material=g, e=1.0, nu=12, nv=8, parent=r)
    B.lathe("lamp_shade", [(0.0, 0.07), (0.02, 0.07), (0.05, 0.03), (0.075, 0.0), (0.072, -0.004), (0.0, 0.05)],
            loc=(0.0, -0.17, 0.44), rot=(-25, 0, 0), material=B.mat("lamp_shade", srgb("#2f3338"), 0.4, metal=0.4),
            segs=32, parent=r)
    B.superellipsoid("lamp_bulb", (0.05, 0.05, 0.02), (0.0, -0.172, 0.448), (-25, 0, 0),
                     material=B.mat_emit("bulb_warm", srgb("#ffd6a0"), 12.0), e=1.0, nu=16, nv=8, parent=r)
    return r


def notebook(parent, loc, rot):
    r = B.empty("note_root", loc, (0, 0, rot), parent=parent)
    B.box("note_cover", (0.15, 0.21, 0.012), (0, 0, 0.006), material=B.mat("note_cover", srgb("#2f4a55"), 0.7),
          bevel=0.002, parent=r)
    B.cylinder("note_pen", 0.004, 0.14, (0.09, 0.0, 0.004), (90, 0, 4), material=graphite_dark(), verts=10, parent=r)


# ---------------------------------------------------------------- AI core

def core_voxels():
    """6x6x6 cube with chamfered corners in cream and graphite, one red 'active' voxel."""
    n = 6
    vox = {}
    rng = random.Random(3)
    cr, gr = srgb("#ece6da"), srgb("#22252a")
    for i in range(n):
        for j in range(n):
            for k in range(n):
                edge = sum(v in (0, n - 1) for v in (i, j, k))
                if edge == 3:
                    continue
                c = gr if (i // 2 + j // 2 + k // 2) % 2 else cr
                if rng.random() < 0.08:
                    c = gr if c is cr else cr
                vox[(i, j, k)] = c
    vox[(n - 1, 1, 3)] = srgb("#e2493f")
    return vox


TOOLS = ["search", "doc", "image", "mail", "database", "calendar"]


def build_core():
    """The AI Agent: voxel core floating over its dock, an instruction ring with a waveform, six tool tiles."""
    B.use_collection("agent")
    cx, cy = CORE
    z0 = RISER[4]
    ar = B.empty("agent_root", (cx, cy, z0), (0, 0, 0), parent=root, hs="agent")
    g = graphite_dark()
    B.cylinder("core_dock", 0.09, 0.03, (0, 0, 0.015), material=g, verts=40, bevel=0.004, parent=ar)
    B.cylinder("core_dock_light", 0.092, 0.006, (0, 0, 0.026), material=teal_glow(4.0), verts=40, parent=ar)
    vs = 0.028
    zc = RING_Z - z0
    B.voxel_mesh("core_body", core_voxels(), vs, (-2.5 * vs, -2.5 * vs, zc - 2.5 * vs), chamfer=0.16, jitter=0.02,
                 rot=(0, 0, 18), parent=ar)
    # instruction ring: two thin tori and waveform bars standing on the inner one
    for name, rad, minor, st in (("ring_outer", 0.215, 0.0045, 3.5), ("ring_inner", 0.185, 0.0025, 2.5)):
        bpy.ops.mesh.primitive_torus_add(major_radius=rad, minor_radius=minor, major_segments=96, minor_segments=8)
        t = bpy.context.active_object
        for c in t.users_collection:
            c.objects.unlink(t)
        B.link(t)
        t.name = name
        t.data.materials.append(teal_glow(st))
        t.parent = ar
        t.location = (0, 0, zc)
        t.rotation_euler = (math.radians(-8), 0, 0)
    rng = random.Random(9)
    n = 72
    bars = []
    for k in range(n):
        a = 2 * math.pi * k / n
        env = 0.35 + 0.65 * abs(math.sin(a * 2.5)) * rng.uniform(0.6, 1.0)
        h = 0.008 + 0.034 * env
        p = (0.2 * math.cos(a), 0.2 * math.sin(a))
        bars.append(((p[0], p[1], zc - h / 2), (p[0], p[1], zc + h / 2), 0.0025))
    w = B.tubes("ring_wave", bars, teal_glow(3.0), parent=ar, sides=4)
    w.rotation_euler = (math.radians(-8), 0, 0)
    w.location = (0, 0, 0)
    # tool tiles floating around the ring, facing him; lines back to the core
    lines = []
    for k, name in enumerate(TOOLS):
        a = math.radians(-150 + 300 * k / (len(TOOLS) - 1))
        x, z = 0.29 * math.sin(a), zc + 0.08 + 0.13 * math.cos(a)
        y = -0.02 + 0.05 * math.cos(a)
        tile = B.empty(f"tool_{name}", (x, y, z), (0, 0, 0), parent=ar)
        B.box(f"tool_{name}_frame", (0.064, 0.012, 0.064), (0, 0.007, 0), material=g, bevel=0.003, parent=tile)
        B.plane(f"tool_{name}_icon", 0.056, 0.056, (0, 0.0, 0), (0, 0, 0),
                B.mat_image(f"tool_{name}", f"work_tool_{name}.png", rough=0.4, emission=1.6, interp="Closest"),
                parent=tile)
        lines.append(((x * 0.82, y + 0.01, z - (z - zc) * 0.18), (0.0, 0.0, zc), 0.0018))
    B.tubes("tool_links", lines[1:], teal_glow(2.0), parent=ar, sides=4)
    B.tubes("tool_link_active", lines[:1], red_glow(), parent=ar, sides=4)
    sx, _, sz = lines[0][0]
    B.superellipsoid("tool_active_dot", (0.014, 0.014, 0.014), (sx, -0.015, sz), material=red_glow(), e=1.0, nu=12,
                     nv=6, parent=ar)
    B.plane("agent_plate", 0.15, 0.033, (0, -0.092, 0.016), (-12, 0, 0),
            B.mat_image("plate_agent", "work_plate_agent.png", rough=0.5, emission=0.5), parent=ar)
    return ar


# ---------------------------------------------------------------- riser + career modules

def build_riser():
    B.use_collection("riser")
    x0, x1, y0, y1, top = RISER
    g = graphite()
    B.box_minmax("riser_top", (x0, y0, top - 0.018), (x1, y1, top), g, bevel=0.004, parent=root)
    for k, x in enumerate((x0 + 0.04, (x0 + x1) / 2 + 0.2, x1 - 0.04)):
        B.box_minmax(f"riser_foot{k}", (x - 0.02, y0 + 0.02, DESK_TOP), (x + 0.02, y1 - 0.02, top - 0.018), g, bevel=0.003,
                     parent=root)
    # the bus: a lit groove along the riser front from the newest module into the core
    B.box_minmax("riser_bus", (CORE[0] + 0.09, y0 - 0.002, top - 0.012), (x1 - 0.03, y0, top - 0.006), teal_glow(3.0),
                 bevel=0, parent=root)


def module_base(key, parent, w=0.24, d=0.15):
    B.box(f"{key}_base", (w, d, 0.022), (0, 0, 0.011), material=graphite(), bevel=0.004, parent=parent)
    B.plane(f"{key}_plate", w * 0.8, w * 0.8 * 112 / 512, (0, -d / 2 - 0.0012, 0.011), (0, 0, 0),
            B.mat_image(f"plate_{key}", f"work_plate_{key}.png", rough=0.5, emission=0.35), parent=parent)
    B.cylinder(f"{key}_port", 0.008, 0.01, (w / 2 - 0.02, -d / 2 - 0.004, 0.011), (90, 0, 0), material=teal_glow(4.0),
               verts=12, parent=parent)


def vox(name, cells, size, origin, parent, **kw):
    return B.voxel_mesh(name, cells, size, origin, chamfer=0.16, jitter=0.03, parent=parent, **kw)


def mod_gov(r):
    """电子政务: a small civic hall with columns, and a phone beside it showing a green chat bubble."""
    s = 0.012
    stone, roof, dark = srgb("#d9d4c8"), srgb("#8c96a0"), srgb("#5a646e")
    c = {}
    for i in range(12):
        for j in range(6):
            c[(i, j, 0)] = stone
            c[(i, j, 1)] = stone
    for i in range(1, 11, 2):
        for k in range(2, 7):
            c[(i, 1, k)] = stone
    for i in range(1, 11):
        for j in range(2, 6):
            for k in range(2, 7):
                c[(i, j, k)] = dark if k in (3, 5) and i % 2 == 0 else stone
    for k, (a, b) in enumerate(((0, 12), (1, 11), (3, 9), (5, 7))):
        for i in range(a, b):
            for j in range(0, 6):
                c[(i, j, 7 + k)] = roof
    vox("gov_hall", c, s, (-0.115, -0.03, 0.022), r)
    ph = B.empty("gov_phone", (0.075, -0.0, 0.022), (0, 0, -8), parent=r)
    B.box("gov_phone_body", (0.05, 0.01, 0.095), (0, 0, 0.0475), material=graphite_dark(), bevel=0.004, parent=ph)
    B.box("gov_phone_screen", (0.042, 0.002, 0.082), (0, -0.0055, 0.0475), material=B.mat("gov_screen", srgb("#e9eef0"),
          0.4, emission=srgb("#e9eef0"), estr=0.8), bevel=0, parent=ph)
    for k, (x, z, w, col) in enumerate(((-0.006, 0.07, 0.024, "#7fd36b"), (0.006, 0.05, 0.022, "#ffffff"),
                                        (-0.004, 0.03, 0.028, "#7fd36b"))):
        B.box(f"gov_bubble{k}", (w, 0.002, 0.011), (x, -0.007, z), material=B.mat(f"bubble_{col}", srgb(col), 0.4,
              emission=srgb(col), estr=0.6), bevel=0.002, parent=ph)


def mod_brand(r):
    """品牌营销 / 游戏化互动: a parkour track over an arch, a strip of great-wall bricks, brand colour blocks."""
    s = 0.012
    c = {}
    track, arch, brick = srgb("#2f3338"), srgb("#e8dcc4"), srgb("#b5764f")
    for i in range(18):
        c[(i, 2, 0)] = track
        c[(i, 3, 0)] = track
    for i in range(18):
        if i % 3 != 1:
            c[(i, 2, 1)] = srgb("#f2f0ea") if i % 2 else track
    for i in range(6, 12):
        for k in range(1, 7):
            if not (7 <= i <= 10 and k <= 4) or k >= 6:
                c[(i, 6, k)] = arch
    for i in range(0, 6):
        for k in range(1, 3 + (i % 2)):
            c[(i, 9, k)] = brick
    for i in range(12, 18):
        for k in range(1, 3 + ((i + 1) % 2)):
            c[(i, 9, k)] = brick
    for (i, k, col) in ((2, 2, "#f2b632"), (14, 3, "#e2493f"), (9, 8, "#f2b632"), (4, 4, "#3aa0e0"), (16, 5, "#f2b632")):
        c[(i, 4, k)] = srgb(col)
    vox("brand_set", c, s, (-0.105, -0.055, 0.022), r)
    runner = {(0, 0, 0): srgb("#1d1f24"), (0, 0, 1): srgb("#e2493f"), (0, 0, 2): srgb("#f1c49c")}
    vox("brand_runner", runner, 0.009, (-0.04, -0.03, 0.04), r)


def mod_games(r):
    """游戏: a checkerboard level with a hero, a coin and a pixel heart, a controller in front."""
    s = 0.012
    c = {}
    for i in range(16):
        for j in range(8):
            c[(i, j, 0)] = srgb("#2d3a2e") if (i + j) % 2 else srgb("#3d5a3c")
    for (i, j, h) in ((3, 5, 3), (4, 5, 3), (11, 6, 2), (12, 6, 4), (12, 5, 2)):
        for k in range(1, h + 1):
            c[(i, j, k)] = srgb("#7cc46a")
    for k, col in ((1, "#2f62d0"), (2, "#e2493f"), (3, "#f1c49c")):
        c[(7, 3, k)] = srgb(col)
    c[(9, 3, 2)] = srgb("#f2c84b")
    for (i, k) in ((13, 3), (15, 3), (13, 4), (14, 4), (15, 4), (14, 2)):
        c[(i, 7, k + 2)] = srgb("#e2493f")
    vox("games_level", c, s, (-0.096, -0.04, 0.022), r)
    pad = B.empty("games_pad", (0.0, -0.06, 0.022), (0, 0, 4), parent=r)
    B.superellipsoid("pad_body", (0.08, 0.04, 0.016), (0, 0, 0.008), material=B.mat("pad_grey", srgb("#c9ccd1"), 0.45),
                     e=0.4, parent=pad)
    B.box("pad_dpad", (0.016, 0.006, 0.004), (-0.022, -0.004, 0.017), material=graphite_dark(), bevel=0.001, parent=pad)
    B.box("pad_dpad2", (0.006, 0.016, 0.004), (-0.022, -0.004, 0.017), material=graphite_dark(), bevel=0.001, parent=pad)
    for k, (x, y) in enumerate(((0.02, -0.002), (0.028, 0.006))):
        B.cylinder(f"pad_btn{k}", 0.004, 0.005, (x, y, 0.017), material=B.mat("pad_red", srgb("#c8323a"), 0.4), verts=12,
                   parent=pad)


def mod_social(r):
    """社交: a round voice room — small avatars around a mic, sound rings rising from it."""
    B.cylinder("social_room", 0.1, 0.014, (0, 0.01, 0.029), material=B.mat("social_floor", srgb("#3a3550"), 0.6),
               verts=48, bevel=0.003, parent=r)
    cols = ["#f2b632", "#e2493f", "#3aa0e0", "#7cc46a", "#b58cf0", "#ece6da"]
    rng = random.Random(4)
    for k, col in enumerate(cols):
        a = math.radians(-60 + k * 52)
        x, y = 0.072 * math.sin(a), 0.01 + 0.072 * math.cos(a)
        cells = {(0, 0, 0): srgb("#2b2d33"), (0, 0, 1): srgb(col), (0, 0, 2): srgb(rng.choice(["#f1c49c", "#d9a07a"]))}
        vox(f"social_avatar{k}", cells, 0.012, (x - 0.006, y - 0.006, 0.036), r)
    B.cylinder("social_mic_stand", 0.003, 0.05, (0, 0.01, 0.061), material=graphite_dark(), verts=8, parent=r)
    B.superellipsoid("social_mic", (0.016, 0.016, 0.024), (0, 0.01, 0.092), material=graphite_dark(), e=0.8, nu=12, nv=8,
                     parent=r)
    for k, rad in enumerate((0.03, 0.045, 0.06)):
        bpy.ops.mesh.primitive_torus_add(major_radius=rad, minor_radius=0.0016, major_segments=48, minor_segments=6)
        t = bpy.context.active_object
        for c in t.users_collection:
            c.objects.unlink(t)
        B.link(t)
        t.name = f"social_wave{k}"
        t.data.materials.append(B.mat_emit("social_wave", srgb("#b58cf0"), 3.0))
        t.parent = r
        t.location = (0, 0.01, 0.12 + 0.012 * k)


def build_modules():
    """Career modules, wired oldest to newest; the cable ends in the core."""
    B.use_collection("modules")
    build = {"gov": mod_gov, "brand": mod_brand, "games": mod_games, "social": mod_social}
    g = graphite_dark()
    for key, deg in MODULES:
        x, _, z = arc_point(deg)
        if key == "social":
            r = B.empty(f"{key}_root", (x - 0.02, (RISER[2] + RISER[3]) / 2, RISER[4]), (0, 0, 0), parent=root, hs=key)
        else:
            r = B.empty(f"{key}_root", (x, FRONT_Y - 0.1, z - 0.07), (0, 0, 0), parent=root, hs=key)
            r.scale = (MOD_SCALE,) * 3
            # wall bracket under the module
            B.box(f"{key}_bracket", (0.03, 0.16, 0.05), (0.0, 0.03, -0.025), material=g, bevel=0.004, parent=r)
        module_base(key, r)
        build[key](r)
        lt = bpy.data.lights.new(f"{key}_light", "POINT")
        lt.energy = 1.4
        lt.color = (1.0, 0.92, 0.82)
        lt.shadow_soft_size = 0.05
        lo = bpy.data.objects.new(f"{key}_light", lt)
        B.link(lo)
        lo.parent = r
        lo.location = (0.0, -0.16, 0.16)
    # the cable: along the arc on the wall, down to the riser, along the bus into the core
    pts = [arc_point(d, FRONT_Y - 0.012) for d in np.linspace(MODULES[0][1] - 6, MODULES[-2][1] + 18, 40)]
    xe, _, ze = pts[-1]
    pts += [(xe - 0.02, FRONT_Y - 0.02, ze - 0.06), (xe - 0.06, RISER[3] - 0.02, RISER[4] + 0.004)]
    pts = [(x, y, z - 0.07) for x, y, z in pts[:-2]] + pts[-2:]
    segs = [(a, b, 0.006) for a, b in zip(pts[:-1], pts[1:])]
    B.tubes("career_cable", segs, teal_glow(2.2), parent=root, sides=8)
    # brighter beads travelling along it
    bead = teal_glow(8.0)
    for k, t in enumerate(np.linspace(0.08, 0.92, 7)):
        i = int(t * (len(pts) - 1))
        p = pts[i]
        B.superellipsoid(f"cable_bead{k}", (0.016, 0.016, 0.016), p, material=bead, e=1.0, nu=10, nv=6, parent=root)


# ---------------------------------------------------------------- room dressing

def floor_lamp(loc):
    """Paper lantern on a stand in the corner behind him: a warm rim on his hair."""
    r = B.empty("flamp_root", loc, (0, 0, 0), parent=root)
    g = graphite_dark()
    B.cylinder("flamp_base", 0.12, 0.02, (0, 0, 0.01), material=g, verts=32, parent=r)
    B.cylinder("flamp_pole", 0.008, 1.42, (0, 0, 0.72), material=g, verts=10, parent=r)
    B.superellipsoid("flamp_shade", (0.36, 0.36, 0.42), (0, 0, 1.62), material=B.mat_emit("paper_glow", srgb("#ffd9a8"), 3.2),
                     e=0.9, nu=24, nv=12, parent=r)


def wall_clock(loc, r=0.13, hm=(1, 40)):
    c = B.empty("clock_root", loc, (90, 0, 0), parent=root)
    B.cylinder("clock_rim", r, 0.035, (0, 0, 0.0175), material=graphite_dark(), verts=48, bevel=0.004, parent=c)
    B.cylinder("clock_face", r - 0.012, 0.002, (0, 0, 0.036), material=cream(), verts=48, parent=c)
    ink = graphite_dark()
    for k in range(12):
        a = math.radians(k * 30)
        L = 0.022 if k % 3 == 0 else 0.01
        mid = r - 0.026 - L / 2
        B.box(f"clock_tick{k}", (0.005, L, 0.004), (mid * math.sin(a), mid * math.cos(a), 0.039), (0, 0, -k * 30),
              material=ink, bevel=0, parent=c)
    h, m = hm
    for name, ang, L, w in (("clock_h", (h % 12 + m / 60) * 30, 0.06, 0.008), ("clock_m", m * 6, 0.09, 0.005)):
        a = math.radians(ang)
        B.tubes(name, [((0, 0, 0.041), (L * math.sin(a), L * math.cos(a), 0.041), w / 2)], ink, parent=c, sides=6)
    B.tubes("clock_s", [((0, 0, 0.043), (0.1 * math.sin(math.radians(150)), 0.1 * math.cos(math.radians(150)), 0.043), 0.0015)],
            red_glow(), parent=c, sides=4)


def build_dressing():
    B.use_collection("dressing")
    wall_clock((0.3, FRONT_Y - 0.001, 1.95))
    floor_lamp((LEFT_X + 0.35, -1.1, 0.0))
    # a plant in the window corner, a framed photo on the wall left of the arc
    pot = P.pot("sill_plant", 0.07, 0.055, 0.12, "#c9785e", (LEFT_X + 0.1, WIN_Y1 - 0.08, WIN_Z0), parent=root)
    P.plant("sill_plant", pot, 0.11, 16, 0.3, 0.2, 0.12, 0.06, seed=33, droop=0.4)
    P.framed("photo_family", "photo_park.png", 0.26, 0.34, (-0.66, FRONT_Y - 0.015, 1.48), parent=root,
             frame_col="#1f2125", mat_w=0.025)
    # books on the desk's left end and a short shelf high on the right
    P.book_stack("desk_books", root, -0.62, 0.55, DESK_TOP, 3, random.Random(12), rot=8)
    wd = walnut()
    shelf = B.empty("wshelf_root", (0.82, FRONT_Y - 0.1, 1.56), (0, 0, 0), parent=root)
    B.box_minmax("wshelf", (0.0, -0.1, -0.025), (0.6, 0.1, 0.0), wd, bevel=0.004, parent=shelf)
    P.book_row("wshelf_books", shelf, 0.03, 0.42, 0.0, 0.16, random.Random(41), max_h=0.24)


def build_lights():
    B.use_collection("lights")
    # desk lamp
    lamp = bpy.data.lights.new("lamp", "SPOT")
    lamp.energy = 22
    lamp.color = (1.0, 0.76, 0.5)
    lamp.spot_size = math.radians(95)
    lamp.spot_blend = 0.6
    lamp.shadow_soft_size = 0.03
    lo = bpy.data.objects.new("lamp", lamp)
    B.link(lo)
    lo.parent = bpy.data.objects["lamp_root"]
    lo.location = (0.0, -0.18, 0.43)
    lo.rotation_euler = (math.radians(-25), 0, 0)
    # the core lights his face
    cl = bpy.data.lights.new("core_light", "POINT")
    cl.energy = 6.0
    cl.color = (0.4, 1.0, 0.88)
    cl.shadow_soft_size = 0.12
    co = bpy.data.objects.new("core_light", cl)
    B.link(co)
    co.parent = root
    co.location = (CORE[0], CORE[1] - 0.12, RING_Z)
    # lantern behind him
    fl = bpy.data.lights.new("lantern", "POINT")
    fl.energy = 40
    fl.color = (1.0, 0.8, 0.58)
    fl.shadow_soft_size = 0.17
    fo = bpy.data.objects.new("lantern", fl)
    B.link(fo)
    fo.parent = root
    fo.location = (LEFT_X + 0.35, -1.1, 1.62)
    # moonlight through the window
    import nightcity
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 0.25
    sun.angle = math.radians(1.0)
    sun.color = (0.7, 0.8, 1.0)
    so = bpy.data.objects.new("sun", sun)
    B.link(so)
    so.rotation_euler = (-nightcity.MOON_DIR()).to_track_quat("-Z", "Y").to_euler()
    # cool fill from the camera side so the blacks keep some detail
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 28
    fill.size = 3.0
    fill.color = (0.75, 0.85, 1.0)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.location = (0.6, -2.0, 2.4)
    stage.look_at(f, (0, 1.6, 0.9))
    pl = bpy.data.lights.new("window_portal", "AREA")
    pl.shape = "RECTANGLE"
    pl.size, pl.size_y = WIN_Y1 - WIN_Y0, WIN_Z1 - WIN_Z0
    pl.energy = 0
    try:
        pl.cycles.is_portal = True
    except Exception:
        pass
    po = bpy.data.objects.new("window_portal", pl)
    B.link(po)
    po.parent = root
    po.location = (LEFT_X - WALL_T - 0.02, (WIN_Y0 + WIN_Y1) / 2, (WIN_Z0 + WIN_Z1) / 2)
    po.rotation_euler = (math.radians(90), 0, math.radians(90))


def build_all():
    global root
    import models_char as C
    root = stage.desk_frame("study_root")
    build_shell()
    build_desk()
    chair = build_chair(root)
    C.build_character(chair, arms="type")
    build_riser()
    build_core()
    build_modules()
    B.use_collection("desk_props")
    keyboard(root, (0.0, 0.36, DESK_TOP))
    trackpad(root, (0.28, 0.34, DESK_TOP))
    mug(root, (0.5, 0.2, DESK_TOP))
    notebook(root, (-0.4, 0.3, DESK_TOP), 12)
    desk_lamp(root, (0.92, 0.62, DESK_TOP), -45)
    # 烧酒 sleeps under the lamp, 小八 has the window sill
    C.build_shaojiu(root, (0.82, 0.46, DESK_TOP), 8).scale = (0.55,) * 3
    C.build_xiaoba(root, (LEFT_X + 0.13, 0.12, WIN_Z0), 90).scale = (0.62,) * 3
    build_dressing()
