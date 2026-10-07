"""The street outside the café window.

Everything up to the opposite shopfronts is baked with the room (collection ``street``, tagged as the
window hotspot, at reduced texel density) so it keeps correct parallax while dragging. Only the far
blocks, the skyline and the clouds go into the ``exterior`` collection rendered as the backdrop.
"""
from __future__ import annotations

import math
import random

import numpy as np

import blib as B
import cafe
import exterior as X
from blib import srgb

WALK_Z = -0.04            # pavement top, a step below the café floor
ROAD_Z = -0.18
CURB_NEAR, CURB_FAR = 7.2, 17.0
FACADE_Y = 21.0
X0, X1 = -16.0, 34.0      # baked street extent (the window wedge widens with distance)


def tag(o, texel=0.45):
    o["hs"] = "window"
    o["texel"] = texel
    return o


def paver_mat(name, c1, c2, mortar, w=0.3, h=0.15):
    if name in B._mats:
        return B._mats[name]
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.85
    p.inputs["Specular IOR Level"].default_value = 0.3
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = w
    br.inputs["Row Height"].default_value = h
    br.inputs["Mortar Size"].default_value = 0.006
    br.inputs["Color1"].default_value = (*srgb(c1), 1)
    br.inputs["Color2"].default_value = (*srgb(c2), 1)
    br.inputs["Mortar"].default_value = (*srgb(mortar), 1)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], p.inputs["Base Color"])
    B._mats[name] = m
    return m


# ---------------------------------------------------------------- ground

def build_ground():
    walk = paver_mat("pavers", "#cfc7b8", "#c4bcad", "#a59d90")
    curb = B.mat("curb", srgb("#bdb8ae"), 0.85)
    road = B.mat_noise("asphalt", srgb("#5d6062"), srgb("#55585a"), scale=40, rough=0.9, spec=0.25)
    paint = B.mat("road_paint", srgb("#ecebe6"), 0.7)
    lane = B.mat("bike_lane", srgb("#7a9a6c"), 0.85)
    tag(B.box_minmax("walk_near", (X0, cafe.OUT_Y, -0.3), (X1, CURB_NEAR, WALK_Z), walk, bevel=0), 0.5)
    tag(B.box_minmax("curb_near", (X0, CURB_NEAR, -0.3), (X1, CURB_NEAR + 0.16, WALK_Z + 0.01), curb, bevel=0.01))
    tag(B.box_minmax("road", (X0, CURB_NEAR + 0.16, -0.4), (X1, CURB_FAR, ROAD_Z), road, bevel=0), 0.3)
    tag(B.box_minmax("bike_lane", (X0, CURB_NEAR + 0.2, ROAD_Z), (X1, CURB_NEAR + 1.6, ROAD_Z + 0.004), lane, bevel=0),
        0.3)
    tag(B.box_minmax("lane_edge", (X0, CURB_NEAR + 1.6, ROAD_Z), (X1, CURB_NEAR + 1.72, ROAD_Z + 0.005), paint, bevel=0),
        0.3)
    mid = (CURB_NEAR + CURB_FAR) / 2 + 0.6
    for k, x in enumerate(np.arange(X0 + 1, X1, 6.0)):
        if 6.0 < x < 11.5:
            continue
        tag(B.box_minmax(f"lane_dash{k}", (x, mid - 0.06, ROAD_Z), (x + 3.0, mid + 0.06, ROAD_Z + 0.005), paint,
                         bevel=0), 0.3)
    # zebra crossing to the bakery
    for k, y in enumerate(np.arange(CURB_NEAR + 1.9, CURB_FAR - 0.3, 0.9)):
        tag(B.box_minmax(f"zebra{k}", (6.5, y, ROAD_Z), (10.5, y + 0.45, ROAD_Z + 0.006), paint, bevel=0), 0.3)
    tag(B.box_minmax("curb_far", (X0, CURB_FAR - 0.16, -0.3), (X1, CURB_FAR, WALK_Z + 0.01), curb, bevel=0.01))
    tag(B.box_minmax("walk_far", (X0, CURB_FAR, -0.3), (X1, FACADE_Y + 0.5, WALK_Z), walk, bevel=0), 0.35)


