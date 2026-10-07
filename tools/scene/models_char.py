"""Voxel character (MouT) and the two cats (烧酒, 小八)."""
from __future__ import annotations

import math

import numpy as np

import blib as B
from blib import sample, sd_box, sd_capsule, sd_ellipsoid, srgb, xf

SKIN = srgb("#f1c49c")
SKIN_SH = srgb("#e3ab82")
EAR = srgb("#eba987")
NAVY = srgb("#2c2f3d")
NAVY_D = srgb("#1d1f28")
HAIR = [srgb("#121214"), srgb("#1a1a1e"), srgb("#242429")]
PANTS = srgb("#34363c")


def _const(c):
    return lambda pts: np.repeat(np.array([c], float), len(pts), 0)


def _union(*sdfs):
    return lambda p: np.min(np.stack([f(p) for f in sdfs]), axis=0)


# ======================================================================= MouT

HEAD_SCALE = 1.1
TORSO_LEAN = -17.0             # negative X rotation tips the top toward +Y (forward)
HEAD_ROT = (-14.0, 0.0, -4.0)  # look down, straight ahead


# Arm poses per scene, chair space: side -> (elbow, wrist, hand tip, hand size at wrist, at tip, hand up axis, thumb).
# Head, torso and seat never change between scenes; only what the hands are doing does.
ARMS = {
    # right fist propping the chin, left hand resting flat on the desk / keyboard
    "chin": {
        "r": ((0.21, 0.47, 0.8), (0.1, 0.38, 0.85), (0.055, 0.335, 0.945), (0.068, 0.05), (0.07, 0.056), (1, 0, 0),
              None),
        "l": ((-0.25, 0.3, 0.8), (-0.08, 0.45, 0.795), (0.025, 0.52, 0.79), (0.08, 0.03), (0.088, 0.026), (0, 0, 1),
              ((-0.04, 0.47, 0.8), (-0.01, 0.45, 0.79))),
    },
    # both hands on a keyboard straight ahead (keys at chair y ~0.5, z ~0.785)
    "type": {
        "r": ((0.25, 0.3, 0.8), (0.13, 0.46, 0.8), (0.085, 0.54, 0.79), (0.08, 0.03), (0.086, 0.026), (0, 0, 1),
              ((0.09, 0.47, 0.8), (0.06, 0.5, 0.792))),
        "l": ((-0.25, 0.3, 0.8), (-0.13, 0.46, 0.8), (-0.085, 0.54, 0.79), (0.08, 0.03), (0.086, 0.026), (0, 0, 1),
              ((-0.09, 0.47, 0.8), (-0.06, 0.5, 0.792))),
    },
    # both hands around a game pad held in front of the belly (pad centre at chair (0, 0.43, 0.735))
    "pad": {
        "r": ((0.23, 0.22, 0.75), (0.11, 0.38, 0.73), (0.07, 0.44, 0.735), (0.07, 0.035), (0.075, 0.03), (0, 0, 1),
              ((0.075, 0.41, 0.755), (0.045, 0.44, 0.765))),
        "l": ((-0.23, 0.22, 0.75), (-0.11, 0.38, 0.73), (-0.07, 0.44, 0.735), (0.07, 0.035), (0.075, 0.03), (0, 0, 1),
              ((-0.075, 0.41, 0.755), (-0.045, 0.44, 0.765))),
    },
}


