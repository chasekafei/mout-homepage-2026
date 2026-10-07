"""此刻: a corner café — shell, shopfront, banquette, coffee bar, the window table and its props.

Same seat and camera as the creation room (``stage``): the table sits on the desk frame, the shopfront
glass runs across the view behind it, the coffee bar follows the angled left wall.
"""
from __future__ import annotations

import math
import random

import bpy
import numpy as np
from mathutils import Vector

import blib as B
import props_room as P
import stage
from blib import srgb
from stage import look_at

CEIL = 3.3
GLASS_Y = 3.4            # inner face of the shopfront
FRAME_T = 0.14
OUT_Y = GLASS_Y + FRAME_T
FRONT_Y = -2.6
RIGHT_X = 4.8
LEFT_X = -8.0
WALL_T = 0.3
CORNER = Vector((-1.25, GLASS_Y, 0))
LW_DIR = Vector((-0.92, -0.39, 0)).normalized()
LW_LEN = 7.5
LW_ANGLE = math.atan2(-LW_DIR.y, -LW_DIR.x)
LW_NORMAL = Vector((-LW_DIR.y, LW_DIR.x, 0))
SILL_Z = 0.86            # window ledge / bottom of the glass
TRANSOM_Z = 2.45
HEAD_Z = 2.95
MULLIONS = (0.25, 1.75, 3.25)
RWIN_Y0, RWIN_Y1, RWIN_Z0, RWIN_Z1 = -1.4, 2.9, 0.75, 2.9
DESK_TOP = stage.DESK_TOP
TABLE = (-0.5, 0.92, 0.0, 0.74)        # desk-local x0, x1, y0, y1
BANQ_Y0 = 2.55                          # front edge of the banquette seat
BANQ_Z = 0.53                           # top of the seat cushion
LEDGE_Y0 = GLASS_Y - 0.36

# toward the sun: low morning sun behind-right, low enough to reach the table through the side window
SUN_DIR = Vector((0.85, -0.37, 0.36)).normalized()


def on_left_wall(s, z, d=0.0):
    p = CORNER + LW_DIR * s + LW_NORMAL * d
    return (p.x, p.y, z)


def wall_root(name, s, d=0.0, z=0.0):
    """Empty on the left wall: local +X runs toward the corner, -Y points into the room."""
    return B.empty(name, on_left_wall(s, z, d), (0, 0, math.degrees(LW_ANGLE)))


# ---------------------------------------------------------------- materials

def plaster():
    return B.mat_noise("cafe_plaster", srgb("#f2ece1"), srgb("#ebe3d6"), scale=6, rough=0.92, detail=3, spec=0.2)


def sage():
    return B.mat("cafe_sage", srgb("#8ea58c"), 0.55, spec=0.35)


def sage_dark():
    return B.mat("cafe_sage_dark", srgb("#5f7a68"), 0.55, spec=0.35)


def steel():
    return B.mat("cafe_steel", srgb("#20282a"), 0.38, metal=0.5)


def oak():
    return B.mat_noise("cafe_oak", srgb("#c4945f"), srgb("#b3824f"), scale=14, rough=0.42, detail=5, spec=0.45)


def walnut():
    return B.mat("cafe_walnut", srgb("#4a3324"), 0.45, spec=0.45)


def fabric(name, color, scale=380):
    c = srgb(color)
    return B.mat_noise(f"fab_{name}", c, tuple(x * 0.9 for x in c), scale=scale, rough=0.95, spec=0.2, bump=0.15)


def ceramic(color="#f4f1ea", name=None):
    return B.mat(name or f"ceramic_{color}", srgb(color), 0.25, spec=0.6, coat=0.3)


# ---------------------------------------------------------------- shell