# ---------------------------------------------------------------- street furniture

def bike(name, loc, rot, frame="#2f6d8c"):
    root = B.empty(f"{name}_root", loc, (0, 0, rot))
    tag(root)
    fm = B.mat(f"bike_{frame}", srgb(frame), 0.35, spec=0.5, coat=0.3)
    tyre = B.mat("tyre", srgb("#1d1d1f"), 0.7)
    chrome = B.mat("chrome", srgb("#d9dadc"), 0.12, metal=1.0)
    r = 0.33
    segs = []
    for cx in (-0.52, 0.52):
        ring = [(cx + r * math.cos(2 * math.pi * i / 28), 0, r + r * math.sin(2 * math.pi * i / 28)) for i in range(29)]
        segs += [(a, b, 0.018) for a, b in zip(ring[:-1], ring[1:])]
    B.tubes(f"{name}_tyres", segs, tyre, parent=root, sides=6)
    bb, seat, head = (0.0, 0, 0.3), (-0.12, 0, 0.82), (0.38, 0, 0.86)
    rear, front = (-0.52, 0, r), (0.52, 0, r)
    fr = [(rear, bb, 0.016), (bb, seat, 0.018), (seat, rear, 0.014), (bb, head, 0.02), (seat, head, 0.018),
          (head, front, 0.016), ((0.38, 0, 0.86), (0.36, 0, 0.98), 0.014)]
    B.tubes(f"{name}_frame", fr, fm, parent=root, sides=8)
    B.tubes(f"{name}_bars", [((0.33, -0.24, 1.0), (0.33, 0.24, 1.0), 0.012)], chrome, parent=root)
    B.box(f"{name}_saddle", (0.22, 0.1, 0.05), (-0.14, 0, 0.88), material=tyre, bevel=0.02, parent=root)
    B.box(f"{name}_basket", (0.3, 0.32, 0.2), (0.58, 0, 0.95),
          material=B.mat("wicker", srgb("#b08850"), 0.85), bevel=0.02, parent=root)
    return root


def planter(name, x0, x1, y, seed):
    wood = B.mat("planter_wood", srgb("#7a5a3e"), 0.75)
    tag(B.box_minmax(f"{name}_box", (x0, y, WALK_Z), (x1, y + 0.36, 0.55), wood, bevel=0.01))
    rng = random.Random(seed)
    for k in range(int((x1 - x0) / 0.32)):
        x = x0 + 0.18 + k * 0.32
        root = B.empty(f"{name}_p{k}", (x, y + 0.18, 0.5), (0, 0, rng.uniform(0, 360)))
        tag(root)
        import props_room as P
        cols = rng.choice([["#9a7fc4", "#8a6db8", "#b39bd8"], ["#f2c84b", "#e9a93a"], ["#e86f5a", "#f29c7a"]])
        P.plant(f"{name}_p{k}", root, 0.0, 14, 0.42, 0.18, 0.1, 0.05, seed=seed * 10 + k, droop=0.1,
                pitch=(50, 85), greens=["#4e7a34", "#5f8a3c"] + cols)


def a_board(loc, rot):
    root = B.empty("aboard_root", loc, (0, 0, rot))
    tag(root, 0.8)
    m = B.mat_image("aboard", "now_aboard.png", rough=0.85, spec=0.2)
    wood = B.mat("aboard_wood", srgb("#8a6646"), 0.7)
    for k, s in enumerate((-1, 1)):
        side = B.empty(f"aboard_side{k}", (0, s * 0.18, 0), (s * 12, 0, 0 if s < 0 else 180), parent=root)
        B.box(f"aboard_frame{k}", (0.6, 0.03, 0.95), (0, 0, 0.47), material=wood, bevel=0.006, parent=side)
        B.plane(f"aboard_face{k}", 0.52, 0.78, (0, -0.017, 0.5), (0, 0, 0), m, parent=side)


