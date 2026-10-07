"""Middle ground: corkboard, shelf contents, plants, guitar, posters, window bench dressing, right shelf."""
from __future__ import annotations

import math
import random

import bpy
import numpy as np

import blib as B
import room as R
from blib import sample, sd_box, sd_capsule, sd_ellipsoid, srgb

LEAF_GREENS = ["#3f6b2c", "#4a7a32", "#56883a", "#2f5a24", "#5f9142", "#46732f"]


def wall_root(name, s, d=0.0, z=0.0, hs=None):
    """Empty on the angled left wall. Local +X runs toward the corner, -Y points into the room."""
    p = R.on_left_wall(s, z, d)
    return B.empty(name, p, (0, 0, math.degrees(R.LW_ANGLE)), hs=hs)


# ------------------------------------------------------------------ plants

def pot(name, r_top, r_bot, h, color, loc, parent=None, rim=True):
    m = B.mat(f"pot_{name}", srgb(color), 0.55, spec=0.35)
    root = B.empty(f"{name}_root", loc, (0, 0, 0), parent=parent)
    prof = [(0.0, 0.0), (r_bot, 0.0), (r_top, h), (r_top - 0.012, h), (r_top - 0.016, h - 0.03), (0.0, h - 0.03)]
    if rim:
        prof = [(0.0, 0.0), (r_bot, 0.0), (r_top * 0.97, h - 0.04), (r_top, h - 0.04), (r_top, h),
                (r_top - 0.014, h), (r_top - 0.018, h - 0.03), (0.0, h - 0.03)]
    B.lathe(f"{name}_pot", prof, (0, 0, 0), material=m, segs=40, parent=root, smooth=False)
    soil = B.mat("soil", srgb("#3a2c22"), 0.95)
    B.cylinder(f"{name}_soil", r_top - 0.02, 0.01, (0, 0, h - 0.035), material=soil, verts=32, parent=root)
    return root


def square_pot(name, w, h, color, loc, parent=None):
    m = B.mat(f"pot_{name}", srgb(color), 0.6, spec=0.3)
    root = B.empty(f"{name}_root", loc, (0, 0, 0), parent=parent)
    B.box(f"{name}_pot", (w, w, h), (0, 0, h / 2), material=m, bevel=0.012, parent=root)
    B.box(f"{name}_soil", (w - 0.03, w - 0.03, 0.01), (0, 0, h - 0.015), material=B.mat("soil", srgb("#3a2c22"), 0.95),
          bevel=0, parent=root)
    return root


def plant(name, root, top_z, n, height, spread, leaf_len, leaf_w, seed, droop=0.25, stem_col="#4d6b33",
          pitch=(10, 55), greens=LEAF_GREENS, hs=None):
    """Bushy plant: stems fan out from the pot centre, one leaf per stem tip plus a few along it."""
    rng = random.Random(seed)
    specs, stems = [], []
    for k in range(n):
        az = rng.uniform(0, 2 * math.pi)
        t = (k + rng.random()) / n
        h = height * (0.35 + 0.65 * math.sqrt(t))
        rad = spread * (0.25 + 0.75 * (1 - t) * rng.uniform(0.6, 1.1))
        tip = (rad * math.cos(az), rad * math.sin(az), top_z + h)
        mid = (tip[0] * 0.45, tip[1] * 0.45, top_z + h * 0.6)
        stems.append(((0, 0, top_z), mid, 0.004))
        stems.append((mid, tip, 0.0035))
        col = srgb(rng.choice(greens))
        L = leaf_len * rng.uniform(0.75, 1.15)
        specs.append(dict(base=tip, yaw=math.degrees(az) + rng.uniform(-30, 30), pitch=rng.uniform(*pitch),
                          roll=rng.uniform(-25, 25), length=L, width=leaf_w * L / leaf_len, fold=0.25,
                          curl=droop * rng.uniform(0.6, 1.3), color=col))
    B.tubes(f"{name}_stems", stems, B.mat(f"stem_{stem_col}", srgb(stem_col), 0.6), parent=root, hs=hs)
    B.leaves(f"{name}_leaves", specs, B.mat_leaf(), parent=root, hs=hs)


# ------------------------------------------------------------------ corkboard

