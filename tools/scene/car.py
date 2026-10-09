"""出发: the driver's seat of a white-interior Model Y. The cockpit never changes; the road outside does.

Desk frame (``stage.DESK_ROOT``): +Y is where he looks, through the windscreen. The car is left-hand drive,
so his door (and the side window) is on his left and the centre screen sits mid-car to his right. The
windscreen is open; the curved glass roof behind its header is a tint, not a refraction: in Cycles a
transparent + emissive shell (the ``glass`` collection, never baked), in the web viewer the same
``x * GLASS_T + GLASS_R`` applied to the backdrop where the view ray crosses the roof (src/scene3d/Room3D.ts).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

import blib as B
import stage
from blib import srgb

L_X, R_X = -0.5, 1.2            # inner faces of the front doors
MID_X = (L_X + R_X) / 2         # car centreline
PASS_X = 2 * MID_X              # passenger seat centre (driver at 0)
FLOOR = 0.06
DASH_Y0, DASH_Y1, DASH_Z = 0.62, 1.12, 0.96   # dash face (towards him), windscreen base, dash top
SILL_Z = 0.92                   # door window line
ROOF = 1.5
BAR_Y = -0.3                    # windscreen header, where the A pillars meet the roof rails (about over his head)
B_PILLAR = (-0.62, -0.5)
SCREEN = (MID_X, 0.585, 0.99)   # centre screen, in front of the dash face
WHEEL_C = (0.0, 0.5, 0.88)      # steering wheel centre, chair space
WHEEL_R, WHEEL_TILT = 0.18, 24.0
ROOF_Y0 = -1.8                  # rear end of the glass roof
ROOF_ARCH = 0.06                # the roof's rise at the centreline
GLASS_T = (0.44, 0.48, 0.53)    # glass roof transmittance
GLASS_R = 0.02                  # sky reflected by the glass roof (linear radiance)
SCREEN_TEX = "depart_screen_nagoya.png"   # per destination, set by scene_depart
SCREEN_EMIT = 1.4               # also the web overlay's (Room3D screen panel)

root = None


# ---------------------------------------------------------------- materials

def leather_white():
    return B.mat_noise("car_leather", srgb("#ecebe7"), srgb("#e2e0db"), scale=300, rough=0.55, detail=3, spec=0.35,
                       bump=0.05)


def soft_black():
    return B.mat("car_soft", srgb("#1e1f22"), 0.62, spec=0.3)


def gloss_black():
    return B.mat("car_gloss", srgb("#0f1012"), 0.18, spec=0.6, coat=0.4)


def trim_wood():
    return B.mat_noise("car_wood", srgb("#b99a76"), srgb("#a8885f"), scale=60, rough=0.45, detail=6, spec=0.4)


def carpet():
    return B.mat_noise("car_carpet", srgb("#232427"), srgb("#1b1c1f"), scale=500, rough=0.95, spec=0.1)


def chrome():
    return B.mat("car_chrome", srgb("#b8bcc2"), 0.25, metal=1.0)


def headliner():
    """Black fabric of the pillars, roof rails and header."""
    return B.mat_noise("car_headliner", srgb("#2a2b2f"), srgb("#232428"), scale=420, rough=0.92, detail=3, spec=0.15)


def frit():
    """Black ceramic band printed round the edge of the windscreen."""
    return B.mat("car_frit", srgb("#0c0d0f"), 0.35, spec=0.5)


def mirror_glass(name="car_mirror_glass", col="#6a7b8f"):
    # the bake keeps only diffuse light: a mirror reads as the pale sky it would reflect
    return B.mat(name, srgb(col), 0.3, spec=0.25)


def paint_white():
    return B.mat("car_paint", srgb("#f2f3f5"), 0.25, spec=0.6, coat=0.6)


WS0 = (DASH_Y1 + 0.02, DASH_Z - 0.02)   # windscreen bottom edge (y, z)
WS1 = (BAR_Y + 0.04, ROOF - 0.02)       # windscreen top edge


WS_N = (0.0, 0.36, 0.93)                 # windscreen normal, pointing out and up


def ws_y(z):
    """Where the windscreen glass is at height z."""
    return WS0[0] + (z - WS0[1]) / (WS1[1] - WS0[1]) * (WS1[0] - WS0[0])


# ---------------------------------------------------------------- shell

def build_cabin():
    B.use_collection("cabin")
    r = root
    soft, wood, white = soft_black(), trim_wood(), leather_white()
    B.box_minmax("floor", (L_X - 0.05, -1.6, FLOOR - 0.04), (R_X + 0.05, DASH_Y1, FLOOR), carpet(), bevel=0, parent=r)
    # dashboard: one long slab, a full-width vent slot and the wood strip under it
    B.box_minmax("dash_top", (L_X - 0.02, DASH_Y0, DASH_Z - 0.06), (R_X + 0.02, DASH_Y1 + 0.05, DASH_Z), soft,
                 bevel=0.02, parent=r)
    B.box_minmax("dash_face", (L_X - 0.02, DASH_Y0 + 0.02, 0.62), (R_X + 0.02, DASH_Y0 + 0.14, DASH_Z - 0.05), soft,
                 bevel=0.02, parent=r)
    B.box_minmax("dash_vent", (L_X + 0.02, DASH_Y0 - 0.003, DASH_Z - 0.085), (R_X - 0.02, DASH_Y0 + 0.03, DASH_Z - 0.065),
                 gloss_black(), bevel=0.002, parent=r)
    B.box_minmax("dash_wood", (L_X, DASH_Y0 - 0.006, DASH_Z - 0.15), (R_X, DASH_Y0 + 0.03, DASH_Z - 0.1), wood,
                 bevel=0.004, parent=r)
    B.box_minmax("dash_lower", (L_X, DASH_Y0 + 0.06, FLOOR), (R_X, DASH_Y1, 0.64), soft, bevel=0.02, parent=r)
    # doors: white upper trim, wood strip, black lower panel, armrest
    for side, x0, x1 in (("l", L_X - 0.08, L_X), ("r", R_X, R_X + 0.08)):
        sx = -1 if side == "l" else 1
        inner = x1 if side == "l" else x0
        B.box_minmax(f"door_{side}", (x0, -1.4, FLOOR), (x1, DASH_Y0 + 0.1, SILL_Z - 0.04), soft, bevel=0.01, parent=r)
        B.box_minmax(f"door_{side}_top", (min(x0, inner - sx * 0.05), -1.4, SILL_Z - 0.06),
                     (max(x1, inner - sx * 0.05), DASH_Y0 + 0.1, SILL_Z), white, bevel=0.012, parent=r)
        B.box_minmax(f"door_{side}_wood", (inner - 0.006, -0.55, SILL_Z - 0.1), (inner + 0.006, DASH_Y0 + 0.08, SILL_Z - 0.07),
                     wood, bevel=0.002, parent=r)
        B.box_minmax(f"door_{side}_arm", (min(inner, inner - sx * 0.09), -0.45, 0.6), (max(inner, inner - sx * 0.09), 0.3, 0.66),
                     white, bevel=0.015, parent=r)
        B.cylinder(f"door_{side}_speaker", 0.07, 0.01, (inner - sx * 0.004, 0.25, 0.28), (0, 90, 0), material=gloss_black(),
                   verts=24, parent=r)
        hl = headliner()
        # B pillar and roof rail: wide, soft headliner trim rather than bare bars
        B.box_minmax(f"bpillar_{side}", (min(x0, inner - sx * 0.05), B_PILLAR[0] - 0.04, SILL_Z - 0.02),
                     (max(x1, inner - sx * 0.05), B_PILLAR[1] + 0.02, ROOF), hl, bevel=0.03, segments=4, parent=r)
        B.box_minmax(f"rail_{side}", (min(x0, inner - sx * 0.08), -1.8, ROOF - 0.075),
                     (max(x1, inner - sx * 0.08), BAR_Y + 0.06, ROOF + 0.02), hl, bevel=0.035, segments=4, parent=r)
        # A pillar: a broad trim panel tapering from the dash corner up to the roof, the windscreen's black
        # frit band along its inner edge
        n = Vector(WS_N)
        a = Vector((inner + sx * 0.02, WS0[0], WS0[1])) - n * 0.05
        b = Vector((inner + sx * 0.01, WS1[0] + 0.03, WS1[1])) - n * 0.035
        tbox(f"apillar_{side}", a, b, (0.13, 0.13), (0.1, 0.09), up=WS_N, material=hl, bevel=0.035, segments=5,
               parent=r)
        fa = Vector((inner - sx * 0.05, WS0[0] - 0.01, WS0[1])) - n * 0.004
        fb = Vector((inner - sx * 0.045, WS1[0] + 0.02, WS1[1])) - n * 0.004
        tbox(f"frit_{side}", tuple(fa), tuple(fb), (0.05, 0.003), (0.04, 0.003), up=WS_N, material=frit(), bevel=0.0,
               parent=r)
        B.superellipsoid(f"dash_corner_{side}", (0.17, 0.2, 0.06), (inner - sx * 0.02, WS0[0] - 0.08, DASH_Z + 0.005),
                         material=soft, e=0.35, parent=r)
        build_door_mirror(side, inner, sx)
    # white bonnet beyond the windscreen, falling away towards the nose
    paint = paint_white()
    tbox("bonnet", (MID_X, DASH_Y1 + 0.02, DASH_Z - 0.04), (MID_X, DASH_Y1 + 1.3, DASH_Z - 0.26),
           (R_X - L_X + 0.12, 0.08), (R_X - L_X - 0.1, 0.08), up=(0, 0, 1), material=paint, bevel=0.06, parent=r)
    B.box_minmax("cowl", (L_X - 0.02, DASH_Y1 - 0.02, DASH_Z - 0.05), (R_X + 0.02, DASH_Y1 + 0.1, DASH_Z - 0.01),
                 gloss_black(), bevel=0.01, parent=r)
    # frit along the bottom of the windscreen, and the thin ambient light under the wood strip
    fy, fz = WS0[0] - 0.03 * 0.93, WS0[1] + 0.03 * 0.36 + 0.004
    tbox("frit_bottom", (L_X - 0.02, fy, fz), (R_X + 0.02, fy, fz), (0.06, 0.003), up=WS_N, material=frit(), bevel=0.0,
           parent=r)
    B.box_minmax("dash_light", (L_X + 0.02, DASH_Y0 - 0.008, DASH_Z - 0.157), (R_X - 0.02, DASH_Y0 + 0.02, DASH_Z - 0.151),
                 B.mat("car_ambient", srgb("#ffd9a0"), 0.5, emission=srgb("#ffd9a0"), estr=2.5), bevel=0.0, parent=r)
    # centre console between the seats
    gl = gloss_black()
    B.box_minmax("console", (MID_X - 0.14, -0.75, FLOOR), (MID_X + 0.14, DASH_Y0 + 0.06, 0.56), soft, bevel=0.02, parent=r)
    B.box_minmax("console_top", (MID_X - 0.13, -0.2, 0.555), (MID_X + 0.13, DASH_Y0 + 0.04, 0.575), gl, bevel=0.01,
                 parent=r)
    B.box_minmax("console_arm", (MID_X - 0.14, -0.75, 0.56), (MID_X + 0.14, -0.22, 0.64), white, bevel=0.03, parent=r)
    for k, y in enumerate((0.02, 0.14)):
        B.cylinder(f"cupholder{k}", 0.04, 0.02, (MID_X, y, 0.568), material=B.mat("car_hole", srgb("#08090a"), 0.6),
                   verts=24, parent=r)
    for k, dx in enumerate((-0.055, 0.055)):
        B.box(f"phone{k}", (0.075, 0.155, 0.009), (MID_X + dx, 0.42, 0.582), (0, 0, 0), material=gl, bevel=0.006, parent=r)


def build_door_mirror(side, inner, sx):
    """Model Y door mirror: white housing on a black sail at the window's front corner, glass facing him."""
    r = root
    base = B.empty(f"door_mirror_{side}", (inner + sx * 0.1, DASH_Y0 + 0.16, SILL_Z + 0.05), (0, 0, -sx * 14), parent=r)
    tbox(f"mirror_sail_{side}", (-sx * 0.1, 0.02, -0.03), (sx * 0.0, 0.03, 0.02), (0.07, 0.02), (0.04, 0.02),
           up=(0, 1, 0), material=gloss_black(), bevel=0.006, parent=base)
    B.superellipsoid(f"mirror_house_{side}", (0.2, 0.1, 0.12), (sx * 0.1, 0.05, 0.05), (0, 0, 0), material=paint_white(),
                     e=0.55, parent=base)
    B.superellipsoid(f"mirror_rim_{side}", (0.185, 0.02, 0.105), (sx * 0.1, 0.0, 0.05), material=gloss_black(), e=0.4,
                     parent=base)
    B.superellipsoid(f"mirror_glass_{side}", (0.17, 0.01, 0.092), (sx * 0.1, -0.008, 0.05), material=mirror_glass(),
                     e=0.4, parent=base)


