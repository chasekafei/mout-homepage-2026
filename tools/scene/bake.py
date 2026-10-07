"""Bake a scene for the realtime web viewer.

Every visible surface stores its final outgoing radiance (albedo x light + emission):
  * small-faced meshes (voxels, leaves, cables) -> per-vertex colour
  * everything else -> one shared radiance atlas
Faces that no camera pose inside the orbit range can see stay in the scene as occluders while
baking and are dropped from the export.

Usage (repo root), every stage takes --scene create|now (default create):
  Blender -b --factory-startup --python tools/scene/bake.py -- --stage plan
  Blender -b --factory-startup --python tools/scene/bake.py -- --stage bake [--atlas 0] [--samples 384] [--vsamples 768]
  Blender -b --factory-startup --python tools/scene/bake.py -- --stage backdrop [--samples 256]
  Blender -b --factory-startup --python tools/scene/bake.py -- --stage lut
Raw outputs go to .cache/bake/<scene>/; `node tools/content/build-assets.mjs scene3d <scene>` publishes them.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from bpy_extras.bmesh_utils import bmesh_linked_uv_islands  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import build as BUILD  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / ".cache" / "bake"  # + /<scene>, set in main()
MARKERS: dict = {}

# Must match src/scene3d/config.ts
ORBIT = {
    "desktop": {"pivot": 2.4, "yaw": 14.0, "pitch": 7.0},
    "mobile": {"pivot": 2.2, "yaw": 12.0, "pitch": 6.0},
}
ASPECT = {"desktop": 16 / 9, "mobile": 9 / 16}
ENC_K = 0.6                 # radiance -> 8 bit: e = sqrt(x / (x + ENC_K))
LUT_N, LUT_LO, LUT_HI = 48, -10.0, 6.5
VERTEX_EDGE = 0.035         # area-weighted max edge below this -> per-vertex bake
TEXELS_AT_1M = 1100.0       # atlas density target (texels per metre at 1 m from the camera)
MAX_ATLAS = 4096


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="create")
    ap.add_argument("--stage", default="plan")
    ap.add_argument("--atlas", type=int, default=0, help="force atlas size (0 = from texel budget)")
    ap.add_argument("--density", type=float, default=1.0)
    ap.add_argument("--samples", type=int, default=384)
    ap.add_argument("--vsamples", type=int, default=768)
    ap.add_argument("--blend", default="")
    ap.add_argument("--res", type=int, default=2560, help="backdrop width")
    return ap.parse_args(argv)


def log(*a):
    print("BAKE", *a, flush=True)


def to_gltf(v):
    return [round(float(v[0]), 5), round(float(v[2]), 5), round(float(-v[1]), 5)]


def encode(x):
    x = np.maximum(x, 0.0)
    return np.sqrt(x / (x + ENC_K))


# ---------------------------------------------------------------- scene + cameras

def build_scene(scene, samples=64):
    a = argparse.Namespace(scene=scene, cam="desktop", campos="", target="", res=1280, samples=samples, exposure=None,
                           mode="bake")
    BUILD.build(a)
    BUILD.setup_render(a)
    s = bpy.context.scene
    s.render.use_compositing = False
    return s


def cam_frame(name):
    cam = bpy.data.objects[f"cam_{name}"]
    m = cam.matrix_world
    pos = m.translation.copy()
    right = (m.to_3x3() @ Vector((1, 0, 0))).normalized()
    up = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
    fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
    half = cam.data.sensor_width / 2 / cam.data.lens
    asp = ASPECT[name]
    th, tv = (half, half / asp) if asp >= 1 else (half * asp, half)
    return dict(pos=pos, fwd=fwd, right=right, up=up, tan_h=th, tan_v=tv)


def orbit_pose(f, yaw, pitch, dist):
    pivot = f["pos"] + f["fwd"] * dist
    R = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, f["right"])
    fwd, right, up = R @ f["fwd"], R @ f["right"], R @ f["up"]
    return dict(pos=pivot - fwd * dist, fwd=fwd, right=right, up=up, tan_h=f["tan_h"], tan_v=f["tan_v"])


def sample_poses(margin_deg=2.5, fov_margin=1.08):
    poses = []
    for name, o in ORBIT.items():
        f = cam_frame(name)
        f["tan_h"] *= fov_margin
        f["tan_v"] *= fov_margin
        Y, P = o["yaw"] + margin_deg, o["pitch"] + margin_deg
        for y in (-Y, -Y / 2, 0, Y / 2, Y):
            for p in (-P, 0, P):
                poses.append(orbit_pose(f, y, p, o["pivot"]))
    return poses


def key_poses():
    out = []
    for name, o in ORBIT.items():
        f = cam_frame(name)
        out.append(orbit_pose(f, 0, 0, o["pivot"]))
        if name == "desktop":
            out += [orbit_pose(f, o["yaw"], 0, o["pivot"]), orbit_pose(f, -o["yaw"], 0, o["pivot"]),
                    orbit_pose(f, 0, o["pitch"], o["pivot"]), orbit_pose(f, 0, -o["pitch"], o["pivot"])]
    return out


# ---------------------------------------------------------------- object prep

def find_hs(ob):
    while ob is not None:
        if ob.get("hs"):
            return ob["hs"]
        ob = ob.parent
    return ""


def find_prop(ob, key, default):
    while ob is not None:
        if key in ob:
            return ob[key]
        ob = ob.parent
    return default


def in_exterior(ob):
    return any(c.name == "exterior" for c in ob.users_collection)


def realize():
    """Replace every interior mesh by a modifier-applied copy (world matrix kept, texture space frozen)."""
    s = bpy.context.scene
    src = [o for o in s.objects if o.type == "MESH" and not o.hide_render and not in_exterior(o)]
    dg = bpy.context.evaluated_depsgraph_get()
    col = bpy.data.collections.new("bake")
    s.collection.children.link(col)
    anchors = {}
    out = []
    for ob in src:
        ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.use_auto_texspace = False
        me.texspace_location = ob.data.texspace_location
        me.texspace_size = ob.data.texspace_size
        hs = find_hs(ob)
        o = bpy.data.objects.new(f"r_{ob.name}", me)
        o.matrix_world = ob.matrix_world.copy()
        o["hs"] = hs
        o["texel"] = find_prop(ob, "texel", 1.0)
        o["src"] = ob.users_collection[0].name if ob.users_collection else ""
        o["detail"] = any(m and m.use_nodes and any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes)
                          for m in me.materials)
        col.objects.link(o)
        out.append(o)
        if hs and len(me.vertices):
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            M = np.array(o.matrix_world)
            w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
            area = sum(p.area for p in me.polygons) * abs(o.matrix_world.to_3x3().determinant()) ** (2 / 3)
            a = anchors.setdefault(hs, {"min": w.min(0), "max": w.max(0), "best": -1.0, "anchor": None})
            a["min"] = np.minimum(a["min"], w.min(0))
            a["max"] = np.maximum(a["max"], w.max(0))
            if area > a["best"]:
                a["best"] = area
                a["anchor"] = (w.min(0) + w.max(0)) / 2
    for ob in src:
        bpy.data.objects.remove(ob, do_unlink=True)
    return out, anchors


def dice(objs, cell=0.5, min_area=0.3):
    """Cut big faces along a world grid and split the cuts, so each tile becomes its own atlas island."""
    tiles = 0
    for o in objs:
        M = o.matrix_world
        s2 = abs(M.to_3x3().determinant()) ** (2 / 3)
        k = 1.0 / o.get("texel", 1.0)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        big = [f for f in bm.faces if f.calc_area() * s2 > min_area * k * k]
        if not big:
            bm.free()
            continue
        geom = set(big)
        for f in big:
            geom.update(f.edges)
            geom.update(f.verts)
        wp = np.array([list(M @ v.co) for v in {v for f in big for v in f.verts}])
        lo, hi = wp.min(0), wp.max(0)
        Mi = M.inverted()
        Mt = M.to_3x3().transposed()
        cuts = []
        for axis in range(3):
            n = Vector((0, 0, 0))
            n[axis] = 1.0
            nl = (Mt @ n).normalized()
            step = cell * k
            for i in range(math.floor(lo[axis] / step) + 1, math.ceil(hi[axis] / step)):
                c = Vector(lo)
                c[axis] = i * step
                if c[axis] - lo[axis] < 0.05 or hi[axis] - c[axis] < 0.05:
                    continue
                r = bmesh.ops.bisect_plane(bm, geom=[g for g in geom if g.is_valid], dist=1e-5,
                                           plane_co=Mi @ c, plane_no=nl)
                geom = set(g for g in r["geom"] if g.is_valid)
                cuts += [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        cuts = [e for e in cuts if e.is_valid and len(e.link_faces) == 2]
        if cuts:
            bmesh.ops.split_edges(bm, edges=cuts)
        bm.to_mesh(o.data)
        tiles += len(bm.faces)
        bm.free()
        o.data.update()
    log(f"dice: {tiles} faces on big-faced objects")


def mesh_arrays(o):
    me = o.data
    n, nv, nl = len(me.polygons), len(me.vertices), len(me.loops)
    M = np.array(o.matrix_world)
    A, t = M[:3, :3], M[:3, 3]
    co = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) @ A.T + t
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    nrm = np.empty(n * 3, np.float64)
    me.polygons.foreach_get("normal", nrm)
    An = np.linalg.inv(A).T
    nrm = nrm.reshape(-1, 3) @ An.T
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    poly = np.repeat(np.arange(n), lt)
    cen = np.zeros((n, 3))
    np.add.at(cen, poly, co[lv])
    cen /= lt[:, None]
    nxt = np.arange(nl) + 1
    nxt[ls + lt - 1] = ls
    elen = np.linalg.norm(co[lv[nxt]] - co[lv], axis=1)
    maxe = np.maximum.reduceat(elen, ls) if n else np.zeros(0)
    rad = np.maximum.reduceat(np.linalg.norm(co[lv] - cen[poly], axis=1), ls) if n else np.zeros(0)
    # polygon area via fan triangulation
    area = np.zeros(n)
    first = co[lv[ls]][poly]
    a2 = np.linalg.norm(np.cross(co[lv] - first, co[lv[nxt]] - first), axis=1) * 0.5
    np.add.at(area, poly, a2)
    return dict(co=co, lv=lv, ls=ls, lt=lt, nrm=nrm, cen=cen, maxe=maxe, rad=rad, area=area, poly=poly)


def frustum_hits(cen, rad, p):
    q = cen - np.array(p["pos"])
    f, r, u = (np.array(p[k]) for k in ("fwd", "right", "up"))
    z = q @ f
    ok = z > -rad
    for axis, tn in ((r, p["tan_h"]), (u, p["tan_v"])):
        for sgn in (1, -1):
            pn = tn * f - sgn * axis
            pn /= np.linalg.norm(pn)
            ok &= q @ pn > -rad
    return ok


def needs_texels(o):
    """Per-face colour on shared vertices (welded voxels) or image textures can't live in vertex colours."""
    a = o.data.attributes.get("vcol")
    if a is not None and a.domain == "CORNER":
        return True
    for m in o.data.materials:
        if m and m.node_tree and any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes):
            return True
    return False


