"""创作: the creation room on the fifth floor, afternoon sun from the right."""
from __future__ import annotations

import bpy
from mathutils import Vector

import props
import room

HOTSPOTS = props.HOTSPOTS

GRADE = {
    "exposure": -0.8, "temperature": 7000, "tint": 4,
    "bloom": 0.45, "glare_tint": (1.0, 0.86, 0.7), "gain": (1.03, 1.0, 0.95), "lift": (1.015, 1.0, 0.985),
}
PLANES = (0.0, props.DESK_TOP)
MIRROR_CLEAR = (0.6, 0.57, 0.53)


def _backdrop_light(s):
    import exterior
    sun = bpy.data.objects["sun"]
    sun.rotation_euler = (-exterior.SUN_DIR).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = exterior.SUN_STRENGTH
    bpy.data.objects["fill"].hide_render = True
    amb = s.world.node_tree.nodes["amb_sky"]
    amb.inputs["B"].default_value = (exterior.AMB, exterior.AMB, exterior.AMB, 1)


BACKDROP = {
    "hfov": 66.0, "aspect": 1.3,
    "target": Vector(((room.WIN_X0 + room.WIN_X1) / 2, room.BACK_Y + room.WALL_T, (room.WIN_Z0 + room.CEIL) / 2 + 0.1)),
    "light": _backdrop_light,
}


def build():
    room.build_shell()
    room.build_exterior()
    room.build_world()
    room.build_lights()
    props.build_all()


def markers():
    o = bpy.data.objects.get("mic_capsule")
    if o is None:
        return {}
    co = [o.matrix_world @ v.co for v in o.data.vertices]
    return {"mic": sum(co, Vector()) / len(co)}


def extra_hotspots():
    lo = (room.WIN_X0, room.BACK_Y, room.WIN_Z0)
    hi = (room.WIN_X1, room.BACK_Y + room.WALL_T, room.CEIL - 0.12)
    return {"window": (lo, hi, ((room.WIN_X0 + room.WIN_X1) / 2, room.BACK_Y, 2.3))}