def build_shell():
    B.use_collection("room")
    pl, sg, st = plaster(), sage(), steel()
    floor = B.mat_image("cafe_terrazzo", "now_terrazzo.png", rough=0.3, spec=0.5, repeat=(10.6, 5.1))
    w, h = RIGHT_X - LEFT_X, OUT_Y - FRONT_Y
    B.plane("floor", w, h, ((LEFT_X + RIGHT_X) / 2, (FRONT_Y + OUT_Y) / 2, 0.0), (-90, 0, 0), floor)
    B.box_minmax("floor_base", (LEFT_X, FRONT_Y, -0.2), (RIGHT_X, OUT_Y, -0.004), floor, bevel=0)
    B.box_minmax("ceiling", (LEFT_X, FRONT_Y, CEIL), (RIGHT_X + WALL_T, OUT_Y, CEIL + 0.2), pl, bevel=0)
    mid = CORNER + LW_DIR * (LW_LEN / 2) - LW_NORMAL * (WALL_T / 2)
    rot = (0, 0, math.degrees(LW_ANGLE))
    B.box("wall_left", (LW_LEN, WALL_T, CEIL), (mid.x, mid.y, CEIL / 2), rot, pl, bevel=0)
    wmid = CORNER + LW_DIR * (LW_LEN / 2) + LW_NORMAL * 0.01
    B.box("wainscot_left", (LW_LEN, 0.02, 1.05), (wmid.x, wmid.y, 0.525), rot, sg, bevel=0.002)
    B.box_minmax("wall_front", (LEFT_X, FRONT_Y - WALL_T, 0), (RIGHT_X, FRONT_Y, CEIL), pl, bevel=0)
    # right wall with a tall side window that lets the morning sun in
    B.box_minmax("wall_right_a", (RIGHT_X, FRONT_Y, 0), (RIGHT_X + WALL_T, RWIN_Y0, CEIL), pl, bevel=0)
    B.box_minmax("wall_right_b", (RIGHT_X, RWIN_Y1, 0), (RIGHT_X + WALL_T, OUT_Y, CEIL), pl, bevel=0)
    B.box_minmax("wall_right_c", (RIGHT_X, RWIN_Y0, 0), (RIGHT_X + WALL_T, RWIN_Y1, RWIN_Z0), pl, bevel=0)
    B.box_minmax("wall_right_d", (RIGHT_X, RWIN_Y0, RWIN_Z1), (RIGHT_X + WALL_T, RWIN_Y1, CEIL), pl, bevel=0)
    for k in range(1, 4):
        y = RWIN_Y0 + (RWIN_Y1 - RWIN_Y0) * k / 4
        B.box_minmax(f"rwin_mull{k}", (RIGHT_X, y - 0.035, RWIN_Z0), (RIGHT_X + 0.08, y + 0.035, RWIN_Z1), st, bevel=0)
    B.box_minmax("rwin_tr", (RIGHT_X, RWIN_Y0, 2.3), (RIGHT_X + 0.08, RWIN_Y1, 2.35), st, bevel=0)
    for name, y0, y1, z1 in (("a", FRONT_Y, RWIN_Y0, 1.05), ("b", RWIN_Y0, RWIN_Y1, RWIN_Z0), ("c", RWIN_Y1, GLASS_Y, 1.05)):
        B.box_minmax(f"wainscot_r{name}", (RIGHT_X - 0.02, y0, 0), (RIGHT_X, y1, z1), sg, bevel=0.002)
    rail = oak()
    B.box_minmax("rail_r", (RIGHT_X - 0.035, RWIN_Y1, 1.03), (RIGHT_X, GLASS_Y, 1.07), rail, bevel=0.004)
    B.box("rail_l", (LW_LEN, 0.035, 0.04), (wmid.x + LW_NORMAL.x * 0.01, wmid.y + LW_NORMAL.y * 0.01, 1.05), rot,
          rail, bevel=0.004)
    build_shopfront()
    # exposed track lights and a beam along the ceiling
    for k, y in enumerate((0.4, 2.2)):
        B.box_minmax(f"track{k}", (-3.0, y - 0.02, CEIL - 0.05), (4.4, y + 0.02, CEIL), st, bevel=0.004)


def build_shopfront():
    """Steel-framed glazing from the corner column to the right wall; the openings stay empty (no glass)."""
    st, sd = steel(), sage_dark()
    x0, x1 = CORNER.x, RIGHT_X
    B.box_minmax("bulkhead", (x0, GLASS_Y, 0), (x1, OUT_Y, SILL_Z), sd, bevel=0)
    B.box_minmax("header", (x0, GLASS_Y, HEAD_Z), (x1, OUT_Y, CEIL), sd, bevel=0)
    B.box_minmax("glaze_bottom", (x0, GLASS_Y, SILL_Z), (x1, GLASS_Y + 0.09, SILL_Z + 0.05), st, bevel=0.004)
    B.box_minmax("glaze_top", (x0, GLASS_Y, HEAD_Z - 0.06), (x1, GLASS_Y + 0.09, HEAD_Z), st, bevel=0.004)
    B.box_minmax("transom", (x0, GLASS_Y, TRANSOM_Z), (x1, GLASS_Y + 0.09, TRANSOM_Z + 0.055), st, bevel=0.004)
    for k, x in enumerate(MULLIONS):
        B.box_minmax(f"mullion{k}", (x - 0.04, GLASS_Y, SILL_Z), (x + 0.04, GLASS_Y + 0.09, HEAD_Z), st, bevel=0.004)
        # slim glazing bars split the transom lights
        for j in (1, 2):
            xx = x - 1.5 + 0.5 * j if x > MULLIONS[0] else x0 + (x - x0) * j / 3
            B.box_minmax(f"tbar{k}{j}", (xx - 0.015, GLASS_Y + 0.01, TRANSOM_Z), (xx + 0.015, GLASS_Y + 0.07, HEAD_Z),
                         st, bevel=0.002)
    for j in (1, 2):
        xx = MULLIONS[-1] + (x1 - MULLIONS[-1]) * j / 3
        B.box_minmax(f"tbar_r{j}", (xx - 0.015, GLASS_Y + 0.01, TRANSOM_Z), (xx + 0.015, GLASS_Y + 0.07, HEAD_Z),
                     st, bevel=0.002)
    B.box_minmax("post_right", (x1 - 0.1, GLASS_Y, 0), (x1, OUT_Y, CEIL), st, bevel=0.004)
    B.box("corner_column", (0.26, 0.26, CEIL), (x0 - 0.05, GLASS_Y + 0.02, CEIL / 2), (0, 0, 0), sd, bevel=0.01)
    # window ledge: deep enough for a cat
    B.box_minmax("ledge", (x0 + 0.08, LEDGE_Y0, SILL_Z - 0.045), (x1 - 0.1, GLASS_Y + 0.02, SILL_Z), oak(), bevel=0.006)