def classify_and_cull(objs, poses, keys):
    """Return per-object (kind, keep mask, flip mask)."""
    data = {o.name: mesh_arrays(o) for o in objs}
    # global BVH over all interior faces (for back-facing candidates)
    verts, polys, owner = [], [], []
    off = 0
    for o in objs:
        d = data[o.name]
        verts.append(d["co"])
        for i in range(len(d["ls"])):
            s0, n = d["ls"][i], d["lt"][i]
            polys.append([int(v) + off for v in d["lv"][s0:s0 + n]])
        owner.append((o.name, len(polys) - len(d["ls"])))
        off += len(d["co"])
    bvh = BVHTree.FromPolygons(np.concatenate(verts).tolist(), polys, all_triangles=False, epsilon=0.0)
    base = {name: start for name, start in owner}
    res = {}
    stats = dict(faces=0, kept=0, flipped=0)
    for o in objs:
        d = data[o.name]
        n = len(d["ls"])
        if n == 0:
            res[o.name] = ("occ", np.zeros(0, bool), np.zeros(0, bool))
            continue
        front = np.zeros(n, bool)
        seen_back = np.zeros(n, bool)
        for p in poses:
            inf = frustum_hits(d["cen"], d["rad"], p)
            facing = ((np.array(p["pos"]) - d["cen"]) * d["nrm"]).sum(1)
            front |= inf & (facing > 0)
            seen_back |= inf & (facing <= 0)
        flip = np.zeros(n, bool)
        cand = np.nonzero(seen_back & ~front)[0]
        b0 = base[o.name]
        for i in cand:
            s0, k = d["ls"][i], d["lt"][i]
            vs = d["co"][d["lv"][s0:s0 + k]]
            c = d["cen"][i]
            pts = [c] + [c + (v - c) * 0.7 for v in vs[:4]]
            hit = False
            for p in keys:
                P = Vector(p["pos"])
                for pt in pts:
                    v = Vector(pt) - P
                    dist = v.length
                    loc, _, idx, hd = bvh.ray_cast(P, v / dist, dist + 1e-3)
                    if idx is not None and idx == b0 + i:
                        hit = True
                        break
                if hit:
                    break
            flip[i] = hit
        keep = front | flip
        w = d["area"].sum()
        edge = float((d["maxe"] * d["area"]).sum() / w) if w > 0 else 0.0
        kind = "vertex" if edge < VERTEX_EDGE and not needs_texels(o) else "atlas"
        if not keep.any():
            kind = "occ"
        res[o.name] = (kind, keep, flip)
        stats["faces"] += n
        stats["kept"] += int(keep.sum())
        stats["flipped"] += int(flip.sum())
    log("cull", stats)
    return res, bvh