def corkboard():
    B.use_collection("corkboard")
    s_c, w, h, z0 = 2.05, 3.1, 1.2, 0.97
    root = wall_root("cork_root", s_c, 0.0, 0.0, hs=None)
    cork = B.mat_noise("cork", srgb("#b88c5a"), srgb("#a27748"), scale=260, rough=0.95, detail=8, bump=0.25,
                       spec=0.15)
    frame = B.mat("cork_frame", srgb("#c9a57a"), 0.6)
    B.box("cork_board", (w, 0.025, h), (0, -0.0125, z0 + h / 2), material=cork, bevel=0.002, parent=root)
    for nm, sz, lc in (("t", (w + 0.04, 0.035, 0.03), (0, -0.017, z0 + h + 0.01)),
                       ("b", (w + 0.04, 0.035, 0.03), (0, -0.017, z0 - 0.01)),
                       ("l", (0.03, 0.035, h + 0.04), (-w / 2 - 0.01, -0.017, z0 + h / 2)),
                       ("r", (0.03, 0.035, h + 0.04), (w / 2 + 0.01, -0.017, z0 + h / 2))):
        B.box(f"cork_frame_{nm}", sz, lc, material=frame, bevel=0.004, parent=root)
    # notes: (texture, width, local x (−x = farther from the corner, toward the camera), z centre, tilt)
    notes = [
        ("note_small_creators.png", 0.42, -1.25, 1.84, -2),
        ("note_wire_0.png", 0.34, -0.8, 1.98, 1.5),
        ("note_sticky_0.png", 0.18, -0.44, 2.2, -3),
        ("note_wire_1.png", 0.3, -0.44, 1.7, 2),
        ("photo_landscape.png", 0.36, 0.0, 2.17, 1),
        ("news_page_0.png", 0.22, -0.02, 1.62, -1.5),
        ("note_better_tools.png", 0.28, 0.36, 1.66, 2.5),
        ("note_wire_2.png", 0.26, 0.68, 1.9, -1.5),
        ("note_sticky_1.png", 0.16, 0.95, 2.2, 3),
        ("note_flow.png", 0.24, 1.18, 1.72, -2),
        ("photo_park.png", 0.22, 1.32, 2.12, 1.5),
        ("note_sticky_0.png", 0.15, -1.38, 1.4, 4),
    ]
    pins = [srgb(c) for c in ("#d8402e", "#e8b93a", "#2f6fd6", "#f2efe8")]
    rng = random.Random(9)
    for k, (tex, nw, x, z, tilt) in enumerate(notes):
        iw, ih = bpy.data.images.load(str(B.TEX / tex), check_existing=True).size
        nh = nw * ih / iw
        m = B.mat_image(f"note_{tex}", tex, rough=0.85, spec=0.2)
        n = B.plane(f"note{k}", nw, nh, (x, -0.027 - k * 0.0004, z), (0, tilt, 0), m, parent=root,
                    hs="writing")
        # paper curls slightly off the board
        n.rotation_euler.x = math.radians(rng.uniform(-2.5, 2.5))
        pm = B.mat(f"pin{k % 4}", pins[k % 4], 0.3, spec=0.6, coat=0.5)
        B.cylinder(f"pin{k}", 0.008, 0.012, (x + rng.uniform(-0.02, 0.02), -0.036, z + nh / 2 - 0.025),
                   (90, 0, 0), material=pm, verts=12, parent=root)


# ------------------------------------------------------------------ left shelf contents

BOOK_COLS = ["#efece5", "#e6dfd2", "#3f4146", "#e9b83a", "#d9d2c5", "#5b5e66", "#f2c94c", "#b9b1a3"]


def book_row(name, parent, x0, x1, z, depth, rng, max_h=0.3, lean_end=True):
    """Standing books from x0 to x1 (shelf-local), spines toward -Y."""
    x = x0
    k = 0
    pages = B.mat("book_pages", srgb("#efe8d8"), 0.85)
    while x < x1 - 0.02:
        t = rng.uniform(0.022, 0.045)
        h = rng.uniform(0.6, 1.0) * max_h
        col = srgb(rng.choice(BOOK_COLS))
        m = B.mat(f"bk_{col}", col, 0.6)
        b = B.box(f"{name}_{k}", (t, depth * rng.uniform(0.75, 0.95), h), (x + t / 2, 0, z + h / 2), material=m,
                  bevel=0.002, parent=parent)
        x += t + 0.002
        k += 1
    return x