# ---------------------------------------------------------------- banquette

def build_banquette():
    B.use_collection("banquette")
    sd, sg = sage_dark(), sage()
    x0, x1 = CORNER.x + 0.18, RIGHT_X - 0.25
    B.box_minmax("banq_base", (x0, BANQ_Y0 + 0.04, 0.06), (x1, LEDGE_Y0, 0.43), sd, bevel=0.008)
    B.box_minmax("banq_toe", (x0 + 0.02, BANQ_Y0 + 0.1, 0), (x1 - 0.02, LEDGE_Y0, 0.06),
                 B.mat("toe_dark", srgb("#2e3833"), 0.7), bevel=0)
    B.box_minmax("banq_back", (x0, LEDGE_Y0, 0.0), (x1, GLASS_Y, SILL_Z - 0.045), sg, bevel=0.004)
    # vertical panel grooves on the base front
    for k, x in enumerate(np.arange(x0 + 0.3, x1 - 0.1, 0.3)):
        B.box_minmax(f"banq_groove{k}", (x - 0.006, BANQ_Y0 + 0.035, 0.08), (x + 0.006, BANQ_Y0 + 0.045, 0.41),
                     B.mat("groove", srgb("#4c6455"), 0.6), bevel=0)
    cush = fabric("mustard", "#d6a143")
    n = 4
    L = (x1 - x0) / n
    for k in range(n):
        cx = x0 + L * (k + 0.5)
        B.superellipsoid(f"banq_cushion{k}", (L - 0.02, LEDGE_Y0 - BANQ_Y0 + 0.02, 0.1), (cx, (BANQ_Y0 + LEDGE_Y0) / 2,
                         BANQ_Z - 0.05), (0, 0, 0), material=cush, e=0.22, puff=0.08)
    # back cushions leaning on the ledge cabinet (gap left for 小八 at the left end)
    pillows = [(-0.75, "#ece5d6", 4), (1.0, "#c9785e", -3), (1.62, "#ece5d6", 2), (2.55, "#6f8a72", -4),
               (3.2, "#ece5d6", 3), (3.85, "#c9785e", -2)]
    for k, (x, col, r) in enumerate(pillows):
        P.pillow(f"banq_pillow{k}", (0.42, 0.14, 0.34), (x, LEDGE_Y0 - 0.08, BANQ_Z + 0.16), (-14, 0, r), color=col)


# ---------------------------------------------------------------- table + chair

table_root = None


def build_table():
    global table_root
    B.use_collection("desk")
    table_root = stage.desk_frame()
    x0, x1, y0, y1 = TABLE
    t = 0.035
    top = B.mat_noise("table_oak", srgb("#c79a68"), srgb("#b98a58"), scale=10, rough=0.32, detail=5, spec=0.5)
    B.box_minmax("desk_top", (x0, y0, DESK_TOP - t), (x1, y1, DESK_TOP), top, bevel=0.006, parent=table_root)
    iron = B.mat("cast_iron", srgb("#1e2224"), 0.5, metal=0.4)
    for k, x in enumerate((x0 + 0.22, x1 - 0.22)):
        y = (y0 + y1) / 2
        B.cylinder(f"tbl_col{k}", 0.03, DESK_TOP - t - 0.05, (x, y, (DESK_TOP - t + 0.05) / 2), material=iron, verts=20,
                   parent=table_root)
        B.box(f"tbl_cap{k}", (0.24, 0.5, 0.025), (x, y, DESK_TOP - t - 0.0125), material=iron, bevel=0.004,
              parent=table_root)
        for a in (0, 90):
            B.box(f"tbl_foot{k}_{a}", (0.5, 0.06, 0.04), (x, y, 0.025), (0, 0, a + 45), material=iron, bevel=0.01,
                  parent=table_root)
    return table_root


