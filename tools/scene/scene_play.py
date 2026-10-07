"""游戏: the game room after school; a CRT straight ahead, the archive, handhelds and an arcade around it."""
from __future__ import annotations

import bpy
from mathutils import Vector

import gameroom as G
import nightcity
import stage

HOTSPOTS = ["tv", "gba", "archive", "handhelds", "arcade", "me", "cat_shaojiu", "cat_xiaoba", "window"]

GRADE = {
    "exposure": 0.1, "temperature": 6200, "tint": 2,
    "bloom": 0.5, "glare_tint": (1.0, 0.86, 0.74), "gain": (1.02, 1.0, 0.97), "lift": (1.0, 1.0, 1.01),
}
PLANES = (0.0, G.TABLE[4])
MIRROR_CLEAR = (0.55, 0.5, 0.46)


def _backdrop_light(s):
    bpy.data.objects["fill"].hide_render = True


BACKDROP = {
    "hfov": 80.0, "aspect": 1.2, "dist": 60.0,
    "target": nightcity.desk_to_world(G.LEFT_X - G.WALL_T, (G.WIN_Y0 + G.WIN_Y1) / 2, 1.5),
    "light": _backdrop_light,
}


def build():
    G.build_all()
    nightcity.build(seed=12, style="dusk", sky_disc=(G.SUN_DIR(), "#ffd9a0", 12.0, 30))
    nightcity.build_world("dusk")
    G.build_lights()


def markers():
    return {}


def extra_hotspots():
    w = nightcity.desk_to_world
    pts = [w(x, y, z) for x in (G.LEFT_X - G.WALL_T, G.LEFT_X) for y in (G.WIN_Y0, G.WIN_Y1) for z in (G.WIN_Z0, G.WIN_Z1)]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return {"window": (tuple(lo), tuple(hi), tuple(w(G.LEFT_X, (G.WIN_Y0 + G.WIN_Y1) / 2, 1.45)))}
