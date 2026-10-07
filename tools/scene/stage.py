"""Shared stage: every scene seats the same character at the same spot, seen by the same cameras.

Scenes change the room, light and props around this frame; they never move the seat or the cameras.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import blib as B

DESK_TOP = 0.76
# work-surface frame: the character sits at local (0, -0.42) facing +Y
DESK_ROOT = ((-0.1, 1.12, 0.0), -24.0)
# chair-space empty (origin at the seat centre, facing +Y), relative to the desk frame
CHAIR = ((0.04, -0.17, 0.0), 16.0)
SEAT_Z = 0.47

CAMERAS = [
    # name, location, yaw (+ = left), pitch (down), lens mm
    ("cam_desktop", (0.0, 0.0, 1.42), 0.0, 15.8, 20.0),
    ("cam_mobile", (0.02, -0.15, 1.72), 0.0, 25.0, 19.0),
]


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def desk_frame(name="desk_root"):
    loc, rot = DESK_ROOT
    return B.empty(name, loc, (0, 0, rot))


def chair_frame(desk, name="chair_root"):
    loc, rot = CHAIR
    return B.empty(name, loc, (0, 0, rot), parent=desk)


def build_cameras():
    B.use_collection("cameras")
    cams = {}
    for name, loc, yaw, pitch, lens in CAMERAS:
        c = bpy.data.cameras.new(name)
        c.lens = lens
        c.sensor_width = 36
        c.clip_start = 0.05
        c.clip_end = 4000
        o = bpy.data.objects.new(name, c)
        B.link(o)
        o.location = loc
        o.rotation_euler = (math.radians(90 - pitch), 0, math.radians(yaw))
        cams[name] = o
    return cams
