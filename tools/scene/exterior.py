"""Neighbourhood seen through the back window.

Tree crowns reach the sill, white low-rise blocks sit between them, a mid-rise belt climbs a gentle
slope toward a hazy skyline, cumulus clouds hang above it. Everything is batched into a handful of
meshes with a per-vertex colour (``vcol``) so the scene stays cheap to build and render.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import blib as B
from blib import srgb

GROUND = -14.0           # street level; the room looks over the roofs from the fifth storey
WIN_Y = 5.92             # outer face of the back wall
CAM = np.array([0.0, 0.0, 1.42])
# The window spans roughly -5..+40 degrees of yaw from the camera once the orbit is included.
YAW_MIN, YAW_MAX = -12.0, 48.0
# Light for the backdrop render only: front-right and higher than the interior sun so the facades
# facing the room catch warm light.
SUN_DIR = Vector((0.62, -0.42, 0.66)).normalized()
SUN_STRENGTH = 5.5
AMB = 0.55
HAZE = srgb("#cfdbe6")


# ---------------------------------------------------------------- terrain

def terrain(x, y):
    """Ground height: flat streets near the house, a long rise toward the skyline."""
    d = np.maximum(np.asarray(y, dtype=np.float64) - WIN_Y, 0.0)
    x = np.asarray(x, dtype=np.float64)
    rise = 30.0 * (1.0 - np.exp(-np.maximum(d - 150.0, 0.0) / 900.0))
    roll = 2.5 * np.sin(x / 140.0 + 0.7) * np.sin(d / 210.0) * np.clip((d - 150.0) / 200.0, 0, 1)
    return GROUND + rise + roll


def in_view(x, y, margin=0.0):
    a = math.degrees(math.atan2(x - CAM[0], y - CAM[1]))
    return YAW_MIN - margin <= a <= YAW_MAX + margin


def spot(rng, d0, d1, margin=0.0):
    """Random ground point at distance d0..d1 from the camera inside the visible wedge."""
    d = d0 + (d1 - d0) * math.sqrt(rng.random())
    a = math.radians(rng.uniform(YAW_MIN - margin, YAW_MAX + margin))
    return CAM[0] + d * math.sin(a), CAM[1] + d * math.cos(a)


# ---------------------------------------------------------------- batched geometry

_ICO: dict[int, tuple[np.ndarray, np.ndarray]] = {}


def ico(sub):
    if sub not in _ICO:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        v = np.array([p.co[:] for p in bm.verts], np.float64)
        f = np.array([[p.index for p in face.verts] for face in bm.faces], np.int64)
        bm.free()
        _ICO[sub] = (v, f)
    return _ICO[sub]


_BOX_V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], np.float64)
_BOX_F = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]], np.int64)


class Batch:
    def __init__(self, name, material, smooth=False):
        self.name, self.material, self.smooth = name, material, smooth
        self.verts: list[np.ndarray] = []
        self.faces: list[np.ndarray] = []   # 2D arrays, one per face size
        self.cols: list[np.ndarray] = []
        self.n = 0

    def add(self, v, f, col):
        v = np.asarray(v, np.float64)
        col = np.asarray(col, np.float64)
        if col.ndim == 1:
            col = np.repeat(col[None, :3], len(v), 0)
        if isinstance(f, np.ndarray) and f.ndim == 2:
            groups = [f]
        else:
            by: dict[int, list] = {}
            for x in f:
                by.setdefault(len(x), []).append(x)
            groups = [np.asarray(g, np.int64) for g in by.values()]
        self.verts.append(v)
        self.faces += [g + self.n for g in groups]
        self.cols.append(col[:, :3])
        self.n += len(v)

    def box(self, x0, y0, z0, x1, y1, z1, col):
        lo, hi = np.array([x0, y0, z0]), np.array([x1, y1, z1])
        self.add(lo + _BOX_V * (hi - lo), _BOX_F, col)

    def cyl(self, cx, cy, z0, z1, r, col, seg=12):
        a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
        ring = np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)
        v = np.concatenate([np.c_[ring, np.full(seg, z0)], np.c_[ring, np.full(seg, z1)]])
        f = [[i, (i + 1) % seg, seg + (i + 1) % seg, seg + i] for i in range(seg)]
        self.add(v, f, col)
        self.add(np.c_[ring, np.full(seg, z1)], [list(range(seg))], col)

    def tube(self, pts, r, col, seg=5):
        """Thin tube along a polyline (wires)."""
        pts = np.asarray(pts, np.float64)
        rings = []
        for i, p in enumerate(pts):
            t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            t /= np.linalg.norm(t)
            u = np.cross(t, [0, 0, 1.0])
            if np.linalg.norm(u) < 1e-6:
                u = np.array([1.0, 0, 0])
            u /= np.linalg.norm(u)
            w = np.cross(t, u)
            a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
            rings.append(p + r * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * w))
        v = np.concatenate(rings)
        f = [[i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k]
             for i in range(len(pts) - 1) for k in range(seg)]
        self.add(v, f, col)

    def blob(self, c, radii, col, rng, sub=2, amp=0.22, shade=(0.62, 1.12), floor=None):
        """Lumpy ellipsoid; darker underneath to fake occlusion. ``floor`` clips the bottom (clouds)."""
        uv, f = ico(sub)
        k = rng.normal(size=(3, 3))
        ph = rng.normal(size=3) * 3.0
        n = sum(np.sin(uv @ k[i] * (1.8 + i * 1.7) + ph[i]) / (1 + i) for i in range(3)) / 1.6
        v = uv * (1 + amp * n)[:, None] * np.asarray(radii) + np.asarray(c)
        if floor is not None:
            v[:, 2] = np.maximum(v[:, 2], floor)
        s = shade[0] + (shade[1] - shade[0]) * np.clip(uv[:, 2] * 0.5 + 0.5 + 0.15 * n, 0, 1)
        self.add(v, f, np.asarray(col)[None, :3] * s[:, None])

    def build(self):
        if not self.verts:
            return None
        v = np.concatenate(self.verts)
        cols = np.concatenate(self.cols)
        me = bpy.data.meshes.new(self.name)
        me.vertices.add(len(v))
        me.vertices.foreach_set("co", v.astype(np.float32).ravel())
        sizes = np.concatenate([np.full(len(g), g.shape[1], np.int64) for g in self.faces])
        flat = np.concatenate([g.ravel() for g in self.faces])
        me.loops.add(len(flat))
        me.loops.foreach_set("vertex_index", flat.astype(np.int32))
        me.polygons.add(len(sizes))
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]])
        me.polygons.foreach_set("loop_start", starts.astype(np.int32))
        me.update(calc_edges=True)
        me.validate()
        if self.smooth:
            me.shade_smooth()
        a = me.attributes.new("vcol", "FLOAT_COLOR", "POINT")
        a.data.foreach_set("color", np.c_[cols, np.ones(len(cols))].astype(np.float32).ravel())
        o = bpy.data.objects.new(self.name, me)
        me.materials.append(self.material)
        B.link(o)
        return o


# ---------------------------------------------------------------- materials

def _haze(nt, shader_out, dist, hstr):
    """Mix toward a glowing haze with camera distance; the haze barely lights other surfaces."""
    cam = nt.nodes.new("ShaderNodeCameraData")
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = -dist
    nt.links.new(cam.outputs["View Distance"], div.inputs[0])
    ex = nt.nodes.new("ShaderNodeMath")
    ex.operation = "EXPONENT"
    nt.links.new(div.outputs[0], ex.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(ex.outputs[0], inv.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*HAZE, 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    st = nt.nodes.new("ShaderNodeMapRange")
    st.inputs["To Min"].default_value = hstr * 0.15
    st.inputs["To Max"].default_value = hstr
    nt.links.new(lp.outputs["Is Camera Ray"], st.inputs["Value"])
    nt.links.new(st.outputs[0], em.inputs["Strength"])
    ms = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(inv.outputs[0], ms.inputs["Fac"])
    nt.links.new(shader_out, ms.inputs[1])
    nt.links.new(em.outputs["Emission"], ms.inputs[2])
    return ms.outputs["Shader"]


def vmat(name, rough=0.85, spec=0.2, dist=700.0, hstr=1.0, windows=None, glow=0.0):
    """Exterior material reading ``vcol``; ``windows`` overlays a facade grid in world space."""
    key = f"ext_{name}"
    if key in B._mats:
        return B._mats[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "vcol"
    col = attr.outputs["Color"]
    if windows:
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
        br.inputs["Brick Width"].default_value = windows[0]
        br.inputs["Row Height"].default_value = windows[1]
        br.inputs["Mortar Size"].default_value = windows[2]
        br.inputs["Mortar Smooth"].default_value = 0.1
        br.inputs["Color1"].default_value = (*srgb("#56636f"), 1)
        br.inputs["Color2"].default_value = (*srgb("#6a7884"), 1)
        nt.links.new(comb.outputs[0], br.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(br.outputs["Fac"], mix.inputs["Factor"])
        nt.links.new(br.outputs["Color"], mix.inputs["A"])
        nt.links.new(col, mix.inputs["B"])
        col = mix.outputs["Result"]
    nt.links.new(col, p.inputs["Base Color"])
    shader = p.outputs["BSDF"]
    if glow:
        # cheap multiple scattering for clouds: a little self-emission lifts the shaded side
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = glow
        nt.links.new(col, em.inputs["Color"])
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(shader, add.inputs[0])
        nt.links.new(em.outputs["Emission"], add.inputs[1])
        shader = add.outputs["Shader"]
    out = nt.nodes.get("Material Output")
    nt.links.new(_haze(nt, shader, dist, hstr), out.inputs["Surface"])
    B._mats[key] = m
    return m


# ---------------------------------------------------------------- pieces

LEAF = [srgb(c) for c in ("#5c8a38", "#6c9a40", "#4d7a30", "#79a548", "#638f3a", "#88b04e", "#557f34")]
WALLS = [srgb(c) for c in ("#f1ece4", "#e9e3d9", "#f6f3ee", "#e2dbd0", "#ece6dc", "#d9d2c8")]
ROOFS = [srgb(c) for c in ("#5e6670", "#6d7178", "#7a746e", "#8b6e62")]
GLASS = srgb("#2f3d4b")
FRAME = srgb("#dcd6cc")


def tree(b, rng, x, y, h, spread=1.0, sub=2, lobes=(7, 12), size=(0.42, 0.62)):
    z0 = float(terrain(x, y))
    col = np.array(rng.choice(LEAF)) * rng.uniform(0.9, 1.08)
    cr = h * 0.4 * spread
    cz = z0 + h - cr * 0.85
    for _ in range(rng.randint(*lobes)):
        u = rng.normal(size=3)
        u /= np.linalg.norm(u)
        u[2] = abs(u[2]) * 0.8 - 0.15
        r = cr * rng.uniform(*size)
        reach = 1.0 - size[0] * 0.6
        c = (x + u[0] * cr * reach, y + u[1] * cr * reach, cz + u[2] * cr * 0.6)
        # sunlit lobes on top read lighter and warmer
        tint = col * rng.uniform(0.93, 1.07) * (1.0 + 0.12 * u[2]) * np.array([1.0 + 0.05 * u[2], 1.0, 1.0])
        b.blob(c, (r, r, r * rng.uniform(0.82, 0.98)), tint, rng, sub=sub, amp=0.2)
    return z0


def house(b, glass, rng, x, y, w, d, floors, storey=3.1, detail=True):
    """White block facing the room: recessed windows on the front (-y) and left (-x) faces."""
    z0 = float(terrain(x, y))
    h = floors * storey + 0.6
    wall = np.array(rng.choice(WALLS))
    x0, x1, y0, y1 = x - w / 2, x + w / 2, y - d / 2, y + d / 2
    b.box(x0, y0, z0 - 2, x1, y1, z0 + h, wall)
    # parapet + roof slab
    p = 0.25
    roof_top = z0 + h
    if rng.random() < 0.25 and floors <= 3:
        rc = np.array(rng.choice(ROOFS))
        rh = min(w, d) * 0.32
        v = [(x0 - 0.3, y0 - 0.4, roof_top), (x1 + 0.3, y0 - 0.4, roof_top), (x1 + 0.3, y, roof_top + rh),
             (x0 - 0.3, y, roof_top + rh), (x0 - 0.3, y1 + 0.4, roof_top), (x1 + 0.3, y1 + 0.4, roof_top)]
        b.add(v, [[0, 1, 2, 3], [3, 2, 5, 4], [0, 3, 4], [1, 5, 2]], rc)
    else:
        trim = wall * 0.94
        b.box(x0, y0, roof_top, x1, y0 + p, roof_top + 0.9, trim)
        b.box(x0, y1 - p, roof_top, x1, y1, roof_top + 0.9, trim)
        b.box(x0, y0, roof_top, x0 + p, y1, roof_top + 0.9, trim)
        b.box(x1 - p, y0, roof_top, x1, y1, roof_top + 0.9, trim)
        if detail:
            for _ in range(rng.randint(1, 3)):
                ax, ay = rng.uniform(x0 + 1, x1 - 2), rng.uniform(y0 + 1, y1 - 2)
                b.box(ax, ay, roof_top, ax + 0.9, ay + 0.6, roof_top + 0.7, srgb("#c9c6c0"))
            if rng.random() < 0.6:
                tx, ty = rng.uniform(x0 + 1.5, x1 - 1.5), rng.uniform(y0 + 1.5, y1 - 1.5)
                b.cyl(tx, ty, roof_top, roof_top + 1.6, 0.7, srgb("#e8e6e1") if rng.random() < 0.6 else srgb("#4d6f8f"))
            if rng.random() < 0.4:
                hx, hy = rng.uniform(x0 + 1, x1 - 4), rng.uniform(y0 + 1, y1 - 3)
                b.box(hx, hy, roof_top, hx + 2.6, hy + 2.2, roof_top + 2.4, wall * 0.97)
    # windows
    bays = max(2, int(w / rng.choice((2.6, 3.0, 3.4))))
    side_bays = max(1, int(d / 3.2))
    ww, wh = rng.uniform(1.1, 1.6), rng.uniform(1.3, 1.6)
    balcony = rng.random() < 0.4
    for fl in range(floors):
        zc = z0 + 0.3 + fl * storey + storey * 0.55
        for i in range(bays):
            xc = x0 + (i + 0.5) * w / bays
            glass.box(xc - ww / 2, y0 - 0.06, zc - wh / 2, xc + ww / 2, y0 + 0.1, zc + wh / 2, GLASS)
            b.box(xc - ww / 2 - 0.12, y0 - 0.12, zc - wh / 2 - 0.16, xc + ww / 2 + 0.12, y0 + 0.02, zc - wh / 2, FRAME)
            if balcony and fl > 0 and i % 2 == 0:
                bz = zc - wh / 2 - 0.25
                b.box(xc - ww / 2 - 0.5, y0 - 1.1, bz - 0.15, xc + ww / 2 + 0.5, y0, bz, wall * 0.95)
                b.box(xc - ww / 2 - 0.5, y0 - 1.1, bz, xc + ww / 2 + 0.5, y0 - 1.0, bz + 1.0, wall * 0.9)
        if x0 > CAM[0] + 2:
            for j in range(side_bays):
                yc = y0 + (j + 0.5) * d / side_bays
                glass.box(x0 - 0.06, yc - ww / 2, zc - wh / 2, x0 + 0.1, yc + ww / 2, zc + wh / 2, GLASS)


def block(b, rng, x, y, w, d, h):
    z0 = float(terrain(x, y))
    col = np.array(rng.choice(WALLS)) * rng.uniform(0.9, 1.0)
    b.box(x - w / 2, y - d / 2, z0 - 3, x + w / 2, y + d / 2, z0 + h, col)
    if rng.random() < 0.5:
        b.box(x - w / 4, y - d / 4, z0 + h, x + w / 4, y + d / 4, z0 + h + 3, col * 0.95)


def tower(b, rng, x, y, tall=False):
    z0 = float(terrain(x, y))
    w = rng.uniform(26, 48)
    h = rng.uniform(150, 260) if tall else rng.uniform(60, 130) * (1.6 if rng.random() < 0.18 else 1.0)
    col = np.array(srgb(rng.choice(("#c7d0d8", "#d6dbe0", "#b9c4ce", "#dfe2e4", "#aab7c3"))))
    b.box(x - w / 2, y - w / 2, z0 - 5, x + w / 2, y + w / 2, z0 + h, col)
    if rng.random() < 0.45:
        s = w * rng.uniform(0.55, 0.75)
        h2 = h * rng.uniform(0.12, 0.3)
        b.box(x - s / 2, y - s / 2, z0 + h, x + s / 2, y + s / 2, z0 + h + h2, col * 0.97)


def cloud(b, rng, x, y, z, size):
    """Cumulus: a flat base with cauliflower lobes piling up toward the middle."""
    col = np.array(srgb("#fbf8f2"))
    for _ in range(rng.randint(18, 28)):
        t = rng.uniform(-0.5, 0.5)
        dome = 1.0 - 4.0 * t * t
        r = size * rng.uniform(0.12, 0.19) * (0.6 + 0.6 * dome)
        c = (x + t * size, y + rng.uniform(-0.12, 0.12) * size,
             z + r * 0.45 + size * 0.26 * dome * rng.uniform(0.2, 1.0))
        b.blob(c, (r, r, r * 0.92), col, rng, sub=3, amp=0.14, shade=(0.74, 1.04), floor=z)


def ground(rng):
    xs = np.linspace(-2600, 4200, 140)
    t = np.linspace(0, 1, 120)
    ys = WIN_Y + 3 + t ** 2.2 * 4600
    X, Y = np.meshgrid(xs, ys)
    Z = terrain(X, Y)
    v = np.stack([X, Y, Z], -1).reshape(-1, 3)
    nx = len(xs)
    f = [[j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i]
         for j in range(len(ys) - 1) for i in range(nx - 1)]
    grass, town = np.array(srgb("#7d8f62")), np.array(srgb("#a3a196"))
    k = np.clip((v[:, 1] - 120) / 600, 0, 1)[:, None]
    n = (np.sin(v[:, 0] / 37) * np.sin(v[:, 1] / 29) * 0.5 + 0.5)[:, None]
    col = (grass * (1 - k) + town * k) * (0.9 + 0.15 * n)
    b = Batch("ext_ground", vmat("ground", rough=0.95, dist=900))
    b.add(v, f, col)
    # near street and pavements
    b.box(-200, WIN_Y + 12, GROUND, 300, WIN_Y + 20, GROUND + 0.05, srgb("#9b9b97"))
    b.box(-200, WIN_Y + 10.5, GROUND, 300, WIN_Y + 12, GROUND + 0.18, srgb("#c9c4b9"))
    b.box(-200, WIN_Y + 20, GROUND, 300, WIN_Y + 21.5, GROUND + 0.18, srgb("#c9c4b9"))
    b.build()


def pole_and_wires(b):
    px, py = 12.5, WIN_Y + 16.5
    z0 = GROUND
    top = z0 + 16.5
    b.cyl(px, py, z0, top, 0.16, srgb("#5a5550"), seg=10)
    arm = top - 0.7
    b.box(px - 1.6, py - 0.09, arm - 0.12, px + 1.6, py + 0.09, arm, srgb("#4a4642"))
    for k in (-1.3, 0.0, 1.3):
        b.box(px + k - 0.05, py - 0.05, arm, px + k + 0.05, py + 0.05, arm + 0.22, srgb("#e6e2da"))
    wires = []
    for k, far in ((-1.3, (-60.0, WIN_Y + 30.0)), (0.0, (-60.0, WIN_Y + 31.0)), (1.3, (-60.0, WIN_Y + 32.0))):
        a = np.array([px + k, py, arm + 0.2])
        for end in (np.array([far[0], far[1], arm + 1.0]), np.array([px + k + 70.0, py - 6.0, arm - 0.4])):
            t = np.linspace(0, 1, 24)[:, None]
            pts = a * (1 - t) + end * t
            pts[:, 2] -= 1.6 * 4 * t[:, 0] * (1 - t[:, 0])
            wires.append(pts)
    for w in wires:
        b.tube(w, 0.022, srgb("#2b2a29"))


# ---------------------------------------------------------------- assembly

def build(seed=11):
    B.use_collection("exterior")
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)

    class R:
        """random.Random facade that also offers numpy normals for the blob noise."""
        random = rng.random
        uniform = rng.uniform
        randint = rng.randint
        choice = rng.choice
        normal = nrng.normal

    ground(rng)

    near = Batch("ext_near", vmat("near", rough=0.8, dist=1400))
    glass = Batch("ext_glass", vmat("glass", rough=0.14, spec=0.6, dist=1400))
    leaves = Batch("ext_leaves", vmat("leaves", rough=0.92, spec=0.15, dist=1100), smooth=True)
    far_trees = Batch("ext_trees_far", vmat("trees_far", rough=0.95, spec=0.1, dist=800), smooth=True)

    # Near band (15-60 m): big crowns up to sill height with a few white blocks between them.
    houses = []
    for _ in range(400):
        if len(houses) >= 18:
            break
        x, y = spot(rng, 45, 125, 4)
        w, d = rng.uniform(9, 15), rng.uniform(8, 12)
        if any(abs(x - hx) < (w + hw) / 2 + 2 and abs(y - hy) < (d + hd) / 2 + 2 for hx, hy, hw, hd in houses):
            continue
        houses.append((x, y, w, d))
        house(near, glass, R, x, y, w, d, rng.randint(2, 4))
    for _ in range(26):
        x, y = spot(rng, 32, 115, 6)
        if any(abs(x - hx) < hw / 2 + 1 and abs(y - hy) < hd / 2 + 1 for hx, hy, hw, hd in houses):
            continue
        z0 = tree(leaves, R, x, y, rng.uniform(9.0, 13.5), spread=rng.uniform(1.0, 1.25), sub=3,
                  lobes=(14, 22), size=(0.3, 0.46))
        near.cyl(x, y, z0, z0 + 4.0, 0.28, srgb("#5a4636"), seg=8)

    # Middle band (70-320 m): denser roofs and trees, still with geometry windows.
    for _ in range(1500):
        if len(houses) >= 170:
            break
        x, y = spot(rng, 125, 480, 3)
        w, d = rng.uniform(10, 22), rng.uniform(9, 16)
        if any(abs(x - hx) < (w + hw) / 2 + 3 and abs(y - hy) < (d + hd) / 2 + 3 for hx, hy, hw, hd in houses):
            continue
        houses.append((x, y, w, d))
        house(near, glass, R, x, y, w, d, rng.randint(2, 6), detail=y < 260)
    # trees grow in clumps (yards, streets, small parks) rather than evenly
    for _ in range(170):
        cx, cy = spot(rng, 110, 480, 3)
        for _ in range(rng.randint(2, 7)):
            x, y = cx + rng.uniform(-14, 14), cy + rng.uniform(-10, 10)
            if any(abs(x - hx) < hw / 2 and abs(y - hy) < hd / 2 for hx, hy, hw, hd in houses):
                continue
            tree(leaves, R, x, y, rng.uniform(9, 14), spread=1.2, sub=2, lobes=(8, 12), size=(0.34, 0.5))

    # Mid-rise belt (320-1100 m): plain blocks with a facade texture, trees as single lumps.
    mid = Batch("ext_mid", vmat("mid", rough=0.85, dist=900, windows=(3.2, 3.0, 1.0)))
    for _ in range(300):
        x, y = spot(rng, 480, 1400, 2)
        block(mid, R, x, y, rng.uniform(18, 40), rng.uniform(14, 26), rng.uniform(14, 42))
    for _ in range(800):
        x, y = spot(rng, 460, 1400, 2)
        r = rng.uniform(5, 9)
        far_trees.blob((x, y, float(terrain(x, y)) + r * 0.9), (r, r, r * 0.8), np.array(rng.choice(LEAF)), R,
                       sub=1, amp=0.25)

    # Skyline (1.4-3.2 km): towers in the haze.
    sky = Batch("ext_skyline", vmat("skyline", rough=0.8, dist=1700, hstr=1.0, windows=(4.0, 3.6, 1.6)))
    for _ in range(150):
        x, y = spot(rng, 1600, 3400, 0)
        tower(sky, R, x, y)
    # a downtown cluster a little right of the window centre gives the skyline a focal point
    for _ in range(14):
        d = rng.uniform(2100, 2800)
        a = math.radians(rng.uniform(16, 30))
        tower(sky, R, d * math.sin(a), d * math.cos(a), tall=True)

    # Cumulus above the skyline.
    clouds = Batch("ext_clouds", vmat("clouds", rough=1.0, spec=0.0, dist=9000, hstr=0.6, glow=0.35), smooth=True)
    for _ in range(10):
        d = rng.uniform(3000, 4800)
        a = math.radians(rng.uniform(YAW_MIN - 10, YAW_MAX + 10))
        x, y = d * math.sin(a), d * math.cos(a)
        el = math.radians(rng.uniform(2.5, 10.0))
        cloud(clouds, R, x, y, d * math.tan(el), rng.uniform(260, 560))

    pole_and_wires(near)
    for b in (near, glass, leaves, far_trees, mid, sky, clouds):
        b.build()
