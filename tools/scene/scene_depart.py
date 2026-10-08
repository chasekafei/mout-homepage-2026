"""出发: behind the wheel of the Model Y; the windscreen and the side window frame whichever road he is on.

The cabin is the same for every destination. ``DEST`` (environment) picks the road outside, its sky and its
sun; the default is 名古屋.
"""
from __future__ import annotations

import os

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
MIRROR_CLEAR = (0.62, 0.7, 0.8)


def _backdrop_light(s):
    bpy.data.objects["fill"].hide_render = True


BACKDROP = {
    "hfov": 118.0, "aspect": 1.7, "dist": 60.0, "tag": DEST,
    "target": nightcity.desk_to_world(C.L_X, C.DASH_Y1 + 0.4, 1.25),
    "light": _backdrop_light,
}


def build():
    root = C.build_all()
    nightcity.S = nightcity.STYLES["dusk"]
    import blib as B
    B.use_collection("exterior")
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