def build_character(parent, arms="chin"):
    """Seated character. ``parent`` is the chair-space empty (origin at the seat centre, facing +Y)."""
    B.use_collection("character")
    root = B.empty("me_root", (0, 0, 0), (0, 0, 0), parent=parent, hs="me")
    vm = B.mat_voxel("vox_cloth", rough=0.82, spec=0.25, sheen=0.25)
    vskin = B.mat_voxel("vox_skin", rough=0.55, spec=0.4)
    vhair = B.mat_voxel("vox_hair", rough=0.6, spec=0.22)

    # ---- torso: soft blocky hard-surface (the concept's shirt is smooth, not stepped) ----
    torso_c = (0.0, 0.03, 0.5)
    cloth = B.mat("me_cloth", NAVY, 0.8, spec=0.3, sheen=0.12)
    cloth_d = B.mat("me_cloth_d", NAVY_D, 0.8, spec=0.3, sheen=0.12)
    R = B.rot_matrix((TORSO_LEAN, 0, 0))
    T = lambda v: tuple(np.array(torso_c) + R @ np.array(v))
    B.tbox("me_torso", T((0, 0, 0)), T((0, 0, 0.5)), (0.3, 0.2), (0.36, 0.21), up=(0, -1, 0), material=cloth,
           bevel=0.035, segments=2, parent=root)
    B.tbox("me_collar", T((0, 0.01, 0.48)), T((0, 0.015, 0.535)), (0.16, 0.14), (0.14, 0.12), up=(0, -1, 0),
           material=cloth_d, bevel=0.02, parent=root)
    B.tbox("me_hem", T((0, 0, -0.01)), T((0, 0, 0.04)), (0.305, 0.205), (0.305, 0.205), up=(0, -1, 0),
           material=cloth_d, bevel=0.02, parent=root)
    pm = B.mat_image("shirt_print", "shirt_print.png", rough=0.8, alpha=True, spec=0.2)
    B.plane("me_print", 0.18, 0.18, T((0, -0.1065, 0.405)), (TORSO_LEAN, 0, 0), pm, parent=root)

    # ---- neck + head ---------------------------------------------------------
    neck_base = np.array(torso_c) + R @ np.array([0, 0.01, 0.53])
    head_c = tuple(neck_base + np.array([0.0, 0.085, 0.045]))
    hs = 0.018

    def head_sdf(p):
        upper = sd_box(p, (0, 0.0, 0.012), (0.09, 0.1, 0.09), 0.05)
        jaw = sd_ellipsoid(p, (0, 0.035, -0.05), (0.072, 0.075, 0.06))
        return np.minimum(upper, jaw)

    def head_col(p):
        c = np.repeat(np.array([SKIN], float), len(p), 0)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        eye = (y > 0.06) & (np.abs(np.abs(x) - 0.042) < 0.016) & (np.abs(z - 0.012) < 0.006)
        c[eye] = srgb("#2a211c")
        brow = (y > 0.06) & (np.abs(np.abs(x) - 0.042) < 0.02) & (np.abs(z - 0.04) < 0.005)
        c[brow] = srgb("#3a2a22")
        mouth = (y > 0.08) & (np.abs(x) < 0.02) & (np.abs(z + 0.055) < 0.005)
        c[mouth] = srgb("#c07c66")
        under = z < -0.075
        c[under] = SKIN_SH
        return c

    nose = lambda p: sd_box(p, (0, 0.108, -0.012), (0.011, 0.016, 0.02), 0.004)
    ears = _union(lambda p: sd_box(p, (0.094, -0.008, -0.005), (0.012, 0.024, 0.032), 0.006),
                  lambda p: sd_box(p, (-0.094, -0.008, -0.005), (0.012, 0.024, 0.032), 0.006))
    vox = sample([(nose, SKIN), (ears, EAR), (head_sdf, head_col)], hs, ((-0.12, -0.12, -0.14), (0.12, 0.14, 0.14)))
    head = B.voxel_solid("me_head", vox, hs, head_c, vskin, parent=root, rot=HEAD_ROT, seed=5, jitter=0.012,
                         bevel=0.25)
    head.scale = (HEAD_SCALE,) * 3
    B.tbox("me_neck", tuple(neck_base + np.array([0, -0.01, -0.04])), tuple(np.array(head_c) + np.array([0, -0.02, -0.07])),
           (0.085, 0.08), up=(0, -1, 0), material=B.mat("me_skin", SKIN, 0.55, spec=0.4), bevel=0.025, parent=root)

    # ---- hair -----------------------------------------------------------------
    hz = 0.034

    def hair_sdf(p):
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        cap = sd_box(p, (0, -0.012, 0.02), (0.122, 0.13, 0.11), 0.085)
        shell = np.minimum(cap, head_sdf(p) - 0.03)
        face_cut = (y > 0.02) & (z < 0.055)
        side_cut = (np.abs(x) > 0.05) & (z < 0.005) & (y > -0.075)
        low_cut = z < -0.075
        inner = head_sdf(p) < -0.03
        keep = (shell <= 0) & ~face_cut & ~side_cut & ~low_cut & ~inner
        return np.where(keep, -1.0, 1.0)

    rng = np.random.default_rng(21)

    def hair_col(p):
        idx = rng.integers(0, 3, len(p))
        return np.array(HAIR, float)[idx]

    vox = sample([(hair_sdf, hair_col)], hz, ((-0.16, -0.17, -0.12), (0.16, 0.17, 0.2)))
    # curly protrusions: push some surface voxels outward
    keys = list(vox.keys())
    ks = set(keys)
    for k in keys:
        if rng.random() < 0.38:
            v = np.array(k, float) * hz - np.array([0, -0.012, 0.02])
            n = v / (np.linalg.norm(v) + 1e-6)
            a = int(np.argmax(np.abs(n)))
            step = [0, 0, 0]
            step[a] = int(np.sign(n[a]))
            nk = (k[0] + step[0], k[1] + step[1], k[2] + step[2])
            front_low = nk[1] * hz > 0.0 and nk[2] * hz < 0.06
            if nk not in ks and not front_low and nk[2] * hz > -0.06:
                vox[nk] = HAIR[rng.integers(0, 3)]
    B.voxel_mesh("me_hair", vox, hz, (0, 0, 0), vhair, chamfer=0.12, parent=head, seed=8, jitter=0.09,
                 pos_jitter=0.09, scale_jitter=0.2)

    # ---- glasses (hard surface, follows the head) -----------------------------
    gm = B.mat("glasses", srgb("#111113"), 0.3, spec=0.6)
    gy = 0.118
    for sx in (-1, 1):
        cx = sx * 0.046
        B.box(f"gl_top{sx}", (0.062, 0.01, 0.01), (cx, gy, 0.036), material=gm, bevel=0.002, parent=head)
        B.box(f"gl_bot{sx}", (0.062, 0.01, 0.01), (cx, gy, -0.006), material=gm, bevel=0.002, parent=head)
        B.box(f"gl_in{sx}", (0.01, 0.01, 0.05), (cx - sx * 0.027, gy, 0.015), material=gm, bevel=0.002, parent=head)
        B.box(f"gl_out{sx}", (0.012, 0.012, 0.052), (cx + sx * 0.03, gy - 0.002, 0.015), material=gm, bevel=0.002,
              parent=head)
        B.box(f"gl_arm{sx}", (0.01, 0.13, 0.01), (sx * 0.1, gy - 0.065, 0.03), material=gm, bevel=0.002, parent=head)
    B.box("gl_bridge", (0.03, 0.008, 0.008), (0, gy, 0.03), material=gm, bevel=0.002, parent=head)

    # ---- arms + hands (hard surface) -----------------------------------------
    skin = B.mat("me_skin", SKIN, 0.55, spec=0.4)
    sh_r, sh_l = T((0.205, 0.0, 0.44)), T((-0.205, 0.0, 0.44))
    for side, sh in (("r", sh_r), ("l", sh_l)):
        B.superellipsoid(f"me_shoulder_{side}", (0.13, 0.15, 0.12), sh, (TORSO_LEAN, 0, 0), material=cloth, e=0.55,
                         parent=root)
    for side, (el, wr, tip, w0, w1, up, thumb) in ARMS[arms].items():
        sh = sh_r if side == "r" else sh_l
        B.tbox(f"me_upper_{side}", sh, el, (0.12, 0.12), (0.1, 0.1), up=(0, 0, 1), material=cloth, bevel=0.025,
               parent=root)
        B.superellipsoid(f"me_elbow_{side}", (0.105, 0.105, 0.1), el, material=cloth, e=0.6, parent=root)
        cuff = tuple(np.array(el) * 0.22 + np.array(wr) * 0.78)
        B.tbox(f"me_fore_{side}", el, cuff, (0.098, 0.092), (0.088, 0.084), up=(0, 0, 1), material=cloth,
               bevel=0.03, parent=root)
        B.tbox(f"me_cuff_{side}", cuff, wr, (0.09, 0.086), (0.086, 0.082), up=(0, 0, 1), material=cloth_d,
               bevel=0.025, parent=root)
        B.tbox(f"me_hand_{side}", wr, tip, w0, w1, up=up, material=skin, bevel=0.018 if up[0] else 0.01, parent=root)
        if thumb:
            B.tbox(f"me_thumb_{side}", thumb[0], thumb[1], (0.024, 0.022), up=(0, 0, 1), material=skin, bevel=0.008,
                   parent=root)

    # ---- legs (mostly hidden, needed for shadows) -------------------------------
    pants = B.mat("me_pants", PANTS, 0.8, sheen=0.3)
    for sx in (-1, 1):
        B.tbox(f"me_thigh{sx}", (sx * 0.1, 0.0, 0.56), (sx * 0.12, 0.42, 0.57), (0.14, 0.14), up=(0, 0, 1),
               material=pants, bevel=0.04, parent=root)
        B.tbox(f"me_shin{sx}", (sx * 0.12, 0.42, 0.57), (sx * 0.13, 0.46, 0.06), (0.11, 0.11), up=(0, 1, 0),
               material=pants, bevel=0.03, parent=root)
    return root


