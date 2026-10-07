"""Room shell, exterior neighbourhood, lighting and cameras for the creation room."""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

import blib as B
from blib import srgb

# Room layout (Blender units = metres, Z up, camera looks roughly toward +Y)
BACK_Y = 5.6
RIGHT_X = 5.4
FRONT_Y = -2.6
CEIL = 3.4
WIN_X0, WIN_X1 = 0.1, 3.65
WIN_Z0 = 0.55
WALL_T = 0.32
# angled left wall ends at a column; a short return wall steps back to the window wall
CORNER = Vector((-1.2, 4.3, 0))
LW_DIR = Vector((-0.92, -0.39, 0)).normalized()  # from the column toward the front-left
LW_LEN = 9.0
LW_ANGLE = math.atan2(-LW_DIR.y, -LW_DIR.x)      # rotation of the wall face about Z
LW_NORMAL = Vector((-LW_DIR.y, LW_DIR.x, 0))     # into the room
LEFT_X = -9.0


def R_on_left_wall(*a, **k):
    return on_left_wall(*a, **k)


def on_left_wall(s, z, d=0.0):
    """Point at distance ``s`` from the corner along the left wall, height z, offset d into the room."""
    p = CORNER + LW_DIR * s + LW_NORMAL * d
    return (p.x, p.y, z)

CAM_SKY = 1.5     # brightness of the art-directed sky seen through the window
SKY_ZENITH, SKY_MID, SKY_HORIZON = "#4f86d0", "#86b0e0", "#d8e4ea"
AMB_SKY = 0.16     # sky light reaching the interior; lower = stronger sun contrast
SUN_DIR = Vector((0.8, 0.45, 0.29)).normalized()  # direction toward the sun (from the right)
# side window in the (off-camera) right wall lets the sun stripe across the desk and floor
RWIN_Y0, RWIN_Y1 = -1.0, 5.45
RWIN_Z0, RWIN_Z1 = 0.25, 3.3


# ---------------------------------------------------------------- materials

def wall_mat():
    return B.mat_noise("wall", srgb("#efe9df"), srgb("#e9e2d6"), scale=6, rough=0.92, detail=3, spec=0.2)


