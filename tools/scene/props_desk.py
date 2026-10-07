"""Desk-top objects: journal, microphone, mug, Rubik's cube, product cartridges, books, laptop."""
from __future__ import annotations

import math
import random

import bmesh
import bpy

import blib as B
from blib import srgb

DESK_TOP = 0.76


def journal(parent, loc, rot):
    """Open notebook with two gently curved pages (writing hotspot)."""
    root = B.empty("journal_root", loc, (0, 0, rot), parent=parent, hs="writing")
    cover = B.mat("journal_cover", srgb("#5a4a3a"), 0.6, spec=0.3)
    B.box("journal_cover", (0.46, 0.32, 0.008), (0, 0, 0.004), material=cover, bevel=0.003, parent=root)
    W, H, n = 0.44, 0.3, 24
    verts, faces, uvs = [], [], []
    for j in range(2):
        for i in range(n + 1):
            u = i / n
            x = (u - 0.5) * W
            # pages bulge upward away from the gutter
            z = 0.012 + 0.02 * math.sin(math.pi * (abs(u - 0.5) * 2) ** 0.7) * (1 - abs(u - 0.5) * 1.1)
            z -= 0.012 * max(0, 1 - abs(u - 0.5) * 12)
            y = (j - 0.5) * H
            verts.append((x, y, z))
            uvs.append((u, j))
    for i in range(n):
        faces.append((i, i + 1, n + 2 + i, n + 1 + i))
    pm = B.mat_image("journal_pages", "journal_pages.png", rough=0.85, spec=0.2)
    obj = B._mesh_obj("journal_pages", verts, faces, pm, None, uvs)
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.parent = root
    # page stack thickness under each half
    paper = B.mat("paper_edge", srgb("#ece4d2"), 0.8)
    for sx in (-1, 1):
        B.box(f"journal_stack{sx}", (W / 2 - 0.01, H - 0.006, 0.01), (sx * W / 4, 0, 0.011), material=paper,
              bevel=0.002, parent=root)
    # pencil
    pen = B.mat("pencil", srgb("#2b2b2e"), 0.4, spec=0.5)
    gold = B.mat("brass", srgb("#c49a4a"), 0.3, metal=1.0)
    p = B.empty("pencil", (W / 2 + 0.04, -0.03, 0.005), (0, 0, 72), parent=root)
    B.cylinder("pencil_body", 0.0045, 0.15, (0, 0, 0), (90, 0, 0), material=pen, verts=6, parent=p)
    B.cylinder("pencil_band", 0.0049, 0.012, (0, 0.078, 0), (90, 0, 0), material=gold, verts=12, parent=p)
    B.cylinder("pencil_tip", 0.0045, 0.018, (0, -0.084, 0), (90, 0, 0), material=B.mat("pencil_wood",
               srgb("#d8b98c"), 0.7), verts=6, r_top=0.0008, parent=p)
    return root


def microphone(parent, loc):
    """CrossPod podcast microphone on a short desk stand (podcast hotspot)."""
    root = B.empty("mic_root", loc, (0, 0, 0), parent=parent, hs="podcast")
    root.scale = (1.35,) * 3
    body = B.mat("mic_body", srgb("#1f2023"), 0.35, metal=0.6)
    grille = B.mat_noise("mic_grille", srgb("#18191b"), srgb("#3a3b3f"), scale=900, rough=0.5, spec=0.4)
    teal = B.mat_emit("mic_led", srgb("#3fe0d0"), 6.0)
    B.cylinder("mic_base", 0.058, 0.014, (0, 0, 0.007), material=body, verts=48, bevel=0.004, parent=root)
    B.cylinder("mic_stem", 0.008, 0.07, (0, 0, 0.05), material=body, verts=16, parent=root)
    B.box("mic_yoke", (0.07, 0.014, 0.012), (0, 0, 0.088), material=body, bevel=0.003, parent=root)
    for sx in (-1, 1):
        B.box(f"mic_arm{sx}", (0.008, 0.014, 0.07), (sx * 0.035, 0, 0.12), material=body, bevel=0.002, parent=root)
        B.cylinder(f"mic_knob{sx}", 0.012, 0.012, (sx * 0.043, 0, 0.13), (0, 90, 0), material=body, verts=20,
                   parent=root)
    prof = [(0.0, 0.085), (0.029, 0.088), (0.031, 0.1), (0.031, 0.205), (0.026, 0.222), (0.0, 0.228)]
    B.lathe("mic_capsule", prof, (0, 0, 0.0), material=grille, segs=40, parent=root)
    B.cylinder("mic_ring", 0.0315, 0.016, (0, 0, 0.11), material=body, verts=40, parent=root)
    B.cylinder("mic_led", 0.0318, 0.003, (0, 0, 0.12), material=teal, verts=40, parent=root)
    # small teal pool of light on the desk
    li = bpy.data.lights.new("mic_glow", "POINT")
    li.energy = 1.6
    li.color = (0.35, 0.95, 0.9)
    li.shadow_soft_size = 0.02
    lo = bpy.data.objects.new("mic_glow", li)
    B.link(lo)
    lo.parent = root
    lo.location = (0.07, -0.02, 0.12)
    # cable
    cab = B.cylinder("mic_cable", 0.004, 0.3, (0, 0.15, 0.004), (90, 0, 0), material=body, verts=8, parent=root)
    return root