def book_stack(name, parent, x, y, z, n, rng, w=(0.2, 0.26), d=(0.15, 0.2), t=(0.022, 0.04), rot=0.0, cols=None):
    zz = z
    for k in range(n):
        th = rng.uniform(*t)
        col = srgb(rng.choice(cols or BOOK_COLS))
        m = B.mat(f"bk_{col}", col, 0.6)
        B.box(f"{name}_{k}", (rng.uniform(*w), rng.uniform(*d), th), (x + rng.uniform(-0.01, 0.01), y, zz + th / 2),
              (0, 0, rot + rng.uniform(-6, 6)), material=m, bevel=0.002, parent=parent)
        zz += th
    return zz


def storage_box(name, parent, x, y, z, w, d, h, color="#efede8"):
    m = B.mat(f"sbox_{color}", srgb(color), 0.7)
    B.box(f"{name}", (w, d, h), (x, y, z + h / 2), material=m, bevel=0.006, parent=parent)
    B.box(f"{name}_hdl", (w * 0.3, 0.004, 0.025), (x, y - d / 2, z + h * 0.72),
          material=B.mat("sbox_hole", srgb("#3b3b3d"), 0.8), bevel=0.003, parent=parent)


def camera(parent, loc, rot):
    root = B.empty("camera_prop", loc, (0, 0, rot), parent=parent)
    body = B.mat("cam_body", srgb("#1d1e21"), 0.45, spec=0.4)
    trim = B.mat("cam_trim", srgb("#9a9ca1"), 0.3, metal=1.0)
    B.box("cam_body", (0.13, 0.06, 0.08), (0, 0, 0.04), material=body, bevel=0.008, parent=root)
    B.box("cam_top", (0.13, 0.06, 0.012), (0, 0, 0.086), material=trim, bevel=0.003, parent=root)
    B.cylinder("cam_lens", 0.028, 0.05, (0.01, -0.05, 0.042), (90, 0, 0), material=body, verts=32, parent=root)
    B.cylinder("cam_glass", 0.02, 0.004, (0.01, -0.076, 0.042), (90, 0, 0),
               material=B.mat("cam_glass", srgb("#202838"), 0.05, spec=0.9), verts=32, parent=root)
    B.cylinder("cam_dial", 0.01, 0.01, (-0.04, 0, 0.097), material=trim, verts=16, parent=root)


def cat_figurine(parent, loc, rot, color="#1a1a1c", name="figure_cat"):
    vs = 0.009
    body = lambda p: sd_ellipsoid(p, (0, 0, 0.04), (0.035, 0.03, 0.045))
    head = lambda p: sd_ellipsoid(p, (0, -0.005, 0.1), (0.033, 0.03, 0.028))
    ears = lambda p: np.minimum(sd_box(p, (0.02, -0.005, 0.13), (0.008, 0.006, 0.01), 0.002),
                                sd_box(p, (-0.02, -0.005, 0.13), (0.008, 0.006, 0.01), 0.002))
    tail = lambda p: sd_capsule(p, (0.03, 0.02, 0.01), (0.05, -0.02, 0.008), 0.009)
    c = srgb(color)
    def col(p):
        out = np.repeat(np.array([c], float), len(p), 0)
        eye = (p[:, 1] < -0.025) & (np.abs(np.abs(p[:, 0]) - 0.014) < 0.006) & (np.abs(p[:, 2] - 0.104) < 0.005)
        out[eye] = srgb("#e8c13e")
        return out
    vox = sample([(ears, c), (head, col), (tail, c), (body, c)], vs, ((-0.07, -0.06, 0.0), (0.07, 0.06, 0.15)))
    return B.voxel_solid(name, vox, vs, loc, B.mat_voxel("vox_fig", rough=0.4, spec=0.5), parent=parent,
                         rot=(0, 0, rot), seed=3, jitter=0.02, bevel=0.25)