def split_occluders(objs, res, col):
    occ_col = bpy.data.collections.new("occluders")
    bpy.context.scene.collection.children.link(occ_col)
    live = []
    for o in objs:
        kind, keep, flip = res[o.name]
        if kind == "occ":
            for c in o.users_collection:
                c.objects.unlink(o)
            occ_col.objects.link(o)
            continue
        if not keep.all():
            occ = o.copy()
            occ.data = o.data.copy()
            occ.name = f"occ_{o.name}"
            occ_col.objects.link(occ)
            bm = bmesh.new()
            bm.from_mesh(occ.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(keep)[0]], context="FACES")
            bm.to_mesh(occ.data)
            bm.free()
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        fl = [bm.faces[i] for i in np.nonzero(flip)[0]]
        if fl:
            bmesh.ops.reverse_faces(bm, faces=fl)
        drop = [bm.faces[i] for i in np.nonzero(~keep)[0]]
        if drop:
            bmesh.ops.delete(bm, geom=drop, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
        o["kind"] = kind
        live.append(o)
    return live, occ_col


# ---------------------------------------------------------------- merge

TEX_NODES = {"TEX_NOISE", "TEX_WAVE", "TEX_BRICK", "TEX_VORONOI", "TEX_GRADIENT", "TEX_MAGIC", "TEX_CHECKER",
             "TEX_MUSGRAVE", "TEX_WHITE_NOISE", "TEX_GABOR"}


def freeze_material(m):
    """Point Generated/Object texture coordinates at baked attributes so meshes can be merged."""
    nt = m.node_tree

    def attr(name):
        n = nt.nodes.new("ShaderNodeAttribute")
        n.attribute_name = name
        n.attribute_type = "GEOMETRY"
        return n

    for n in list(nt.nodes):
        if n.type == "TEX_COORD":
            for out, an in (("Generated", "__gen"), ("Object", "__obj")):
                links = [l for l in nt.links if l.from_node == n and l.from_socket.name == out]
                if links:
                    a = attr(an)
                    for l in links:
                        nt.links.new(a.outputs["Vector"], l.to_socket)
        elif n.type in TEX_NODES:
            v = n.inputs.get("Vector")
            if v is not None and not v.is_linked:
                nt.links.new(attr("__gen").outputs["Vector"], v)


def freeze_object(o, hs_index):
    me = o.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    loc = np.array(me.texspace_location, np.float32)
    size = np.array(me.texspace_size, np.float32)
    size[np.abs(size) < 1e-6] = 1.0
    gen = (co - loc) / (2 * size) + 0.5
    for name, val in (("__gen", gen), ("__obj", co)):
        a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", val.astype(np.float32).ravel())
    v = me.attributes.get("vcol")
    if v is not None and v.domain == "POINT":
        c = np.empty(nv * 4, np.float32)
        v.data.foreach_get("color", c)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        cc = c.reshape(-1, 4)[lv]
        me.attributes.remove(v)
        v = me.attributes.new("vcol", "FLOAT_COLOR", "CORNER")
        v.data.foreach_set("color", cc.ravel())
    for name, val in (("__hs", hs_index), ("__det", int(bool(o.get("detail")))),
                      ("__tex", int(round(100 * o.get("texel", 1.0))))):
        a = me.attributes.get(name) or me.attributes.new(name, "INT", "FACE")
        a.data.foreach_set("value", np.full(len(me.polygons), val, np.int32))
    me.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)


