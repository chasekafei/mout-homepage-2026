"""Shared stage: every scene seats the same character at the same spot, seen by the same cameras.

Scenes change the room, light and props around this frame; they never move the seat or the cameras.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import blib as B

DESK_TOP = 0.76
# Seat centre in world space and the way the character faces (degrees, + = left of the cameras' +Y).
# The body, chair and work surface share this heading, so whatever he looks at sits straight ahead of him;
# turning the whole seat to camera-right keeps that spot clear of his head and shoulders.
SEAT = (-0.42, 0.948)
YAW = -36.0
# chair-space empty (origin at the seat centre, facing +Y), relative to the desk frame
CHAIR = ((0.0, -0.17, 0.0), 0.0)


def _desk_root():
    a = math.radians(YAW)
    cx, cy = CHAIR[0][0], CHAIR[0][1]
    return ((SEAT[0] - (cx * math.cos(a) - cy * math.sin(a)), SEAT[1] - (cx * math.sin(a) + cy * math.cos(a)), 0.0), YAW)


# work-surface frame: the character sits at local (0, -0.17) facing +Y
DESK_ROOT = _desk_root()
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
        c.clip_end = 40000
        o = bpy.data.objects.new(name, c)
        B.link(o)
        o.location = loc
        o.rotation_euler = (math.radians(90 - pitch), 0, math.radians(yaw))
        cams[name] = o
    return cams