def left_shelf_contents():
    B.use_collection("shelf_left")
    s0, s1 = 0.3, 3.6
    sc = (s0 + s1) / 2
    depth = 0.42
    root = wall_root("lsc_root", sc, depth / 2)
    L = s1 - s0
    rng = random.Random(4)
    # cubby x ranges (local x toward the corner is +)
    t = 0.035
    edges = [-L / 2 + t + k * (L - t) / 4 for k in range(5)]
    cub = [(edges[k] + 0.01, edges[k + 1] - t - 0.01) for k in range(4)]
    top, mid, bot = 0.9, 0.4875, 0.0775
    # top surface: book stack, small plant, yellow notebooks, camera, black cat figure
    book_stack("ls_top_books", root, -1.42, 0.0, top, 4, rng, cols=["#efece5", "#d9d2c5", "#5b5e66", "#efece5"])
    p = pot("ls_plant", 0.07, 0.055, 0.12, "#e9e5dd", (-0.92, 0.02, top), parent=root)
    plant("ls_plant", p, 0.1, 14, 0.13, 0.12, 0.09, 0.06, seed=12, droop=0.35, pitch=(5, 40))
    book_stack("ls_yellow", root, -0.48, -0.02, top, 2, rng, w=(0.22, 0.24), d=(0.16, 0.17), t=(0.02, 0.026),
               cols=["#f2c94c", "#e9b83a"], rot=8)
    camera(root, (-0.02, -0.03, top), -12)
    cat_figurine(root, (0.36, -0.03, top), -10)
    # cubbies
    x0, x1 = cub[0]
    book_stack("lc0u", root, x0 + 0.16, -0.02, mid, 5, rng, cols=["#f2c94c", "#e9b83a", "#efece5"])
    book_row("lc0ur", root, x0 + 0.38, x1, mid, depth * 0.8, rng, max_h=0.32)
    storage_box("lc0b", root, (x0 + x1) / 2 - 0.15, 0.0, bot, 0.34, 0.32, 0.26)
    book_stack("lc0bs", root, x1 - 0.17, 0.0, bot, 4, rng)
    x0, x1 = cub[1]
    book_row("lc1u", root, x0, x0 + 0.34, mid, depth * 0.8, rng, max_h=0.3)
    book_stack("lc1us", root, x1 - 0.16, -0.02, mid, 6, rng, t=(0.018, 0.03))
    storage_box("lc1b", root, (x0 + x1) / 2, 0.0, bot, 0.42, 0.32, 0.22)
    x0, x1 = cub[2]
    storage_box("lc2u", root, (x0 + x1) / 2 - 0.12, 0.0, mid, 0.36, 0.32, 0.2)
    book_row("lc2ur", root, x1 - 0.2, x1, mid, depth * 0.8, rng, max_h=0.3)
    book_row("lc2b", root, x0, x1 - 0.3, bot, depth * 0.8, rng, max_h=0.32)
    x0, x1 = cub[3]
    book_stack("lc3u", root, (x0 + x1) / 2, -0.02, mid, 5, rng, cols=["#e9b83a", "#efece5", "#f2c94c"])
    storage_box("lc3b", root, (x0 + x1) / 2, 0.0, bot, 0.4, 0.32, 0.24)


# ------------------------------------------------------------------ guitar