def bentwood_chair(name, parent, loc=(0, 0, 0), rot=0.0, hs=None):
    """Thonet-style café chair; local -Y is the back."""
    root = B.empty(f"{name}_root", loc, (0, 0, rot), parent=parent, hs=hs)
    wd = walnut()
    cane = B.mat_noise("cane", srgb("#d8bd86"), srgb("#c3a46b"), scale=900, rough=0.8, bump=0.3, spec=0.25)
    B.cylinder(f"{name}_seat", 0.205, 0.022, (0, 0.02, 0.499), material=cane, verts=40, parent=root)
    B.cylinder(f"{name}_rim", 0.215, 0.04, (0, 0.02, 0.485), material=wd, verts=40, parent=root)
    segs = []
    for sx in (-1, 1):
        segs.append(((sx * 0.15, 0.15, 0.47), (sx * 0.2, 0.22, 0.0), 0.016))
        segs.append(((sx * 0.155, -0.12, 0.47), (sx * 0.19, -0.2, 0.0), 0.016))
    # back hoop rises from the rear legs
    arc = []
    for i in range(15):
        a = math.pi * i / 14
        arc.append((0.16 * math.cos(a), -0.15 - 0.035 * math.sin(a), 0.5 + 0.29 * math.sin(a) ** 0.8))
    arc = [(0.16, -0.135, 0.47)] + arc + [(-0.16, -0.135, 0.47)]
    for a, b in zip(arc[:-1], arc[1:]):
        segs.append((a, b, 0.014))
    ring = [(0.19 * math.cos(2 * math.pi * i / 20), 0.02 + 0.19 * math.sin(2 * math.pi * i / 20), 0.2) for i in range(21)]
    for a, b in zip(ring[:-1], ring[1:]):
        segs.append((a, b, 0.009))
    B.tubes(f"{name}_frame", segs, wd, parent=root, sides=8)
    return root


def build_chair():
    B.use_collection("chair")
    return bentwood_chair("chair", stage.chair_frame(table_root))


# ---------------------------------------------------------------- table props

def laptop_open(parent, loc, rot):
    root = B.empty("laptop_root", loc, (0, 0, rot), parent=parent, hs="project")
    al = B.mat("laptop_silver", srgb("#c9cbd0"), 0.3, metal=0.75)
    dark = B.mat("laptop_dark", srgb("#18181a"), 0.5)
    w, d = 0.31, 0.215
    B.box("laptop_base", (w, d, 0.011), (0, 0, 0.0055), material=al, bevel=0.003, parent=root)
    B.box("laptop_keys", (w - 0.03, d * 0.45, 0.001), (0, 0.035, 0.0115), material=dark, bevel=0, parent=root)
    B.box("laptop_pad", (0.11, 0.07, 0.0008), (0, -0.06, 0.0112), material=B.mat("laptop_pad", srgb("#b8bac0"), 0.25,
                                                                              metal=0.6), bevel=0, parent=root)
    tilt = -16.0
    lid = B.empty("laptop_hinge", (0, d / 2, 0.011), (tilt, 0, 0), parent=root)
    B.box("laptop_lid", (w, 0.006, d), (0, 0.003, d / 2), material=al, bevel=0.003, parent=lid)
    B.box("laptop_bezel", (w - 0.006, 0.001, d - 0.006), (0, -0.0005, d / 2), material=dark, bevel=0, parent=lid)
    scr = B.mat_image("laptop_screen", "now_laptop_screen.png", rough=0.2, spec=0.3, emission=1.6)
    B.plane("laptop_screen", w - 0.018, (w - 0.018) * 10 / 16, (0, -0.0012, d / 2 + 0.004), (0, 0, 0), scr, parent=lid)
    return root