def street_tree(name, x, y, h, seed):
    rng = random.Random(seed)
    bark = B.mat("bark", srgb("#5b4a3c"), 0.85)
    tag(B.cylinder(f"{name}_trunk", 0.12, h * 0.55, (x, y, WALK_Z + h * 0.275), material=bark, verts=12))
    tag(B.box_minmax(f"{name}_grate", (x - 0.6, y - 0.6, WALK_Z - 0.02), (x + 0.6, y + 0.6, WALK_Z + 0.008),
                     B.mat("grate", srgb("#3a3836"), 0.6, metal=0.5), bevel=0))
    nrng = np.random.default_rng(seed)

    class R:
        random = rng.random
        uniform = rng.uniform
        randint = rng.randint
        choice = rng.choice
        normal = nrng.normal

    b = X.Batch(f"{name}_crown", B.mat_leaf("street_leaf", rough=0.7, translucency=0.25), smooth=True)
    col = np.array(rng.choice(X.LEAF)) * 1.05
    cz = WALK_Z + h * 0.68
    cr = h * 0.3
    for _ in range(16):
        u = nrng.normal(size=3)
        u /= np.linalg.norm(u)
        u[2] *= 0.7
        r = cr * rng.uniform(0.38, 0.55)
        b.blob((x + u[0] * cr * 0.7, y + u[1] * cr * 0.7, cz + u[2] * cr * 0.65), (r, r, r * 0.9),
               col * rng.uniform(0.9, 1.1) * (1 + 0.1 * u[2]), R, sub=3, amp=0.22)
    tag(b.build(), 0.4)


def lamp_post(name, x, y):
    m = B.mat("lamp_green", srgb("#2c3d36"), 0.45, metal=0.4)
    tag(B.cylinder(f"{name}_pole", 0.06, 4.2, (x, y, WALK_Z + 2.1), material=m, verts=12))
    tag(B.cylinder(f"{name}_base", 0.12, 0.5, (x, y, WALK_Z + 0.25), material=m, verts=16))
    tag(B.box(f"{name}_head", (0.3, 0.3, 0.42), (x, y, WALK_Z + 4.4), material=B.mat("lamp_glass", srgb("#efe8d6"), 0.3),
              bevel=0.03))
    tag(B.box(f"{name}_cap", (0.4, 0.4, 0.08), (x, y, WALK_Z + 4.64), material=m, bevel=0.02))


def car(name, x, y, color, rot=0.0):
    root = B.empty(f"{name}_root", (x, y, ROAD_Z), (0, 0, rot))
    tag(root, 0.5)
    body = B.mat(f"car_{color}", srgb(color), 0.3, spec=0.6, coat=0.6)
    glass = B.mat("car_glass", srgb("#2c343c"), 0.15, spec=0.7)
    tyre = B.mat("tyre", srgb("#1d1d1f"), 0.7)
    B.box(f"{name}_body", (3.9, 1.72, 0.7), (0, 0, 0.62), material=body, bevel=0.12, segments=3, parent=root)
    B.box(f"{name}_cabin", (2.1, 1.56, 0.56), (-0.2, 0, 1.2), material=glass, bevel=0.12, segments=3, parent=root)
    B.box(f"{name}_roof", (1.9, 1.5, 0.08), (-0.25, 0, 1.47), material=body, bevel=0.03, parent=root)
    for sx in (-1.3, 1.3):
        for sy in (-0.8, 0.8):
            B.cylinder(f"{name}_wheel{sx}{sy}", 0.32, 0.2, (sx, sy, 0.32), (90, 0, 0), material=tyre, verts=20,
                       parent=root)