def guitar(loc, yaw):
    B.use_collection("guitar")
    root = B.empty("guitar_root", loc, (0, 0, yaw))
    body_m = B.mat("guitar_body", srgb("#2a211d"), 0.25, spec=0.6, coat=0.6)
    edge_m = B.mat("guitar_edge", srgb("#8a6a4c"), 0.4, coat=0.3)
    neck_m = B.mat("guitar_neck", srgb("#3a2a20"), 0.45)
    metal = B.mat("guitar_metal", srgb("#c9c9c9"), 0.25, metal=1.0)

    def half_width(z):
        a = math.sqrt(max(0.0, 0.19 ** 2 - (z - 0.19) ** 2))
        b = math.sqrt(max(0.0, 0.145 ** 2 - (z - 0.45) ** 2))
        w = max(a, b)
        if 0.22 < z < 0.46:
            w = max(w, 0.118 + 0.02 * abs(z - 0.34) / 0.12)
        return w

    zs = [i / 40 * 0.595 for i in range(41)]
    right = [(max(0.004, half_width(z)), z) for z in zs]
    outline = right + [(-x, z) for x, z in reversed(right)]
    tilt = 14.0
    g = B.empty("guitar_tilt", (0, 0, 0.08), (-tilt, 0, 0), parent=root)
    B.extrude("guitar_body", outline, 0.1, (0, -0.05, 0.0), material=body_m, bevel=0.012, parent=g)
    B.extrude("guitar_binding", [(x * 1.01, z) for x, z in outline], 0.012, (0, -0.056, 0.0), material=edge_m,
              parent=g)
    B.cylinder("guitar_hole", 0.045, 0.004, (0, -0.062, 0.36), (90, 0, 0),
               material=B.mat("guitar_hole", srgb("#0c0b0b"), 0.9), verts=40, parent=g)
    B.box("guitar_bridge", (0.11, 0.012, 0.024), (0, -0.058, 0.13), material=neck_m, bevel=0.003, parent=g)
    B.box("guitar_neck", (0.05, 0.03, 0.46), (0, -0.03, 0.59 + 0.23), material=neck_m, bevel=0.006, parent=g)
    B.box("guitar_fret", (0.048, 0.006, 0.44), (0, -0.047, 0.59 + 0.23), material=B.mat("fretboard",
          srgb("#1a1412"), 0.5), bevel=0.002, parent=g)
    B.box("guitar_head", (0.075, 0.025, 0.17), (0, -0.025, 1.05 + 0.085), (6, 0, 0), material=body_m, bevel=0.008,
          parent=g)
    for k in range(3):
        for sx in (-1, 1):
            B.cylinder(f"guitar_peg{k}{sx}", 0.008, 0.03, (sx * 0.05, -0.02, 1.09 + k * 0.045), (0, 90, 0),
                       material=metal, verts=12, parent=g)
    B.tubes("guitar_strings", [((x, -0.066, 0.13), (x * 0.6, -0.05, 1.04), 0.0007)
                               for x in np.linspace(-0.022, 0.022, 6)], metal, parent=g)
    # A-frame stand
    st = B.mat("stand", srgb("#1b1b1d"), 0.4, metal=0.5)
    B.tubes("guitar_stand", [((-0.15, -0.18, 0.0), (0.0, -0.06, 0.12), 0.008), ((0.15, -0.18, 0.0), (0.0, -0.06, 0.12),
                                                                              0.008),
                             ((0, 0.25, 0.0), (0, 0.04, 0.6), 0.008), ((-0.13, -0.12, 0.1), (0.13, -0.12, 0.1), 0.008)],
            st, parent=root)


# ------------------------------------------------------------------ posters

def framed(name, tex, w, h, loc, rot_z=0.0, frame_col="#2b2522", mat_w=0.03, parent=None, hs=None):
    root = B.empty(f"{name}_root", loc, (0, 0, rot_z), parent=parent, hs=hs)
    fm = B.mat(f"frame_{frame_col}", srgb(frame_col), 0.45)
    t, d = 0.025, 0.03
    B.box(f"{name}_back", (w, 0.01, h), (0, 0.0, 0), material=B.mat("frame_mat", srgb("#f4f1ea"), 0.8), bevel=0,
          parent=root)
    for nm, sz, lc in (("t", (w + 2 * t, d, t), (0, -d / 2, h / 2 + t / 2)), ("b", (w + 2 * t, d, t), (0, -d / 2, -h / 2 - t / 2)),
                       ("l", (t, d, h), (-w / 2 - t / 2, -d / 2, 0)), ("r", (t, d, h), (w / 2 + t / 2, -d / 2, 0))):
        B.box(f"{name}_f{nm}", sz, lc, material=fm, bevel=0.003, parent=root)
    m = B.mat_image(f"poster_{tex}", tex, rough=0.75, spec=0.25)
    B.plane(f"{name}_art", w - 2 * mat_w, h - 2 * mat_w, (0, -0.006, 0), (0, 0, 0), m, parent=root)
    return root


def posters():
    B.use_collection("posters")
    y = R.BACK_Y - 0.005
    framed("poster_still", "poster_still.png", 0.62, 0.92, (-0.62, y, 1.86))
    framed("poster_calmer", "poster_calmer.png", 0.54, 0.69, (4.5, y, 2.05), frame_col="#f2efe9", mat_w=0.0)
    framed("photo_small", "photo_park.png", 0.2, 0.26, (4.08, y, 1.42), frame_col="#2b2522", mat_w=0.02)


# ------------------------------------------------------------------ window bench dressing