def merge(objs, name):
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    g = objs[0]
    g.name = name
    g.data.name = name
    return g


def merge_all(live, occ_col):
    ids = BUILD.SCENE.HOTSPOTS
    mats = {s.material for o in list(live) + list(occ_col.objects) for s in o.material_slots if s.material}
    for m in mats:
        if m.use_nodes:
            freeze_material(m)
    for o in list(live) + list(occ_col.objects):
        hs = o.get("hs", "")
        freeze_object(o, ids.index(hs) + 1 if hs in ids else 0)
    vs = [o for o in live if o["kind"] == "vertex"]
    at = [o for o in live if o["kind"] == "atlas"]
    vert = merge(vs, "room_vertex")
    atl = merge(at, "room_atlas")
    occ = [o for o in occ_col.objects if o.type == "MESH" and len(o.data.polygons)]
    if len(occ) > 1:
        merge(occ, "room_occluders")
    log(f"merged: vertex {len(vert.data.vertices)} verts, atlas {len(atl.data.polygons)} faces")
    return vert, atl


# ---------------------------------------------------------------- atlas uv

def nearest_visible(pts, poses, bvh):
    """Closest camera distance from which any of the sample points is unoccluded and inside the frustum."""
    cand = []
    for p in poses:
        P = p["pos"]
        for pt, n in pts:
            v = pt - P
            if n.dot(v) >= 0:
                continue
            z = v.dot(p["fwd"])
            if z <= 0.05:
                continue
            if abs(v.dot(p["right"])) > p["tan_h"] * z or abs(v.dot(p["up"])) > p["tan_v"] * z:
                continue
            cand.append((v.length, P, pt))
    cand.sort(key=lambda c: c[0])
    for dist, P, pt in cand:
        loc, _, idx, hd = bvh.ray_cast(P, (pt - P) / dist, dist + 0.01)
        if idx is None or hd > dist - 0.004:
            return dist
    return None


