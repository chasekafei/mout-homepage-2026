"""Build and render the MouT.me creation room.

Usage (from repo root):
    Blender -b --factory-startup --python tools/scene/build.py -- \
        --mode preview|final|mask|depth --cam desktop|mobile [--res 1280] [--samples 64] [--out path]
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

import bpy  # noqa: E402

import blib as B  # noqa: E402
import room  # noqa: E402

ROOT = HERE.parents[1]


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="preview")
    ap.add_argument("--cam", default="desktop")
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--out", default="")
    ap.add_argument("--blend", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--campos", default="")
    ap.add_argument("--target", default="")
    ap.add_argument("--exposure", type=float, default=-0.8)
    return ap.parse_args(argv)


def setup_render(args):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    s.cycles.device = "GPU"
    s.cycles.samples = args.samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.02
    s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
    s.cycles.max_bounces = 8
    s.cycles.diffuse_bounces = 4
    s.cycles.glossy_bounces = 3
    s.cycles.transmission_bounces = 4
    s.cycles.sample_clamp_indirect = 8.0
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.cycles.blur_glossy = 1.0
    ratio = 16 / 9 if args.cam == "desktop" else 9 / 16
    if ratio >= 1:
        s.render.resolution_x = args.res
        s.render.resolution_y = round(args.res / ratio)
    else:
        s.render.resolution_y = args.res
        s.render.resolution_x = round(args.res * ratio)
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    s.render.image_settings.color_depth = "8"
    vs = s.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    vs.exposure = args.exposure
    if hasattr(vs, "use_white_balance"):
        vs.use_white_balance = True
        vs.white_balance_temperature = 7000
        vs.white_balance_tint = 4
    s.render.film_transparent = False


def setup_compositor(bloom=0.45):
    """Soft bloom on the sunlit highlights plus a gentle warm grade (beauty pass only)."""
    s = bpy.context.scene
    t = bpy.data.node_groups.new("beauty_comp", "CompositorNodeTree")
    t.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = t.nodes.new("CompositorNodeRLayers")
    gl = t.nodes.new("CompositorNodeGlare")
    for key, val in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", 1.2), ("Smoothness", 0.6),
                     ("Strength", bloom), ("Size", 0.7), ("Saturation", 1.1)):
        try:
            gl.inputs[key].default_value = val
        except Exception as e:  # noqa: BLE001
            print("glare input", key, e)
    try:
        gl.inputs["Tint"].default_value = (1.0, 0.86, 0.7, 1.0)
    except Exception:
        pass
    cb = t.nodes.new("CompositorNodeColorBalance")
    cols = [i for i in cb.inputs if i.type == "RGBA"]
    named = {i.name: i for i in cols}
    if "Gain" in named:
        named["Gain"].default_value = (1.03, 1.0, 0.95, 1)
    if "Lift" in named:
        named["Lift"].default_value = (1.015, 1.0, 0.985, 1)
    out = t.nodes.new("NodeGroupOutput")
    t.links.new(rl.outputs["Image"], gl.inputs["Image"])
    t.links.new(gl.outputs["Image"], cb.inputs["Image"])
    t.links.new(cb.outputs["Image"], out.inputs[0])
    s.compositing_node_group = t
    s.render.use_compositing = True


def build(args):
    B.reset()
    B.mat_voxel("voxel")
    room.build_shell()
    room.build_exterior()
    room.build_world()
    room.build_lights()
    cams = room.build_cameras()
    import props
    props.build_all()
    s = bpy.context.scene
    if args.cam == "top":
        c = bpy.data.cameras.new("cam_top")
        c.type = "ORTHO"
        c.ortho_scale = 11
        o = bpy.data.objects.new("cam_top", c)
        bpy.context.scene.collection.objects.link(o)
        o.location = (0.6, 1.2, 3.3)
        s.camera = o
        return cams
    s.camera = cams[f"cam_{args.cam}"]
    if args.campos:
        c = bpy.data.cameras.new("cam_dbg")
        c.lens = 28
        o = bpy.data.objects.new("cam_dbg", c)
        bpy.context.scene.collection.objects.link(o)
        o.location = [float(v) for v in args.campos.split(",")]
        room.look_at(o, [float(v) for v in args.target.split(",")])
        s.camera = o
    return cams


# ------------------------------------------------------------------ passes

def override_mask():
    """Flat emission ID render: each hotspot object gets its id colour."""
    import props
    ids = props.HOTSPOTS
    m = bpy.data.materials.new("mask_override")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    for o in bpy.data.objects:
        hs = o.get("hs")
        p = o.parent
        while hs is None and p is not None:
            hs = p.get("hs")
            p = p.parent
        if hs is None and any(c.name == "exterior" for c in o.users_collection):
            hs = "window"
        if hs in ids:
            v = (ids.index(hs) + 1) * 16 / 255.0
            lin = v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            o.color = (lin, 0, 0, 1)
        else:
            o.color = (0, 0, 0, 1)
    vl = bpy.context.view_layer
    vl.material_override = m
    s = bpy.context.scene
    wnt = s.world.node_tree
    for l in list(wnt.links):
        if l.to_node.name == "Background":
            wnt.links.remove(l)
    wv = (ids.index("window") + 1) * 16 / 255.0
    wl = wv / 12.92 if wv <= 0.04045 else ((wv + 0.055) / 1.055) ** 2.4
    wnt.nodes["Background"].inputs["Color"].default_value = (wl, 0, 0, 1)
    wnt.nodes["Background"].inputs["Strength"].default_value = 1
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    s.cycles.samples = 1
    s.cycles.use_denoising = False
    s.cycles.use_adaptive_sampling = False
    s.cycles.filter_width = 0.01
    s.render.dither_intensity = 0
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0
    s.render.image_settings.color_mode = "RGB"
    for o in bpy.data.objects:
        if o.type == "CAMERA":
            o.data.dof.use_dof = False


def override_depth(near=0.5, far=14.0):
    m = bpy.data.materials.new("depth_override")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    cam = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = near
    mr.inputs["From Max"].default_value = far
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(cam.outputs["View Z Depth"], mr.inputs["Value"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mr.outputs[0], em.inputs["Strength"])
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    bpy.context.view_layer.material_override = m
    s = bpy.context.scene
    w = s.world.node_tree
    w.nodes["Background"].inputs["Strength"].default_value = 1
    for l in list(w.links):
        if l.to_node.name == "Background" and l.to_socket.name == "Color":
            w.links.remove(l)
    w.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    s.cycles.samples = 8
    s.cycles.use_denoising = False
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0
    s.render.image_settings.color_mode = "BW"
    s.render.dither_intensity = 0
    s.render.image_settings.color_depth = "16"
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
        if o.type == "CAMERA":
            o.data.dof.use_dof = False


def export_anchors(path: Path):
    """Project hotspot centres and bounds to normalised screen coords."""
    from bpy_extras.object_utils import world_to_camera_view
    import props
    s = bpy.context.scene
    cam = s.camera
    deps = bpy.context.evaluated_depsgraph_get()
    data = {}
    for o in bpy.data.objects:
        hs = o.get("hs")
        p = o.parent
        while hs is None and p is not None:
            hs = p.get("hs")
            p = p.parent
        if hs not in props.HOTSPOTS or o.type != "MESH":
            continue
        ev = o.evaluated_get(deps)
        mw = ev.matrix_world
        verts = ev.data.vertices
        step = max(1, len(verts) // 400)
        pts = [world_to_camera_view(s, cam, mw @ verts[i].co) for i in range(0, len(verts), step)]
        d = data.setdefault(hs, {"min": [1e9, 1e9], "max": [-1e9, -1e9]})
        for p_ in pts:
            x, y = p_.x, 1 - p_.y
            d["min"] = [min(d["min"][0], x), min(d["min"][1], y)]
            d["max"] = [max(d["max"][0], x), max(d["max"][1], y)]
    for hs, d in data.items():
        d["center"] = [(d["min"][0] + d["max"][0]) / 2, (d["min"][1] + d["max"][1]) / 2]
    path.write_text(json.dumps({"ids": props.HOTSPOTS, "anchors": data}, indent=1))


def report_stats(glb):
    dg = bpy.context.evaluated_depsgraph_get()
    rows, procedural = [], set()
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        ev.to_mesh_clear()
        col = ob.users_collection[0].name if ob.users_collection else "-"
        rows.append((tris, ob.name, col))
        for slot in ob.material_slots:
            m = slot.material
            if m and m.use_nodes and any(n.type in ("TEX_NOISE", "TEX_VORONOI", "TEX_WAVE", "TEX_MUSGRAVE", "ATTRIBUTE", "OBJECT_INFO") for n in m.node_tree.nodes):
                procedural.add(m.name)
    rows.sort(reverse=True)
    by_col = {}
    for t, _, c in rows:
        by_col[c] = by_col.get(c, 0) + t
    print(f"STATS objects={len(rows)} tris={sum(r[0] for r in rows)} materials={len(bpy.data.materials)} procedural={len(procedural)}")
    print("STATS by collection:", sorted(by_col.items(), key=lambda x: -x[1]))
    print("STATS top objects:", [(n, t) for t, n, _ in rows[:25]])
    print("STATS procedural materials:", sorted(procedural))
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_apply=True, export_lights=False, export_cameras=True)
    print(f"STATS glb {glb} {glb.stat().st_size / 1e6:.1f} MB")


def main():
    args = parse()
    t0 = time.time()
    build(args)
    setup_render(args)
    s = bpy.context.scene
    out = Path(args.out) if args.out else ROOT / ".cache" / "renders" / f"{args.mode}_{args.cam}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.mode in ("preview", "final"):
        setup_compositor()
    else:
        s.render.use_compositing = False
    if args.mode == "mask":
        override_mask()
    elif args.mode == "depth":
        override_depth()
    elif args.mode == "anchors":
        export_anchors(out.with_suffix(".json"))
        print("ANCHORS", out.with_suffix(".json"))
        return
    elif args.mode == "stats":
        report_stats(out.with_suffix(".glb"))
        return
    if args.only == "sun":
        s.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0
        bpy.data.objects["fill"].hide_render = True
    elif args.only == "nosun":
        bpy.data.objects["sun"].hide_render = True
    elif args.only == "sky":
        bpy.data.objects["sun"].hide_render = True
        bpy.data.objects["fill"].hide_render = True
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    s.render.filepath = str(out)
    print(f"BUILD {time.time() - t0:.1f}s, rendering {s.render.resolution_x}x{s.render.resolution_y}")
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_DONE {time.time() - t1:.1f}s -> {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