def pillow(name, size, loc, rot, color=None, tex=None):
    w, d, h = size
    if tex:
        m = B.mat_image(f"pillow_{tex}", tex, rough=0.9, spec=0.2)
    else:
        m = B.mat_noise(f"pillow_{color}", srgb(color), tuple(c * 0.9 for c in srgb(color)), scale=300, rough=0.95,
                        spec=0.2, bump=0.15)
    return B.superellipsoid(name, (w, d, h), loc, rot, material=m, e=0.28, puff=0.35)


def bench_dressing():
    B.use_collection("bench")
    zt = 0.55
    yb = R.BACK_Y - 0.1
    pillow("pillow_dark", (0.42, 0.16, 0.36), (0.3, yb - 0.08, zt + 0.17), (-12, 0, -4), color="#55565c")
    pillow("pillow_cat", (0.5, 0.16, 0.38), (0.82, yb - 0.12, zt + 0.18), (-10, 0, 3), tex="pillow_cat.png")
    # knitted throw over the bench edge
    knit = B.mat_noise("knit", srgb("#7b7c80"), srgb("#8e8f93"), scale=420, rough=0.95, detail=4, bump=0.4, spec=0.2)
    y0 = R.BACK_Y - 0.52
    B.box_minmax("throw_top", (0.95, y0 + 0.02, zt - 0.005), (1.6, y0 + 0.45, zt + 0.03), knit, bevel=0.012)
    B.box_minmax("throw_drop", (0.97, y0 - 0.03, 0.18), (1.58, y0 + 0.02, zt + 0.02), knit, bevel=0.015)
    fr = B.mat("knit_fringe", srgb("#6f7074"), 0.95)
    B.tubes("throw_fringe", [((x, y0 - 0.025, 0.19), (x + 0.004, y0 - 0.03, 0.12), 0.004)
                             for x in np.linspace(0.99, 1.56, 22)], fr)
    # bench plant + books on the right end
    book_stack("bench_books", None, 2.92, yb - 0.18, zt, 3, random.Random(2), cols=["#efece5", "#e9b83a", "#5b5e66"],
               rot=-8)
    p = pot("bench_plant", 0.09, 0.07, 0.13, "#e9e5dd", (3.3, yb - 0.08, zt))
    plant("bench_plant", p, 0.11, 20, 0.2, 0.2, 0.12, 0.075, seed=31, droop=0.3)
    # small wooden side table at the right end of the bench
    wood = B.mat("side_wood", srgb("#b38a5e"), 0.5)
    x0, x1, y0t, y1t, ht = 3.7, 4.1, R.BACK_Y - 0.95, R.BACK_Y - 0.55, 0.55
    B.box_minmax("side_top", (x0, y0t, ht - 0.03), (x1, y1t, ht), wood, bevel=0.005)
    B.box_minmax("side_shelf", (x0 + 0.02, y0t + 0.02, 0.12), (x1 - 0.02, y1t - 0.02, 0.14), wood, bevel=0.004)
    for xx in (x0 + 0.01, x1 - 0.04):
        for yy in (y0t + 0.01, y1t - 0.04):
            B.box_minmax(f"side_leg{xx}{yy}", (xx, yy, 0), (xx + 0.03, yy + 0.03, ht - 0.03), wood, bevel=0.003)
    book_stack("side_books", None, (x0 + x1) / 2, (y0t + y1t) / 2, ht, 3, random.Random(6), w=(0.22, 0.26), rot=4)
    book_stack("side_books2", None, (x0 + x1) / 2, (y0t + y1t) / 2, 0.14, 2, random.Random(7), w=(0.2, 0.24), rot=-3)


# ------------------------------------------------------------------ right shelf contents

def retro_console(loc, rot):
    root = B.empty("retro_console", loc, (0, 0, rot))
    y = B.mat("console_yellow", srgb("#e8b52e"), 0.4, spec=0.5, coat=0.4)
    d = B.mat("console_dark", srgb("#1e1f22"), 0.4)
    B.box("console_body", (0.2, 0.12, 0.09), (0, 0, 0.045), material=d, bevel=0.012, parent=root)
    B.box("console_face", (0.17, 0.004, 0.07), (0, -0.061, 0.047), material=y, bevel=0.004, parent=root)
    B.box("console_screen", (0.07, 0.003, 0.045), (-0.03, -0.064, 0.05),
          material=B.mat_emit("console_screen", srgb("#7fd6c4"), 0.6), bevel=0.0, parent=root)
    for k, c in enumerate(("#d8402e", "#2f6fd6")):
        B.cylinder(f"console_btn{k}", 0.008, 0.006, (0.04 + k * 0.025, -0.064, 0.04 + k * 0.012), (90, 0, 0),
                   material=B.mat(f"btn_{c}", srgb(c), 0.3), verts=12, parent=root)