def latte(parent, loc):
    root = B.empty("latte_root", loc, (0, 0, 0), parent=parent)
    cer = ceramic("#f4f1ea", "cup_white")
    B.lathe("saucer", [(0.0, 0.0), (0.05, 0.0), (0.072, 0.008), (0.075, 0.012), (0.07, 0.012), (0.045, 0.006),
                       (0.0, 0.006)], material=cer, segs=48, parent=root)
    B.lathe("cup", [(0.0, 0.008), (0.03, 0.008), (0.042, 0.03), (0.048, 0.062), (0.049, 0.068), (0.046, 0.068),
                    (0.044, 0.062), (0.0, 0.062)], material=cer, segs=48, parent=root)
    foam = B.mat_image("latte_foam", "now_latte.png", rough=0.5, spec=0.3)
    B.plane("latte_top", 0.088, 0.088, (0, 0, 0.0625), (-90, 0, 20), foam, parent=root)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.018, minor_radius=0.005, location=(0, 0, 0))
    t = bpy.context.active_object
    for c in t.users_collection:
        c.objects.unlink(t)
    B.link(t)
    t.name = "cup_handle"
    t.data.materials.append(cer)
    t.parent = root
    t.location = (0.055, -0.012, 0.04)
    t.rotation_euler = (math.radians(90), 0, math.radians(-20))
    B.box("spoon", (0.09, 0.012, 0.003), (-0.015, -0.055, 0.0125), (0, 0, 12),
          material=B.mat("spoon", srgb("#c8c9cc"), 0.2, metal=1.0), bevel=0.0015, parent=root)
    return root


def coaster(parent, loc, rot):
    root = B.empty("coaster_root", loc, (0, 0, rot), parent=parent, hs="thought")
    B.box("coaster_card", (0.1, 0.1, 0.004), (0, 0, 0.002), material=B.mat("kraft", srgb("#c9a77c"), 0.85), bevel=0.001,
          parent=root)
    B.plane("coaster_face", 0.098, 0.098, (0, 0, 0.0042), (-90, 0, 0),
            B.mat_image("coaster_face", "now_coaster.png", rough=0.85, spec=0.2), parent=root)
    pen = B.mat("pen_black", srgb("#1b1c1f"), 0.35)
    B.cylinder("coaster_pen", 0.0045, 0.13, (0.075, -0.01, 0.0045), (90, 0, 80), material=pen, verts=12, parent=root)
    return root


def croissant_plate(parent, loc):
    root = B.empty("plate_root", loc, (0, 0, 0), parent=parent)
    B.lathe("plate", [(0.0, 0.0), (0.06, 0.0), (0.095, 0.01), (0.1, 0.015), (0.094, 0.015), (0.06, 0.006), (0.0, 0.006)],
            material=ceramic("#e9e3d6", "plate"), segs=48, parent=root)
    crust = B.mat_noise("crust", srgb("#c98a3e"), srgb("#a8662a"), scale=60, rough=0.55, spec=0.4, bump=0.3)
    for k, (x, y, s, r) in enumerate(((-0.025, 0.0, 1.0, 20), (0.035, 0.02, 0.6, -30))):
        for j in range(5):
            u = (j - 2) / 2
            B.superellipsoid(f"croissant{k}_{j}", (0.035 * s, 0.05 * s * (1 - 0.35 * abs(u)), 0.035 * s * (1 - 0.3 * abs(u))),
                             (x + math.cos(math.radians(r)) * u * 0.03 * s, y + math.sin(math.radians(r)) * u * 0.03 * s
                              + 0.012 * u * u * s, 0.022 * s), (0, 0, r + u * 30), material=crust, e=0.6, nu=12, nv=8,
                             parent=root)
    return root


def bud_vase(parent, loc):
    root = B.empty("vase_root", loc, (0, 0, 0), parent=parent)
    B.lathe("vase", [(0.0, 0.0), (0.028, 0.0), (0.034, 0.03), (0.026, 0.08), (0.012, 0.11), (0.014, 0.125), (0.0, 0.125)],
            material=ceramic("#c9785e", "vase_terracotta"), segs=32, parent=root)
    stem = B.mat("stem_green", srgb("#5d7b3a"), 0.6)
    petal = B.mat("petal_yellow", srgb("#f2c84b"), 0.6, spec=0.3)
    rng = random.Random(4)
    segs = []
    for k in range(3):
        a = k * 2.1 + 0.3
        tip = (0.05 * math.cos(a), 0.05 * math.sin(a), 0.27 + rng.uniform(-0.03, 0.03))
        segs.append(((0, 0, 0.1), tip, 0.0022))
        B.superellipsoid(f"flower{k}", (0.035, 0.035, 0.02), tip, (rng.uniform(-20, 20), rng.uniform(-20, 20), 0),
                         material=petal, e=0.7, nu=16, nv=8, parent=root)
    B.tubes("vase_stems", segs, stem, parent=root)
    return root


def phone(parent, loc, rot):
    root = B.empty("phone_root", loc, (0, 0, rot), parent=parent)
    B.box("phone", (0.074, 0.152, 0.008), (0, 0, 0.004), material=B.mat("phone_body", srgb("#2b2d33"), 0.3, spec=0.6),
          bevel=0.004, parent=root)
    return root


def build_table_props():
    B.use_collection("desk_props")
    z = DESK_TOP
    r = table_root
    # the character's torso hides the left half of the table from the camera: keep things to his right
    laptop_open(r, (0.38, 0.4, z), -32)
    coaster(r, (0.62, 0.1, z), 10)
    latte(r, (0.84, 0.26, z))
    phone(r, (0.06, 0.62, z), 12)