def floor_mat():
    if "floor" in B._mats:
        return B._mats["floor"]
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.42
    p.inputs["Specular IOR Level"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.offset_frequency = 1
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.4
    br.inputs["Row Height"].default_value = 0.19
    br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Mortar Smooth"].default_value = 0.3
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*srgb("#d8bf9f"), 1)
    br.inputs["Color2"].default_value = (*srgb("#cdb190"), 1)
    br.inputs["Mortar"].default_value = (*srgb("#a38667"), 1)
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    # grain
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.inputs["Scale"].default_value = 3.0
    wv.inputs["Distortion"].default_value = 6
    wv.inputs["Detail"].default_value = 3
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.12
    nt.links.new(br.outputs["Color"], mix.inputs["A"])
    nt.links.new(wv.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    B._mats["floor"] = m
    return m


# ---------------------------------------------------------------- shell

def planks(w=0.19, gap=0.004, seed=3):
    """Light oak floor as individual bevelled planks running toward the window."""
    import numpy as np
    rng = random.Random(seed)
    verts, faces, cols = [], [], []
    x = -6.0
    while x < RIGHT_X:
        y = FRONT_Y - rng.uniform(0, 1.5)
        while y < BACK_Y + 0.4:
            L = rng.uniform(1.2, 2.2)
            x0, x1, y0, y1 = x + gap, x + w - gap, y + gap, min(y + L, BACK_Y + 0.4) - gap
            z0, z1 = -0.02, 0.0
            b = len(verts)
            verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                      (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
            faces += [(b, b + 3, b + 2, b + 1), (b + 4, b + 5, b + 6, b + 7), (b, b + 1, b + 5, b + 4),
                      (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7)]
            t = rng.uniform(-1, 1)
            base = srgb("#dcc4a6")
            c = tuple(min(1, max(0, v * (1 + 0.09 * t) + rng.uniform(-0.01, 0.01))) for v in base)
            cols += [c] * 8
            y += L
        x += w
    me = bpy.data.meshes.new("floor_planks")
    me.from_pydata(verts, [], faces)
    a = me.attributes.new("vcol", "FLOAT_COLOR", "POINT")
    a.data.foreach_set("color", np.array([(*c, 1) for c in cols], np.float32).ravel())
    me.update()
    o = bpy.data.objects.new("floor_planks", me)
    me.materials.append(plank_mat())
    B.link(o)
    m = o.modifiers.new("bevel", "BEVEL")
    m.width = 0.0025
    m.segments = 1
    return o


def plank_mat():
    if "planks" in B._mats:
        return B._mats["planks"]
    m = bpy.data.materials.new("planks")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Roughness"].default_value = 0.38
    p.inputs["Specular IOR Level"].default_value = 0.5
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "vcol"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (18, 1.2, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 6
    nz.inputs["Detail"].default_value = 4
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.9
    mr.inputs["To Max"].default_value = 1.06
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(a.outputs["Color"], mix.inputs["A"])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        nt.links.new(mr.outputs[0], comb.inputs[k])
    nt.links.new(comb.outputs[0], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    B._mats["planks"] = m
    return m

def build_shell():
    B.use_collection("room")
    wm = wall_mat()
    fm = floor_mat()
    B.box_minmax("floor_base", (LEFT_X - 0.3, FRONT_Y, -0.2), (RIGHT_X, BACK_Y + 0.5, -0.01), fm, bevel=0)
    planks()
    B.box_minmax("ceiling", (LEFT_X - 0.3, FRONT_Y, CEIL), (RIGHT_X, BACK_Y + 0.5, CEIL + 0.2), wm, bevel=0)
    mid = CORNER + LW_DIR * (LW_LEN / 2) - LW_NORMAL * (WALL_T / 2)
    B.box("wall_left", (LW_LEN, WALL_T, CEIL), (mid.x, mid.y, CEIL / 2), (0, 0, math.degrees(LW_ANGLE)), wm, bevel=0)
    B.box_minmax("wall_front", (LEFT_X, FRONT_Y - WALL_T, 0), (RIGHT_X, FRONT_Y, CEIL), wm, bevel=0)
    B.box_minmax("wall_right_a", (RIGHT_X, FRONT_Y, 0), (RIGHT_X + WALL_T, RWIN_Y0, CEIL), wm, bevel=0)
    B.box_minmax("wall_right_b", (RIGHT_X, RWIN_Y1, 0), (RIGHT_X + WALL_T, BACK_Y + WALL_T, CEIL), wm, bevel=0)
    B.box_minmax("wall_right_c", (RIGHT_X, RWIN_Y0, 0), (RIGHT_X + WALL_T, RWIN_Y1, RWIN_Z0), wm, bevel=0)
    B.box_minmax("wall_right_d", (RIGHT_X, RWIN_Y0, RWIN_Z1), (RIGHT_X + WALL_T, RWIN_Y1, CEIL), wm, bevel=0)
    mull = B.mat("window_frame", srgb("#2c2d30"), 0.4, metal=0.4)
    n = 8
    for k in range(1, n):
        y = RWIN_Y0 + (RWIN_Y1 - RWIN_Y0) * k / n
        B.box_minmax(f"rwin_mull{k}", (RIGHT_X, y - 0.04, RWIN_Z0), (RIGHT_X + 0.1, y + 0.04, RWIN_Z1), mull, bevel=0)
    B.box_minmax("rwin_tr", (RIGHT_X, RWIN_Y0, 2.2), (RIGHT_X + 0.1, RWIN_Y1, 2.26), mull, bevel=0)
    # back wall with the window opening
    B.box_minmax("wall_back_l", (CORNER.x - WALL_T, BACK_Y, 0), (WIN_X0, BACK_Y + WALL_T, CEIL), wm, bevel=0)
    B.box_minmax("wall_return", (CORNER.x - WALL_T, CORNER.y, 0), (CORNER.x, BACK_Y, CEIL), wm, bevel=0)
    B.box_minmax("wall_back_r", (WIN_X1, BACK_Y, 0), (RIGHT_X + WALL_T, BACK_Y + WALL_T, CEIL), wm, bevel=0)
    B.box_minmax("wall_back_sill", (WIN_X0, BACK_Y, 0), (WIN_X1, BACK_Y + WALL_T, WIN_Z0), wm, bevel=0)
    B.box_minmax("wall_back_head", (WIN_X0, BACK_Y, CEIL - 0.08), (WIN_X1, BACK_Y + WALL_T, CEIL), wm, bevel=0)
    # skirting
    sk = B.mat("skirting", srgb("#d9cfc2"), 0.6)
    B.box_minmax("skirt_back", (CORNER.x, BACK_Y - 0.02, 0), (WIN_X0, BACK_Y, 0.08), sk, bevel=0.003)
    B.box_minmax("skirt_return", (CORNER.x, CORNER.y, 0), (CORNER.x + 0.02, BACK_Y, 0.08), sk, bevel=0.003)
    B.box_minmax("skirt_back_r", (WIN_X1, BACK_Y - 0.02, 0), (RIGHT_X, BACK_Y, 0.08), sk, bevel=0.003)
    # column / pipe at the left/back corner
    dark = B.mat("graphite", srgb("#3a3b3e"), 0.55, metal=0.2)
    col_m = B.mat("column", srgb("#5d5f63"), 0.6)
    B.box("corner_column", (0.24, 0.24, CEIL), (CORNER.x - 0.06, CORNER.y - 0.06, CEIL / 2), (0, 0, 0), col_m,
          bevel=0.01)
    pend = R_on_left_wall(0.25, 0, 0.12)
    B.cylinder("pipe", 0.008, 1.3, (pend[0], pend[1], CEIL - 0.65), material=dark, verts=12)
    B.cylinder("pipe_lamp", 0.03, 0.1, (pend[0], pend[1], CEIL - 1.33), material=dark, verts=24)
    # window frame
    frame = B.mat("window_frame", srgb("#2c2d30"), 0.4, metal=0.4)
    fy = BACK_Y + WALL_T * 0.55
    t = 0.05
    B.box_minmax("win_frame_l", (WIN_X0, fy - t, WIN_Z0), (WIN_X0 + 0.06, fy + t, CEIL), frame, bevel=0.004)
    B.box_minmax("win_frame_r", (WIN_X1 - 0.06, fy - t, WIN_Z0), (WIN_X1, fy + t, CEIL), frame, bevel=0.004)
    B.box_minmax("win_frame_b", (WIN_X0, fy - t, WIN_Z0), (WIN_X1, fy + t, WIN_Z0 + 0.05), frame, bevel=0.004)
    B.box_minmax("win_frame_t", (WIN_X0, fy - t, CEIL - 0.12), (WIN_X1, fy + t, CEIL - 0.06), frame, bevel=0.004)


# ---------------------------------------------------------------- exterior

def build_exterior():
    import exterior
    exterior.build()


# ---------------------------------------------------------------- world + lights

def build_world(cloud=True):
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    sky = nt.nodes.new("ShaderNodeTexSky")
    types = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
    for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        if t in types:
            sky.sky_type = t
            break
    elev = math.asin(SUN_DIR.z)
    rot = math.atan2(SUN_DIR.x, SUN_DIR.y)
    for attr, val in (("sun_elevation", elev), ("sun_rotation", -rot + math.pi), ("sun_disc", False),
                      ("altitude", 40.0), ("air_density", 1.0), ("aerosol_density", 1.0), ("ozone_density", 1.0)):
        if hasattr(sky, attr):
            try:
                setattr(sky, attr, val)
            except Exception:
                pass
    phys = sky.outputs["Color"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    # art-directed sky for camera rays: saturated zenith fading to a pale hazy horizon
    gz = nt.nodes.new("ShaderNodeMapRange")
    gz.inputs["From Min"].default_value = 0.0
    gz.inputs["From Max"].default_value = 0.42
    nt.links.new(sep.outputs["Z"], gz.inputs["Value"])
    grad = nt.nodes.new("ShaderNodeValToRGB")
    el = grad.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*srgb(SKY_HORIZON), 1)
    el[1].position, el[1].color = 1.0, (*srgb(SKY_ZENITH), 1)
    mid = el.new(0.3)
    mid.color = (*srgb(SKY_MID), 1)
    nt.links.new(gz.outputs[0], grad.inputs["Fac"])
    cam_sky = grad.outputs["Color"]
    if cloud:
        addz = nt.nodes.new("ShaderNodeMath")
        addz.operation = "ADD"
        addz.inputs[1].default_value = 0.08
        nt.links.new(sep.outputs["Z"], addz.inputs[0])
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        for axis in ("X", "Y"):
            d = nt.nodes.new("ShaderNodeMath")
            d.operation = "DIVIDE"
            nt.links.new(sep.outputs[axis], d.inputs[0])
            nt.links.new(addz.outputs[0], d.inputs[1])
            nt.links.new(d.outputs[0], comb.inputs[axis])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1.4
        noise.inputs["Detail"].default_value = 10
        noise.inputs["Roughness"].default_value = 0.58
        nt.links.new(comb.outputs[0], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.53
        ramp.inputs["From Max"].default_value = 0.7
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
        hz = nt.nodes.new("ShaderNodeMapRange")
        hz.inputs["From Min"].default_value = 0.03
        hz.inputs["From Max"].default_value = 0.2
        nt.links.new(sep.outputs["Z"], hz.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(ramp.outputs[0], mul.inputs[0])
        nt.links.new(hz.outputs[0], mul.inputs[1])
        cloud_c = nt.nodes.new("ShaderNodeMix")
        cloud_c.data_type = "RGBA"
        nt.links.new(cam_sky, cloud_c.inputs["A"])
        cloud_c.inputs["B"].default_value = (*srgb("#f6f4ef"), 1)
        nt.links.new(mul.outputs[0], cloud_c.inputs["Factor"])
        cam_sky = cloud_c.outputs["Result"]
    gain = nt.nodes.new("ShaderNodeMix")
    gain.data_type = "RGBA"
    gain.blend_type = "MULTIPLY"
    gain.inputs["Factor"].default_value = 1.0
    nt.links.new(cam_sky, gain.inputs["A"])
    gain.inputs["B"].default_value = (CAM_SKY, CAM_SKY, CAM_SKY, 1)
    amb = nt.nodes.new("ShaderNodeMix")
    amb.name = "amb_sky"
    amb.data_type = "RGBA"
    amb.blend_type = "MULTIPLY"
    amb.inputs["Factor"].default_value = 1.0
    nt.links.new(phys, amb.inputs["A"])
    amb.inputs["B"].default_value = (AMB_SKY, AMB_SKY, AMB_SKY, 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    pick = nt.nodes.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    nt.links.new(lp.outputs["Is Camera Ray"], pick.inputs["Factor"])
    nt.links.new(amb.outputs["Result"], pick.inputs["A"])
    nt.links.new(gain.outputs["Result"], pick.inputs["B"])
    nt.links.new(pick.outputs["Result"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return w


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def build_lights(sun_strength=26.0):
    B.use_collection("lights")
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = sun_strength
    sun.angle = math.radians(2.2)
    sun.color = (1.0, 0.74, 0.5)
    o = bpy.data.objects.new("sun", sun)
    B.link(o)
    o.location = (10, 10, 10)
    o.rotation_euler = (-SUN_DIR).to_track_quat("-Z", "Y").to_euler()
    # soft bounce from the open camera side
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 150
    fill.size = 4.0
    fill.color = (1.0, 0.9, 0.8)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.location = (0.6, -2.2, 2.6)
    look_at(f, (0, 1.6, 0.8))
    # window bounce on the bench / left room
    win = bpy.data.lights.new("window_portal", "AREA")
    win.shape = "RECTANGLE"
    win.size = WIN_X1 - WIN_X0
    win.size_y = CEIL - WIN_Z0
    win.energy = 0
    if hasattr(win, "cycles"):
        try:
            win.cycles.is_portal = True
        except Exception:
            pass
    wo = bpy.data.objects.new("window_portal", win)
    B.link(wo)
    wo.location = ((WIN_X0 + WIN_X1) / 2, BACK_Y + WALL_T + 0.02, (WIN_Z0 + CEIL) / 2)
    wo.rotation_euler = (math.radians(90), 0, 0)


CAMERAS = [
    # name, location, yaw (+ = left), pitch (down), lens mm
    ("cam_desktop", (0.0, 0.0, 1.42), 0.0, 15.8, 20.0),
    ("cam_mobile", (0.02, -0.15, 1.72), 0.0, 25.0, 19.0),
]


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
