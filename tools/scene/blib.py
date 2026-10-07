"""Shared Blender helpers: materials, primitives and the voxel mesh builder."""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "tools" / "scene" / "build" / "tex"

_mats: dict[str, bpy.types.Material] = {}


# ---------------------------------------------------------------- scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mats.clear()


def collection(name: str, parent=None) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


_active_col: list[bpy.types.Collection] = []


def use_collection(name: str):
    _active_col.clear()
    _active_col.append(collection(name))


def link(obj, hs: str | None = None):
    col = _active_col[0] if _active_col else bpy.context.scene.collection
    col.objects.link(obj)
    if hs:
        obj["hs"] = hs
    return obj


def place(obj, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    obj.location = loc
    obj.rotation_euler = Euler([math.radians(a) for a in rot])
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, hs=None):
    e = bpy.data.objects.new(name, None)
    link(e, hs)
    return place(e, loc, rot, parent)


# ---------------------------------------------------------------- materials

def _principled(mat):
    nt = mat.node_tree
    return nt.nodes.get("Principled BSDF")


def mat(name, color=(0.8, 0.8, 0.8), rough=0.6, metal=0.0, spec=0.5, emission=None, estr=0.0, coat=0.0,
        sheen=0.0) -> bpy.types.Material:
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = _principled(m)
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Specular IOR Level"].default_value = spec
    if coat:
        p.inputs["Coat Weight"].default_value = coat
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
    if emission:
        p.inputs["Emission Color"].default_value = (*emission, 1)
        p.inputs["Emission Strength"].default_value = estr
    _mats[name] = m
    return m