def unwrap(atlas_objs, poses, density, force, bvh):
    for o in atlas_objs:
        me = o.data
        lm = me.uv_layers.get("LM") or me.uv_layers.new(name="LM", do_init=False)
        for uv in me.uv_layers:
            uv.active_render = uv.name != "LM"
        me.uv_layers.active = lm
    vl = bpy.context.view_layer
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in atlas_objs:
        o.select_set(True)
    vl.objects.active = atlas_objs[0]
    t0 = time.time()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"smart_project {time.time() - t0:.1f}s")
    need = 0.0
    islands_total = 0
    hidden = 0
    per_obj = {}
    by_tex = {}
    for o in atlas_objs:
        need_before = need
        M = o.matrix_world
        Mn = M.to_3x3().inverted().transposed()
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uv = bm.loops.layers.uv["LM"]
        det = bm.faces.layers.int.get("__det")
        tex = bm.faces.layers.int.get("__tex")
        isl = bmesh_linked_uv_islands(bm, uv)
        islands_total += len(isl)
        for faces in isl:
            bonus = 1.4 if det is not None and any(f[det] for f in faces) else 1.0
            if tex is not None:
                bonus *= max(f[tex] for f in faces) / 100.0
            a3 = 0.0
            auv = 0.0
            for f in faces:
                a3 += f.calc_area()
                us = [l[uv].uv for l in f.loops]
                for k in range(1, len(us) - 1):
                    auv += abs((us[k] - us[0]).cross(us[k + 1] - us[0])) * 0.5
            if a3 <= 0 or auv <= 0:
                continue
            pts = []
            for f in sorted(faces, key=lambda f: -f.calc_area())[:10]:
                c = f.calc_center_median()
                nw = (Mn @ f.normal).normalized()
                pts.append((M @ c, nw))
                if len(faces) <= 2:
                    for v in f.verts:
                        pts.append((M @ (c + (v.co - c) * 0.8), nw))
            d = nearest_visible(pts, poses, bvh)
            if d is None:
                hidden += 1
                rho = 15.0
            else:
                rho = TEXELS_AT_1M * density * bonus / max(d, 0.6)
            # world scale factor (objects keep their matrix until export)
            s3 = abs(M.to_3x3().determinant()) ** (2 / 3)
            a3w = a3 * s3
            need += a3w * rho * rho
            cls = max(f[tex] for f in faces) if tex is not None else 100
            by_tex[cls] = by_tex.get(cls, 0.0) + a3w * rho * rho
            k = math.sqrt(a3w / auv) * rho / 1000.0
            uc = Vector((0.0, 0.0))
            n = 0
            for f in faces:
                for l in f.loops:
                    uc += l[uv].uv
                    n += 1
            uc /= n
            for f in faces:
                for l in f.loops:
                    l[uv].uv = uc + (l[uv].uv - uc) * k
        bm.to_mesh(o.data)
        bm.free()
        per_obj[o.name] = need - need_before
    top = sorted(per_obj.items(), key=lambda x: -x[1])[:16]
    log(f"atlas hidden islands={hidden}; top:", [(n, round(v / 1e6, 2)) for n, v in top],
        "by texel %:", {k: round(v / 1e6, 2) for k, v in sorted(by_tex.items())})
    eff = 0.68
    res = force or int(min(MAX_ATLAS, max(512, 256 * math.ceil(math.sqrt(need / eff) / 256))))
    log(f"atlas: islands={islands_total} texels_needed={need / 1e6:.1f}M -> size {res} "
        f"(achieved density {min(1.0, math.sqrt(res * res * eff / need)):.2f}x)")
    for o in atlas_objs:
        o.select_set(True)
    t0 = time.time()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    margin = 2.5 / res
    try:
        bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="CARDINAL", scale=True,
                                merge_overlap=False, margin_method="FRACTION", margin=margin, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    cover = 0.0
    for o in atlas_objs:
        uvs = np.empty(len(o.data.loops) * 2, np.float32)
        o.data.uv_layers["LM"].data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        for p in o.data.polygons:
            u = uvs[p.loop_start:p.loop_start + p.loop_total]
            x, y = u[:, 0], u[:, 1]
            cover += 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    log(f"pack {time.time() - t0:.1f}s, coverage {cover:.2f}, density {math.sqrt(cover * res * res / need):.2f}x")
    return res