# ======================================================================= cats

TABBY = srgb("#7d5c3e")
TABBY_L = srgb("#9c7a52")
TABBY_D = srgb("#2c2017")
WHITE = srgb("#f1eee8")
PINK = srgb("#e6a7a6")
NOSE = srgb("#d9837f")
LID = srgb("#3a2a22")


def _ear_pair(cx, cy, cz, spread, yaw=0.0, tilt=12.0, h=0.05, base=(0.03, 0.016)):
    def f(p):
        out = []
        for sx in (-1, 1):
            q = xf(p, (cx + sx * spread * math.cos(math.radians(yaw)), cy - sx * spread * math.sin(math.radians(yaw)), cz),
                   (0, sx * tilt, yaw))
            out.append(B.sd_pyramid(q, base, h))
        return np.minimum(*out)
    return f


def _bands(pts, tail_pts, freq=60.0):
    """Ring bands along a tail polyline (distance travelled along the curve)."""
    best = np.full(len(pts), 1e9)
    along = np.zeros(len(pts))
    acc = 0.0
    for a, b in zip(tail_pts[:-1], tail_pts[1:]):
        a, b = np.array(a), np.array(b)
        ab = b - a
        L = np.linalg.norm(ab)
        t = np.clip(((pts - a) @ ab) / (L * L), 0, 1)
        d = np.linalg.norm(pts - (a + t[:, None] * ab), axis=1)
        m = d < best
        best[m] = d[m]
        along[m] = acc + t[m] * L
        acc += L
    return np.sin(along * freq) > 0.15