def mat_image(name, image: str, rough=0.7, alpha=False, emission=0.0, spec=0.3, repeat=(1, 1), interp="Linear"):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = _principled(m)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(TEX / image), check_existing=True)
    tex.interpolation = interp
    if repeat != (1, 1):
        uv = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (repeat[0], repeat[1], 1)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
    if alpha:
        nt.links.new(tex.outputs["Alpha"], p.inputs["Alpha"])
    if emission:
        nt.links.new(tex.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = emission
    _mats[name] = m
    return m


def mat_voxel(name, rough=0.62, spec=0.35, sheen=0.0) -> bpy.types.Material:
    """Material that reads the per-voxel colour attribute ``vcol``."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = _principled(m)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "vcol"
    nt.links.new(a.outputs["Color"], p.inputs["Base Color"])
    _mats[name] = m
    return m


def mat_noise(name, c1, c2, scale=40.0, rough=0.8, detail=6.0, bump=0.0, spec=0.3):
    """Procedural two-tone material (cork, wood grain, fabric)."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = _principled(m)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.7
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    if bump:
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump
        nt.links.new(n.outputs["Fac"], b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    _mats[name] = m
    return m


def mat_emit(name, color, strength=4.0):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    out = nt.nodes.get("Material Output")
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    _mats[name] = m
    return m


def mat_leaf(name="leaf", rough=0.45, translucency=0.3):
    """Foliage: per-vertex ``vcol`` tint with a little light leaking through."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = _principled(m)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = 0.45
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "vcol"
    nt.links.new(a.outputs["Color"], p.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(a.outputs["Color"], tr.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMixShader")
    ms.inputs["Fac"].default_value = translucency
    nt.links.new(p.outputs["BSDF"], ms.inputs[1])
    nt.links.new(tr.outputs["BSDF"], ms.inputs[2])
    nt.links.new(ms.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    _mats[name] = m
    return m


# ---------------------------------------------------------------- primitives

def _vcol_mesh(name, verts, faces, cols, material, parent=None, hs=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(f) for f in faces])
    attr = me.attributes.new("vcol", "FLOAT_COLOR", "POINT")
    flat = np.ones((len(verts), 4), np.float32)
    flat[:, :3] = np.asarray(cols, np.float32)
    attr.data.foreach_set("color", flat.ravel())
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    me.update()
    obj = bpy.data.objects.new(name, me)
    if material:
        me.materials.append(material)
    link(obj, hs)
    if parent is not None:
        obj.parent = parent
    return obj


def leaves(name, specs, material=None, parent=None, hs=None):
    """Many curved leaves in one mesh.

    spec: dict(base, yaw, pitch, roll, length, width, fold, curl, color[, tip]).
    A leaf grows along local +X from ``base``; pitch tilts it up, curl droops it toward the tip.
    """
    verts, faces, cols = [], [], []
    nl, nw = 9, 2
    for s in specs:
        L, W = s["length"], s["width"]
        R = rot_matrix((s.get("roll", 0), -s.get("pitch", 0), s.get("yaw", 0)))
        base = np.array(s["base"], float)
        c = np.array(s["color"], float)
        tip = s.get("tip", 0.85)
        start = len(verts)
        for i in range(nl + 1):
            t = i / nl
            half = W * 0.5 * (math.sin(math.pi * min(1.0, t ** 0.9)) ** tip) * (1.0 if t < 0.98 else 0.2)
            for j in range(-nw, nw + 1):
                u = j / nw
                x = L * t
                y = u * half
                z = s.get("fold", 0.15) * abs(u) * half - s.get("curl", 0.2) * L * t * t
                verts.append(base + R @ np.array([x, y, z]))
                shade = 0.82 + 0.18 * (1 - abs(u)) * (0.6 + 0.4 * t)
                cols.append(c * shade)
        row = 2 * nw + 1
        for i in range(nl):
            for j in range(row - 1):
                a = start + i * row + j
                faces.append((a, a + 1, a + row + 1, a + row))
    obj = _vcol_mesh(name, verts, faces, cols, material or mat_leaf(), parent, hs)
    obj.modifiers.new("solid", "SOLIDIFY").thickness = 0.0025
    return obj


def tubes(name, segs, material=None, parent=None, hs=None, sides=6):
    """Thin tubes (stems, cables) merged into one mesh: segs = [(a, b, r), ...]."""
    verts, faces = [], []
    for a, b, r in segs:
        a, b = np.array(a, float), np.array(b, float)
        d = b - a
        n = d / (np.linalg.norm(d) + 1e-9)
        ref = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
        u = np.cross(n, ref)
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        start = len(verts)
        for end in (a, b):
            for k in range(sides):
                t = 2 * math.pi * k / sides
                verts.append(end + r * (math.cos(t) * u + math.sin(t) * v))
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((start + k, start + k2, start + sides + k2, start + sides + k))
    obj = _mesh_obj(name, [tuple(map(float, p)) for p in verts], faces, material, hs)
    for p in obj.data.polygons:
        p.use_smooth = True
    if parent is not None:
        obj.parent = parent
    return obj


def tbox(name, a, b, size_a, size_b=None, up=(0, 0, 1), material=None, bevel=0.01, segments=3, parent=None,
         hs=None):
    """Tapered box running from point a to point b; size = (width, depth) of each end cap.

    Local X is perpendicular to the bone and to ``up``; local Y completes the frame.
    """
    a, b = Vector(a), Vector(b)
    size_b = size_b or size_a
    ax = (b - a).normalized()
    upv = Vector(up)
    xv = ax.cross(upv)
    if xv.length < 1e-6:
        xv = ax.cross(Vector((1, 0, 0)))
    xv.normalize()
    yv = xv.cross(ax).normalized()
    v = []
    for c, (w, d) in ((a, size_a), (b, size_b)):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v.append(tuple(c + xv * (sx * w / 2) + yv * (sy * d / 2)))
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = _mesh_obj(name, v, f, material, hs)
    if bevel > 0:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = segments
        m.limit_method = "NONE"
        m.use_clamp_overlap = True
        m.harden_normals = True
    obj.data.shade_smooth()
    if parent is not None:
        obj.parent = parent
    return obj


def superellipsoid(name, size, loc=(0, 0, 0), rot=(0, 0, 0), material=None, e=0.3, puff=0.0, nu=32, nv=16,
                   parent=None, hs=None):
    """Soft box (pillow / cushion). UV: front (-Y) face maps x->u, z->v."""
    a, b, c = (s / 2 for s in size)
    v, f, uvs = [], [], []

    def sp(x, p):
        return math.copysign(abs(x) ** p, x)

    for j in range(nv + 1):
        phi = -math.pi / 2 + math.pi * j / nv
        for i in range(nu + 1):
            th = -math.pi + 2 * math.pi * i / nu
            cx, cz = sp(math.cos(phi), e), sp(math.sin(phi), e)
            x = a * cx * sp(math.cos(th), e)
            y = b * cx * sp(math.sin(th), e)
            z = c * cz
            # pillows bulge in the middle of the big faces
            y *= 1.0 + puff * (1 - abs(x / a) ** 2) * (1 - abs(z / c) ** 2) if abs(y) > 0.5 * b else 1.0
            v.append((x, y, z))
            uvs.append((0.5 + x / (2 * a), 0.5 + z / (2 * c)))
    row = nu + 1
    for j in range(nv):
        for i in range(nu):
            p0 = j * row + i
            f.append((p0, p0 + 1, p0 + row + 1, p0 + row))
    obj = _mesh_obj(name, v, f, material, hs, uvs)
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.modifiers.new("weld", "WELD").merge_threshold = 1e-5
    place(obj, loc, rot, parent)
    return obj


def extrude(name, outline, depth, loc=(0, 0, 0), rot=(0, 0, 0), material=None, bevel=0.0, parent=None, hs=None):
    """Extrude a closed 2D outline (in local XZ, facing -Y) by ``depth`` along +Y."""
    n = len(outline)
    v = [(x, 0.0, z) for x, z in outline] + [(x, depth, z) for x, z in outline]
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n + j, n + i))
    obj = _mesh_obj(name, v, f, material, hs)
    if bevel > 0:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 3
        m.limit_method = "ANGLE"
    place(obj, loc, rot, parent)
    return obj


def _mesh_obj(name, verts, faces, material=None, hs=None, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        loop_uv = []
        for f in faces:
            for vi in f:
                loop_uv.extend(uvs[vi])
        uvl.data.foreach_set("uv", loop_uv)
    me.update()
    obj = bpy.data.objects.new(name, me)
    if material:
        me.materials.append(material)
    link(obj, hs)
    return obj


def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), material=None, bevel=0.006, segments=2, parent=None, hs=None):
    """Axis-aligned box centred on ``loc`` with a real bevel modifier."""
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = _mesh_obj(name, v, f, material, hs)
    if bevel > 0:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = segments
        m.limit_method = "NONE"
    place(obj, loc, rot, parent)
    return obj


def box_minmax(name, mn, mx, material=None, bevel=0.006, segments=2, parent=None, hs=None):
    size = [b - a for a, b in zip(mn, mx)]
    loc = [(a + b) / 2 for a, b in zip(mn, mx)]
    return box(name, size, loc, (0, 0, 0), material, bevel, segments, parent, hs)


def cylinder(name, r, h, loc=(0, 0, 0), rot=(0, 0, 0), material=None, verts=48, bevel=0.0, parent=None, hs=None,
             cap=True, r_top=None):
    r_top = r if r_top is None else r_top
    v, f = [], []
    for i in range(verts):
        a = 2 * math.pi * i / verts
        v.append((r * math.cos(a), r * math.sin(a), -h / 2))
    for i in range(verts):
        a = 2 * math.pi * i / verts
        v.append((r_top * math.cos(a), r_top * math.sin(a), h / 2))
    for i in range(verts):
        j = (i + 1) % verts
        f.append((i, j, verts + j, verts + i))
    if cap:
        f.append(tuple(reversed(range(verts))))
        f.append(tuple(range(verts, 2 * verts)))
    uvs = [(i / verts, 0) for i in range(verts)] + [(i / verts, 1) for i in range(verts)]
    obj = _mesh_obj(name, v, f, material, hs)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    if bevel > 0:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 2
        m.limit_method = "ANGLE"
        m.angle_limit = math.radians(50)
    place(obj, loc, rot, parent)
    return obj


def plane(name, w, h, loc=(0, 0, 0), rot=(0, 0, 0), material=None, parent=None, hs=None, sub=(1, 1)):
    """XZ-plane facing -Y (towards a camera standing in front of a wall)."""
    nx, nz = sub
    v, uvs = [], []
    for j in range(nz + 1):
        for i in range(nx + 1):
            u, t = i / nx, j / nz
            v.append(((u - 0.5) * w, 0, (t - 0.5) * h))
            uvs.append((u, t))
    f = []
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            f.append((a, a + 1, a + nx + 2, a + nx + 1))
    obj = _mesh_obj(name, v, f, material, hs, uvs)
    place(obj, loc, rot, parent)
    return obj


def lathe(name, profile, loc=(0, 0, 0), rot=(0, 0, 0), material=None, segs=48, parent=None, hs=None, smooth=True):
    """Revolve a list of (r, z) points around Z."""
    v, f, uvs = [], [], []
    n = len(profile)
    for i in range(segs + 1):
        a = 2 * math.pi * i / segs
        for k, (r, z) in enumerate(profile):
            v.append((r * math.cos(a), r * math.sin(a), z))
            uvs.append((i / segs, k / (n - 1)))
    for i in range(segs):
        i2 = i + 1
        for k in range(n - 1):
            f.append((i * n + k, i2 * n + k, i2 * n + k + 1, i * n + k + 1))
    obj = _mesh_obj(name, v, f, material, hs, uvs)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    obj.modifiers.new("weld", "WELD").merge_threshold = 1e-5
    place(obj, loc, rot, parent)
    return obj


# ---------------------------------------------------------------- voxels

def _chamfer_cube(c: float):
    """Unit chamfered cube centred at origin: 24 verts, 26 faces."""
    verts, idx = [], {}
    h, i_ = 0.5, 0.5 - c
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                for axis in range(3):
                    p = [sx * i_, sy * i_, sz * i_]
                    p[axis] = (sx, sy, sz)[axis] * h
                    idx[(sx, sy, sz, axis)] = len(verts)
                    verts.append(p)
    faces = []
    for axis in range(3):
        for s in (-1, 1):
            quad = []
            o = [a for a in range(3) if a != axis]
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                key = [0, 0, 0]
                key[axis] = s
                key[o[0]] = a
                key[o[1]] = b
                quad.append(idx[(*key, axis)])
            faces.append(quad)
    # edge quads
    for axis in range(3):  # edge runs along `axis`
        o = [a for a in range(3) if a != axis]
        for a in (-1, 1):
            for b in (-1, 1):
                k0 = [0, 0, 0]
                k0[o[0]] = a
                k0[o[1]] = b
                lo, hi = list(k0), list(k0)
                lo[axis], hi[axis] = -1, 1
                faces.append([idx[(*lo, o[0])], idx[(*hi, o[0])], idx[(*hi, o[1])], idx[(*lo, o[1])]])
    # corner triangles
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                faces.append([idx[(sx, sy, sz, 0)], idx[(sx, sy, sz, 1)], idx[(sx, sy, sz, 2)]])
    verts = np.array(verts, dtype=np.float32)
    fixed = []
    for f in faces:
        p = verts[f]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if np.dot(n, p.mean(axis=0)) < 0:
            f = list(reversed(f))
        fixed.append(f)
    return verts, fixed


def voxel_mesh(name, vox: dict, size: float, origin=(0, 0, 0), material=None, chamfer=0.14, jitter=0.035,
               parent=None, hs=None, seed=1, scale_z=1.0, cull=True, pos_jitter=0.0, scale_jitter=0.0, rot=(0, 0, 0)):
    """Build one mesh of individual chamfered cubes.

    ``vox`` maps integer (i, j, k) -> (r, g, b) linear colour.
    Fully enclosed voxels are skipped.
    """
    keys = list(vox.keys())
    if cull:
        ks = set(keys)
        keys = [k for k in keys if not all(
            (k[0] + dx, k[1] + dy, k[2] + dz) in ks
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]
    tv, tf = _chamfer_cube(chamfer)
    nv = len(tv)
    n = len(keys)
    rng = np.random.default_rng(seed)
    centers = np.array(keys, dtype=np.float32) * size
    centers[:, 2] *= scale_z
    sc = np.array([size, size, size * scale_z], dtype=np.float32)
    per = np.ones((n, 1, 3), np.float32)
    if scale_jitter:
        per = per * rng.uniform(1 - scale_jitter * 0.4, 1 + scale_jitter, (n, 1, 1)).astype(np.float32)
    if pos_jitter:
        centers = centers + rng.uniform(-pos_jitter, pos_jitter, (n, 3)).astype(np.float32) * size
    verts = (tv[None, :, :] * sc[None, None, :] * per + centers[:, None, :]).reshape(-1, 3)
    cols = np.array([vox[k] for k in keys], dtype=np.float32)
    if jitter:
        cols = np.clip(cols * (1 + rng.uniform(-jitter, jitter, (n, 1))), 0, 1)
    me = bpy.data.meshes.new(name)
    faces = []
    for c in range(n):
        base = c * nv
        faces.extend([[base + i for i in f] for f in tf])
    me.from_pydata(verts.tolist(), [], faces)
    attr = me.attributes.new("vcol", "FLOAT_COLOR", "POINT")
    rgba = np.concatenate([np.repeat(cols, nv, axis=0), np.ones((n * nv, 1), np.float32)], axis=1)
    attr.data.foreach_set("color", rgba.ravel())
    me.update()
    obj = bpy.data.objects.new(name, me)
    me.materials.append(material or mat_voxel("voxel"))
    link(obj, hs)
    place(obj, origin, rot, parent)
    return obj


_FACE_DIRS = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


def voxel_solid(name, vox: dict, size: float, origin=(0, 0, 0), material=None, bevel=0.22, jitter=0.03,
                parent=None, hs=None, seed=1, rot=(0, 0, 0), segments=2):
    """Voxels as one welded surface: flat areas stay planar, only steps get bevelled."""
    rng = np.random.default_rng(seed)
    ks = set(vox.keys())
    vidx: dict = {}
    verts, faces, fcols = [], [], []
    for k in vox:
        c = np.array(vox[k], np.float32)
        if jitter:
            c = np.clip(c * (1 + rng.uniform(-jitter, jitter)), 0, 1)
        for d, corners in _FACE_DIRS:
            if (k[0] + d[0], k[1] + d[1], k[2] + d[2]) in ks:
                continue
            f = []
            for o in corners:
                g = (k[0] + o[0], k[1] + o[1], k[2] + o[2])
                vi = vidx.get(g)
                if vi is None:
                    vi = len(verts)
                    vidx[g] = vi
                    verts.append(((g[0] - 0.5) * size, (g[1] - 0.5) * size, (g[2] - 0.5) * size))
                f.append(vi)
            faces.append(f)
            fcols.append(c)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    attr = me.attributes.new("vcol", "FLOAT_COLOR", "CORNER")
    cols = np.repeat(np.array(fcols, np.float32), 4, axis=0)
    rgba = np.concatenate([cols, np.ones((len(cols), 1), np.float32)], axis=1)
    attr.data.foreach_set("color", rgba.ravel())
    me.update()
    obj = bpy.data.objects.new(name, me)
    me.materials.append(material or mat_voxel("voxel"))
    link(obj, hs)
    place(obj, origin, rot, parent)
    if bevel:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel * size
        m.segments = segments
        m.limit_method = "ANGLE"
        m.angle_limit = math.radians(30)
        m.harden_normals = False
        m.use_clamp_overlap = True
    return obj


def rot_matrix(rot_deg):
    """3x3 rotation (local -> parent) for an XYZ euler in degrees."""
    return np.array(Euler([math.radians(a) for a in rot_deg]).to_matrix())


def xf(p, center=(0, 0, 0), rot=(0, 0, 0)):
    """Transform parent-space points into a rotated local frame."""
    R = rot_matrix(rot)
    return (p - np.array(center)) @ R


def sd_pyramid(p, base_half, h):
    """Square-ish pyramid standing on z=0 with apex at z=h (approximate SDF)."""
    t = np.clip(p[..., 2] / h, 0, 1)
    bx = base_half[0] * (1 - t) + 1e-4
    by = base_half[1] * (1 - t) + 1e-4
    inside = (np.abs(p[..., 0]) <= bx) & (np.abs(p[..., 1]) <= by) & (p[..., 2] >= 0) & (p[..., 2] <= h)
    return np.where(inside, -1.0, 1.0)


# ---------------------------------------------------------------- SDF sampling

def sd_ellipsoid(p, c, r):
    q = (p - np.array(c)) / np.array(r)
    return (np.linalg.norm(q, axis=-1) - 1.0) * min(r)


def sd_capsule(p, a, b, r):
    a, b = np.array(a), np.array(b)
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - r


def sd_box(p, c, half, r=0.0):
    q = np.abs(p - np.array(c)) - (np.array(half) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.max(q, axis=-1), 0) - r


def sample(shapes, size, bounds):
    """Voxelise a list of (sdf_fn, colour_fn_or_rgb) in priority order.

    bounds: ((x0,y0,z0),(x1,y1,z1)) in metres. Returns {(i,j,k): rgb}.
    """
    (x0, y0, z0), (x1, y1, z1) = bounds
    ii = np.arange(math.floor(x0 / size), math.ceil(x1 / size) + 1)
    jj = np.arange(math.floor(y0 / size), math.ceil(y1 / size) + 1)
    kk = np.arange(math.floor(z0 / size), math.ceil(z1 / size) + 1)
    I, J, K = np.meshgrid(ii, jj, kk, indexing="ij")
    P = np.stack([I, J, K], -1).reshape(-1, 3).astype(np.float64) * size
    idx = np.stack([I, J, K], -1).reshape(-1, 3)
    out = {}
    taken = np.zeros(len(P), bool)
    for sdf, col in shapes:
        d = sdf(P)
        hit = (d <= 0) & ~taken
        if not hit.any():
            continue
        taken |= hit
        pts = P[hit]
        ids = idx[hit]
        if callable(col):
            cs = col(pts)
        else:
            cs = np.repeat(np.array([col], float), len(pts), 0)
        for k, c in zip(map(tuple, ids), cs):
            if c is not None and not (isinstance(c, np.ndarray) and np.isnan(c).any()):
                out[k] = tuple(float(x) for x in c)
    return out


def srgb(hexstr: str):
    """Convert '#rrggbb' to linear rgb tuple."""
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)