# ---------------------------------------------------------------- bake

def prep_materials(objs, img):
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    for m in mats:
        nt = m.node_tree
        node = nt.nodes.get("__bake")
        if node is None:
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = "__bake"
        node.image = img
        nt.nodes.active = node


def diffuse_only():
    """Glossy is filtered out of the bake, but specular/coat layers would still take their energy from
    the diffuse below; drop them so the bake carries the full diffuse albedo. Metals have no diffuse
    lobe; bake them as their tinted dielectric look."""
    for m in bpy.data.materials:
        if m.name.startswith("ext_") or not m.node_tree:
            continue
        p = m.node_tree.nodes.get("Principled BSDF")
        if p is None:
            continue
        for key in ("Metallic", "Specular IOR Level", "Coat Weight"):
            s = p.inputs[key]
            if not s.is_linked:
                s.default_value = 0.0


def select_only(objs):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def bake_vertex(objs, samples):
    for o in objs:
        me = o.data
        a = me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        me.color_attributes.active_color = a
    select_only(objs)
    s = bpy.context.scene
    s.cycles.samples = samples
    s.render.bake.target = "VERTEX_COLORS"
    t0 = time.time()
    bpy.ops.object.bake(type="COMBINED", pass_filter={"EMIT", "DIRECT", "INDIRECT", "DIFFUSE", "TRANSMISSION"},
                        target="VERTEX_COLORS", use_clear=True)
    log(f"vertex bake {time.time() - t0:.1f}s ({sum(len(o.data.vertices) for o in objs)} verts)")


def bake_atlas(objs, res, samples):
    s = bpy.context.scene
    imgs = {}
    for k in ("rad", "alb", "nrm"):
        img = bpy.data.images.new(f"atlas_{k}", res, res, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color" if k == "nrm" else "Linear Rec.709"
        imgs[k] = img
    select_only(objs)
    s.render.bake.target = "IMAGE_TEXTURES"
    s.render.bake.margin = 4
    s.render.bake.margin_type = "EXTEND"
    for k, typ, filt, spp in (("alb", "DIFFUSE", {"COLOR"}, 4), ("nrm", "NORMAL", set(), 4),
                              ("rad", "COMBINED", {"EMIT", "DIRECT", "INDIRECT", "DIFFUSE", "TRANSMISSION"}, samples)):
        prep_materials(objs, imgs[k])
        s.cycles.samples = spp
        t0 = time.time()
        kw = dict(type=typ, target="IMAGE_TEXTURES", uv_layer="LM", margin=4, margin_type="EXTEND", use_clear=True)
        if filt:
            kw["pass_filter"] = filt
        if typ == "NORMAL":
            kw["normal_space"] = "OBJECT"
        bpy.ops.object.bake(**kw)
        log(f"atlas {k} bake {time.time() - t0:.1f}s")
        imgs[k].filepath_raw = str(OUT / f"atlas_{k}.exr")
        imgs[k].file_format = "OPEN_EXR"
        imgs[k].save()
    return imgs


def denoise(imgs, res):
    """OIDN through a compositor-only render (no render layer node, so nothing gets ray traced)."""
    s = bpy.context.scene
    t = bpy.data.node_groups.new("denoise", "CompositorNodeTree")
    t.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes = {}
    for k in ("rad", "alb", "nrm"):
        n = t.nodes.new("CompositorNodeImage")
        n.image = imgs[k]
        nodes[k] = n
    dn = t.nodes.new("CompositorNodeDenoise")
    try:
        dn.prefilter = "ACCURATE"
    except Exception:  # noqa: BLE001
        pass
    try:
        dn.inputs["HDR"].default_value = True
    except Exception:  # noqa: BLE001
        try:
            dn.use_hdr = True
        except Exception:  # noqa: BLE001
            pass
    out = t.nodes.new("NodeGroupOutput")
    t.links.new(nodes["rad"].outputs["Image"], dn.inputs["Image"])
    t.links.new(nodes["alb"].outputs["Image"], dn.inputs["Albedo"])
    t.links.new(nodes["nrm"].outputs["Image"], dn.inputs["Normal"])
    t.links.new(dn.outputs["Image"], out.inputs[0])
    s.compositing_node_group = t
    s.render.use_compositing = True
    s.render.resolution_x = res
    s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "OPEN_EXR"
    s.render.image_settings.color_depth = "32"
    s.render.image_settings.color_mode = "RGB"
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0
    if hasattr(s.view_settings, "use_white_balance"):
        s.view_settings.use_white_balance = False
    s.render.filepath = str(OUT / "atlas_den.exr")
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"denoise {time.time() - t0:.1f}s")
    img = bpy.data.images.load(str(OUT / "atlas_den.exr"))
    return img


