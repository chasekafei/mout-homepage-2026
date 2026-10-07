"""游戏: the game room after school, low sun through the side window, a CRT straight ahead.

Desk frame (``stage.DESK_ROOT``): +Y is where the character looks. The TV cabinet stands against the
front wall; the handheld shelf hangs above it; the game archive wraps the front-left corner and keeps
going up the wall as pixels; the arcade cabinet fills the front-right corner; the window is on his left.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bpy
import numpy as np

import blib as B
import stage
from blib import srgb
from exterior import Batch

LEFT_X, RIGHT_X = -1.3, 2.0
FRONT_Y, BACK_Y = 1.45, -2.6
CEIL = 2.7
WALL_T = 0.2
WIN_Y0, WIN_Y1, WIN_Z0, WIN_Z1 = -0.35, 0.8, 0.82, 2.25
TABLE = (-0.3, 0.72, 0.42, 0.84, 0.4)         # x0, x1, y0, y1, top
CAB = (-0.42, 0.52, FRONT_Y - 0.44, FRONT_Y - 0.02, 0.5)   # TV cabinet x0, x1, y0, y1, top
CRT_X, CRT_Y0 = 0.05, CAB[2] + 0.02                         # screen centre x, front face y
ARCH_X0, ARCH_X1, ARCH_Y0 = LEFT_X + 0.02, -0.5, FRONT_Y - 0.3   # archive on the front wall
ARCH_SIDE_Y0 = 0.86                                              # archive along the left wall
CRT_W, CRT_H = 0.66, 0.54
SHELF_DZ, SHELF_N = 0.22, 9
LIBRARY = Path(__file__).parent / "data" / "game_library.json"

root = None


# ---------------------------------------------------------------- materials

def wall_paint():
    return B.mat_noise("game_wall", srgb("#7c9a96"), srgb("#759390"), scale=7, rough=0.9, detail=3, spec=0.2)


def graphite():
    return B.mat("game_graphite", srgb("#2b2d32"), 0.45, metal=0.25, spec=0.45)


def graphite_dark():
    return B.mat("game_graphite_d", srgb("#18191d"), 0.5, spec=0.4)


def teak():
    return B.mat_noise("game_teak", srgb("#9a6238"), srgb("#87542f"), scale=14, rough=0.4, detail=5, spec=0.5)


def plastic(name, hexc, rough=0.4):
    return B.mat(f"plastic_{name}", srgb(hexc), rough, spec=0.5)


def glow(name, hexc, strength):
    return B.mat_emit(f"game_glow_{name}", srgb(hexc), strength)


def floor_mat():
    if "game_floor" in B._mats:
        return B._mats["game_floor"]
    m = bpy.data.materials.new("game_floor")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.35
    p.inputs["Specular IOR Level"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.1
    br.inputs["Row Height"].default_value = 0.14
    br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Color1"].default_value = (*srgb("#b07a4c"), 1)
    br.inputs["Color2"].default_value = (*srgb("#a06c41"), 1)
    br.inputs["Mortar"].default_value = (*srgb("#5e3f25"), 1)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], p.inputs["Base Color"])
    B._mats["game_floor"] = m
    return m


def vcol_mat(name, rough=0.45, emit=0.0):
    key = f"game_vcol_{name}"
    if key in B._mats:
        return B._mats[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = 0.5
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "vcol"
    nt.links.new(a.outputs["Color"], p.inputs["Base Color"])
    if emit:
        nt.links.new(a.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = emit
    B._mats[key] = m
    return m


# ---------------------------------------------------------------- shell

def build_shell():
    B.use_collection("room")
    r = root
    wall = wall_paint()
    B.box_minmax("floor", (LEFT_X - 0.1, BACK_Y, -0.1), (RIGHT_X + 0.1, FRONT_Y + 0.1, 0.0), floor_mat(), bevel=0, parent=r)
    B.box_minmax("ceiling", (LEFT_X - WALL_T, BACK_Y, CEIL), (RIGHT_X + WALL_T, FRONT_Y + WALL_T, CEIL + 0.15),
                 B.mat("game_ceiling", srgb("#e4ddd0"), 0.9), bevel=0, parent=r)
    B.box_minmax("wall_front", (LEFT_X - WALL_T, FRONT_Y, 0), (RIGHT_X + WALL_T, FRONT_Y + WALL_T, CEIL), wall, bevel=0,
                 parent=r)
    B.box_minmax("wall_right", (RIGHT_X, BACK_Y, 0), (RIGHT_X + WALL_T, FRONT_Y, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_back", (LEFT_X - WALL_T, BACK_Y - WALL_T, 0), (RIGHT_X + WALL_T, BACK_Y, CEIL), wall, bevel=0,
                 parent=r)
    x0, x1 = LEFT_X - WALL_T, LEFT_X
    B.box_minmax("wall_left_a", (x0, BACK_Y, 0), (x1, WIN_Y0, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_b", (x0, WIN_Y1, 0), (x1, FRONT_Y, CEIL), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_c", (x0, WIN_Y0, 0), (x1, WIN_Y1, WIN_Z0), wall, bevel=0, parent=r)
    B.box_minmax("wall_left_d", (x0, WIN_Y0, WIN_Z1), (x1, WIN_Y1, CEIL), wall, bevel=0, parent=r)
    fr = B.mat("game_winframe", srgb("#e9e4da"), 0.5)
    B.box_minmax("win_sill", (LEFT_X - 0.08, WIN_Y0 - 0.04, WIN_Z0 - 0.04), (LEFT_X + 0.16, WIN_Y1 + 0.04, WIN_Z0), fr,
                 bevel=0.006, parent=r)
    ym = (WIN_Y0 + WIN_Y1) / 2
    for name, a, b in (("win_frame_l", (x0, WIN_Y0, WIN_Z0), (x1 + 0.02, WIN_Y0 + 0.05, WIN_Z1)),
                       ("win_frame_r", (x0, WIN_Y1 - 0.05, WIN_Z0), (x1 + 0.02, WIN_Y1, WIN_Z1)),
                       ("win_frame_t", (x0, WIN_Y0, WIN_Z1 - 0.05), (x1 + 0.02, WIN_Y1, WIN_Z1)),
                       ("win_mullion", (x0 + 0.06, ym - 0.025, WIN_Z0), (x1, ym + 0.025, WIN_Z1))):
        B.box_minmax(name, a, b, fr, bevel=0.003, parent=r)
    # half-drawn roller blind
    B.box_minmax("win_blind", (LEFT_X + 0.03, WIN_Y0 + 0.02, WIN_Z1 - 0.32), (LEFT_X + 0.045, WIN_Y1 - 0.02, WIN_Z1 + 0.06),
                 B.mat("game_blind", srgb("#efe2c4"), 0.9), bevel=0.002, parent=r)
    sk = B.mat("game_skirting", srgb("#e9e4da"), 0.6)
    B.box_minmax("skirt_front", (LEFT_X, FRONT_Y - 0.015, 0), (RIGHT_X, FRONT_Y, 0.08), sk, bevel=0.002, parent=r)
    B.box_minmax("skirt_left", (LEFT_X, WIN_Y1, 0), (LEFT_X + 0.015, FRONT_Y, 0.08), sk, bevel=0.002, parent=r)
    rug = B.mat_image("game_rug", "game_rug.png", rough=0.95, spec=0.1)
    B.box_minmax("rug", (-0.9, -0.9, 0.0), (1.2, 1.12, 0.01), rug, bevel=0.003, parent=r)


# ---------------------------------------------------------------- seat

def build_chair(desk):
    """Low coral armchair; the back stays below his shoulders."""
    B.use_collection("chair")
    ch = stage.chair_frame(desk)
    fab = B.mat_noise("game_chair", srgb("#d9604e"), srgb("#c95747"), scale=420, rough=0.95, spec=0.2, bump=0.15)
    B.superellipsoid("chair_seat", (0.52, 0.5, 0.12), (0, 0.0, 0.41), material=fab, e=0.3, parent=ch)
    B.superellipsoid("chair_base", (0.62, 0.56, 0.2), (0, -0.01, 0.25), material=fab, e=0.25, parent=ch)
    B.superellipsoid("chair_back", (0.62, 0.16, 0.36), (0, -0.25, 0.6), (-8, 0, 0), material=fab, e=0.3, parent=ch)
    for sx in (-1, 1):
        B.superellipsoid(f"chair_arm{sx}", (0.1, 0.52, 0.2), (sx * 0.3, -0.02, 0.5), material=fab, e=0.3, parent=ch)
    for sx in (-1, 1):
        for sy in (-1, 1):
            B.cylinder(f"chair_foot{sx}{sy}", 0.018, 0.14, (sx * 0.26, sy * 0.22, 0.07), material=teak(), verts=10,
                       r_top=0.014, parent=ch)
    return ch


def fc_pad(parent, loc, rot=0.0, name="pad"):
    """Family-computer style pad: cream body, dark face plate, d-pad, two red buttons."""
    p = B.empty(f"{name}_root", loc, (0, 0, rot), parent=parent)
    B.box(f"{name}_body", (0.13, 0.055, 0.016), (0, 0, 0), material=plastic("cream", "#e8e2d3"), bevel=0.004, parent=p)
    B.box(f"{name}_face", (0.112, 0.04, 0.002), (0, 0, 0.0085), material=plastic("pad_face", "#2a2b30"), bevel=0,
          parent=p)
    dk = plastic("pad_dpad", "#141418")
    B.box(f"{name}_dpad_h", (0.026, 0.008, 0.004), (-0.035, 0, 0.011), material=dk, bevel=0.001, parent=p)
    B.box(f"{name}_dpad_v", (0.008, 0.026, 0.004), (-0.035, 0, 0.011), material=dk, bevel=0.001, parent=p)
    for k, x in enumerate((0.026, 0.044)):
        B.cylinder(f"{name}_btn{k}", 0.0055, 0.004, (x, -0.004, 0.011), material=plastic("pad_red", "#c8323a"), verts=12,
                   parent=p)
    return p


# ---------------------------------------------------------------- TV, cabinet, consoles

def build_tv():
    B.use_collection("tv")
    x0, x1, y0, y1, top = CAB
    tv = B.empty("tv_root", (0, 0, 0), (0, 0, 0), parent=root, hs="tv")
    wd = teak()
    t = 0.022
    B.box_minmax("cab_top", (x0, y0, top - t), (x1, y1, top), wd, bevel=0.004, parent=tv)
    B.box_minmax("cab_bottom", (x0, y0, 0.03), (x1, y1, 0.03 + t), wd, bevel=0.004, parent=tv)
    B.box_minmax("cab_mid", (x0 + t, y0 + 0.01, 0.29), (x1 - t, y1, 0.29 + t * 0.8), wd, bevel=0.003, parent=tv)
    for k, x in enumerate((x0, (x0 + x1) / 2 - t / 2, x1 - t)):
        B.box_minmax(f"cab_side{k}", (x, y0, 0.03), (x + t, y1, top - t), wd, bevel=0.003, parent=tv)
    B.box_minmax("cab_back", (x0, y1 - 0.01, 0.03), (x1, y1, top), wd, bevel=0, parent=tv)
    for k, x in enumerate((x0 + 0.04, x1 - 0.04)):
        B.cylinder(f"cab_leg{k}", 0.015, 0.03, (x, (y0 + y1) / 2, 0.015), material=graphite(), verts=12, parent=tv)
    # CRT: bezel box, tapered back, curved-looking screen
    shell = B.mat("crt_shell", srgb("#34363c"), 0.5, spec=0.45)
    W, H = CRT_W, CRT_H
    zc = top + H / 2
    sw_, sh_ = 0.53, 0.4
    sx = CRT_X - 0.03
    B.box("crt_front", (W, 0.12, H), (CRT_X, CRT_Y0 + 0.06, zc), material=shell, bevel=0.025, parent=tv)
    B.tbox("crt_back", (CRT_X, CRT_Y0 + 0.1, zc + 0.005), (CRT_X, y1 - 0.02, zc + 0.02), (W * 0.92, H * 0.88),
           (W * 0.5, H * 0.5), up=(0, 0, 1), material=shell, bevel=0.03, parent=tv)
    B.box("crt_glass_rim", (sw_ + 0.03, 0.012, sh_ + 0.03), (sx, CRT_Y0 - 0.002, zc + 0.02), material=graphite_dark(),
          bevel=0.012, parent=tv)
    B.superellipsoid("crt_screen", (sw_, 0.02, sh_), (sx, CRT_Y0 - 0.006, zc + 0.02), material=B.mat_image(
        "crt_screen", "game_crt.png", rough=0.15, emission=2.2, spec=0.7, interp="Closest"), e=0.15, nu=24, nv=12,
        parent=tv)
    kx = CRT_X + W / 2 - 0.045
    for k in range(4):
        B.cylinder(f"crt_knob{k}", 0.01, 0.01, (kx, CRT_Y0 - 0.004, zc + 0.14 - k * 0.055), (90, 0, 0),
                   material=graphite_dark(), verts=12, parent=tv)
    B.box("crt_led", (0.008, 0.004, 0.004), (kx, CRT_Y0 - 0.002, zc - 0.2), material=glow("led", "#e8574a", 6),
          bevel=0, parent=tv)
    # consoles in the cabinet: FC + MD upstairs, PS4 + Switch dock downstairs
    mid = 0.29 + t * 0.8
    lx, rx = (x0 + (x0 + x1) / 2) / 2, ((x0 + x1) / 2 + x1) / 2
    fc = B.empty("fc_root", (lx, y0 + 0.17, mid), (0, 0, 0), parent=tv)
    B.box("fc_body", (0.22, 0.15, 0.06), (0, 0, 0.03), material=plastic("fc_cream", "#e6dfcd"), bevel=0.006, parent=fc)
    B.box("fc_top", (0.2, 0.08, 0.004), (0, 0.025, 0.061), material=plastic("fc_red", "#8f2a2c"), bevel=0, parent=fc)
    B.box("fc_cart", (0.1, 0.02, 0.085), (0, 0.025, 0.1), material=plastic("cart_beige", "#d2c39f"), bevel=0.004, parent=fc)
    B.box("fc_cart_label", (0.08, 0.002, 0.05), (0, 0.0145, 0.105), material=plastic("cart_label", "#2fc9ab"), bevel=0,
          parent=fc)
    md = B.empty("md_root", (rx, y0 + 0.17, mid), (0, 0, 0), parent=tv)
    B.box("md_body", (0.24, 0.2, 0.065), (0, 0, 0.0325), material=plastic("md_black", "#17181b", 0.35), bevel=0.01,
          parent=md)
    B.cylinder("md_dial", 0.055, 0.006, (0.03, 0.02, 0.068), material=plastic("md_dial", "#2b2d32", 0.3), verts=32,
               parent=md)
    B.box("md_led", (0.006, 0.003, 0.003), (-0.09, -0.1, 0.05), material=glow("md_led", "#e8574a", 6), bevel=0, parent=md)
    B.box("ps4", (0.27, 0.24, 0.04), (lx, y0 + 0.17, 0.052 + 0.02 + 0.002), material=plastic("ps4", "#15161a", 0.3),
          bevel=0.006, parent=tv)
    B.box("ps4_light", (0.24, 0.002, 0.004), (lx, y0 + 0.049, 0.074), material=glow("ps4", "#5aa0ff", 5), bevel=0,
          parent=tv)
    sw = B.empty("switch_root", (rx, y0 + 0.2, 0.052), (0, 0, 0), parent=tv)
    B.box("sw_dock", (0.17, 0.05, 0.1), (0, 0, 0.05), material=plastic("sw_dock", "#2b2d32", 0.35), bevel=0.008, parent=sw)
    B.box("sw_tablet", (0.17, 0.014, 0.1), (0, -0.03, 0.09), material=plastic("sw_screen", "#101114", 0.2), bevel=0.004,
          parent=sw)
    for sx, c in ((-1, "#00b2d8"), (1, "#ff4a3d")):
        B.box(f"sw_joy{sx}", (0.035, 0.014, 0.1), (sx * 0.1, -0.03, 0.09), material=plastic(f"joy{sx}", c, 0.35),
              bevel=0.006, parent=sw)
    # pads: one in his hands, one waiting on the table for a friend; both wired to the FC
    return tv, fc


def cable(name, pts, parent, r=0.0035):
    """Smooth wire through the midpoints of ``pts`` (quadratic B-spline), pinned at both ends."""
    pts = [np.array(p, float) for p in pts]
    fine = [pts[0]]
    for a, b, c in zip(pts[:-2], pts[1:-1], pts[2:]):
        m0, m1 = (a + b) / 2, (b + c) / 2
        for t in np.linspace(0, 1, 6, endpoint=False):
            fine.append((1 - t) ** 2 * m0 + 2 * (1 - t) * t * b + t ** 2 * m1)
    fine += [(pts[-2] + pts[-1]) / 2, pts[-1]]
    B.tubes(name, [(tuple(a), tuple(b), r) for a, b in zip(fine[:-1], fine[1:])], plastic("cable", "#1d1e22", 0.5),
            parent=parent, sides=6)


# ---------------------------------------------------------------- handheld shelf

def build_handhelds():
    B.use_collection("handhelds")
    z = 1.3
    hr = B.empty("handhelds_root", (0.05, FRONT_Y - 0.09, z), (0, 0, 0), parent=root, hs="handhelds")
    B.box("hh_shelf", (1.02, 0.17, 0.025), (0, 0.0, -0.0125), material=teak(), bevel=0.004, parent=hr)
    for sx in (-1, 1):
        B.box(f"hh_bracket{sx}", (0.02, 0.12, 0.08), (sx * 0.42, 0.02, -0.065), material=graphite(), bevel=0.003, parent=hr)
    items = [
        ("gb", 0.09, 0.148, "#c9c6bf", ("#9bbc0f", 0.06, 0.054, 0.035)),
        ("nds", 0.133, 0.15, "#eceae6", ("#3a3f48", 0.08, 0.06, 0.035)),
        ("psp", 0.17, 0.074, "#17181b", ("#22324a", 0.11, 0.062, 0.0)),
        ("psv", 0.182, 0.083, "#1d1f24", ("#2a3b55", 0.12, 0.068, 0.0)),
        ("swlite", 0.208, 0.091, "#2fc9ab", ("#15171b", 0.12, 0.068, 0.0)),
    ]
    gap = 0.045
    total = sum(w for _, w, *_ in items) + gap * (len(items) - 1)
    x = -total / 2
    for name, w, h, col, (scol, sw_, sh_, sdz) in items:
        cx = x + w / 2
        it = B.empty(f"hh_{name}", (cx, 0.0, 0.0), (-12, 0, 0), parent=hr)
        B.box(f"hh_{name}_stand", (w * 0.5, 0.05, 0.012), (0, 0.035, 0.006), material=graphite_dark(), bevel=0.002,
              parent=it)
        B.box(f"hh_{name}_body", (w, 0.022, h), (0, 0, h / 2 + 0.01), material=plastic(name, col, 0.35), bevel=0.008,
              parent=it)
        B.box(f"hh_{name}_screen", (sw_, 0.002, sh_), (0, -0.012, h / 2 + 0.01 + sdz), material=B.mat(
            f"hh_scr_{name}", srgb(scol), 0.2, emission=srgb(scol), estr=0.6), bevel=0, parent=it)
        if name == "nds":
            B.box("hh_nds_screen2", (0.08, 0.002, 0.06), (0, -0.012, 0.045), material=B.mat(
                "hh_scr_nds2", srgb("#3a3f48"), 0.2, emission=srgb("#3a3f48"), estr=0.6), bevel=0, parent=it)
        if name == "swlite":
            for sx in (-1, 1):
                B.cylinder(f"hh_sw_stick{sx}", 0.008, 0.006, (sx * 0.083, -0.013, h / 2 + 0.03 * (1 if sx < 0 else -1) + 0.01),
                           (90, 0, 0), material=graphite_dark(), verts=12, parent=it)
        x += w + gap


# ---------------------------------------------------------------- game archive

PLATFORMS = {
    # band colour, height, depth, thickness range
    "ps": ("#1f5fbf", 0.17, 0.135, (0.013, 0.016)),
    "switch": ("#e60012", 0.17, 0.105, (0.011, 0.012)),
    "dvd": ("#222326", 0.19, 0.135, (0.014, 0.018)),
    "gb": ("#9aa0a8", 0.13, 0.025, (0.07, 0.07)),
    "big": ("#e9e4da", 0.22, 0.16, (0.04, 0.07)),
}
BOX_COLS = ["#e8574a", "#2fc9ab", "#ffd34a", "#3d3e44", "#5a6c8a", "#f1efe8", "#8e3f20", "#6aa6ff", "#b58cf0",
            "#d9b07a", "#1b2838", "#c4663a", "#7cc46a", "#e9e4da"]


def library(rng, n):
    """Real library if tools/scene/data/game_library.json exists (list of {platform, color}), else a plausible mix."""
    if LIBRARY.exists():
        games = json.loads(LIBRARY.read_text())
        games = [(g.get("platform", "dvd"), g.get("color") or rng.choice(BOX_COLS)) for g in games]
    else:
        plats = ["ps"] * 5 + ["switch"] * 3 + ["dvd"] * 3 + ["gb"]
        games = [(rng.choice(plats), rng.choice(BOX_COLS)) for _ in range(n)]
    # shelved by platform, like a real collection
    return sorted(games, key=lambda g: list(PLATFORMS).index(g[0]) if g[0] in PLATFORMS else 2)


def build_archive():
    B.use_collection("archive")
    ar = B.empty("archive_root", (0, 0, 0), (0, 0, 0), parent=root, hs="archive")
    rng = random.Random(7)
    frame = graphite()
    H = SHELF_N * SHELF_DZ + 0.05
    # front-wall unit
    for k in range(SHELF_N + 1):
        z = 0.04 + k * SHELF_DZ
        B.box_minmax(f"arch_shelf{k}", (ARCH_X0, ARCH_Y0, z - 0.02), (ARCH_X1, FRONT_Y - 0.005, z), teak(), bevel=0.003,
                     parent=ar)
        if k < SHELF_N:
            B.box_minmax(f"arch_side_shelf{k}", (LEFT_X + 0.005, ARCH_SIDE_Y0, z - 0.02), (LEFT_X + 0.3, ARCH_Y0, z), teak(),
                         bevel=0.003, parent=ar)
    for k, x in enumerate((ARCH_X1 - 0.02, (ARCH_X0 + ARCH_X1) / 2)):
        B.box_minmax(f"arch_post{k}", (x, ARCH_Y0, 0), (x + 0.02, FRONT_Y - 0.005, H), frame, bevel=0.002, parent=ar)
    B.box_minmax("arch_post_side", (LEFT_X + 0.28, ARCH_SIDE_Y0, 0), (LEFT_X + 0.3, ARCH_SIDE_Y0 + 0.02, H), frame,
                 bevel=0.002, parent=ar)
    boxes = Batch("arch_boxes", vcol_mat("boxes", 0.45))
    games = library(rng, 900)
    gi = 0

    def fill(span0, span1, z, along_x):
        nonlocal gi
        s = span0 + 0.01
        while gi < len(games):
            plat, col = games[gi]
            band, h, d, (t0, t1) = PLATFORMS.get(plat, PLATFORMS["dvd"])
            t = rng.uniform(t0, t1)
            if s + t > span1 - 0.01:
                return
            gi += 1
            hh = h * rng.uniform(0.97, 1.0)
            c = np.array(srgb(col))
            bc = np.array(srgb(band))
            if along_x:   # front unit: spine faces -Y
                y0 = ARCH_Y0 + 0.012
                boxes.box(s, y0, z, s + t, y0 + d, z + hh - 0.026, c)
                boxes.box(s, y0, z + hh - 0.026, s + t, y0 + d, z + hh, bc)
                if rng.random() < 0.6:
                    boxes.box(s + t * 0.2, y0 - 0.0015, z + hh * 0.3, s + t * 0.8, y0, z + hh * 0.62,
                              np.clip(c * 0.55 + 0.45, 0, 1))
            else:         # side unit: spine faces +X
                x1 = LEFT_X + 0.29
                boxes.box(x1 - d, s, z, x1, s + t, z + hh - 0.026, c)
                boxes.box(x1 - d, s, z + hh - 0.026, x1, s + t, z + hh, bc)
                if rng.random() < 0.6:
                    boxes.box(x1, s + t * 0.2, z + hh * 0.3, x1 + 0.0015, s + t * 0.8, z + hh * 0.62,
                              np.clip(c * 0.55 + 0.45, 0, 1))
            s += t + rng.uniform(0.0005, 0.002)

    for k in range(SHELF_N):
        z = 0.04 + k * SHELF_DZ
        mid = (ARCH_X0 + ARCH_X1) / 2
        fill(ARCH_X0 + 0.0, mid, z, True)
        fill(mid + 0.02, ARCH_X1 - 0.02, z, True)
        fill(ARCH_SIDE_Y0 + 0.02, ARCH_Y0, z, False)
    o = boxes.build()
    o.parent = ar
    # the library keeps going as pixels up the wall: thinning towards the ceiling
    px = Batch("arch_pixels", vcol_mat("pixels", 0.5, emit=2.4))
    cols = [np.array(srgb(c)) for c in ("#2fc9ab", "#5ff0d8", "#e8574a", "#ffd34a", "#6aa6ff")]
    s = 0.045
    for i in range(int((ARCH_X1 - ARCH_X0) / s)):
        for j in range(int((CEIL - H - 0.05) / s)):
            z = H + 0.03 + j * s
            p = 0.85 * (1 - j / ((CEIL - H) / s)) ** 1.6 * (0.6 + 0.4 * (i / ((ARCH_X1 - ARCH_X0) / s)))
            if rng.random() < p:
                x = ARCH_X0 + i * s
                px.box(x + 0.006, FRONT_Y - 0.03, z + 0.006, x + s - 0.006, FRONT_Y - 0.005, z + s - 0.006,
                       cols[rng.randrange(len(cols))] * rng.uniform(0.6, 1.0))
    o = px.build()
    o.parent = ar


# ---------------------------------------------------------------- arcade

def build_arcade():
    B.use_collection("arcade")
    x0, x1 = 0.66, 1.26
    ac = B.empty("arcade_root", ((x0 + x1) / 2 + 0.12, FRONT_Y - 0.01, 0), (0, 0, -12), parent=root, hs="arcade")
    ac.scale = (0.9,) * 3
    side = B.mat("arcade_side", srgb("#e8574a"), 0.45, spec=0.5)
    body = graphite_dark()
    # side profile in (depth toward the room = -y, z); local x of extrude -> world y after rot
    prof = [(0.0, 0.0), (-0.62, 0.0), (-0.62, 0.86), (-0.5, 0.98), (-0.34, 1.0), (-0.26, 1.5), (-0.36, 1.56),
            (-0.36, 1.78), (0.0, 1.78)]
    hw = (x1 - x0) / 2
    # rotated 90 about Z: outline x -> world y, extrusion -> world -x
    for sx in (-1, 1):
        B.extrude(f"arcade_side{sx}", prof, 0.03, (hw if sx > 0 else -hw + 0.03, 0, 0), (0, 0, 90), side, bevel=0.004,
                  parent=ac)
    w = 2 * hw - 0.06
    B.box("arcade_front", (w, 0.02, 0.86), (0, -0.6, 0.43), material=body, bevel=0.003, parent=ac)
    B.box("arcade_coin", (0.12, 0.012, 0.14), (0, -0.612, 0.6), material=B.mat("arcade_coin", srgb("#b9bcc1"), 0.3,
          metal=0.8), bevel=0.003, parent=ac)
    B.box("arcade_coin_led", (0.03, 0.004, 0.012), (0, -0.62, 0.64), material=glow("coin", "#ffd34a", 6), bevel=0,
          parent=ac)
    # control panel
    cp = B.empty("arcade_cp", (0, -0.42, 0.99), (-14, 0, 0), parent=ac)
    B.box("arcade_panel", (w, 0.26, 0.03), (0, 0, 0), material=body, bevel=0.004, parent=cp)
    B.box("arcade_panel_art", (w - 0.04, 0.2, 0.002), (0, 0, 0.016), material=B.mat("arcade_art", srgb("#2fc9ab"), 0.4),
          bevel=0, parent=cp)
    B.cylinder("arcade_stick", 0.006, 0.06, (-0.12, 0.0, 0.045), material=graphite_dark(), verts=10, parent=cp)
    B.superellipsoid("arcade_ball", (0.035, 0.035, 0.035), (-0.12, 0.0, 0.08), material=plastic("ball", "#e8574a", 0.3),
                     e=1.0, nu=16, nv=8, parent=cp)
    for k, (x, y, c) in enumerate(((0.02, 0.02, "#ffd34a"), (0.07, 0.03, "#2fc9ab"), (0.12, 0.03, "#e8574a"),
                                   (0.03, -0.04, "#6aa6ff"), (0.08, -0.03, "#f1efe8"), (0.13, -0.03, "#b58cf0"))):
        B.cylinder(f"arcade_btn{k}", 0.014, 0.012, (x, y, 0.021), material=plastic(f"btn{k}", c, 0.3), verts=16, parent=cp)
    # screen, bezel, marquee
    sc = B.empty("arcade_scr", (0, -0.3, 1.25), (-14, 0, 0), parent=ac)
    B.box("arcade_bezel", (w, 0.03, 0.5), (0, 0.02, 0), material=body, bevel=0.004, parent=sc)
    B.plane("arcade_screen", 0.3, 0.4, (0, 0.003, 0.0), (0, 0, 0), B.mat_image("arcade_screen", "game_arcade.png", rough=0.2,
            emission=2.4, spec=0.6, interp="Closest"), parent=sc)
    B.box("arcade_top", (w, 0.36, 0.02), (0, -0.18, 1.77), material=body, bevel=0.003, parent=ac)
    B.box("arcade_marquee_box", (w, 0.08, 0.22), (0, -0.33, 1.67), material=body, bevel=0.003, parent=ac)
    B.plane("arcade_marquee", w - 0.02, 0.2, (0, -0.372, 1.67), (0, 0, 0), B.mat_image("arcade_marquee", "game_marquee.png",
            rough=0.3, emission=3.0, interp="Closest"), parent=ac)


# ---------------------------------------------------------------- table + props

def gba(parent, loc, rot):
    """Indigo GBA with the wedding invitation running on it."""
    g = B.empty("gba_root", loc, (0, 0, rot), parent=parent, hs="gba")
    B.superellipsoid("gba_body", (0.145, 0.082, 0.024), (0, 0, 0.012), material=plastic("gba", "#5b4fb8", 0.35), e=0.35,
                     nu=24, nv=10, parent=g)
    B.box("gba_bezel", (0.074, 0.054, 0.002), (0, 0.004, 0.0245), material=graphite_dark(), bevel=0.002, parent=g)
    B.plane("gba_screen", 0.06, 0.04, (0, 0.004, 0.0262), (-90, 0, 0), B.mat_image(
        "gba_screen", "game_gba.png", rough=0.2, emission=1.6, spec=0.6, interp="Closest"), parent=g)
    B.box("gba_dpad_h", (0.02, 0.006, 0.003), (-0.052, 0.004, 0.025), material=graphite_dark(), bevel=0.001, parent=g)
    B.box("gba_dpad_v", (0.006, 0.02, 0.003), (-0.052, 0.004, 0.025), material=graphite_dark(), bevel=0.001, parent=g)
    for k, (x, y) in enumerate(((0.05, 0.008), (0.06, -0.002))):
        B.cylinder(f"gba_btn{k}", 0.005, 0.004, (x, y, 0.025), material=plastic("gba_btn", "#2e2a6a", 0.3), verts=12,
                   parent=g)


def build_table():
    B.use_collection("table")
    x0, x1, y0, y1, top = TABLE
    tb = B.empty("table_root", (0, 0, 0), (0, 0, 0), parent=root)
    B.box_minmax("table_top", (x0, y0, top - 0.03), (x1, y1, top), teak(), bevel=0.006, parent=tb)
    for sx in (x0 + 0.05, x1 - 0.05):
        for sy in (y0 + 0.05, y1 - 0.05):
            B.cylinder(f"table_leg{sx:.2f}{sy:.2f}", 0.016, top - 0.03, (sx, sy, (top - 0.03) / 2), material=graphite(),
                       verts=12, parent=tb)
    gba(tb, (0.2, 0.56, top), -12)
    fc_pad(tb, (-0.1, 0.74, top + 0.008), 18, "pad2")
    carts = B.empty("carts_root", (0.12, 0.75, top), (0, 0, -8), parent=tb)
    for k, c in enumerate(("#2fc9ab", "#e8574a", "#ffd34a", "#6aa6ff")):
        B.box(f"cart{k}", (0.075, 0.12, 0.018), (0.004 * k, 0.0, 0.009 + k * 0.0185), (0, 0, k * 6),
              material=plastic("cart_beige", "#d2c39f"), bevel=0.003, parent=carts)
        B.box(f"cart{k}_label", (0.06, 0.07, 0.001), (0.004 * k, 0.01, 0.0185 + k * 0.0185), (0, 0, k * 6),
              material=plastic(f"cart_label{k}", c), bevel=0, parent=carts)
    can = B.empty("can_root", (-0.22, 0.52, top), (0, 0, 0), parent=tb)
    B.cylinder("can", 0.033, 0.12, (0, 0, 0.06), material=B.mat("can", srgb("#e8574a"), 0.25, metal=0.6), verts=24,
               bevel=0.003, parent=can)
    B.cylinder("can_top", 0.03, 0.004, (0, 0, 0.121), material=B.mat("can_top", srgb("#c9ccd1"), 0.25, metal=0.9),
               verts=24, parent=can)
    return tb


def build_lights():
    B.use_collection("lights")
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = SUN_STRENGTH
    sun.angle = math.radians(1.2)
    sun.color = (1.0, 0.66, 0.42)
    so = bpy.data.objects.new("sun", sun)
    B.link(so)
    so.rotation_euler = (-SUN_DIR()).to_track_quat("-Z", "Y").to_euler()
    for name, energy, col, size, loc in (
            ("crt_light", 5.0, (0.75, 0.85, 1.0), (0.5, 0.38), (CRT_X - 0.03, CRT_Y0 - 0.03, CAB[4] + CRT_H / 2 + 0.02)),
            ("arcade_light", 3.0, (0.8, 0.85, 1.0), (0.3, 0.4), (1.05, FRONT_Y - 0.4, 1.12))):
        a = bpy.data.lights.new(name, "AREA")
        a.shape = "RECTANGLE"
        a.size, a.size_y = size
        a.energy = energy
        a.color = col
        o = bpy.data.objects.new(name, a)
        B.link(o)
        o.parent = root
        o.location = loc
        o.rotation_euler = (math.radians(90), 0, 0)
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 130
    fill.size = 3.0
    fill.color = (1.0, 0.9, 0.82)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.location = (0.9, -1.7, 2.35)
    stage.look_at(f, (0, 1.6, 0.8))
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


SUN_STRENGTH = 13.0


def SUN_DIR():
    """Direction toward the low sun: out of the window and behind him, so the beam lands on the front-left corner."""
    import nightcity
    from mathutils import Vector
    out, along = nightcity.outward()
    return (out * 0.7 - along * 0.8 + Vector((0, 0, 0.36))).normalized()


def build_all():
    global root
    import models_char as C
    root = stage.desk_frame("game_root")
    build_shell()
    chair = build_chair(root)
    C.build_character(chair, arms="pad")
    pad = fc_pad(chair, (0.0, 0.43, 0.735), 0, "pad1")
    tv, fc = build_tv()
    build_handhelds()
    build_archive()
    build_arcade()
    tb = build_table()
    # cables from both pads to the FC, draped over the table edge and along the floor
    fcx = (CAB[0] + (CAB[0] + CAB[1]) / 2) / 2
    cy = stage.CHAIR[0][1]
    cable("pad1_cable", [(0.0, cy + 0.455, 0.735), (-0.03, cy + 0.5, 0.7), (-0.08, TABLE[2] - 0.02, TABLE[4] + 0.01),
                         (-0.12, TABLE[2] + 0.12, TABLE[4] + 0.004), (-0.2, TABLE[3] - 0.1, TABLE[4] + 0.004),
                         (-0.24, TABLE[3] + 0.04, 0.2), (-0.24, CAB[2] - 0.04, 0.01), (fcx - 0.06, CAB[2] + 0.02, 0.2),
                         (fcx - 0.06, CAB[2] + 0.1, 0.33)], root)
    cable("pad2_cable", [(-0.09, 0.77, TABLE[4] + 0.01), (-0.06, TABLE[3] - 0.02, TABLE[4] + 0.005),
                         (0.02, TABLE[3] + 0.06, 0.15), (-0.04, CAB[2] - 0.06, 0.01), (fcx + 0.05, CAB[2] + 0.02, 0.2),
                         (fcx + 0.05, CAB[2] + 0.1, 0.33)], root)
    # 烧酒 on the warm CRT, 小八 stretched out on the table
    C.build_shaojiu(tv, (CRT_X + 0.02, CRT_Y0 + 0.22, CAB[4] + CRT_H), 0).scale = (0.58,) * 3
    C.build_xiaoba(tb, (0.52, 0.66, TABLE[4]), -165).scale = (0.45,) * 3
