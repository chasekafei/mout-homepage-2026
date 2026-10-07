"""Navigable scenes. Each lives in scene_<id>.py and provides:

    HOTSPOTS        interactive ids; order defines the id encoding (index + 1), max 15
    GRADE           exposure / white balance / bloom / colour balance shared by renders, LUT and runtime
    PLANES          heights (m) of the two glossy horizontal planes reflected at runtime: floor, work surface
    MIRROR_CLEAR    encoded radiance for whatever the bake culled above those planes (ceiling)
    BACKDROP        exterior view behind the window: hfov / aspect / target (Blender coords) / light(scene),
                    optional dist (m, default 40) of the runtime backdrop plane
    build()         room, exterior (collection "exterior"), world, lights and props around the shared stage
    markers()       named points for overlays, e.g. {"mic": Vector}
    extra_hotspots() {id: (min, max, anchor)} for hotspots that are not meshes (the window view)
"""
from __future__ import annotations

import importlib

NAMES = ("now", "create")


def load(name: str):
    if name not in NAMES:
        raise SystemExit(f"unknown scene {name!r}; expected one of {NAMES}")
    return importlib.import_module(f"scene_{name}")