def image_array(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


def save_png(arr, path, name):
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), arr.dtype)], axis=2)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()


# ---------------------------------------------------------------- export

def export(vert, atl, anchors, res):
    """Two meshes: COLOR_0.rgb = encoded radiance (vertex mesh), TEXCOORD_0 = atlas uv; COLOR_0.a = hotspot id."""
    for g, kind in ((vert, "vertex"), (atl, "atlas")):
        me = g.data
        me.materials.clear()
        hs = np.empty(len(me.polygons), np.int32)
        me.attributes["__hs"].data.foreach_get("value", hs)
        lt = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("loop_total", lt)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        vid = np.zeros(len(me.vertices), np.float32)
        vid[lv] = np.repeat(hs, lt)
        if kind == "vertex":
            # Corner bake, then each vertex takes the corner of its largest face: averaging in the
            # chamfer corners would darken every voxel top.
            cc = me.color_attributes["Col"]
            corner = np.empty(len(cc.data) * 4, np.float32)
            cc.data.foreach_get("color", corner)
            corner = corner.reshape(-1, 4)
            area = np.empty(len(me.polygons), np.float32)
            me.polygons.foreach_get("area", area)
            la = np.repeat(area, lt)
            best = np.zeros(len(me.vertices), np.float32)
            np.maximum.at(best, lv, la)
            pick = la >= best[lv]
            c = np.ones((len(me.vertices), 4), np.float32)
            c[lv[pick], :3] = encode(corner[pick, :3])
            me.color_attributes.remove(cc)
            col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        else:
            col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
            c = np.ones((len(me.vertices), 4), np.float32)
        c[:, 3] = vid / 255.0
        col.data.foreach_set("color", c.ravel())
        for a in [a.name for a in me.color_attributes if a.name != "Col"]:
            me.color_attributes.remove(me.color_attributes[a])
        me.color_attributes.active_color = me.color_attributes["Col"]
        for uv in [u.name for u in me.uv_layers if not (kind == "atlas" and u.name == "LM")]:
            me.uv_layers.remove(me.uv_layers[uv])
        for a in [a.name for a in me.attributes if a.name.startswith("__")]:
            me.attributes.remove(me.attributes[a])
        g["kind"] = kind
    select_only([vert, atl])
    glb = OUT / "room.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb), export_format="GLB", use_selection=True, export_apply=False, export_normals=False,
        export_texcoords=True, export_materials="NONE", export_vertex_color="ACTIVE", export_all_vertex_colors=False,
        export_active_vertex_color_when_no_material=True, export_extras=True, export_yup=True,
        export_cameras=False, export_lights=False, export_tangents=False)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (vert, atl))
    log(f"export {glb} {glb.stat().st_size / 1e6:.1f} MB, {tris} tris")

    cams = {}
    for name in ORBIT:
        f = cam_frame(name)
        cams[name] = {
            "pos": to_gltf(f["pos"]), "fwd": to_gltf(f["fwd"]), "up": to_gltf(f["up"]),
            "vfov": math.degrees(2 * math.atan(f["tan_v"])), "aspect": ASPECT[name], **ORBIT[name],
        }
    S = BUILD.SCENE
    boxes = {k: (a["min"], a["max"], a["anchor"]) for k, a in anchors.items()}
    boxes.update(S.extra_hotspots())
    hs = {}
    for k, (mn, mx, anchor) in boxes.items():
        lo, hi = np.array(to_gltf(mn)), np.array(to_gltf(mx))
        hs[k] = {"min": np.minimum(lo, hi).tolist(), "max": np.maximum(lo, hi).tolist(), "anchor": to_gltf(anchor)}
    g = S.GRADE
    manifest = {
        "scene": S.__name__.removeprefix("scene_"), "atlas": res, "encodeK": ENC_K, "lut": {"n": LUT_N, "lo": LUT_LO, "hi": LUT_HI},
        "grade": {"bloom": g["bloom"], "tint": g["glare_tint"], "gain": g["gain"], "lift": g["lift"]},
        "planes": list(S.PLANES), "mirrorClear": list(S.MIRROR_CLEAR),
        "cameras": cams, "hotspots": hs, "ids": S.HOTSPOTS,
        "markers": {k: to_gltf(v) for k, v in MARKERS.items()},
    }
    (OUT / "room.json").write_text(json.dumps(manifest, indent=1))
    log("manifest", OUT / "room.json")


# ---------------------------------------------------------------- stages