# ---------------------------------------------------------------- coffee bar

def build_bar():
    B.use_collection("bar")
    s0, s1 = 0.15, 3.8
    L = s1 - s0
    depth, h = 0.62, 1.0
    root = wall_root("bar_root", (s0 + s1) / 2, depth / 2 + 0.02)
    body = B.mat("bar_body", srgb("#3d4f45"), 0.6)
    B.box("bar_body", (L, depth - 0.06, h - 0.04), (0, 0.03, (h - 0.04) / 2), material=body, bevel=0.004, parent=root)
    slat = oak()
    xs = np.arange(-L / 2 + 0.03, L / 2 - 0.02, 0.055)
    for k, x in enumerate(xs):
        B.box(f"bar_slat{k}", (0.042, 0.022, h - 0.12), (x, -depth / 2 + 0.01, 0.08 + (h - 0.12) / 2), material=slat,
              bevel=0.006, segments=2, parent=root)
    B.box("bar_kick", (L, 0.02, 0.08), (0, -depth / 2 + 0.03, 0.04), material=B.mat("toe_dark", srgb("#2e3833"), 0.7),
          bevel=0, parent=root)
    marble = B.mat_noise("marble", srgb("#f3f0ea"), srgb("#dcd6cc"), scale=3.5, rough=0.22, detail=8, spec=0.55)
    B.box("bar_top", (L + 0.04, depth + 0.04, 0.04), (0, 0, h - 0.02), material=marble, bevel=0.006, parent=root)
    ztop = h
    # espresso machine
    em = B.empty("espresso_root", (0.95, 0.02, ztop), (0, 0, 0), parent=root)
    cream = B.mat("espresso_cream", srgb("#efe5d2"), 0.3, spec=0.6, coat=0.4)
    chrome = B.mat("chrome", srgb("#d9dadc"), 0.12, metal=1.0)
    blk = B.mat("espresso_black", srgb("#1c1c1e"), 0.4)
    B.box("esp_body", (0.66, 0.46, 0.4), (0, 0.05, 0.2 + 0.06), material=cream, bevel=0.02, parent=em)
    B.box("esp_tray", (0.62, 0.22, 0.04), (0, -0.12, 0.03), material=chrome, bevel=0.006, parent=em)
    B.box("esp_rail", (0.62, 0.4, 0.04), (0, 0.05, 0.49), material=chrome, bevel=0.01, parent=em)
    for k, x in enumerate((-0.17, 0.17)):
        B.cylinder(f"esp_group{k}", 0.045, 0.07, (x, -0.2, 0.26), material=chrome, verts=24, parent=em)
        B.box(f"esp_handle{k}", (0.025, 0.16, 0.025), (x, -0.3, 0.2), (8, 0, 0), material=blk, bevel=0.008, parent=em)
        B.cylinder(f"esp_shot{k}", 0.027, 0.055, (x, -0.17, 0.08), material=ceramic(), verts=20, parent=em)
    B.tubes("esp_wand", [((0.3, -0.16, 0.36), (0.34, -0.24, 0.12), 0.006)], chrome, parent=em)
    for k in range(5):
        B.cylinder(f"esp_cup{k}", 0.032, 0.05, (-0.24 + k * 0.1, 0.05, 0.535), material=ceramic(), verts=20, parent=em)
    # grinder
    gr = B.empty("grinder_root", (1.5, 0.04, ztop), (0, 0, 0), parent=root)
    B.box("grinder_body", (0.16, 0.24, 0.36), (0, 0, 0.18), material=blk, bevel=0.02, parent=gr)
    B.lathe("grinder_hopper", [(0.0, 0.36), (0.035, 0.36), (0.08, 0.5), (0.082, 0.52), (0.0, 0.52)],
            material=B.mat("hopper_beans", srgb("#4a2c1c"), 0.35, spec=0.6), segs=32, parent=gr)
    # cup towers + jars
    for k in range(3):
        for j in range(4):
            B.cylinder(f"cupstack{k}_{j}", 0.04, 0.055, (0.2 + k * 0.1, 0.0, ztop + 0.03 + j * 0.05),
                       material=ceramic(["#f4f1ea", "#c9785e", "#6f8a72"][k]), verts=20, parent=root)
    # pastry stand
    ps = B.empty("pastry_root", (-0.3, -0.04, ztop), (0, 0, 0), parent=root)
    B.cylinder("stand_foot", 0.04, 0.12, (0, 0, 0.06), material=ceramic(), verts=24, parent=ps)
    B.cylinder("stand_plate", 0.17, 0.012, (0, 0, 0.126), material=ceramic(), verts=40, parent=ps)
    croissant_plate(ps, (0.0, 0.0, 0.13))
    # register tablet
    tb = B.empty("tablet_root", (-0.95, 0.0, ztop), (0, 0, 0), parent=root)
    B.cylinder("tablet_stand", 0.06, 0.012, (0, 0, 0.006), material=chrome, verts=24, parent=tb)
    B.box("tablet", (0.25, 0.012, 0.18), (0, 0, 0.13), (-70, 0, 180), material=blk, bevel=0.006, parent=tb)
    # plant at the near end of the bar
    pr = P.pot("bar_plant", 0.09, 0.07, 0.15, "#c9785e", (-1.55, 0.02, ztop), parent=root)
    P.plant("bar_plant", pr, 0.13, 24, 0.28, 0.24, 0.14, 0.09, seed=52, droop=0.35)
    build_bar_wall()