def _tail(pts, r):
    return _union(*[(lambda a, b: (lambda p: sd_capsule(p, a, b, r)))(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])


def _face(c, eye_dx, eye_z, front_y, nose_x):
    """Closed eyes as short dark dashes plus a pink nose on the front of the head."""
    def paint(p, col):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        front = y < front_y
        eye = front & (np.abs(np.abs(x - c) - eye_dx) < 0.018) & (np.abs(z - eye_z) < 0.0076)
        col[eye] = LID
        return col
    return paint


def build_shaojiu(parent, loc, rot_z):
    """烧酒: brown tabby, curled asleep with the head (toward +X) resting on white paws, face to -Y."""
    B.use_collection("cats")
    vs = 0.0145
    hx, hy, hz = 0.155, -0.045, 0.1
    body = _union(lambda p: sd_ellipsoid(p, (-0.03, 0.01, 0.085), (0.17, 0.125, 0.087)),
                  lambda p: sd_ellipsoid(p, (-0.13, 0.02, 0.08), (0.105, 0.115, 0.08)))
    head = lambda p: sd_ellipsoid(p, (hx, hy, hz), (0.088, 0.077, 0.07))
    cheeks = lambda p: sd_ellipsoid(p, (hx, hy - 0.03, hz - 0.022), (0.078, 0.055, 0.05))
    muzzle = lambda p: sd_ellipsoid(p, (hx + 0.003, hy - 0.07, hz - 0.03), (0.036, 0.026, 0.026))
    paws = _union(lambda p: sd_ellipsoid(p, (hx - 0.055, hy - 0.085, 0.022), (0.036, 0.034, 0.024)),
                  lambda p: sd_ellipsoid(p, (hx + 0.04, hy - 0.08, 0.022), (0.034, 0.032, 0.022)))
    tail_pts = [(-0.23, -0.0, 0.035), (-0.2, -0.1, 0.03), (-0.1, -0.15, 0.028), (0.02, -0.155, 0.026)]
    tail = _tail(tail_pts, 0.028)
    ears = _ear_pair(hx, hy + 0.005, hz + 0.05, 0.048, yaw=0, tilt=16, h=0.058, base=(0.032, 0.018))

    def fur(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        ang = np.arctan2(z - 0.0, x + 0.04)
        stripe = np.sin(ang * 7.0 + np.hypot(x + 0.04, z) * 9) > 0.25
        c = np.where(stripe[:, None], np.array(TABBY_D), np.array(TABBY))
        light = (z < 0.07) & ~stripe & (y < -0.05)
        c[light] = TABBY_L
        chest = (x > 0.07) & (y < -0.07) & (z < 0.09)
        c[chest] = WHITE
        return c

    def head_col(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        c = np.repeat(np.array([TABBY], float), len(p), 0)
        st = (np.abs(np.sin((x - hx) * 120)) > 0.75) & (z > hz + 0.035)
        c[st] = TABBY_D
        side = (np.abs(x - hx) > 0.06) & (np.sin(z * 150) > 0.5)
        c[side] = TABBY_D
        return _face(hx, 0.034, hz + 0.005, hy - 0.06, hx)(p, c)

    def ear_col(p):
        c = np.repeat(np.array([TABBY], float), len(p), 0)
        inner = (p[:, 1] < hy - 0.003) & (np.abs(np.abs(p[:, 0] - hx) - 0.048) < 0.016) & (p[:, 2] < hz + 0.095)
        c[inner] = PINK
        return c

    def cheek_col(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        c = np.repeat(np.array([TABBY_L], float), len(p), 0)
        c[(z < hz - 0.03) | ((y < hy - 0.06) & (np.abs(x - hx) < 0.03))] = WHITE
        return _face(hx, 0.034, hz + 0.005, hy - 0.06, hx)(p, c)

    def muzzle_col(p):
        c = np.repeat(np.array([WHITE], float), len(p), 0)
        c[(p[:, 2] > hz - 0.022) & (np.abs(p[:, 0] - hx - 0.003) < 0.009)] = NOSE
        return c

    def tail_col(p):
        return np.where(_bands(p, tail_pts, 70)[:, None], np.array(TABBY_D), np.array(TABBY))

    vox = sample([(muzzle, muzzle_col), (paws, WHITE), (ears, ear_col), (cheeks, cheek_col),
                  (head, head_col), (tail, tail_col), (body, fur)],
                 vs, ((-0.3, -0.22, 0.0), (0.27, 0.16, 0.24)))
    m = B.mat_voxel("vox_fur", rough=0.78, spec=0.3, sheen=0.5)
    return B.voxel_solid("cat_shaojiu", vox, vs, loc, m, parent=parent, hs="cat_shaojiu", rot=(0, 0, rot_z),
                         seed=31, jitter=0.05, bevel=0.22)


BLUE = srgb("#666b75")
BLUE_D = srgb("#4f535c")


def build_xiaoba(parent, loc, rot_z):
    """小八: blue & white British shorthair lying on its side, legs stretched toward -Y, head at +X."""
    B.use_collection("cats")
    vs = 0.0145
    hx, hy, hz = 0.275, -0.06, 0.09
    body = _union(lambda p: sd_ellipsoid(p, (0.0, 0.0, 0.098), (0.235, 0.13, 0.1)),
                  lambda p: sd_ellipsoid(p, (-0.16, 0.0, 0.09), (0.12, 0.13, 0.093)))
    head = lambda p: sd_ellipsoid(p, (hx, hy, hz), (0.092, 0.08, 0.078))
    cheeks = lambda p: sd_ellipsoid(p, (hx, hy - 0.03, hz - 0.025), (0.085, 0.058, 0.052))
    muzzle = lambda p: sd_ellipsoid(p, (hx, hy - 0.072, hz - 0.03), (0.036, 0.026, 0.026))
    fpaws = _union(lambda p: sd_capsule(p, (0.13, -0.08, 0.026), (0.3, -0.16, 0.022), 0.028),
                   lambda p: sd_capsule(p, (0.16, -0.05, 0.026), (0.37, -0.12, 0.022), 0.026))
    hpaws = _union(lambda p: sd_capsule(p, (-0.13, -0.08, 0.03), (-0.02, -0.16, 0.024), 0.03),
                   lambda p: sd_capsule(p, (-0.2, -0.07, 0.03), (-0.11, -0.17, 0.024), 0.028))
    tail_pts = [(-0.28, 0.03, 0.04), (-0.35, -0.04, 0.03), (-0.31, -0.12, 0.026), (-0.22, -0.16, 0.024)]
    tail = _tail(tail_pts, 0.029)
    ears = _ear_pair(hx, hy + 0.01, hz + 0.058, 0.052, yaw=0, tilt=18, h=0.06, base=(0.034, 0.019))

    def fur(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        c = np.repeat(np.array([BLUE], float), len(p), 0)
        stripe = np.sin(x * 34 + z * 10) > 0.3
        c[stripe] = BLUE_D
        c[(z > 0.17) & ~stripe] = BLUE
        belly = (y < -0.07) & (z < 0.09)
        chest = (x > 0.14) & (y < -0.03) & (z < 0.12)
        patch = (x > -0.08) & (x < 0.1) & (y < -0.03) & (z < 0.13)
        c[belly | chest | patch] = WHITE
        return c

    def head_col(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        c = np.repeat(np.array([BLUE], float), len(p), 0)
        blaze = (y < hy - 0.03) & (np.abs(x - hx) < (hz + 0.03 - z) * 0.45) & (z < hz + 0.02)
        c[blaze] = WHITE
        return _face(hx, 0.036, hz + 0.008, hy - 0.06, hx)(p, c)

    def cheek_col(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        c = np.repeat(np.array([WHITE], float), len(p), 0)
        c[(np.abs(x - hx) > 0.055) & (z > hz - 0.02)] = BLUE
        return _face(hx, 0.036, hz + 0.008, hy - 0.06, hx)(p, c)

    def ear_col(p):
        c = np.repeat(np.array([BLUE], float), len(p), 0)
        inner = (p[:, 1] < hy + 0.006) & (np.abs(np.abs(p[:, 0] - hx) - 0.052) < 0.017) & (p[:, 2] < hz + 0.105)
        c[inner] = PINK
        return c

    def muzzle_col(p):
        c = np.repeat(np.array([WHITE], float), len(p), 0)
        c[(p[:, 2] > hz - 0.022) & (np.abs(p[:, 0] - hx) < 0.009)] = NOSE
        return c

    def tail_col(p):
        return np.where(_bands(p, tail_pts, 60)[:, None], np.array(BLUE_D), np.array(BLUE))

    vox = sample([(muzzle, muzzle_col), (fpaws, WHITE), (hpaws, WHITE), (ears, ear_col),
                  (cheeks, cheek_col), (head, head_col), (tail, tail_col), (body, fur)],
                 vs, ((-0.42, -0.22, 0.0), (0.42, 0.16, 0.24)))
    m = B.mat_voxel("vox_fur", rough=0.78, spec=0.3, sheen=0.5)
    o = B.voxel_solid("cat_xiaoba", vox, vs, loc, m, parent=parent, hs="cat_xiaoba", rot=(0, 0, rot_z),
                      seed=41, jitter=0.05, bevel=0.22)
    o.scale = (0.8,) * 3
    return o
