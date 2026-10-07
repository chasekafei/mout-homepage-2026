"""Furniture and props for the creation room."""
from __future__ import annotations

import math

import bpy

import blib as B
import room as R
import stage
from blib import srgb

# Interactive hotspot ids (order defines the mask encoding; max 15).
HOTSPOTS = [
    "writing",      # journal + corkboard  -> 写作 / 社思现场
    "podcast",      # microphone            -> CrossPod 串台
    "products",     # cartridges            -> 独立产品
    "rubik",        # Rubik's cube          -> 旧个人网站
    "cat_shaojiu",  # tabby                 -> 烧酒
    "cat_xiaoba",   # blue & white          -> 小八
    "me",           # the character         -> 关于我 / 和我聊聊
    "books",        # book stack            -> 创作方法
    "window",       # window view           -> 出发 (teaser)
]

DESK_TOP = stage.DESK_TOP
MAIN_X0, MAIN_X1 = -1.0, 1.75
MAIN_Y0, MAIN_Y1 = 0.0, 0.85


def graphite():
    return B.mat("desk_graphite", srgb("#46474c"), 0.42, spec=0.5)


def graphite_dark():
    return B.mat("graphite_dark", srgb("#2a2b2e"), 0.5, spec=0.4)


desk_root = None


def build_desk():
    global desk_root
    B.use_collection("desk")
    g = graphite()
    gd = graphite_dark()
    desk_root = stage.desk_frame()
    t = 0.045
    B.box_minmax("desk_top", (MAIN_X0, MAIN_Y0, DESK_TOP - t), (MAIN_X1, MAIN_Y1, DESK_TOP), g, bevel=0.008,
                 parent=desk_root)
    # pedestals with drawers
    peds = (("ped_l", MAIN_X0 + 0.04, MAIN_X0 + 0.56, MAIN_Y0 + 0.04, MAIN_Y1 - 0.04, "y"),
            ("ped_r", MAIN_X1 - 0.56, MAIN_X1 - 0.04, MAIN_Y0 + 0.04, MAIN_Y1 - 0.04, "y"))
    for name, x0, x1, y0, y1, face in peds:
        B.box_minmax(name, (x0, y0, 0.02), (x1, y1, DESK_TOP - t), gd, bevel=0.006, parent=desk_root)
        for k, (z0, z1) in enumerate(((0.05, 0.3), (0.32, 0.5), (0.52, 0.69))):
            if face == "y":
                B.box_minmax(f"{name}_drw{k}", (x0 + 0.015, y0 - 0.02, z0), (x1 - 0.015, y0, z1), g, bevel=0.004,
                             parent=desk_root)
                B.box_minmax(f"{name}_hdl{k}", ((x0 + x1) / 2 - 0.08, y0 - 0.034, z1 - 0.05),
                             ((x0 + x1) / 2 + 0.08, y0 - 0.02, z1 - 0.035), gd, bevel=0.003, parent=desk_root)
            else:
                B.box_minmax(f"{name}_drw{k}", (x0 - 0.02, y0 + 0.015, z0), (x0, y1 - 0.015, z1), g, bevel=0.004,
                             parent=desk_root)
                B.box_minmax(f"{name}_hdl{k}", (x0 - 0.034, (y0 + y1) / 2 - 0.08, z1 - 0.05),
                             (x0 - 0.02, (y0 + y1) / 2 + 0.08, z1 - 0.035), gd, bevel=0.003, parent=desk_root)
    B.box_minmax("desk_modesty", (MAIN_X0 + 0.56, MAIN_Y1 - 0.08, 0.3), (MAIN_X1 - 0.56, MAIN_Y1 - 0.05,
                                                                            DESK_TOP - t), gd, bevel=0.004, parent=desk_root)
    return desk_root


def build_chair():
    B.use_collection("chair")
    fab = B.mat_noise("chair_fabric", srgb("#4a4b51"), srgb("#3f4045"), scale=900, rough=0.8, bump=0.2, spec=0.3)
    frm = B.mat("chair_frame", srgb("#2a2b2f"), 0.4, metal=0.5)
    root = stage.chair_frame(desk_root)
    B.box("chair_seat", (0.52, 0.5, 0.08), (0, 0.02, 0.47), material=fab, bevel=0.025, parent=root)
    B.box("chair_back", (0.44, 0.07, 0.44), (0, -0.25, 0.79), (-8, 0, 0), material=fab, bevel=0.03, parent=root)
    B.box("chair_back_frame", (0.48, 0.045, 0.48), (0, -0.285, 0.79), (-8, 0, 0), material=frm, bevel=0.02,
          parent=root)
    for sx in (-1, 1):
        B.box(f"chair_arm_{sx}", (0.065, 0.34, 0.045), (sx * 0.3, 0.05, 0.68), material=frm, bevel=0.014, parent=root)
        B.box(f"chair_armpost_{sx}", (0.04, 0.04, 0.2), (sx * 0.3, -0.06, 0.58), material=frm, bevel=0.01,
              parent=root)
    B.cylinder("chair_post", 0.03, 0.38, (0, 0, 0.26), material=frm, parent=root, verts=24)
    for k in range(5):
        a = k * 2 * math.pi / 5
        B.box(f"chair_leg{k}", (0.32, 0.05, 0.035), (0.16 * math.cos(a), 0.16 * math.sin(a), 0.06),
              (0, 0, math.degrees(a)), material=frm, bevel=0.01, parent=root)
        B.cylinder(f"chair_wheel{k}", 0.025, 0.03, (0.3 * math.cos(a), 0.3 * math.sin(a), 0.025),
                   (90, 0, math.degrees(a)), material=frm, parent=root, verts=16)
    return root