def build_bar_wall():
    root = wall_root("barwall_root", 0.0, 0.0)
    oakm = oak()
    for k, z in enumerate((1.48, 1.86, 2.24)):
        B.box(f"shelf{k}", (1.45, 0.24, 0.03), (-0.95, -0.12, z), material=oakm, bevel=0.004, parent=root)
        for sx in (-1.55, -0.35):
            B.box(f"shelf{k}_br{sx}", (0.02, 0.18, 0.06), (sx, -0.09, z - 0.045), material=steel(), bevel=0.002,
                  parent=root)
    rng = random.Random(23)
    bag = B.mat("bean_bag", srgb("#c79f6d"), 0.8)
    label = B.mat("bag_label", srgb("#f1ebe0"), 0.8)
    jar = B.mat("jar_glass", srgb("#a9b7b0"), 0.15, spec=0.7)
    beans = B.mat("hopper_beans", srgb("#4a2c1c"), 0.35, spec=0.6)
    for k, z in enumerate((1.495, 1.875, 2.255)):
        x = -1.6
        while x < -0.35:
            kind = rng.random()
            if kind < 0.4:
                w = 0.11
                B.box(f"bag{k}_{x:.2f}", (w, 0.07, 0.2), (x + w / 2, -0.12, z + 0.1), (0, 0, rng.uniform(-4, 4)), material=bag,
                      bevel=0.012, parent=root)
                B.box(f"bagl{k}_{x:.2f}", (w * 0.7, 0.002, 0.07), (x + w / 2, -0.156, z + 0.1), material=label, bevel=0,
                      parent=root)
            elif kind < 0.8:
                w = 0.1
                B.cylinder(f"jar{k}_{x:.2f}", 0.045, 0.16, (x + w / 2, -0.12, z + 0.08), material=jar, verts=20,
                           parent=root)
                B.cylinder(f"jarb{k}_{x:.2f}", 0.04, 0.1, (x + w / 2, -0.12, z + 0.055), material=beans, verts=16,
                           parent=root)
                B.cylinder(f"jarl{k}_{x:.2f}", 0.047, 0.02, (x + w / 2, -0.12, z + 0.17), material=oakm, verts=20,
                           parent=root)
            else:
                w = 0.14
                pr = P.pot(f"shelfplant{k}_{x:.2f}", 0.055, 0.045, 0.09, rng.choice(["#f1eee8", "#c9785e"]),
                           (x + w / 2, -0.12, z), parent=root)
                P.plant(f"shelfplant{k}_{x:.2f}", pr, 0.08, 12, 0.12, 0.12, 0.08, 0.05, seed=k * 7 + int(x * 100),
                        droop=0.55, pitch=(-30, 20))
            x += w + 0.03
    # chalkboard menu
    P.framed("menu", "now_menu.png", 0.84, 1.05, (-2.55, -0.02, 2.02), parent=root, frame_col="#6b4a33", mat_w=0.0)
    # pendants over the bar
    glow = B.mat_emit("globe_glow", srgb("#ffe2b8"), 7.0)
    cord = B.mat("cord", srgb("#1a1a1a"), 0.6)
    brass = B.mat("brass", srgb("#c9a45a"), 0.25, metal=1.0)
    for k, s in enumerate((0.9, 2.1)):
        p = on_left_wall(s, 0, 0.45)
        B.cylinder(f"pend_cord{k}", 0.004, CEIL - 2.32, (p[0], p[1], (CEIL + 2.32) / 2), material=cord, verts=8)
        B.cylinder(f"pend_cap{k}", 0.03, 0.05, (p[0], p[1], 2.31), material=brass, verts=20)
        B.superellipsoid(f"pend_globe{k}", (0.2, 0.2, 0.2), (p[0], p[1], 2.2), (0, 0, 0), material=glow, e=1.0,
                         nu=24, nv=12)


