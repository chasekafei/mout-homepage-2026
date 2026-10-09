"""出发: behind the wheel of the Model Y; the windscreen and the side window frame whichever road he is on.

The cabin is the same for every destination. ``DEST`` (environment) picks the road outside, its sky and its
sun; the default is 名古屋. A destination with a painted view (tools/scene/paint.py -> paint_radiance.py) shows
it on the backdrop plane instead of the modelled road.
"""
from __future__ import annotations

import os
from pathlib import Path

import bpy
from mathutils import Vector

import car as C
import nightcity
import dests

DEST = os.environ.get("DEST", "nagoya")
if DEST not in dests.DESTS:
    raise SystemExit(f"unknown destination {DEST!r}; expected one of {tuple(dests.DESTS)}")
D = dests.DESTS[DEST]

HOTSPOTS = ["nav", "pingpong", "cinema", "passport", "me", "cat_shaojiu", "cat_xiaoba", "window"]

GRADE = {
    "exposure": 0.0, "temperature": 6300, "tint": 2,
    "bloom": 0.4, "glare_tint": (1.0, 0.9, 0.8), "gain": (1.02, 1.0, 0.98), "lift": (1.0, 1.0, 1.01),
}
PLANES = (C.FLOOR, 0.575)


def _cam(name, desk_pos, pitch, lens):
    import stage
    return (name, tuple(nightcity.desk_to_world(*desk_pos)), stage.YAW, pitch, lens)


# Unlike the rooms, the road is ahead of him: both cameras sit behind his right shoulder and look down the
# lane, so the windscreen frames the destination and the centre screen sits mid-frame.
CAMERAS = [
    _cam("cam_desktop", (0.64, -1.0, 1.3), 5.0, 20.0),
    _cam("cam_mobile", (0.44, -0.82, 1.38), 15.0, 19.0),
]
MIRROR_CLEAR = (0.62, 0.7, 0.8)


def _backdrop_light(s):
    bpy.data.objects["fill"].hide_render = True


BACKDROP = {
    "hfov": 118.0, "aspect": 16 / 9, "dist": 60.0, "tag": DEST,
    "target": nightcity.desk_to_world(0.64, 40.0, 1.3),
    "light": _backdrop_light,
    # the cabin is baked once, under the Nagoya sky; at dusk and at night the viewer scales its radiance so it
    # sits in the light outside (linear RGB, per view)
    "cabin_gain": {"doha": (0.95, 0.74, 0.55), "changsha": (0.95, 0.78, 0.62), "harbin": (0.34, 0.42, 0.68)},
}


ENC_K = 0.6                   # must match bake.ENC_K (paint_radiance reads it from scene.json)
PAINTED = Path(__file__).resolve().parents[2] / ".cache" / "paint" / DEST / "radiance.png"


def build_painted():
    """The painted view (tools/scene/paint.py) on the backdrop plane, emitting the radiance it decodes to."""
    import math
    import blib as B

    pos, target = Vector(CAMERAS[0][1]), BACKDROP["target"]
    q = (target - pos).normalized().to_track_quat("-Z", "Y")
    fwd, right, up = q @ Vector((0, 0, -1)), q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0))
    d = BACKDROP["dist"]
    hw = d * math.tan(math.radians(BACKDROP["hfov"] / 2))
    hh = hw / BACKDROP["aspect"]
    c = pos + fwd * d
    me = bpy.data.meshes.new("painted")
    me.from_pydata([c + right * sx * hw + up * sy * hh for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))], [],
                   [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, (u, v) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    m = bpy.data.materials.new("painted")
    nt = m.node_tree
    nt.nodes.clear()
    img = bpy.data.images.load(str(PAINTED))
    img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    # e = sqrt(x / (x + K))  ->  x = K e^2 / (1 - e^2)
    sq = nt.nodes.new("ShaderNodeVectorMath")
    sq.operation = "MULTIPLY"
    nt.links.new(tex.outputs["Color"], sq.inputs[0])
    nt.links.new(tex.outputs["Color"], sq.inputs[1])
    one = nt.nodes.new("ShaderNodeVectorMath")
    one.operation = "SUBTRACT"
    one.inputs[0].default_value = (1.0005, 1.0005, 1.0005)
    nt.links.new(sq.outputs[0], one.inputs[1])
    div = nt.nodes.new("ShaderNodeVectorMath")
    div.operation = "DIVIDE"
    nt.links.new(sq.outputs[0], div.inputs[0])
    nt.links.new(one.outputs[0], div.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = ENC_K
    nt.links.new(div.outputs[0], em.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    me.materials.append(m)
    ob = bpy.data.objects.new("painted", me)
    B.link(ob)
    ob.visible_shadow = False
    return ob


def build():
    C.SCREEN_TEX = f"depart_screen_{DEST}.png"
    root = C.build_all()
    nightcity.S = nightcity.STYLES["dusk"]
    import blib as B
    B.use_collection("exterior")
    if PAINTED.exists():
        build_painted()
    else:
        D["build"](root)
    nightcity.build_world(D["sky"])
    C.build_lights(dests.sun_world(DEST), D["sun_strength"], D["sun_col"])


def markers():
    return {}


def _opening():
    """Windscreen plus the driver's side window, as desk-frame points."""
    pts = []
    for x in (C.L_X - 0.08, C.R_X + 0.08):
        for y in (C.DASH_Y1, C.BAR_Y):
            for z in (C.DASH_Z, C.ROOF):
                pts.append((x, y, z))
    for y in (C.B_PILLAR[1], C.DASH_Y0):
        for z in (C.SILL_Z, C.ROOF):
            pts.append((C.L_X - 0.08, y, z))
    return pts


def extra_hotspots():
    w = nightcity.desk_to_world
    pts = [w(*p) for p in _opening()]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return {"window": (tuple(lo), tuple(hi), tuple(w(-0.2, 1.3, 1.3)))}