def stage_bake(args, plan_only=False):
    t0 = time.time()
    build_scene(args.scene)
    MARKERS.update(BUILD.SCENE.markers())
    poses = sample_poses()
    objs, anchors = realize()
    log(f"realized {len(objs)} objects in {time.time() - t0:.1f}s")
    dice(objs)
    res, bvh = classify_and_cull(objs, poses, key_poses())
    kinds = {}
    for o in objs:
        k = res[o.name][0]
        kinds[k] = kinds.get(k, 0) + 1
    log("kinds", kinds)
    live, occ_col = split_occluders(objs, res, None)
    vert, atl = merge_all(live, occ_col)
    size = unwrap([atl], poses, args.density, args.atlas, bvh)
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    if plan_only:
        log(f"plan done {time.time() - t0:.1f}s")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    diffuse_only()
    bake_vertex([vert], args.vsamples)
    imgs = bake_atlas([atl], size, args.samples)
    den = denoise(imgs, size)
    save_png(encode(image_array(den)[..., :3]), OUT / "atlas.png", "atlas_enc")
    log("atlas.png written")
    export(vert, atl, anchors, size)
    log(f"bake done {time.time() - t0:.1f}s")


def stage_backdrop(args):
    """Exterior seen through the back window, rendered from the desktop camera into a linear EXR."""
    s = build_scene(args.scene, args.samples)
    bd = BUILD.SCENE.BACKDROP
    for o in s.objects:
        if o.type == "MESH" and not in_exterior(o):
            o.hide_render = True
    # The exterior gets its own art-directed light; the room keeps its own sun.
    bd["light"](s)
    f = cam_frame("desktop")
    fwd = (bd["target"] - f["pos"]).normalized()
    hfov, aspect = bd["hfov"], bd["aspect"]
    c = bpy.data.cameras.new("cam_backdrop")
    c.sensor_fit = "HORIZONTAL"
    c.sensor_width = 36
    c.lens = 18 / math.tan(math.radians(hfov / 2))
    c.clip_start = 0.5
    c.clip_end = 5000
    o = bpy.data.objects.new("cam_backdrop", c)
    s.collection.objects.link(o)
    o.location = f["pos"]
    o.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
    s.camera = o
    bpy.context.view_layer.update()
    W = args.res
    s.render.resolution_x = W
    s.render.resolution_y = round(W / aspect)
    s.cycles.samples = args.samples
    s.render.image_settings.file_format = "OPEN_EXR"
    s.render.image_settings.color_depth = "16"
    s.render.image_settings.color_mode = "RGB"
    s.render.use_compositing = False
    OUT.mkdir(parents=True, exist_ok=True)
    s.render.filepath = str(OUT / "backdrop.exr")
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"backdrop render {time.time() - t0:.1f}s")
    img = bpy.data.images.load(str(OUT / "backdrop.exr"))
    save_png(encode(image_array(img)[..., :3]), OUT / "backdrop.png", "bd_enc")
    m = o.matrix_world.to_3x3()
    meta = {
        "pos": to_gltf(o.location), "fwd": to_gltf(m @ Vector((0, 0, -1))), "up": to_gltf(m @ Vector((0, 1, 0))),
        "right": to_gltf(m @ Vector((1, 0, 0))), "hfov": hfov, "aspect": aspect, "dist": bd.get("dist", 40.0),
    }
    (OUT / "backdrop.json").write_text(json.dumps(meta, indent=1))
    log("backdrop written")


def stage_lut(args):
    """Scene-linear -> display LUT carrying exposure, white balance, AgX and the look (no compositor effects)."""
    s = build_scene(args.scene)
    N = LUT_N
    v = 2.0 ** (LUT_LO + np.linspace(0, 1, N) * (LUT_HI - LUT_LO))
    v[0] = 0.0
    # strip layout: x = b * N + r, y = g
    r = np.tile(v, N)[None, :].repeat(N, 0)
    b = np.repeat(v, N)[None, :].repeat(N, 0)
    g = v[:, None].repeat(N * N, 1)
    arr = np.stack([r, g, b, np.ones_like(r)], -1).astype(np.float32)
    img = bpy.data.images.new("lut", N * N, N, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709"
    img.pixels.foreach_set(arr.ravel())
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_depth = "16"
    s.render.image_settings.color_mode = "RGB"
    OUT.mkdir(parents=True, exist_ok=True)
    img.save_render(str(OUT / "lut.png"), scene=s)
    log("lut written", s.view_settings.view_transform, s.view_settings.look, s.view_settings.exposure)


def main():
    global OUT
    args = parse()
    OUT = OUT / args.scene
    if args.stage in ("plan", "bake"):
        stage_bake(args, plan_only=args.stage == "plan")
    elif args.stage == "backdrop":
        stage_backdrop(args)
    elif args.stage == "lut":
        stage_lut(args)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