def build_furniture():
    planter("planter_a", -0.9, 0.1, cafe.OUT_Y + 0.05, 3)
    planter("planter_b", 2.15, 3.15, cafe.OUT_Y + 0.05, 5)
    bike("bike", (1.0, 5.3, WALK_Z), 4)
    a_board((3.9, 4.6, WALK_Z), -18)
    for k, x in enumerate(np.arange(-6.0, 20.0, 3.2)):
        if 6.0 < x < 11.0:
            continue
        m = B.mat("bollard", srgb("#2c3d36"), 0.5, metal=0.3)
        tag(B.cylinder(f"bollard{k}", 0.07, 0.85, (x, CURB_NEAR - 0.35, WALK_Z + 0.425), material=m, verts=12))
    street_tree("tree_n0", -3.2, CURB_NEAR - 0.9, 6.5, 1)
    street_tree("tree_n1", 13.5, CURB_NEAR - 0.9, 7.0, 2)
    lamp_post("lamp_n", 4.8, CURB_NEAR - 0.4)
    for k, x in enumerate((-10.5, -2.5, 5.0, 12.5, 20.5, 28.0)):
        street_tree(f"tree_f{k}", x, CURB_FAR + 0.9, rng_h(k), 10 + k)
    car("car_a", -5.6, CURB_FAR - 1.15, "#8fb8b4")
    car("car_b", 16.4, CURB_FAR - 1.15, "#efe4cf", 180)
    car("car_c", 25.0, CURB_NEAR + 2.6, "#d36b55", 180)


def rng_h(k):
    return (7.2, 6.4, 7.6, 6.8, 7.4, 6.6)[k]


# ---------------------------------------------------------------- opposite shophouses

FACADES = ["#f1e3cf", "#e8d3c2", "#dfe5dc", "#f3ece2", "#e9c9a8", "#d7dde3", "#efe0d8", "#e4dccd"]
AWNINGS = [("#2f6d5a", "#f2ece0"), ("#b9533f", "#f4ece2"), ("#e1b24a", "#f6f0e4"), ("#3c5f8a", "#f2ede3")]
SIGNS = ["now_sign_bakery.png", "now_sign_books.png", "now_sign_flowers.png", "now_sign_laundry.png"]