def outward(obj):
    """Point a closed solid's faces out: the bake culls whatever faces away from every camera."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def tbox(*a, **k):
    return outward(B.tbox(*a, **k))


def extrude(*a, **k):
    return outward(B.extrude(*a, **k))


def sweep(name, pts, size, up=(0, 0, 1), material=None, bevel=0.012, parent=None, hs=None):
    """One continuous rounded bar along a polyline (a tbox per segment shows its seams)."""
    pts = [Vector(p) for p in pts]
    w, d = size
    v = []
    for i, c in enumerate(pts):
        ax = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        xv = ax.cross(Vector(up)).normalized()
        yv = xv.cross(ax).normalized()
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v.append(tuple(c + xv * (sx * w / 2) + yv * (sy * d / 2)))
    n = len(pts)
    f = [(0, 3, 2, 1), (4 * (n - 1), 4 * (n - 1) + 1, 4 * (n - 1) + 2, 4 * (n - 1) + 3)]
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)
        f += [(a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k) for k in range(4)]
    obj = outward(B._mesh_obj(name, v, f, material, hs))
    if bevel > 0:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 4
        m.limit_method = "ANGLE"
        m.use_clamp_overlap = True
        m.harden_normals = True
    obj.data.shade_smooth()
    if parent is not None:
        obj.parent = parent
    return obj


def roof_z(x):
    """Height of the glass roof across the car (arched, the rails at ROOF)."""
    t = (x - MID_X) / ((R_X - L_X) / 2 + 0.06)
    return ROOF + ROOF_ARCH * (1 - t * t)


def mat_glass():
    m = bpy.data.materials.new("car_glass")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*GLASS_T, 1)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    em.inputs["Strength"].default_value = GLASS_R
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def build_roof():
    """Curved glass roof from the windscreen header back, with the black header, B-pillar bow and mirror."""
    B.use_collection("glass")
    nx, ny = 24, 6
    x0, x1 = L_X - 0.06, R_X + 0.06
    verts, faces = [], []
    for j in range(ny + 1):
        y = ROOF_Y0 + (BAR_Y - ROOF_Y0) * j / ny
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            verts.append((x, y, roof_z(x)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    g = B._mesh_obj("roof_glass", verts, faces, mat_glass())
    g.parent = root
    B.use_collection("cabin")
    soft = soft_black()
    # thin black bands following the arch: the windscreen header and the bow over the B pillars
    n = 10
    hl = headliner()
    xs = [x0 + (x1 - x0) * k / 24 for k in range(25)]
    # both cameras sit just behind the bow, so it stays slim or it hides the whole glass roof
    for name, y0, y1, th in (("roof_header", BAR_Y - 0.04, BAR_Y + 0.06, 0.035),
                             ("roof_bow", B_PILLAR[0] + 0.035, B_PILLAR[1] - 0.025, 0.025)):
        sweep(name, [(x, (y0 + y1) / 2, roof_z(x) - 0.012 - th / 2) for x in xs], (y1 - y0, th), material=hl,
              bevel=0.012, parent=root)
    # frit band on the glass just ahead of the header, following its arch
    sweep("frit_top", [(x, BAR_Y + 0.1, roof_z(x) - 0.058) for x in xs], (0.08, 0.003), up=WS_N, material=frit(),
          bevel=0.0, parent=root)
    build_rear_mirror()


def build_rear_mirror():
    """Rear-view mirror glued high on the windscreen ahead of him, hanging from the camera housing in its frit
    patch. High enough to clear the screen from the phone camera."""
    gz = ROOF - 0.075
    slope = math.degrees(math.atan2(WS1[1] - WS0[1], WS0[0] - WS1[0]))
    lo = Vector((MID_X, ws_y(gz - 0.02), gz - 0.02))
    hi = Vector((MID_X, ws_y(WS1[1]), WS1[1])) + Vector((0, 0.02, 0))
    n = Vector(WS_N)
    tbox("frit_patch", tuple(lo - n * 0.002), tuple(hi - n * 0.002), (0.07, 0.003), (0.11, 0.003), up=WS_N,
           material=frit(), bevel=0.0, parent=root)
    hc = Vector((MID_X, ws_y(gz), gz)) - n * 0.02
    B.superellipsoid("camera_housing", (0.065, 0.06, 0.035), tuple(hc), (slope, 0, 0), material=gloss_black(), e=0.4,
                     parent=root)
    m = B.empty("rear_mirror", (MID_X, hc.y + 0.01, hc.z - 0.056), (-4, 0, 9), parent=root)
    tbox("mirror_stem", (0, 0.01, 0.02), (0, 0.0, 0.046), (0.022, 0.018), up=(0, 1, 0), material=gloss_black(),
           bevel=0.006, parent=m)
    B.superellipsoid("mirror_body", (0.25, 0.032, 0.066), (0, 0.004, 0), material=gloss_black(), e=0.28, parent=m)
    B.superellipsoid("mirror_face", (0.24, 0.004, 0.058), (0, -0.0125, 0), material=mirror_glass("car_mirror_rear", "#56616e"),
                     e=0.28, parent=m)


def build_screen():
    B.use_collection("cabin")
    sc = B.empty("screen_root", SCREEN, (0, 0, 0), parent=root, hs="nav")
    w, h = 0.46, 0.2875
    tilt = -10
    B.box("screen_bezel", (w + 0.014, 0.022, h + 0.014), (0, 0.012, 0), (tilt, 0, 0), material=gloss_black(), bevel=0.006,
          parent=sc)
    B.plane("screen_face", w, h, (0, -0.0005, 0), (tilt, 0, 0), material=B.mat_image(
        "car_screen", SCREEN_TEX, rough=0.2, emission=SCREEN_EMIT, spec=0.6), parent=sc)
    # it grows out of the seam between the dash and the wood strip rather than standing on the dash
    B.box_minmax("screen_stalk", (-0.06, 0.015, -h / 2 + 0.01), (0.06, 0.09, -h / 2 + 0.07), soft_black(), bevel=0.01,
                 parent=sc)


def build_wheel(chair):
    B.use_collection("cabin")
    cx, cy, cz = WHEEL_C
    t = math.radians(WHEEL_TILT)
    up = Vector((0, math.sin(t), math.cos(t)))   # the rim's top leans away from him
    rt = Vector((1, 0, 0))
    nrm = rt.cross(up)                           # wheel face, towards his chest
    c = Vector(WHEEL_C)
    leather = B.mat("car_wheel", srgb("#18191b"), 0.5, spec=0.35)
    ring = [(WHEEL_R + 0.017 * math.cos(2 * math.pi * k / 16), 0.021 * math.sin(2 * math.pi * k / 16)) for k in range(17)]
    B.lathe("wheel_rim", ring, WHEEL_C, (90 - WHEEL_TILT, 0, 0), material=leather, segs=72, parent=chair)
    hub = c - nrm * 0.01
    for k, a in enumerate((0.0, math.pi, -math.pi / 2)):
        p = c + 0.17 * (math.cos(a) * rt + math.sin(a) * up)
        tbox(f"wheel_spoke{k}", tuple(hub), tuple(p), (0.05 if k < 2 else 0.04, 0.02), up=tuple(nrm), material=leather,
               bevel=0.008, parent=chair)
    B.superellipsoid("wheel_hub", (0.135, 0.05, 0.105), tuple(hub), (-WHEEL_TILT, 0, 0), material=leather, e=0.42,
                     parent=chair)
    tesla_t(chair, hub + nrm * 0.026 + up * 0.008, 0.052)
    for sx in (-1, 1):
        B.cylinder(f"wheel_scroll{sx}", 0.012, 0.012, tuple(c + rt * sx * 0.085 + nrm * 0.012), (90 - WHEEL_TILT, 0, 0),
                   material=chrome(), verts=16, parent=chair)
    col_end = Vector((cx, DASH_Y0 - (-0.17) + 0.02, cz - 0.08))
    tbox("wheel_column", tuple(hub - nrm * 0.03), tuple(col_end), (0.07, 0.07), (0.09, 0.09), up=(0, 0, 1),
           material=soft_black(), bevel=0.02, parent=chair)
    B.box("wheel_stalk", (0.12, 0.012, 0.012), (cx + 0.1, cy + 0.06, cz - 0.02), (0, 0, -8), material=soft_black(),
          bevel=0.004, parent=chair)


def tesla_t(parent, at, size):
    """The Tesla T in silver on the wheel hub, facing him: the arched bar over a stem tapering to a point."""
    s = size
    bar = [(-0.5, 0.38), (-0.3, 0.47), (0.0, 0.5), (0.3, 0.47), (0.5, 0.38),
           (0.46, 0.3), (0.3, 0.37), (0.0, 0.4), (-0.3, 0.37), (-0.46, 0.3)]
    stem = [(-0.24, 0.31), (-0.09, 0.25), (-0.055, -0.5), (0.0, -0.6), (0.055, -0.5), (0.09, 0.25), (0.24, 0.31),
            (0.0, 0.355)]
    silver = B.mat("tesla_t", srgb("#e4e6e9"), 0.3, spec=0.8)
    for name, pts in (("bar", bar), ("stem", stem)):
        extrude(f"wheel_t_{name}", [(x * s, z * s) for x, z in pts][::-1], 0.004, tuple(at), (-WHEEL_TILT, 0, 0),
                  material=silver, parent=parent)


def build_seat(chair, name):
    white = leather_white()
    B.superellipsoid(f"{name}_cushion", (0.52, 0.52, 0.12), (0, 0.0, 0.42), material=white, e=0.3, parent=chair)
    B.superellipsoid(f"{name}_base", (0.5, 0.5, 0.26), (0, -0.02, 0.22), material=soft_black(), e=0.2, parent=chair)
    B.superellipsoid(f"{name}_back", (0.52, 0.14, 0.42), (0, -0.26, 0.68), (-4, 0, 0), material=white, e=0.3, parent=chair)
    for sx in (-1, 1):
        B.superellipsoid(f"{name}_bolster{sx}", (0.08, 0.13, 0.34), (sx * 0.25, -0.22, 0.64), (-4, 0, 0), material=white,
                         e=0.4, parent=chair)
        B.superellipsoid(f"{name}_cush_bolster{sx}", (0.08, 0.46, 0.1), (sx * 0.25, 0.0, 0.47), material=white, e=0.4,
                         parent=chair)


# ---------------------------------------------------------------- props

def build_props():
    """Everything he brought is on the passenger side of the dash, where the camera sees it: the paddle and ball
    on top, the Asian Games and cinema tickets tucked into the vent, the passport with its boarding passes."""
    B.use_collection("props")
    z = DASH_Z + 0.001
    pp = B.empty("pingpong_root", (MID_X + 0.34, DASH_Y0 + 0.11, z), (0, 0, 28), parent=root, hs="pingpong")
    B.cylinder("paddle_red", 0.075, 0.006, (0, 0, 0.012), material=B.mat("paddle_red", srgb("#c8262c"), 0.55, spec=0.3),
               verts=40, parent=pp)
    B.cylinder("paddle_black", 0.075, 0.006, (0, 0, 0.006), material=B.mat("paddle_black", srgb("#141416"), 0.6),
               verts=40, parent=pp)
    B.box("paddle_handle", (0.03, 0.1, 0.022), (0, -0.115, 0.011), material=trim_wood(), bevel=0.006, parent=pp)
    B.superellipsoid("ball", (0.04, 0.04, 0.04), (0.1, 0.05, 0.02), material=B.mat("ball", srgb("#ff8a3d"), 0.4), e=1.0,
                     parent=pp)
    # the two tickets tucked into the dash-wide vent slot, hanging over the wood towards him
    vz = DASH_Z - 0.065
    gt = B.empty("games_ticket_root", (MID_X + 0.34, DASH_Y0 - 0.014, vz), (0, 0, -4), parent=root, hs="pingpong")
    B.plane("ticket_games", 0.15, 0.067, (0, 0, -0.03), (-5, 3, 0),
            material=B.mat_image("ticket_games", "depart_ticket_games.png", rough=0.5), parent=gt)
    ct = B.empty("cinema_root", (MID_X + 0.5, DASH_Y0 - 0.014, vz), (0, 0, 5), parent=root, hs="cinema")
    for k, (dx, dz, ry) in enumerate(((0.0, -0.03, -4), (0.025, -0.036, 5))):
        B.plane(f"ticket_cinema{k}", 0.13, 0.061, (dx, -0.002 - 0.002 * k, dz), (-4, ry, 0),
                material=B.mat_image("ticket_cinema", "depart_ticket_cinema.png", rough=0.55), parent=ct)
    pa = B.empty("passport_root", (R_X - 0.12, DASH_Y0 + 0.11, z), (0, 0, -14), parent=root, hs="passport")
    B.box("passport_body", (0.09, 0.125, 0.011), (0, 0, 0.0055), material=B.mat("passport_edge", srgb("#2c3550"), 0.6),
          bevel=0.002, parent=pa)
    B.plane("passport", 0.088, 0.123, (0, 0, 0.0112), (-90, 0, 0),
            material=B.mat_image("passport", "depart_passport.png", rough=0.6), parent=pa)
    for k, (dx, dy, rz) in enumerate(((0.03, 0.06, -18), (0.045, 0.045, 8))):
        B.plane(f"boarding{k}", 0.15, 0.06, (dx, dy, 0.013 + k * 0.001), (-90, 0, rz),
                material=B.mat_image("boarding", "depart_boarding.png", rough=0.5), parent=pa)


# ---------------------------------------------------------------- lights

def build_lights(sun_dir, sun_strength=4.0, sun_col=(1.0, 0.93, 0.84)):
    B.use_collection("lights")
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = sun_strength
    sun.angle = math.radians(1.5)
    sun.color = sun_col
    so = bpy.data.objects.new("sun", sun)
    B.link(so)
    so.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 25
    fill.size = 1.0
    fill.color = (1.0, 0.96, 0.92)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.parent = root
    f.location = (PASS_X, -1.2, 1.4)
    f.rotation_euler = (Vector((0.0, 0.5, 0.8)) - Vector(f.location)).to_track_quat("-Z", "Y").to_euler()


def build_all():
    global root
    import models_char as C
    root = stage.desk_frame("car_root")
    build_cabin()
    build_roof()
    build_screen()
    B.use_collection("chair")
    chair = stage.chair_frame(root)
    build_seat(chair, "seat_d")
    passenger = B.empty("passenger_root", (PASS_X, stage.CHAIR[0][1], 0), (0, 0, 0), parent=root)
    build_seat(passenger, "seat_p")
    build_wheel(chair)
    C.build_character(chair, arms="wheel")
    build_props()
    # the two cats as little dash figures on the passenger side, behind his things (the seat is hidden from the
    # desktop camera by its backrest)
    B.use_collection("cats")
    C.build_shaojiu(root, (MID_X + 0.36, DASH_Y0 + 0.26, DASH_Z), 20).scale = (0.42,) * 3
    C.build_xiaoba(root, (R_X - 0.16, DASH_Y0 + 0.27, DASH_Z), -15).scale = (0.4,) * 3
    return root