def mug(parent, loc, rot=0.0):
    root = B.empty("mug_root", loc, (0, 0, rot), parent=parent, hs="podcast")
    m = B.mat_image("mug_print", "mug_print.png", rough=0.35, spec=0.5)
    inner = B.mat("mug_inner", srgb("#1a1a1c"), 0.3)
    coffee = B.mat("coffee", srgb("#3b2416"), 0.15, spec=0.6)
    B.cylinder("coaster", 0.058, 0.006, (0, 0, 0.003), material=B.mat("coaster", srgb("#2e2f33"), 0.7), verts=40,
               parent=root)
    B.lathe("mug_outer", [(0.0398, 0.008), (0.0405, 0.1)], (0, 0, 0), (0, 0, 200), material=m, segs=48,
            parent=root)
    B.lathe("mug_shell", [(0.0, 0.006), (0.036, 0.006), (0.0398, 0.008), (0.0398, 0.008), (0.0405, 0.1),
                          (0.039, 0.102), (0.0365, 0.1), (0.0355, 0.02), (0.0, 0.02)], (0, 0, 0), (0, 0, 0),
            material=inner, segs=48, parent=root)
    B.cylinder("mug_coffee", 0.0357, 0.004, (0, 0, 0.085), material=coffee, verts=32, parent=root)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.026, minor_radius=0.0065, location=(0, 0, 0))
    t = bpy.context.active_object
    for c in t.users_collection:
        c.objects.unlink(t)
    B.link(t)
    t.name = "mug_handle"
    t.data.materials.append(inner)
    t.parent = root
    t.location = (0.043, 0.0, 0.055)
    t.rotation_euler = (math.radians(90), 0, 0)
    t.scale = (0.8, 1.0, 1.0)
    return root


RUBIK = {"U": "#f5f5f0", "D": "#f2c400", "F": "#e8402c", "B": "#ff8a1f", "R": "#2a62d8", "L": "#2aa84a"}


def rubik(parent, loc, rot):
    """3x3x3 Rubik's cube, scrambled (old personal site hotspot)."""
    root = B.empty("rubik_root", loc, (0, 0, rot), parent=parent, hs="rubik")
    s = 0.022
    core = B.mat("rubik_core", srgb("#141416"), 0.35, spec=0.5)
    rng = random.Random(5)
    faces = list(RUBIK.values())
    sticker_mats = {c: B.mat(f"rubik_{c}", srgb(c), 0.25, spec=0.6, coat=0.3) for c in faces}
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for k in (-1, 0, 1):
                B.box(f"rk_{i}{j}{k}", (s * 0.98, s * 0.98, s * 0.98), (i * s, j * s, k * s + 1.5 * s), material=core,
                      bevel=0.0025, parent=root)
                for axis, val, (rx, ry) in ((0, i, (0, 90)), (1, j, (90, 0)), (2, k, (0, 0))):
                    if val == 0:
                        continue
                    c = sticker_mats[rng.choice(faces)]
                    off = [i * s, j * s, k * s + 1.5 * s]
                    off[axis] += val * s * 0.5
                    size = [s * 0.82, s * 0.82, 0.0012]
                    if axis == 0:
                        size = [0.0012, s * 0.82, s * 0.82]
                    elif axis == 1:
                        size = [s * 0.82, 0.0012, s * 0.82]
                    B.box(f"rs_{i}{j}{k}{axis}", size, tuple(off), material=c, bevel=0.0012, segments=1, parent=root)
    return root


def cartridges(parent, loc, rot):
    """Three personal-product cartridges in a row (products hotspot)."""
    root = B.empty("cart_root", loc, (0, 0, rot), parent=parent, hs="products")
    specs = [
        ("muse", srgb("#2c2d31"), "icon_muse.png", srgb("#f2efe6")),
        ("inn", srgb("#34353a"), "icon_inn.png", srgb("#49d6c2")),
        ("stp", srgb("#ece8de"), "icon_stp.png", srgb("#ff8a3d")),
    ]
    for n, (key, col, icon, led) in enumerate(specs):
        x = (n - 1) * 0.078
        c = B.empty(f"cart_{key}", (x, 0, 0), (0, 0, 0), parent=root, hs="products")
        c["product"] = key
        body = B.mat(f"cart_body_{key}", col, 0.42, spec=0.45)
        B.box(f"cart_{key}_body", (0.056, 0.044, 0.088), (0, 0, 0.044), material=body, bevel=0.005, parent=c)
        B.box(f"cart_{key}_cap", (0.05, 0.038, 0.008), (0, 0, 0.09), material=B.mat("cart_cap", srgb("#1f2023"), 0.4),
              bevel=0.002, parent=c)
        B.box(f"cart_{key}_slot", (0.026, 0.006, 0.004), (0, -0.004, 0.0945), material=B.mat_emit(f"cart_led_{key}",
                                                                                                   led, 2.5), bevel=0,
              parent=c)
        icon_m = B.mat_image(f"cart_icon_{key}", icon, rough=0.5, alpha=True)
        B.plane(f"cart_{key}_icon", 0.032, 0.032, (0, -0.0225, 0.046), (0, 0, 0), icon_m, parent=c)
    return root


