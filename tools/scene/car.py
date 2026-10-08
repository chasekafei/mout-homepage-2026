"""出发: the driver's seat of a white-interior Model Y. The cockpit never changes; the road outside does.

Desk frame (``stage.DESK_ROOT``): +Y is where he looks, through the windscreen. The car is left-hand drive,
so his door (and the side window) is on his left and the centre screen sits to his right. There is no glass:
the windscreen and the glass roof are one open sweep between the A pillars and the roof rails, with no header
across the top, because the mobile camera sits above roof height and would see it cut through the frame.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import blib as B
import stage
from blib import srgb

L_X, R_X = -0.5, 1.2            # inner faces of the front doors
MID_X = (L_X + R_X) / 2         # car centreline
PASS_X = 2 * MID_X              # passenger seat centre (driver at 0)
FLOOR = 0.06
DASH_Y0, DASH_Y1, DASH_Z = 0.62, 1.12, 0.96   # dash face (towards him), windscreen base, dash top
SILL_Z = 0.92                   # door window line
ROOF = 1.5
BAR_Y = -0.02                   # where the A pillars meet the roof rails
B_PILLAR = (-0.62, -0.5)
SCREEN = (MID_X, 0.7, 1.1)      # centre screen
WHEEL_C = (0.0, 0.5, 0.88)      # steering wheel centre, chair space
WHEEL_R, WHEEL_TILT = 0.18, 24.0

root = None


# ---------------------------------------------------------------- materials

def leather_white():
    return B.mat_noise("car_leather", srgb("#ecebe7"), srgb("#e2e0db"), scale=300, rough=0.55, detail=3, spec=0.35,
                       bump=0.05)


def soft_black():
    return B.mat("car_soft", srgb("#1e1f22"), 0.62, spec=0.3)


def gloss_black():
    return B.mat("car_gloss", srgb("#0f1012"), 0.18, spec=0.6, coat=0.4)


def trim_wood():
    return B.mat_noise("car_wood", srgb("#b99a76"), srgb("#a8885f"), scale=60, rough=0.45, detail=6, spec=0.4)


def carpet():
    return B.mat_noise("car_carpet", srgb("#232427"), srgb("#1b1c1f"), scale=500, rough=0.95, spec=0.1)


def chrome():
    return B.mat("car_chrome", srgb("#b8bcc2"), 0.25, metal=1.0)


# ---------------------------------------------------------------- shell

def build_cabin():
    B.use_collection("cabin")
    r = root
    soft, wood, white = soft_black(), trim_wood(), leather_white()
    B.box_minmax("floor", (L_X - 0.05, -1.6, FLOOR - 0.04), (R_X + 0.05, DASH_Y1, FLOOR), carpet(), bevel=0, parent=r)
    # dashboard: one long slab, a full-width vent slot and the wood strip under it
    B.box_minmax("dash_top", (L_X - 0.02, DASH_Y0, DASH_Z - 0.06), (R_X + 0.02, DASH_Y1 + 0.05, DASH_Z), soft,
                 bevel=0.02, parent=r)
    B.box_minmax("dash_face", (L_X - 0.02, DASH_Y0 + 0.02, 0.62), (R_X + 0.02, DASH_Y0 + 0.14, DASH_Z - 0.05), soft,
                 bevel=0.02, parent=r)
    B.box_minmax("dash_vent", (L_X + 0.02, DASH_Y0 - 0.003, DASH_Z - 0.085), (R_X - 0.02, DASH_Y0 + 0.03, DASH_Z - 0.065),
                 gloss_black(), bevel=0.002, parent=r)
    B.box_minmax("dash_wood", (L_X, DASH_Y0 - 0.006, DASH_Z - 0.15), (R_X, DASH_Y0 + 0.03, DASH_Z - 0.1), wood,
                 bevel=0.004, parent=r)
    B.box_minmax("dash_lower", (L_X, DASH_Y0 + 0.06, FLOOR), (R_X, DASH_Y1, 0.64), soft, bevel=0.02, parent=r)
    # doors: white upper trim, wood strip, black lower panel, armrest
    for side, x0, x1 in (("l", L_X - 0.08, L_X), ("r", R_X, R_X + 0.08)):
        sx = -1 if side == "l" else 1
        inner = x1 if side == "l" else x0
        B.box_minmax(f"door_{side}", (x0, -1.4, FLOOR), (x1, DASH_Y0 + 0.1, SILL_Z - 0.04), soft, bevel=0.01, parent=r)
        B.box_minmax(f"door_{side}_top", (min(x0, inner - sx * 0.05), -1.4, SILL_Z - 0.06),
                     (max(x1, inner - sx * 0.05), DASH_Y0 + 0.1, SILL_Z), white, bevel=0.012, parent=r)
        B.box_minmax(f"door_{side}_wood", (inner - 0.006, -0.55, SILL_Z - 0.1), (inner + 0.006, DASH_Y0 + 0.08, SILL_Z - 0.07),
                     wood, bevel=0.002, parent=r)
        B.box_minmax(f"door_{side}_arm", (min(inner, inner - sx * 0.09), -0.45, 0.6), (max(inner, inner - sx * 0.09), 0.3, 0.66),
                     white, bevel=0.015, parent=r)
        B.cylinder(f"door_{side}_speaker", 0.07, 0.01, (inner - sx * 0.004, 0.25, 0.28), (0, 90, 0), material=gloss_black(),
                   verts=24, parent=r)
        # B pillar and roof rail
        B.box_minmax(f"bpillar_{side}", (x0, B_PILLAR[0], SILL_Z - 0.02), (x1 + (0.02 if side == "l" else 0), B_PILLAR[1], ROOF),
                     soft, bevel=0.01, parent=r)
        B.box_minmax(f"rail_{side}", (x0, -1.8, ROOF - 0.05), (x1 + (0.03 if side == "l" else 0), BAR_Y + 0.04, ROOF + 0.02),
                     soft, bevel=0.01, parent=r)
        # A pillar from the windscreen base up to the crossbar
        a = (inner - sx * 0.01, DASH_Y1 + 0.02, DASH_Z - 0.02)
        b = (inner + sx * 0.02, BAR_Y + 0.04, ROOF - 0.02)
        B.tbox(f"apillar_{side}", a, b, (0.07, 0.05), up=(0, 0, 1), material=soft, bevel=0.012, parent=r)
        # door mirror outside the window line
        B.superellipsoid(f"mirror_{side}", (0.06, 0.1, 0.07), (inner + sx * 0.14, DASH_Y0 + 0.02, SILL_Z + 0.06),
                         material=B.mat("car_paint", srgb("#f2f3f5"), 0.25, spec=0.6, coat=0.6), e=0.5, parent=r)
    # white bonnet beyond the windscreen, falling away towards the nose
    paint = B.mat("car_paint", srgb("#f2f3f5"), 0.25, spec=0.6, coat=0.6)
    B.tbox("bonnet", (MID_X, DASH_Y1 + 0.02, DASH_Z - 0.04), (MID_X, DASH_Y1 + 1.3, DASH_Z - 0.26),
           (R_X - L_X + 0.12, 0.08), (R_X - L_X - 0.1, 0.08), up=(0, 0, 1), material=paint, bevel=0.06, parent=r)
    B.box_minmax("cowl", (L_X - 0.02, DASH_Y1 - 0.02, DASH_Z - 0.05), (R_X + 0.02, DASH_Y1 + 0.1, DASH_Z - 0.01),
                 gloss_black(), bevel=0.01, parent=r)
    # centre console between the seats
    gl = gloss_black()
    B.box_minmax("console", (MID_X - 0.14, -0.75, FLOOR), (MID_X + 0.14, DASH_Y0 + 0.06, 0.56), soft, bevel=0.02, parent=r)
    B.box_minmax("console_top", (MID_X - 0.13, -0.2, 0.555), (MID_X + 0.13, DASH_Y0 + 0.04, 0.575), gl, bevel=0.01,
                 parent=r)
    B.box_minmax("console_arm", (MID_X - 0.14, -0.75, 0.56), (MID_X + 0.14, -0.22, 0.64), white, bevel=0.03, parent=r)
    for k, y in enumerate((0.02, 0.14)):
        B.cylinder(f"cupholder{k}", 0.04, 0.02, (MID_X, y, 0.568), material=B.mat("car_hole", srgb("#08090a"), 0.6),
                   verts=24, parent=r)
    for k, dx in enumerate((-0.055, 0.055)):
        B.box(f"phone{k}", (0.075, 0.155, 0.009), (MID_X + dx, 0.42, 0.582), (0, 0, 0), material=gl, bevel=0.006, parent=r)


def build_screen():
    B.use_collection("cabin")
    sc = B.empty("screen_root", SCREEN, (0, 0, 0), parent=root, hs="nav")
    w, h = 0.38, 0.24
    tilt = -10
    B.box("screen_bezel", (w + 0.014, 0.022, h + 0.014), (0, 0.012, 0), (tilt, 0, 0), material=gloss_black(), bevel=0.006,
          parent=sc)
    B.plane("screen_face", w, h, (0, -0.0005, 0), (tilt, 0, 0), material=B.mat_image(
        "car_screen", "depart_screen.png", rough=0.2, emission=1.4, spec=0.6), parent=sc)
    B.box_minmax("screen_stalk", (-0.04, 0.02, -(SCREEN[2] - DASH_Z) - 0.01), (0.04, 0.07, -h / 2 + 0.02),
                 soft_black(), bevel=0.01, parent=sc)


def build_wheel(chair):
    B.use_collection("cabin")
    cx, cy, cz = WHEEL_C
    t = math.radians(WHEEL_TILT)
    up = Vector((0, math.sin(t), math.cos(t)))   # the rim's top leans away from him
    rt = Vector((1, 0, 0))
    nrm = rt.cross(up)                           # wheel face, towards his chest
    c = Vector(WHEEL_C)
    leather = B.mat("car_wheel", srgb("#18191b"), 0.5, spec=0.35)
    ring = [(WHEEL_R + 0.017 * math.cos(2 * math.pi * k / 16), 0.021 * math.sin(2 * math.pi * k / 16)) for k in range(17)]
    B.lathe("wheel_rim", ring, WHEEL_C, (90 - WHEEL_TILT, 0, 0), material=leather, segs=72, parent=chair)
    hub = c - nrm * 0.01
    for k, a in enumerate((0.0, math.pi, -math.pi / 2)):
        p = c + 0.17 * (math.cos(a) * rt + math.sin(a) * up)
        B.tbox(f"wheel_spoke{k}", tuple(hub), tuple(p), (0.05 if k < 2 else 0.04, 0.02), up=tuple(nrm), material=leather,
               bevel=0.008, parent=chair)
    B.superellipsoid("wheel_hub", (0.09, 0.05, 0.07), tuple(hub), (-WHEEL_TILT, 0, 0), material=leather, e=0.5,
                     parent=chair)
    B.box("wheel_badge", (0.022, 0.004, 0.026), tuple(hub + nrm * 0.026), (-WHEEL_TILT, 0, 0), material=chrome(), bevel=0.002,
          parent=chair)
    for sx in (-1, 1):
        B.cylinder(f"wheel_scroll{sx}", 0.012, 0.012, tuple(c + rt * sx * 0.085 + nrm * 0.012), (90 - WHEEL_TILT, 0, 0),
                   material=chrome(), verts=16, parent=chair)
    col_end = Vector((cx, DASH_Y0 - (-0.17) + 0.02, cz - 0.08))
    B.tbox("wheel_column", tuple(hub - nrm * 0.03), tuple(col_end), (0.07, 0.07), (0.09, 0.09), up=(0, 0, 1),
           material=soft_black(), bevel=0.02, parent=chair)
    B.box("wheel_stalk", (0.12, 0.012, 0.012), (cx + 0.1, cy + 0.06, cz - 0.02), (0, 0, -8), material=soft_black(),
          bevel=0.004, parent=chair)


def build_seat(chair, name):
    white = leather_white()
    B.superellipsoid(f"{name}_cushion", (0.52, 0.52, 0.12), (0, 0.0, 0.42), material=white, e=0.3, parent=chair)
    B.superellipsoid(f"{name}_base", (0.5, 0.5, 0.26), (0, -0.02, 0.22), material=soft_black(), e=0.2, parent=chair)
    B.superellipsoid(f"{name}_back", (0.52, 0.14, 0.42), (0, -0.26, 0.68), (-4, 0, 0), material=white, e=0.3, parent=chair)
    for sx in (-1, 1):
        B.superellipsoid(f"{name}_bolster{sx}", (0.08, 0.13, 0.34), (sx * 0.25, -0.22, 0.64), (-4, 0, 0), material=white,
                         e=0.4, parent=chair)
        B.superellipsoid(f"{name}_cush_bolster{sx}", (0.08, 0.46, 0.1), (sx * 0.25, 0.0, 0.47), material=white, e=0.4,
                         parent=chair)


# ---------------------------------------------------------------- props

def build_props():
    B.use_collection("props")
    # paddle and the Asian Games ticket on the console tray
    pp = B.empty("pingpong_root", (MID_X + 0.02, 0.36, 0.585), (0, 0, 28), parent=root, hs="pingpong")
    B.cylinder("paddle_red", 0.075, 0.006, (0, 0, 0.012), material=B.mat("paddle_red", srgb("#c8262c"), 0.55, spec=0.3),
               verts=40, parent=pp)
    B.cylinder("paddle_black", 0.075, 0.006, (0, 0, 0.006), material=B.mat("paddle_black", srgb("#141416"), 0.6),
               verts=40, parent=pp)
    B.box("paddle_handle", (0.03, 0.1, 0.022), (0, -0.115, 0.009), material=trim_wood(), bevel=0.006, parent=pp)
    B.cylinder("ball", 0.02, 0.04, (0.09, 0.02, 0.02), material=B.mat("ball", srgb("#ff8a3d"), 0.4), verts=20, parent=pp)
    B.plane("ticket_games", 0.15, 0.067, (-0.02, 0.1, 0.0015), (-90, 0, -40),
            material=B.mat_image("ticket_games", "depart_ticket_games.png", rough=0.5), parent=pp)
    # movie ticket clipped to the vent in front of the passenger
    ct = B.empty("cinema_root", (PASS_X + 0.06, DASH_Y0 - 0.012, DASH_Z - 0.06), (0, 0, 0), parent=root, hs="cinema")
    B.plane("ticket_cinema", 0.11, 0.052, (0, -0.002, -0.022), (-6, 0, 4),
            material=B.mat_image("ticket_cinema", "depart_ticket_cinema.png", rough=0.55), parent=ct)
    B.box("ticket_clip", (0.02, 0.01, 0.022), (0, 0, 0.0), material=chrome(), bevel=0.002, parent=ct)
    # passport with boarding passes on the passenger side of the dash
    pa = B.empty("passport_root", (PASS_X - 0.03, DASH_Y0 + 0.15, DASH_Z), (0, 0, -14), parent=root, hs="passport")
    B.box("passport_body", (0.09, 0.125, 0.011), (0, 0, 0.0055), material=B.mat("passport_edge", srgb("#2c3550"), 0.6),
          bevel=0.002, parent=pa)
    B.plane("passport", 0.088, 0.123, (0, 0, 0.0112), (-90, 0, 0),
            material=B.mat_image("passport", "depart_passport.png", rough=0.6), parent=pa)
    for k, (dx, dy, rz) in enumerate(((0.03, 0.06, -18), (0.045, 0.045, 8))):
        B.plane(f"boarding{k}", 0.15, 0.06, (dx, dy, 0.013 + k * 0.001), (-90, 0, rz),
                material=B.mat_image("boarding", "depart_boarding.png", rough=0.5), parent=pa)


# ---------------------------------------------------------------- lights

def build_lights(sun_dir, sun_strength=4.0, sun_col=(1.0, 0.93, 0.84)):
    B.use_collection("lights")
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = sun_strength
    sun.angle = math.radians(1.5)
    sun.color = sun_col
    so = bpy.data.objects.new("sun", sun)
    B.link(so)
    so.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 25
    fill.size = 1.0
    fill.color = (1.0, 0.96, 0.92)
    f = bpy.data.objects.new("fill", fill)
    B.link(f)
    f.parent = root
    f.location = (PASS_X, -1.2, 1.4)
    f.rotation_euler = (Vector((0.0, 0.5, 0.8)) - Vector(f.location)).to_track_quat("-Z", "Y").to_euler()


def build_all():
    global root
    import models_char as C
    root = stage.desk_frame("car_root")
    build_cabin()
    build_screen()
    B.use_collection("chair")
    chair = stage.chair_frame(root)
    build_seat(chair, "seat_d")
    passenger = B.empty("passenger_root", (PASS_X, stage.CHAIR[0][1], 0), (0, 0, 0), parent=root)
    build_seat(passenger, "seat_p")
    build_wheel(chair)
    C.build_character(chair, arms="wheel")
    build_props()
    # two cats sunning themselves on the dash: 烧酒 at the foot of the windscreen in front of him, 小八 by the screen
    B.use_collection("cats")
    C.build_shaojiu(root, (-0.22, DASH_Y1 - 0.12, DASH_Z), 30).scale = (0.5,) * 3
    C.build_xiaoba(root, (MID_X + 0.27, DASH_Y1 - 0.1, DASH_Z), 30).scale = (0.42,) * 3
    return root