def shophouse(k, x0, x1, floors, rng, sign=None):
    y = FACADE_Y
    w = x1 - x0
    wall = B.mat(f"facade{k % len(FACADES)}", srgb(FACADES[k % len(FACADES)]), 0.85, spec=0.25)
    trim = B.mat("facade_trim", srgb("#f6f3ee"), 0.7)
    glass = B.mat("shop_glass", srgb("#2f3a40"), 0.2, spec=0.6)
    inside = B.mat_emit("shop_inside", srgb("#f3d9b0"), 0.9)
    frame = B.mat("shop_frame", srgb("#26302d"), 0.45, metal=0.3)
    g = 3.8
    h = g + floors * 3.2 + 0.5
    tex = 0.75
    tag(B.box_minmax(f"house{k}", (x0, y, WALK_Z - 0.3), (x1, y + 8.0, h), wall, bevel=0), tex)
    tag(B.box_minmax(f"house{k}_cornice", (x0 - 0.05, y - 0.25, h - 0.3), (x1 + 0.05, y, h), trim, bevel=0.02), tex)
    tag(B.box_minmax(f"house{k}_band", (x0, y - 0.12, g - 0.05), (x1, y, g + 0.15), trim, bevel=0.01), tex)
    # ground-floor shop: lit interior behind dark glass, a door and an awning
    sx0, sx1 = x0 + 0.35, x1 - 0.35
    tag(B.box_minmax(f"house{k}_shopin", (sx0, y + 0.6, WALK_Z), (sx1, y + 0.62, g - 0.7), inside, bevel=0), tex)
    tag(B.box_minmax(f"house{k}_counter", (sx0 + 0.4, y + 0.3, WALK_Z), (sx0 + 0.4 + w * 0.35, y + 0.58, 0.95),
                     B.mat("shop_counter", srgb("#8a6a4c"), 0.6), bevel=0.01), tex)
    for j, xx in enumerate(np.linspace(sx0, sx1, max(2, int(w / 1.6)) + 1)):
        tag(B.box_minmax(f"house{k}_mull{j}", (xx - 0.04, y - 0.04, WALK_Z), (xx + 0.04, y + 0.04, g - 0.6), frame,
                         bevel=0), tex)
    tag(B.box_minmax(f"house{k}_sill", (sx0, y - 0.06, WALK_Z), (sx1, y + 0.04, 0.45), frame, bevel=0), tex)
    tag(B.box_minmax(f"house{k}_head", (sx0, y - 0.06, g - 0.75), (sx1, y + 0.04, g - 0.6), frame, bevel=0), tex)
    tag(B.box_minmax(f"house{k}_glass", (sx0, y + 0.02, 0.45), (sx1, y + 0.03, g - 0.75), glass, bevel=0), tex)
    # sign band above the shopfront
    if sign:
        iw, ih = {"now_sign_flowers.png": (900, 320)}.get(sign, (1400, 320))
        sw = min(w * 0.7, 3.4)
        sh = sw * ih / iw
        tag(B.plane(f"house{k}_sign", sw, sh, ((x0 + x1) / 2, y - 0.14, g - 0.3), (0, 0, 0),
                    B.mat_image(f"sign_{sign}", sign, rough=0.6, spec=0.3)), 0.9)
    else:
        tag(B.box_minmax(f"house{k}_signb", (x0 + w * 0.2, y - 0.12, g - 0.5), (x1 - w * 0.2, y, g - 0.12),
                         B.mat(f"signb{k % 3}", srgb(["#2f3a40", "#7a4a36", "#d9cbb4"][k % 3]), 0.6), bevel=0.01), tex)
    a0, a1 = AWNINGS[k % len(AWNINGS)]
    n = max(4, int(w / 0.5))
    for j in range(n):
        xa = sx0 + (sx1 - sx0) * j / n
        xb = sx0 + (sx1 - sx0) * (j + 1) / n
        mat = B.mat(f"awn_{a0 if j % 2 == 0 else a1}", srgb(a0 if j % 2 == 0 else a1), 0.85)
        o = B.box_minmax(f"house{k}_awn{j}", (xa, y - 1.3, g - 0.68), (xb, y, g - 0.6), mat, bevel=0)
        o.rotation_euler.x = math.radians(-18)
        o.location.y += 0.0
        o.location.z -= 0.2
        tag(o, tex)
    # upper floors: tall windows with frames, sills and the odd balcony / flower box
    bays = max(2, int(w / 2.1))
    for fl in range(floors):
        z0 = g + 0.6 + fl * 3.2
        balcony = rng.random() < 0.35
        for j in range(bays):
            xc = x0 + (j + 0.5) * w / bays
            ww, wh = 1.0, 1.75
            tag(B.box_minmax(f"house{k}_w{fl}{j}", (xc - ww / 2, y - 0.02, z0), (xc + ww / 2, y + 0.02, z0 + wh), glass,
                             bevel=0), tex)
            if rng.random() < 0.45:
                tag(B.box_minmax(f"house{k}_cur{fl}{j}", (xc - ww / 2 + 0.05, y - 0.03, z0 + 0.05),
                                 (xc - ww / 2 + 0.05 + ww * rng.uniform(0.3, 0.5), y - 0.025, z0 + wh - 0.1),
                                 B.mat("curtain", srgb("#efe7da"), 0.9), bevel=0), tex)
            tag(B.box_minmax(f"house{k}_wf{fl}{j}", (xc - ww / 2 - 0.1, y - 0.1, z0 - 0.12), (xc + ww / 2 + 0.1, y, z0),
                             trim, bevel=0.01), tex)
            tag(B.box_minmax(f"house{k}_wt{fl}{j}", (xc - ww / 2 - 0.08, y - 0.08, z0 + wh), (xc + ww / 2 + 0.08, y,
                                                                                            z0 + wh + 0.12), trim,
                             bevel=0.01), tex)
            if balcony and j % 2 == 0:
                rail = B.mat("rail_black", srgb("#2a2c2e"), 0.5, metal=0.4)
                tag(B.box_minmax(f"house{k}_bal{fl}{j}", (xc - 0.8, y - 0.7, z0 - 0.2), (xc + 0.8, y, z0 - 0.08), trim,
                                 bevel=0.01), tex)
                tag(B.box_minmax(f"house{k}_balr{fl}{j}", (xc - 0.8, y - 0.72, z0 - 0.08), (xc + 0.8, y - 0.68, z0 + 0.9),
                                 rail, bevel=0), tex)
            elif rng.random() < 0.4:
                tag(B.box_minmax(f"house{k}_fb{fl}{j}", (xc - 0.5, y - 0.3, z0 - 0.1), (xc + 0.5, y, z0 + 0.12),
                                 B.mat("flowerbox", srgb("#c9785e"), 0.8), bevel=0.01), tex)
                tag(B.box_minmax(f"house{k}_fl{fl}{j}", (xc - 0.46, y - 0.28, z0 + 0.12), (xc + 0.46, y - 0.02, z0 + 0.3),
                                 B.mat("flowers_red", srgb("#d8574a"), 0.8), bevel=0.04), tex)