def books(parent, loc, rot):
    """Stack of four books with spines toward the camera (books hotspot)."""
    root = B.empty("books_root", loc, (0, 0, rot), parent=parent, hs="books")
    specs = [(0.045, srgb("#efede6"), 0), (0.04, srgb("#46484d"), 1), (0.042, srgb("#e9b83a"), 2),
             (0.038, srgb("#f1efe9"), 3)]
    z = 0.0
    pages = B.mat("book_pages", srgb("#efe8d8"), 0.85)
    for n, (t, col, sp) in reversed(list(enumerate(specs))):
        jitter = (n * 7 % 5 - 2) * 0.004
        b = B.empty(f"book{n}", (jitter, 0, z), (0, 0, (n % 2) * 2 - 1), parent=root, hs="books")
        cov = B.mat(f"book_cover{n}", col, 0.55)
        B.box(f"book{n}_cover", (0.25, 0.18, t), (0, 0, t / 2), material=cov, bevel=0.003, parent=b)
        B.box(f"book{n}_pages", (0.242, 0.17, t - 0.006), (0.004, 0.006, t / 2), material=pages, bevel=0.001,
              parent=b)
        sm = B.mat_image(f"spine_{sp}", f"spine_{sp}.png", rough=0.55)
        B.plane(f"book{n}_spine", 0.25, t * 0.94, (0, -0.0905, t / 2), (0, 0, 0), sm, parent=b)
        z += t
    return root


def pen_cup(parent, loc):
    root = B.empty("pencup_root", loc, (0, 0, 0), parent=parent)
    m = B.mat("pencup", srgb("#2c2d31"), 0.45, spec=0.4)
    B.box("pencup", (0.075, 0.075, 0.095), (0, 0, 0.0475), material=m, bevel=0.006, parent=root)
    rng = random.Random(3)
    cols = ["#1c1c1e", "#2f5fd0", "#f2f0ea", "#e8b93a", "#1c1c1e", "#7a7d84"]
    for k, c in enumerate(cols):
        a = k / len(cols) * 2 * math.pi
        h = rng.uniform(0.13, 0.17)
        B.cylinder(f"pen{k}", 0.0045, h, (0.018 * math.cos(a), 0.018 * math.sin(a), 0.04 + h / 2),
                   (rng.uniform(-8, 8), rng.uniform(-8, 8), 0), material=B.mat(f"pen_{c}", srgb(c), 0.4), verts=8,
                   parent=root)
    return root


def laptop(parent, loc, rot):
    root = B.empty("laptop_root", loc, (0, 0, rot), parent=parent)
    al = B.mat("laptop_al", srgb("#3b3c40"), 0.32, metal=0.7)
    B.box("laptop_base", (0.33, 0.23, 0.009), (0, 0, 0.0045), material=al, bevel=0.003, parent=root)
    B.box("laptop_lid", (0.33, 0.23, 0.007), (0, 0, 0.0125), material=al, bevel=0.003, parent=root)
    B.box("laptop_notch", (0.07, 0.006, 0.004), (0, -0.112, 0.008), material=B.mat("laptop_dark", srgb("#18181a"),
                                                                                    0.5), bevel=0, parent=root)
    return root


def sticky(parent, loc, rot, tex="note_sticky_0.png"):
    m = B.mat_image(f"sticky_{tex}", tex, rough=0.85)
    p = B.plane("desk_sticky", 0.07, 0.07, loc, (-90, 0, rot), m, parent=parent)
    return p


def build(desk_root):
    B.use_collection("desk_props")
    z = DESK_TOP
    journal(desk_root, (0.12, 0.35, z), -8)
    microphone(desk_root, (0.1, 0.7, z))
    mug(desk_root, (-0.2, 0.68, z), 0)
    rubik(desk_root, (0.42, 0.15, z), 18)
    cartridges(desk_root, (0.66, 0.3, z), -6)
    pen_cup(desk_root, (-0.42, 0.62, z))
    books(desk_root, (0.36, 0.72, z), -4)
    laptop(desk_root, (-0.5, 0.25, z), 6)
