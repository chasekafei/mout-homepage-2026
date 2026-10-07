"""此刻: a window seat in a corner café, morning sun from behind-right, the street outside."""
from __future__ import annotations

import bpy
from mathutils import Vector

import cafe
import room
import stage

HOTSPOTS = ["project", "thought", "me", "cat_shaojiu", "cat_xiaoba", "window"]

GRADE = {
    "exposure": -0.55, "temperature": 6300, "tint": 2,
    "bloom": 0.4, "glare_tint": (1.0, 0.92, 0.82), "gain": (1.02, 1.0, 0.97), "lift": (1.0, 1.0, 1.01),
}
PLANES = (0.0, stage.DESK_TOP)
MIRROR_CLEAR = (0.66, 0.64, 0.6)


def _backdrop_light(s):
    bpy.data.objects["fill"].hide_render = True


BACKDROP = {
    "hfov": 110.0, "aspect": 2.0, "dist": 80.0,
    "target": Vector((2.76, 9.61, 2.47)),
    "light": _backdrop_light,
}


def build():
    import street
    cafe.build_all()
    street.build()
    room.build_world(sun_dir=cafe.SUN_DIR, cam_sky_gain=1.3, amb_sky=0.3)
    cafe.build_lights()


def markers():
    return {}


def extra_hotspots():
    lo = (cafe.CORNER.x, cafe.GLASS_Y, cafe.SILL_Z)
    hi = (cafe.RIGHT_X, cafe.OUT_Y, cafe.HEAD_Z)
    return {"window": (lo, hi, ((cafe.CORNER.x + cafe.RIGHT_X) / 2, cafe.GLASS_Y, 1.9))}
