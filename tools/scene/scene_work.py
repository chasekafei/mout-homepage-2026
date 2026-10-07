"""工作: a home study late at night; the AI Agent he builds now, and every earlier industry wired into it."""
from __future__ import annotations

import bpy
from mathutils import Vector

import nightcity
import stage
import study

HOTSPOTS = ["agent", "social", "games", "brand", "gov", "me", "cat_shaojiu", "cat_xiaoba", "window"]

GRADE = {
    "exposure": 0.0, "temperature": 6500, "tint": 0,
    "bloom": 0.55, "glare_tint": (0.85, 1.0, 0.95), "gain": (0.99, 1.0, 1.02), "lift": (0.995, 1.0, 1.015),
}
PLANES = (0.0, stage.DESK_TOP)
MIRROR_CLEAR = (0.2, 0.21, 0.24)


def _backdrop_light(s):
    bpy.data.objects["fill"].hide_render = True


def _window(x, y, z):
    return nightcity.desk_to_world(x, y, z)


BACKDROP = {
    "hfov": 80.0, "aspect": 1.2, "dist": 60.0,
    "target": _window(study.LEFT_X - study.WALL_T, (study.WIN_Y0 + study.WIN_Y1) / 2, 1.5),
    "light": _backdrop_light,
}


def build():
    study.build_all()
    nightcity.build()
    nightcity.build_world("night")
    study.build_lights()


def markers():
    return {}


def extra_hotspots():
    pts = [_window(x, y, z) for x in (study.LEFT_X - study.WALL_T, study.LEFT_X) for y in (study.WIN_Y0, study.WIN_Y1)
           for z in (study.WIN_Z0, study.WIN_Z1)]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return {"window": (tuple(lo), tuple(hi), tuple(_window(study.LEFT_X, (study.WIN_Y0 + study.WIN_Y1) / 2, 1.9)))}