def build_rug():
    B.use_collection("room")
    m = B.mat_image("rug", "rug.png", rough=0.95, spec=0.1, repeat=(3, 3), interp="Closest")
    B.plane("rug", 2.6, 2.2, (-0.6, 0.7, 0.009), (-90, 0, -24), m)
    B.box("rug_base", (2.6, 2.2, 0.008), (-0.6, 0.7, 0.004), (0, 0, -24), B.mat("rug_edge", srgb("#6a6762"), 0.95), bevel=0.003)


def build_left_shelf():
    """Low graphite open shelf along the angled left wall."""
    B.use_collection("shelf_left")
    g = B.mat("shelf_graphite", srgb("#46474b"), 0.55, spec=0.4)
    s0, s1 = 0.3, 3.6
    L = s1 - s0
    depth, h, t = 0.42, 0.9, 0.035
    c = R.on_left_wall((s0 + s1) / 2, 0, depth / 2)
    root = B.empty("shelf_left_root", (c[0], c[1], 0), (0, 0, math.degrees(R.LW_ANGLE)))
    # local frame: x along the wall (toward the corner = +x), y = depth (−y into the room)
    for name, z in (("top", h - t / 2), ("mid", 0.47), ("bot", 0.06)):
        B.box(f"ls_{name}", (L, depth, t), (0, 0, z), material=g, bevel=0.004, parent=root)
    for k in range(5):
        x = -L / 2 + t / 2 + k * (L - t) / 4
        B.box(f"ls_div{k}", (t, depth, h - 0.04), (x, 0, (h + 0.04) / 2), material=g, bevel=0.004, parent=root)
    B.box("ls_back", (L, 0.01, h), (0, depth / 2 - 0.005, h / 2), material=g, bevel=0, parent=root)
    return root


def build_bench():
    B.use_collection("bench")
    wm = R.wall_mat()
    cush = B.mat_noise("cushion", srgb("#d9d5cd"), srgb("#d0cbc2"), scale=120, rough=0.95, spec=0.2, bump=0.1)
    y0 = R.BACK_Y - 0.52
    B.box_minmax("bench_base", (R.WIN_X0, y0, 0), (R.WIN_X1, R.BACK_Y + 0.2, 0.46), wm, bevel=0.01)
    B.box_minmax("bench_cushion", (R.WIN_X0 + 0.02, y0 + 0.02, 0.46), (R.WIN_X1 - 0.02, R.BACK_Y + 0.18, 0.55),
                 cush, bevel=0.03, segments=3)
    wood = B.mat("light_wood", srgb("#b58f68"), 0.55)
    B.box_minmax("bench_trim", (R.WIN_X0, y0 - 0.005, 0.0), (R.WIN_X1, y0 + 0.01, 0.06), wood, bevel=0.003)


def build_right_shelf():
    B.use_collection("shelf_right")
    m = B.mat("metal_shelf", srgb("#2f3033"), 0.45, metal=0.5)
    x0, x1 = 3.75, 4.75
    y0, y1 = R.BACK_Y - 0.48, R.BACK_Y - 0.04
    for z in (0.04, 0.36, 0.68, 0.98):
        B.box_minmax(f"rs_{z}", (x0, y0, z), (x1, y1, z + 0.03), m, bevel=0.004)
    for xx in (x0, x1 - 0.03):
        for yy in (y0, y1 - 0.03):
            B.box_minmax(f"rs_post_{xx}_{yy}", (xx, yy, 0), (xx + 0.03, yy + 0.03, 1.02), m, bevel=0.003)


def proxies():
    """Temporary stand-ins used while calibrating the camera."""
    B.use_collection("proxy")
    hair = B.mat("proxy_hair", srgb("#151515"), 0.6)
    r = desk_root
    B.box("p_books", (0.28, 0.2, 0.2), (1.1, 0.2, DESK_TOP + 0.1), material=B.mat("p_book", srgb("#e8c13e")),
          hs="books", parent=r)
    B.box("p_mic", (0.08, 0.08, 0.3), (0.14, 0.72, DESK_TOP + 0.15), material=hair, hs="podcast", parent=r)
    B.box("p_journal", (0.42, 0.3, 0.02), (0.24, 0.32, DESK_TOP + 0.01), material=B.mat("p_paper", srgb("#efe6d2")),
          hs="writing", parent=r)
    B.box("p_rubik", (0.07, 0.07, 0.07), (0.47, 0.14, DESK_TOP + 0.035), material=B.mat("p_rub", srgb("#dd3333")),
          hs="rubik", parent=r)


def build_all():
    import models_char as C
    build_desk()
    chair = build_chair()
    C.build_character(chair)
    C.build_shaojiu(desk_root, (-0.7, 0.26, DESK_TOP), 22)
    C.build_xiaoba(desk_root, (0.8, 0.6, DESK_TOP), 30)
    build_rug()
    build_left_shelf()
    build_bench()
    build_right_shelf()
    import props_desk
    import props_room
    props_desk.build(desk_root)
    props_room.build_all()