def voxel_robot(loc, rot):
    vs = 0.012
    body = lambda p: sd_box(p, (0, 0, 0.05), (0.04, 0.03, 0.045), 0.006)
    head = lambda p: sd_box(p, (0, 0, 0.125), (0.045, 0.035, 0.032), 0.006)
    ant = lambda p: sd_capsule(p, (0, 0, 0.16), (0, 0, 0.185), 0.006)
    white, grey, teal = srgb("#eeece6"), srgb("#9fa2a8"), srgb("#3fd0c0")
    def col(p):
        c = np.repeat(np.array([white], float), len(p), 0)
        eye = (p[:, 1] < -0.028) & (np.abs(np.abs(p[:, 0]) - 0.018) < 0.008) & (np.abs(p[:, 2] - 0.13) < 0.007)
        c[eye] = teal
        return c
    vox = sample([(ant, grey), (head, col), (body, white)], vs, ((-0.07, -0.06, 0.0), (0.07, 0.06, 0.2)))
    return B.voxel_solid("voxel_robot", vox, vs, loc, B.mat_voxel("vox_fig", rough=0.4, spec=0.5), rot=(0, 0, rot),
                         seed=5, jitter=0.02, bevel=0.25)


def right_shelf_contents():
    B.use_collection("shelf_right")
    x0, x1 = 3.75, 4.75
    yc = R.BACK_Y - 0.26
    tiers = R_SHELF_TIERS
    zt = tiers[-1] + 0.03
    p = pot("rs_plant", 0.1, 0.08, 0.14, "#3f4146", (4.5, yc, zt))
    plant("rs_plant", p, 0.12, 22, 0.24, 0.24, 0.13, 0.08, seed=41, droop=0.3)
    cat_figurine(None, (4.08, yc - 0.06, zt), 15, color="#1c1c1f", name="figure_cat_r")
    z2 = tiers[-2] + 0.03
    retro_console((4.0, yc - 0.04, z2), 6)
    voxel_robot((4.48, yc - 0.04, z2), -10)
    z1 = tiers[1] + 0.03
    box_m = B.mat("cardboard", srgb("#c49a6c"), 0.85)
    B.box("rs_box", (0.4, 0.34, 0.28), (4.35, yc, z1 + 0.14), (0, 0, -4), material=box_m, bevel=0.006)
    B.plane("rs_box_label", 0.26, 0.2, (4.33, yc - 0.172, z1 + 0.15), (0, 0, -4),
            B.mat_image("box_label", "box_label.png", rough=0.85))
    book_stack("rs_books", None, 3.97, yc, z1, 3, random.Random(12), w=(0.2, 0.24), rot=3)
    book_row("rs_row", B.empty("rs_row_root", (0, yc, 0)), x0 + 0.05, x0 + 0.4, tiers[0] + 0.03, 0.3,
             random.Random(13), max_h=0.28)


R_SHELF_TIERS = (0.04, 0.36, 0.68, 0.98)


# ------------------------------------------------------------------ big plant + foreground plant

def big_plant():
    B.use_collection("plants")
    p = square_pot("big_plant", 0.36, 0.44, "#f1eee8", (-1.16, 3.92, 0))
    plant("big_plant", p, 0.42, 30, 0.95, 0.4, 0.22, 0.14, seed=7, droop=0.25, pitch=(-5, 45))


def foreground_plant():
    B.use_collection("plants")
    p = square_pot("fg_plant", 0.32, 0.7, "#55575c", (-0.98, 1.02, 0))
    plant("fg_plant", p, 0.68, 36, 0.36, 0.26, 0.12, 0.1, seed=19, droop=0.3, pitch=(5, 50))


def build_all():
    corkboard()
    left_shelf_contents()
    guitar((-0.98, 5.22, 0.0), -8)
    posters()
    bench_dressing()
    right_shelf_contents()
    big_plant()
    foreground_plant()