# ---------------------------------------------------------------- right side

def build_right():
    B.use_collection("right")
    tr = B.empty("table2_root", (2.75, 1.55, 0), (0, 0, 0))
    top = B.mat_noise("marble", srgb("#f3f0ea"), srgb("#dcd6cc"), scale=3.5, rough=0.22, detail=8, spec=0.55)
    iron = B.mat("cast_iron", srgb("#1e2224"), 0.5, metal=0.4)
    B.cylinder("t2_top", 0.33, 0.03, (0, 0, 0.725), material=top, verts=48, parent=tr)
    B.cylinder("t2_col", 0.03, 0.68, (0, 0, 0.36), material=iron, verts=20, parent=tr)
    B.cylinder("t2_foot", 0.2, 0.025, (0, 0, 0.0125), material=iron, verts=32, parent=tr)
    bentwood_chair("chair2", None, (2.3, 1.25, 0), -52)
    bentwood_chair("chair3", None, (3.25, 1.95, 0), 128)
    cup = B.empty("t2_cup", (2.68, 1.5, 0.74), (0, 0, 0))
    B.lathe("t2_cupbody", [(0.0, 0.0), (0.032, 0.0), (0.04, 0.09), (0.0, 0.09)], material=ceramic("#6f8a72", "cup_sage"),
            segs=32, parent=cup)
    P.book_stack("t2_books", None, 2.86, 1.66, 0.74, 2, random.Random(8), w=(0.2, 0.24), rot=18,
                 cols=["#e9b83a", "#efece5"])
    # fiddle-leaf fig in the corner by the glass
    pot = P.pot("fig", 0.2, 0.16, 0.42, "#c9785e", (4.3, 2.75, 0))
    B.cylinder("fig_trunk", 0.018, 1.0, (4.3, 2.75, 0.85), material=B.mat("fig_bark", srgb("#6b5644"), 0.8), verts=10)
    P.plant("fig", pot, 0.4, 34, 1.35, 0.42, 0.26, 0.2, seed=61, droop=0.12, pitch=(0, 35),
            greens=["#2f5a24", "#3a6a2a", "#447834", "#2a5020"])
    # coat hooks + framed print by the side window
    P.framed("print_r", "photo_park.png", 0.32, 0.42, (RIGHT_X - 0.02, -1.9, 1.75), rot_z=90, frame_col="#2b2522",
             mat_w=0.02)


# ---------------------------------------------------------------- lights

def build_lights(sun_strength=20.0):
    B.use_collection("lights")
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = sun_strength
    sun.angle = math.radians(1.6)
    sun.color = (1.0, 0.88, 0.72)
    o = bpy.data.objects.new("sun", sun)
    B.link(o)
    o.location = (10, -6, 10)
    o.rotation_euler = (-SUN_DIR).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 110
    fill.size = 4.0
    fill.color = (1.0, 0.93, 0.86)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.location = (0.6, -2.2, 2.6)
    look_at(f, (0, 1.6, 0.8))
    for name, size, size_y, loc, rot in (
            ("front_portal", RIGHT_X - CORNER.x, HEAD_Z - SILL_Z, ((CORNER.x + RIGHT_X) / 2, OUT_Y + 0.02, (SILL_Z + HEAD_Z) / 2),
             (math.radians(90), 0, 0)),
            ("side_portal", RWIN_Y1 - RWIN_Y0, RWIN_Z1 - RWIN_Z0, (RIGHT_X + WALL_T + 0.02, (RWIN_Y0 + RWIN_Y1) / 2,
                                                              (RWIN_Z0 + RWIN_Z1) / 2), (math.radians(90), 0, math.radians(-90)))):
        pl = bpy.data.lights.new(name, "AREA")
        pl.shape = "RECTANGLE"
        pl.size, pl.size_y = size, size_y
        pl.energy = 0
        try:
            pl.cycles.is_portal = True
        except Exception:
            pass
        po = bpy.data.objects.new(name, pl)
        B.link(po)
        po.location = loc
        po.rotation_euler = rot


def build_all():
    import models_char as C
    build_shell()
    build_banquette()
    build_table()
    chair = build_chair()
    C.build_character(chair)
    # 小八 has taken the free half of the table, 烧酒 curls up on the window ledge
    C.build_xiaoba(table_root, (0.64, 0.61, DESK_TOP), 12).scale = (0.66,) * 3
    C.build_shaojiu(None, (2.3, (LEDGE_Y0 + GLASS_Y) / 2 + 0.01, SILL_Z), -4)
    build_table_props()
    bud_vase(None, (1.3, (LEDGE_Y0 + GLASS_Y) / 2, SILL_Z))
    build_bar()
    build_right()