def build_shophouses():
    rng = random.Random(77)
    x = -26.0
    k = 0
    signs = {2: SIGNS[0], 3: SIGNS[2], 4: SIGNS[1], 6: SIGNS[3]}
    while x < 46.0:
        w = rng.uniform(5.5, 8.5)
        if k == 5:
            x += 4.0          # side street
        shophouse(k, x, x + w, rng.choice((1, 2, 2, 3)), rng, signs.get(k))
        x += w
        k += 1


# ---------------------------------------------------------------- backdrop (far)

def build_far():
    B.use_collection("exterior")
    X.GROUND = WALK_Z - 0.2
    X.WIN_Y = FACADE_Y + 10
    X.YAW_MIN, X.YAW_MAX = -45.0, 80.0
    rng = random.Random(5)
    nrng = np.random.default_rng(5)

    class R:
        random = rng.random
        uniform = rng.uniform
        randint = rng.randint
        choice = rng.choice
        normal = nrng.normal

    X.ground(rng)
    near = X.Batch("ext_near", X.vmat("near", rough=0.8, dist=1400))
    # pavement behind the shophouses and down the side street
    near.box(-80, FACADE_Y, X.GROUND - 0.1, 140, X.WIN_Y + 4, X.GROUND + 0.18, srgb("#c9c4b9"))
    glass = X.Batch("ext_glass", X.vmat("glass", rough=0.14, spec=0.6, dist=1400))
    leaves = X.Batch("ext_leaves", X.vmat("leaves", rough=0.92, spec=0.15, dist=1100), smooth=True)
    # the block behind the shophouses and the side street
    houses = []
    for _ in range(600):
        if len(houses) >= 40:
            break
        x, y = X.spot(rng, 38, 160, 6)
        w, d = rng.uniform(12, 22), rng.uniform(10, 16)
        if y < FACADE_Y + 14:
            continue
        if any(abs(x - hx) < (w + hw) / 2 + 2 and abs(y - hy) < (d + hd) / 2 + 2 for hx, hy, hw, hd in houses):
            continue
        houses.append((x, y, w, d))
        X.house(near, glass, R, x, y, w, d, rng.randint(4, 8))
    for _ in range(40):
        x, y = X.spot(rng, 40, 200, 6)
        if any(abs(x - hx) < hw / 2 + 1 and abs(y - hy) < hd / 2 + 1 for hx, hy, hw, hd in houses):
            continue
        X.tree(leaves, R, x, y, rng.uniform(9, 14), spread=1.2, sub=2, lobes=(10, 14), size=(0.34, 0.5))
    sky = X.Batch("ext_skyline", X.vmat("skyline", rough=0.8, dist=1700, hstr=1.0, windows=(4.0, 3.6, 1.6)))
    for _ in range(90):
        x, y = X.spot(rng, 500, 2600, 0)
        X.tower(sky, R, x, y)
    for _ in range(10):
        d = rng.uniform(1600, 2400)
        a = math.radians(rng.uniform(-5, 25))
        X.tower(sky, R, d * math.sin(a), d * math.cos(a), tall=True)
    clouds = X.Batch("ext_clouds", X.vmat("clouds", rough=1.0, spec=0.0, dist=9000, hstr=0.6, glow=0.35), smooth=True)
    for _ in range(12):
        d = rng.uniform(2500, 4500)
        a = math.radians(rng.uniform(-50, 85))
        x, y = d * math.sin(a), d * math.cos(a)
        el = math.radians(rng.uniform(4.0, 14.0))
        X.cloud(clouds, R, x, y, d * math.tan(el), rng.uniform(260, 560))
    for b in (near, glass, leaves, sky, clouds):
        b.build()


def build():
    B.use_collection("street")
    build_ground()
    build_furniture()
    build_shophouses()
    build_far()
