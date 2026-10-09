"""Every destination outside the car. Each builder lays its road, scenery and landmark in the desk frame.

The landmark sits about 30 degrees left of straight ahead and under ten degrees of elevation, the one patch
of sky both cameras see through the windscreen; ``Sightline`` keeps trees and buildings out of its way.
"""
from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

import nightcity
from roads import ASPHALT, EYE, GROUND, MID, Kit, Sightline, col


# ---------------------------------------------------------------- 名古屋

def mirai_tower(k, x, y):
    """中部電力 MIRAI TOWER: four-legged steel lattice, the main deck at 90 m, the Sky Balcony at 100 m, a mast to 180 m."""
    s = k.land
    steel = col("#d7d4cc")
    z0 = GROUND
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = Vector((x + sx * 11.0, y + sy * 11.0, z0))
            b = Vector((x + sx * 2.2, y + sy * 2.2, z0 + 98))
            legs.append((a, b))
            s.tube([tuple(a), tuple(a.lerp(b, 0.5)), tuple(b)], 0.55, steel, seg=6)
    # bracing rings and diagonals
    for t in np.linspace(0.08, 0.92, 9):
        ring = [a.lerp(b, t) for a, b in legs]
        order = [0, 1, 3, 2, 0]
        s.tube([tuple(ring[i]) for i in order], 0.22, steel, seg=5)
    for t0, t1 in zip(np.linspace(0.0, 0.9, 10)[:-1], np.linspace(0.1, 1.0, 10)[1:]):
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            (a0, b0), (a1, b1) = legs[i], legs[j]
            s.tube([tuple(a0.lerp(b0, t0)), tuple(a1.lerp(b1, t1))], 0.12, steel, seg=4)
            s.tube([tuple(a1.lerp(b1, t0)), tuple(a0.lerp(b0, t1))], 0.12, steel, seg=4)
    # glass deck and open balcony
    s.box(x - 6.5, y - 6.5, z0 + 86, x + 6.5, y + 6.5, z0 + 93, col("#3c4a58"))
    s.box(x - 6.8, y - 6.8, z0 + 93, x + 6.8, y + 6.8, z0 + 93.6, steel)
    s.box(x - 5.4, y - 5.4, z0 + 98, x + 5.4, y + 5.4, z0 + 101, col("#8d9aa6"))
    s.box(x - 2.4, y - 2.4, z0 + 101, x + 2.4, y + 2.4, z0 + 110, steel)
    s.tube([(x, y, z0 + 110), (x, y, z0 + 180)], 0.7, steel, seg=6)
    s.tube([(x, y, z0 + 150), (x, y, z0 + 180)], 0.4, col("#c74034"), seg=6)
    # the base building (エレベーター棟) between the legs
    s.box(x - 5, y - 5, z0, x + 5, y + 5, z0 + 12, col("#bfbab0"))


def nagoya_castle(k, x, y):
    """Distant 名古屋城 keep on its stone base: white walls, green copper roofs, gold on the ridge."""
    s = k.land
    z = GROUND + 4
    s.box(x - 26, y - 22, GROUND - 1, x + 26, y + 22, z + 12, col("#a49f93"))
    w, d = 34.0, 28.0
    for lv, hgt in enumerate((7.0, 6.0, 5.5, 5.0, 4.5)):
        s.box(x - w / 2, y - d / 2, z + 12, x + w / 2, y + d / 2, z + 12 + hgt, col("#efede6"))
        s.box(x - w / 2 - 1.5, y - d / 2 - 1.5, z + 12 + hgt - 0.6, x + w / 2 + 1.5, y + d / 2 + 1.5, z + 12 + hgt + 0.8,
              col("#5f8b78"))
        z += hgt + 0.8
        w, d = w * 0.8, d * 0.8
    s.box(x - w / 2, y - 1.5, z + 12, x + w / 2, y + 1.5, z + 15, col("#5f8b78"))
    k.glow.box(x - w / 2 - 0.3, y - 0.6, z + 14.5, x - w / 2 + 1.2, y + 0.6, z + 17, col("#d8b452") * 0.25)


def nagoya(root):
    """久屋大通 heading north: the park opens on the left, MIRAI TOWER rises over it, offices line the right."""
    k = Kit("nagoya", 26)
    rng = k.rng
    tower = (-502.0, 805.0)      # 32 degrees left, 950 m out
    sl = Sightline(*tower, half=4.5, top=1.0)
    k.road(-1.6, 9.0, y1=1600, lanes=(-1.45, 8.85), dashes=(1.9, 5.4))
    k.sidewalk(-6.0, -1.6, y1=1600)
    k.sidewalk(9.0, 13.0, y1=1600)
    # the park: lawn, gravel paths, groves of zelkova and camphor that leave the tower in the clear
    k.solid.box(-1400, 8, GROUND - 0.4, -6.0, 1500, GROUND + 0.18, col("#7f9a55"))
    k.solid.box(-1400, -60, GROUND - 0.4, -6.0, 6, GROUND + 0.18, col("#7f9a55"))
    for x0, x1 in ((-14, -11), (-60, -56)):
        k.solid.box(x0, -60, GROUND + 0.18, x1, 1500, GROUND + 0.2, col("#c9bfa9"))
    k.solid.box(-1400, 300, GROUND + 0.18, -6.0, 304, GROUND + 0.2, col("#c9bfa9"))
    for y in np.arange(-40, 1500, 9.0):
        x, yy, h = -8.6 + rng.uniform(-0.4, 0.4), y + rng.uniform(-2, 2), rng.uniform(6.5, 8.5)
        if sl.ok(x, yy, GROUND + h, 0.64 * h * 0.9):
            k.tree(x, yy, h, spread=0.9)
    placed = 0
    for _ in range(4000):
        if placed >= 260:
            break
        d = 18 + 900 * rng.random() ** 1.6
        a = math.radians(rng.uniform(10, 85))
        x, y = EYE[0] - d * math.sin(a), EYE[1] + d * math.cos(a)
        if x > -16 or y < 8:
            continue
        h = rng.uniform(5, 11)
        if sl.ok(x, y, GROUND + h, 0.64 * h * 1.1):
            k.tree(x, y, h, spread=1.1)
            placed += 1
    walls = ("#e8e2d6", "#d9d3c8", "#c7c1b7", "#efebe3", "#b9b4ab", "#d6cbb8", "#9ea6ad")
    # offices on the right, a distant ring of the city beyond the park
    k.street_row(13.0, -40, 1500, walls, h=(14, 42), face="-x", band_p=0.55, sign_p=0.45)
    k.skyline(120, 900, (80, 500), 70, (30, 120), walls)
    # the far side of the park: a row of offices, with a gap where the tower stands
    y = -40.0
    while y < 1400:
        w, d, h = rng.uniform(14, 40), rng.uniform(18, 30), rng.uniform(18, 60)
        if sl.ok(-170 - d / 2, y + w / 2, GROUND + h, max(w, d) / 2 + 4):
            k.building(-170 - d, y, -170, y + w, h, col(rng.choice(walls), 0.05, rng), roof=col("#7b7e82"), face="+x")
        y += w + rng.uniform(2, 10)
    for _ in range(90):
        d, a = rng.uniform(1300, 2400), math.radians(rng.uniform(5, 85))
        x, y = EYE[0] - d * math.sin(a), EYE[1] + d * math.cos(a)
        h = rng.uniform(15, 70)
        if sl.ok(x, y, GROUND + h):
            w = rng.uniform(25, 60)
            k.far.box(x - w / 2, y - w / 2, GROUND - 1, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(walls), 0.06, rng))
    # the cross street at 60 m: crossing, Japanese signals, the left turn into the park road
    k.solid.box(-60, 58, GROUND - 0.39, 60, 74, GROUND + 0.001, ASPHALT)
    k.crosswalk(-1.6, 9.0, 52.5)
    k.signal_jp(-2.0, 55.0, 8.6)
    k.signal_jp(11.0, 77.0, -8.6)
    k.pole_line(11.2, -40, 600, 31.0)
    # traffic: a white sedan ahead, a navy one alongside, a city bus and a kei car further up
    k.car(MID(), 15.0, "#f1f0ec")
    k.car(3.7, 7.5, "#2b3a55")
    k.car(7.2, 26.0, "#e8e3d4", "bus")
    k.car(3.7, 40.0, "#a9b0b6", "kei")
    k.car(MID() + 0.2, 44.0, "#7a2f2f")
    # lamp posts on the park side carry plain-colour Asian Games banners
    for i, y in enumerate(np.arange(19, 280, 17.0)):
        if not sl.ok(-2.0, y, GROUND + 8.0):
            continue
        k.solid.cyl(-2.0, y, GROUND, GROUND + 8.0, 0.09, col("#6f7275"), seg=8)
        k.solid.box(-2.0, y - 0.05, GROUND + 7.9, -0.9, y + 0.05, GROUND + 8.0, col("#6f7275"))
        k.solid.box(-1.1, y - 0.25, GROUND + 7.72, -0.7, y + 0.25, GROUND + 7.85, col("#d8d6d0"))
        k.banner(-2.06, y + 0.4, GROUND + 7.4, ("#d23c3c", "#2c6fb5", "#e4a91f")[i % 3])
    mirai_tower(k, *tower)
    nagoya_castle(k, -1050.0, 900.0)
    for x, y, z, sz in ((-700, 900, 230, 90), (-260, 1200, 300, 120), (-1100, 600, 200, 80), (200, 1300, 280, 110),
                        (-900, 1500, 380, 150)):
        k.cloud(x, y, z, sz)
    k.build(root)



# ---------------------------------------------------------------- shared layout

def polar(bearing, dist):
    """Ground point ``dist`` metres from the desktop camera, ``bearing`` degrees left of straight ahead."""
    b = math.radians(bearing)
    return EYE[0] - dist * math.sin(b), EYE[1] + dist * math.cos(b)


def rht_avenue(k, line="#e9e7e0", oncoming=7.0, double=True, y1=2000.0):
    """Right-hand traffic: our two lanes, the oncoming ones on the left beyond the centre line."""
    k.road(-1.6 - oncoming, 5.4, y1=y1, lanes=(-1.45 - oncoming, 5.25), dashes=(1.9, -1.6 - oncoming / 2))
    for dx in ((-0.18, 0.0) if double else (0.0,)):
        k.solid.box(-1.6 + dx - 0.06, -60, GROUND, -1.6 + dx + 0.06, y1, GROUND + 0.005, col(line))


def coast(k, shore, sea="#2f6f96", beach="#c9bfa8", land="#9a9a7a", beach_w=14.0, y0=-60.0, y1=2600.0, step=10.0):
    """Sea everywhere left of the shoreline (x as a function of y through ``shore`` points), beach, then land up to x0."""
    ys, xs = zip(*shore)
    k.sea(-6000, y0, 200, 9000, sea)
    for y in np.arange(y0, y1, step):
        x = float(np.interp(y + step / 2, ys, xs))
        k.solid.box(x, y, GROUND - 3, x + beach_w, y + step, GROUND - 0.3, col(beach))
        k.solid.box(x + beach_w, y, GROUND - 3, x + beach_w + 400, y + step, GROUND + 0.05, col(land))


def shore_x(shore, y):
    ys, xs = zip(*shore)
    return float(np.interp(y, ys, xs))


# ---------------------------------------------------------------- 第比利斯

def tbilisi(root):
    """The Mtkvari embankment: the old town climbs the far bank to Narikala, Sameba's gold dome beyond."""
    k = Kit("tbilisi", 31, dist=1400.0)
    rng = k.rng
    fort, statue, church = polar(29, 640), polar(37, 690), polar(16, 1300)
    sls = (Sightline(*polar(33, 660), half=8.5, top=4.4), Sightline(*church, half=4.0, top=1.8))

    def clear(x, y, z, r=0.0):
        return all(s.ok(x, y, z, r) for s in sls)

    rht_avenue(k)
    k.sidewalk(-12.0, -8.6, y1=2000)
    k.rail(-11.7, -60, 1200, colour="#b9ad95")
    k.sea(-2000, -60, -12.0, 3000, "#5f7d70", z=GROUND - 5.0)
    k.solid.box(-14.0, -60, GROUND - 8, -12.0, 1600, GROUND + 0.1, col("#b8a98c"))
    # the far bank rises from the river into the Sololaki ridge, Narikala and the statue on its crest
    ridge_h, ridge_r = 82.0, 260.0
    for i in range(16):
        b = 18 + i * 2.6 + rng.uniform(-1, 1)
        x, y = polar(b, rng.uniform(760, 900))
        k.mountain(x, y, rng.uniform(62, 78), rng.uniform(220, 280), rock="#8c8068", grass="#7b8150", z0=GROUND - 5, rough=0.12)
    for p in (fort, statue):
        k.mountain(*p, ridge_h, ridge_r, rock="#8c8068", grass="#7b8150", z0=GROUND - 5, rough=0.06)
    for _ in range(1400):
        x, y = rng.uniform(-330, -70), rng.uniform(-40, 1400)
        z = GROUND - 5 + max(0.0, -x - 70) * 0.2
        w, d, h = rng.uniform(5, 10), rng.uniform(5, 9), rng.uniform(5, 11)
        if not clear(x, y, z + h, w):
            continue
        c = col(rng.choice(("#e9dcc2", "#d9b98c", "#c98d64", "#efe6d4", "#b7c4c8", "#d8c7a4")), 0.05, rng)
        k.facade.box(x - w / 2, y - d / 2, z - 6, x + w / 2, y + d / 2, z + h, c)
        k.solid.box(x - w / 2 - 0.4, y - d / 2 - 0.4, z + h, x + w / 2 + 0.4, y + d / 2 + 0.4, z + h + 1.2,
                    col(rng.choice(("#a5543a", "#8f4a34", "#6f6a66", "#b4643f"))))
    # Narikala: towers and a curtain wall stepping down the ridge either side of the crest
    fx, fy = fort
    pts = []
    for t in np.linspace(-1, 1, 9):
        x, y = fx + t * 68, fy + t * 34
        z = GROUND - 5 + ridge_h * (1 - min(1.0, math.hypot(x - fx, y - fy) / ridge_r)) ** 1.5
        k.land.box(x - 6, y - 6, z - 12, x + 6, y + 6, z + 16, col("#9a8c74"))
        k.land.box(x - 6.6, y - 6.6, z + 16, x + 6.6, y + 6.6, z + 18.5, col("#857760"))
        pts.append((x, y, z + 9))
    k.land.tube(pts, 3.0, col("#a39479"), seg=4)
    # Kartlis Deda: a slim aluminium figure with outstretched arms on a plinth
    mx, my = statue
    mz = GROUND - 5 + ridge_h
    k.land.box(mx - 3, my - 3, mz - 6, mx + 3, my + 3, mz + 6, col("#8a8a86"))
    k.land.box(mx - 1.6, my - 1.6, mz + 6, mx + 1.6, my + 1.6, mz + 24, col("#c4c8ca"))
    k.land.blob((mx, my, mz + 25.5), (1.4, 1.4, 1.8), col("#c4c8ca"), k.np, sub=1, amp=0.0)
    k.land.tube([(mx, my - 7, mz + 19), (mx, my + 7, mz + 19)], 0.6, col("#c4c8ca"), seg=5)
    # Sameba cathedral on Elia hill: body, drum and the gold dome
    sx, sy = church
    k.mountain(sx, sy, 45, 260, rock="#8c8068", grass="#7b8150", z0=GROUND - 5)
    z = GROUND - 5 + 44
    k.land.box(sx - 32, sy - 26, z, sx + 32, sy + 26, z + 34, col("#d9c9a8"))
    k.land.box(sx - 18, sy - 34, z, sx + 18, sy + 34, z + 34, col("#d9c9a8"))
    k.land.cyl(sx, sy, z + 34, z + 70, 10, col("#d9c9a8"), seg=16)
    k.land.blob((sx, sy, z + 74), (10.5, 10.5, 12), col("#e0b64a"), k.np, sub=2, amp=0.0, shade=(0.9, 1.15))
    k.land.tube([(sx, sy, z + 84), (sx, sy, z + 96)], 0.9, col("#e0b64a"), seg=6)
    # the Bridge of Peace: a white wave of steel and glass over the river
    by = 340.0
    k.solid.box(-70, by - 2.5, GROUND - 0.4, -12, by + 2.5, GROUND, col("#cfd2d0"))
    for t in np.linspace(0, 1, 7):
        x = -70 + 58 * t
        k.solid.tube([(x, by - 3.2, GROUND), (x, by - 1.5, GROUND + 4 + 2 * math.sin(t * math.pi)), (x, by + 1.5, GROUND + 4 + 2 * math.sin(t * math.pi)),
                      (x, by + 3.2, GROUND)], 0.25, col("#e9f1f2"), seg=4)
    walls = ("#e6dcc8", "#d6c6a6", "#cdbb9c", "#efe7d8", "#c4b8a6", "#b9a68c")
    k.street_row(9.0, -40, 1500, walls, h=(10, 22), face="-x", band_p=0.5, sign_p=0.2,
                 bands=("#6b4a34", "#3d5a6b", "#8a3a2c", "#e9e1d0"))
    k.sidewalk(5.4, 9.0, y1=2000)
    for y in np.arange(26, 900, 22.0):
        x = -9.6
        if clear(x, y, GROUND + 9, 3):
            k.tree(x, y, rng.uniform(7, 9), spread=0.8)
    k.car(3.6, 14.0, "#d9c24a", "kei")
    k.car(MID(), 30.0, "#9aa1a8")
    k.car(-3.4, 52.0, "#efefea")
    k.car(-6.0, 26.0, "#2d3238")
    for x, y, z, sz in ((-600, 1200, 300, 120), (-200, 1600, 360, 140), (300, 1500, 320, 120)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 巴统

def alphabet_tower(k, x, y, h=130.0):
    """Two steel strands twisting round a slim core, the round viewing deck on top."""
    s = k.land
    z0 = GROUND
    s.cyl(x, y, z0, z0 + h - 12, 3.0, col("#e8eaec"), seg=12)
    for ph in (0.0, math.pi):
        pts = [(x + 6.5 * math.cos(ph + t * 7.5), y + 6.5 * math.sin(ph + t * 7.5), z0 + t * (h - 14)) for t in np.linspace(0, 1, 60)]
        s.tube(pts, 1.1, col("#c9ced2"), seg=5)
    for t in np.linspace(0.05, 0.95, 14):
        s.cyl(x, y, z0 + t * (h - 14), z0 + t * (h - 14) + 0.8, 6.8, col("#9aa3aa"), seg=12)
    s.blob((x, y, z0 + h - 6), (8, 8, 7), col("#dfe3e6"), k.np, sub=2, amp=0.0, shade=(0.85, 1.1))


def batumi(root):
    """The Black Sea boulevard: palms and pebbles on the left, the Alphabet Tower where the bay curves away."""
    k = Kit("batumi", 41, dist=1800.0)
    rng = k.rng
    shore = [(-60, -40.0), (150, -40.0), (450, -280.0), (900, -560.0), (1600, -760.0), (3000, -1000.0)]
    tower = polar(30, 800)
    sl = Sightline(*tower, half=5.0, top=1.5)
    coast(k, shore, sea="#2c6f93", beach="#a9a69e", land="#86955e", beach_w=16)
    rht_avenue(k)
    k.sidewalk(-30.0, -8.6, y1=160, colour="#c9c2b0")
    k.solid.box(-24.0, -60, GROUND + 0.15, -22.0, 160, GROUND + 0.17, col("#d9cfb8"))
    for y in np.arange(-30, 1200, 11.0):
        for xo in (-11.0, -19.0, -27.0):
            x = max(xo, shore_x(shore, y) + 20) if y > 150 else xo
            h = rng.uniform(7, 10)
            if sl.ok(x, y, GROUND + h, 4):
                k.palm(x + rng.uniform(-0.6, 0.6), y + rng.uniform(-1, 1), h, (rng.uniform(-0.06, 0.06), rng.uniform(-0.04, 0.04)))
    alphabet_tower(k, *tower)
    # the skyline along the curve of the bay, Batumi Tower with its wheel in the middle
    walls = ("#e8ecef", "#c9d2d8", "#b6c3cc", "#efe6d8", "#9fb3c0", "#d9d2c4")
    for _ in range(70):
        d, b = rng.uniform(1100, 2600), rng.uniform(0, 28)
        x, y = polar(b, d)
        if x < shore_x(shore, y) + 30:
            continue
        h = rng.uniform(25, 110)
        if sl.ok(x, y, GROUND + h, 20):
            w = rng.uniform(18, 40)
            k.far.box(x - w / 2, y - w / 2, GROUND, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(walls), 0.05, rng))
    bx, by = polar(12, 1700)
    k.land.box(bx - 14, by - 14, GROUND, bx + 14, by + 14, GROUND + 190, col("#dfe4e8"))
    k.land.tube([(bx - 15, by + 30 * math.cos(t), GROUND + 120 + 30 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40)], 1.2,
                col("#c74a3c"), seg=5)
    for i in range(18):
        x, y = polar(rng.uniform(-30, 25), rng.uniform(6000, 11000))
        k.mountain(x, y, rng.uniform(350, 800), rng.uniform(1800, 3000), rock="#577048", grass="#4c6a3c", rough=0.25)
    k.street_row(9.0, -40, 1600, walls, h=(15, 45), face="-x", band_p=0.5, sign_p=0.25)
    k.sidewalk(5.4, 9.0, y1=2000)
    k.car(3.6, 12.0, "#f1f0ec")
    k.car(-3.4, 40.0, "#c9c2b0")
    k.car(MID(), 34.0, "#3a4a6a")
    for i in range(4):
        x, y = polar(rng.uniform(35, 70), rng.uniform(500, 1400))
        if x < shore_x(shore, y) - 50:
            k.boat(x, y, 16, "#f2f2ee", mast=False)
    for x, y, z, sz in ((-700, 1400, 300, 140), (-200, 2000, 420, 180), (-1200, 900, 260, 110)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 北疆 · 赛里木湖

def yurt(k, x, y, r=3.2):
    k.solid.cyl(x, y, GROUND, GROUND + 2.0, r, col("#f2efe6"), seg=14)
    k.solid.tube([(x, y, GROUND + 2.0), (x, y, GROUND + 3.4)], r * 0.95, col("#e8e2d2"), seg=14)
    k.solid.box(x - 0.6, y - r - 0.05, GROUND, x + 0.6, y - r + 0.2, GROUND + 1.6, col("#b23a3a"))


def sayram(root):
    """The ring road round Sayram Lake: grassland down to the blue water, the Tian Shan white on the far shore."""
    k = Kit("sayram", 51, dist=6000.0, hstr=0.8)
    rng = k.rng
    k.road(-5.1, 1.9, y1=3000, lanes=(-4.95, 1.75), dashes=())
    for y in np.arange(-60, 3000, 9.0):
        k.solid.box(-1.66, y, GROUND, -1.54, y + 4.5, GROUND + 0.005, col("#e8c23a"))
    k.solid.box(-60, -60, GROUND - 1, -5.1, 3000, GROUND - 0.05, col("#87a25a"))
    k.solid.box(1.9, -60, GROUND - 1, 400, 3000, GROUND - 0.05, col("#8fa660"))
    k.sea(-9000, -60, -60, 12000, "#1f86b8", z=GROUND - 1.5)
    k.solid.box(-62, -60, GROUND - 3, -55, 3000, GROUND - 0.6, col("#b8b29c"))
    for _ in range(400):
        x, y = rng.uniform(-55, -6), rng.uniform(5, 400)
        s = rng.uniform(0.6, 2.2)
        k.solid.box(x, y, GROUND - 0.06, x + s, y + s * rng.uniform(0.6, 1.4), GROUND - 0.02,
                    col(rng.choice(("#e7c84a", "#d9d9e8", "#b8a0d0", "#9ab65a", "#7f9c4c"))))
    # the far shore: snow peaks of the Tian Shan, foothills below them
    for i in range(22):
        b = -10 + i * 4.6 + rng.uniform(-2, 2)
        d = rng.uniform(11000, 16000)
        x, y = polar(b, d)
        k.mountain(x, y, rng.uniform(1100, 1700), rng.uniform(2500, 4200), rock="#7d7a80", grass="#6f7a5a", snow="#f4f6f8",
                   snowline=0.5, z0=GROUND - 1.5, rough=0.3)
    for i in range(16):
        b = -5 + i * 6 + rng.uniform(-2, 2)
        x, y = polar(b, rng.uniform(6000, 9000))
        k.mountain(x, y, rng.uniform(300, 600), rng.uniform(1500, 2500), rock="#6c7a58", grass="#5f7a48", z0=GROUND - 1.5)
    # green slopes on the right with a camp of yurts and grazing horses
    for i in range(10):
        r = rng.uniform(300, 600)
        k.mountain(rng.uniform(r * 1.25 + 40, 1400), rng.uniform(100, 2500), rng.uniform(60, 160), r, rock="#7d8f58",
                   grass="#8fa660")
    for i, (x, y) in enumerate(((34, 70), (42, 82), (30, 96))):
        yurt(k, x, y)
    for _ in range(10):
        x, y = rng.uniform(15, 80), rng.uniform(20, 200)
        k.solid.box(x - 1.0, y - 0.3, GROUND + 0.8, x + 1.0, y + 0.3, GROUND + 1.6, col(rng.choice(("#5a3a28", "#2a2420", "#8a6a4a"))))
    k.car(-3.4, 70.0, "#efefea")
    k.car(MID(), 120.0, "#3a3e44")
    for x, y, z, sz in ((-3000, 9000, 2600, 900), (-1200, 12000, 3000, 1100), (1500, 10000, 2800, 900)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 多哈

def tornado_tower(k, x, y, h=195.0):
    for t in np.linspace(0, 1, 26):
        r = 16 - 6.0 * math.sin(math.pi * min(1.0, t * 1.05))
        k.land.cyl(x, y, GROUND + t * h, GROUND + t * h + h / 26 + 0.1, r, col("#3e5468") * (0.9 + 0.2 * (t % 0.08 > 0.04)), seg=16)


def doha_tower(k, x, y, h=238.0):
    k.land.cyl(x, y, GROUND, GROUND + h * 0.88, 23, col("#c9c3b4"), seg=20)
    k.land.blob((x, y, GROUND + h * 0.88), (23, 23, h * 0.12), col("#9fb5c4"), k.np, sub=2, amp=0.0, shade=(0.9, 1.1))
    k.land.tube([(x, y, GROUND + h * 0.95), (x, y, GROUND + h + 8)], 1.0, col("#d8d4cc"), seg=5)


def dhow(k, x, y, L, colour):
    """Wooden hull with a rising bow and a high square stern, one raked mast and its long lateen yard."""
    z = GROUND - 1.6
    W = L * 0.15

    def at(u, s, h):
        return (x + s, y + u, z + h)

    v, f = [], []
    ts = np.linspace(-1, 1, 11)
    for t in ts:
        w = W * max(0.08, (1 - t * t) ** 0.5) * (1.0 if t < 0.7 else 0.85 + 0.5 * (t - 0.7))
        deck = 1.3 + 0.9 * t * t + (0.8 * t if t > 0 else 0.0)
        v += [at(t * L / 2, -w * 0.35, -0.3), at(t * L / 2, w * 0.35, -0.3), at(t * L / 2, w, deck), at(t * L / 2, -w, deck)]
    for i in range(len(ts) - 1):
        a, b = 4 * i, 4 * i + 4
        f += [[a + j, a + (j + 1) % 4, b + (j + 1) % 4, b + j] for j in range(4)]
    n = 4 * (len(ts) - 1)
    f += [[3, 2, 1, 0], [n, n + 1, n + 2, n + 3]]
    k.solid.add(np.array(v), f, col(colour))
    k.solid.box(*at(-L * 0.25, -W * 0.8, 1.3)[:2], z + 1.3, *at(L * 0.2, W * 0.8, 1.45)[:2], z + 1.45, col("#6b4c32"))
    m0 = at(-L * 0.08, 0, 1.4)
    k.solid.tube([m0, at(-L * 0.14, 0, L * 0.75)], 0.11, col("#5e4630"), seg=5)
    k.solid.tube([at(-L * 0.62, 0, L * 0.25), at(L * 0.35, 0, L * 0.9)], 0.07, col("#5e4630"), seg=4)


def doha(root):
    """The Corniche: a palm median, dhows in the bay, the West Bay towers across the water."""
    k = Kit("doha", 61, dist=1500.0, hstr=1.1)
    rng = k.rng
    k.road(-11.0, 5.4, y1=3000, lanes=(-10.85, 5.25), dashes=(1.9, -7.5))
    k.solid.box(-4.0, -60, GROUND - 0.4, -1.6, 3000, GROUND + 0.2, col("#c9b892"))
    k.sidewalk(-19.0, -11.0, y1=3000, colour="#d9ccb0")
    k.rail(-18.7, -60, 2000, h=0.9, colour="#e8e2d4")
    k.sea(-9000, -60, -19.0, 12000, "#2f8aa0", z=GROUND - 1.6)
    k.solid.box(-21, -60, GROUND - 4, -19, 3000, GROUND + 0.1, col("#cbbd9c"))
    skyline_b = (18, 44)
    sl = Sightline(*polar(31, 2600), half=14.0, top=0.6)
    for y in np.arange(-20, 1500, 12.0):
        h = rng.uniform(8, 11)
        if sl.ok(-2.8, y, GROUND + h, 4):
            k.palm(-2.8, y, h)
        if y % 36 < 12 and sl.ok(-15.0, y, GROUND + h, 4):
            k.palm(-15.0, y + 5, h * 0.9)
    # West Bay across the bay
    glass = ("#3e5468", "#5b7184", "#8aa0b2", "#b8c4cc", "#2f3f52", "#cfd6da")
    for _ in range(46):
        b, d = rng.uniform(*skyline_b), rng.uniform(2300, 3200)
        x, y = polar(b, d)
        w, h = rng.uniform(25, 45), rng.uniform(80, 210)
        k.land.box(x - w / 2, y - w / 2, GROUND - 1.6, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(glass), 0.06, rng))
    doha_tower(k, *polar(27, 2500))
    tornado_tower(k, *polar(34, 2400))
    for i in range(3):
        x, y = polar(31 + i * 1.2, 2700)
        k.land.box(x - 14, y - 14, GROUND - 1.6, x + 14, y + 14, GROUND + 230 - i * 20, col("#c7ccd0"))
    k.solid.box(-2600, 1500, GROUND - 1.7, 0, 4200, GROUND - 1.0, col("#d8cdb4"))
    for i in range(9):
        x, y = polar(rng.uniform(26, 62), rng.uniform(40, 260))
        if x < -30:
            dhow(k, x, y, rng.uniform(12, 18), rng.choice(("#a97b4f", "#8f6844", "#b98a5a")))
    k.street_row(9.0, -40, 1600, ("#e9dcc4", "#d8c8a8", "#efe6d4", "#cdbb98"), h=(8, 20), face="-x", band_p=0.3, sign_p=0.1)
    k.sidewalk(5.4, 9.0, y1=3000, colour="#d9ccb0")
    k.car(3.6, 13.0, "#f4f4f2")
    k.car(MID(), 32.0, "#1e1f22")
    k.car(-7.6, 30.0, "#e8e3d4")
    k.build(root)


# ---------------------------------------------------------------- 北海道

def hokkaido(root):
    """Biei: a straight farm road with arrow snow poles, patchwork hills, a lone tree, the Tokachi range."""
    k = Kit("hokkaido", 71, dist=4000.0, hstr=0.8)
    rng = k.rng
    k.road(-1.9, 5.4, y1=3000, lanes=(-1.75, 5.25), dashes=())
    k.solid.box(1.84, -60, GROUND, 1.96, 3000, GROUND + 0.005, col("#e8c23a"))
    tree = polar(31, 420)
    sl = Sightline(*tree, half=4.0, top=1.2)
    stripes = [col(c) for c in ("#7fa64a", "#c9b45a", "#6d9440", "#a77fc0", "#9a7a50", "#8fb85a", "#d9c46a")]
    k.solid.box(-3000, -60, GROUND - 1, -1.9, 3000, GROUND - 0.1, col("#86a850"))
    k.solid.box(5.4, -60, GROUND - 1, 3000, 3000, GROUND - 0.1, col("#86a850"))
    # patchwork: strips of crops over the rolling ground, the near ones flat
    for i in range(60):
        x0 = -6 - i * 9.0
        k.solid.box(x0 - 9.0, 0, GROUND - 0.1, x0, 380, GROUND - 0.02, stripes[i % len(stripes)] * rng.uniform(0.92, 1.05))
    for _ in range(22):
        x, y = polar(rng.uniform(8, 80), rng.uniform(450, 2200))
        h = rng.uniform(12, 35)
        if not sl.ok(x, y, GROUND + h, 200):
            continue
        k.mountain(x, y, h, rng.uniform(220, 420), rock=rng.choice(("#7fa64a", "#9ab55a", "#c9b45a")), grass="#7fa64a", rough=0.1,
                   rings=6, segs=20)
    # the lone tree on its hill
    tx, ty = tree
    k.mountain(tx, ty, 8, 160, rock="#8fb85a", grass="#7fa64a", rough=0.05, rings=6, segs=20)
    for dx in (-2.5, 2.5):
        k.solid.cyl(tx + dx, ty, GROUND + 7.5, GROUND + 18, 0.5, col("#5a4a3a"), seg=6)
        for j in range(6):
            k.leaf.blob((tx + dx + rng.uniform(-1.5, 1.5), ty + rng.uniform(-1.5, 1.5), GROUND + 17 + j * 2.6), (3.6 - j * 0.35,) * 2 + (2.6,),
                        col("#3f6a2c"), k.np, sub=2, amp=0.25)
    # the Tokachi range, a little snow left in the gullies
    for i in range(14):
        x, y = polar(-6 + i * 5.5 + rng.uniform(-2, 2), rng.uniform(18000, 26000))
        k.mountain(x, y, rng.uniform(1200, 1900), rng.uniform(3000, 5000), rock="#6d7280", grass="#5f7050", snow="#eef2f6",
                   snowline=0.7, rough=0.35)
    # arrow snow poles on both sides
    for y in np.arange(34, 900, 40.0):
        for x, sx in ((-2.8, 1), (6.3, -1)):
            if not sl.ok(x, y, GROUND + 5, 1):
                continue
            k.solid.box(x - 0.06, y - 0.06, GROUND, x + 0.06, y + 0.06, GROUND + 5.0, col("#e8e6e0"))
            k.solid.box(min(x, x + sx * 1.1), y - 0.03, GROUND + 4.6, max(x, x + sx * 1.1), y + 0.03, GROUND + 4.7, col("#e8e6e0"))
            ax = x + sx * 1.1
            k.solid.add(np.array([[ax - 0.3, y, GROUND + 4.65], [ax + 0.3, y, GROUND + 4.65], [ax, y, GROUND + 3.95]]), [[0, 1, 2]],
                        col("#d23c34"))
    for y in np.arange(40, 600, 60.0):
        k.tree(rng.uniform(12, 40), y + rng.uniform(-10, 10), rng.uniform(8, 14), palette=[col("#3f6a2c"), col("#4f7a34")])
    k.car(3.6, 60.0, "#efefea")
    for x, y, z, sz in ((-3000, 9000, 2400, 900), (0, 12000, 2900, 1100), (-6000, 8000, 2200, 800)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 福冈

def fukuoka_tower(k, x, y, h=234.0):
    s = k.land
    v = []
    for z, r in ((GROUND, 14.0), (GROUND + h * 0.6, 11.0), (GROUND + h * 0.62, 11.5)):
        v.append([(x + r * math.cos(a), y + r * math.sin(a), z) for a in (math.radians(90), math.radians(210), math.radians(330))])
    pts = np.array(v[0] + v[1])
    faces = [[0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5], [3, 4, 5]]
    s.add(pts, faces, col("#3d5f80"))
    for a in (90, 210, 330):
        r0, r1 = 14.6, 11.6
        ax, ay = math.cos(math.radians(a)), math.sin(math.radians(a))
        s.tube([(x + r0 * ax, y + r0 * ay, GROUND), (x + r1 * ax, y + r1 * ay, GROUND + h * 0.6)], 0.9, col("#e8eaec"), seg=4)
    s.box(x - 9, y - 9, GROUND + h * 0.6, x + 9, y + 9, GROUND + h * 0.66, col("#c9ced2"))
    s.tube([(x, y, GROUND + h * 0.66), (x, y, GROUND + h)], 1.6, col("#e8eaec"), seg=6)


def fukuoka(root):
    """Momochi: the seaside park and the beach on the left, Fukuoka Tower and the dome along the bay."""
    k = Kit("fukuoka", 81, dist=2200.0)
    rng = k.rng
    shore = [(-60, -70.0), (300, -70.0), (800, -300.0), (1400, -700.0), (2400, -1100.0)]
    tower = polar(32, 1500)
    sl = Sightline(*tower, half=5.0, top=1.0)
    coast(k, shore, sea="#2f7898", beach="#e3d6b8", land="#88a05c", beach_w=30)
    k.road(-1.6, 13.4, y1=2600, lanes=(-1.45, 13.25), dashes=(1.9, 9.9))
    k.solid.box(5.4, -60, GROUND - 0.4, 6.4, 2600, GROUND + 0.2, col("#8fa060"))
    k.sidewalk(-8.0, -1.6, y1=2600)
    for _ in range(200):
        x, y = rng.uniform(-60, -10), rng.uniform(-40, 1000)
        if x < shore_x(shore, y) + 32:
            continue
        h = rng.uniform(6, 10)
        if sl.ok(x, y, GROUND + h, 4):
            (k.palm if rng.random() < 0.45 else k.tree)(x, y, h)
    for y in np.arange(-30, 900, 10.0):
        if sl.ok(-4.0, y, GROUND + 7, 3):
            k.tree(-4.0, y, rng.uniform(6, 7.5), spread=0.8)
    fukuoka_tower(k, *tower)
    dx, dy = polar(21, 1250)
    k.land.blob((dx, dy, GROUND), (110, 110, 70), col("#c9ced2"), k.np, sub=3, amp=0.0, shade=(0.8, 1.1), floor=GROUND)
    walls = ("#efebe3", "#e2ddd3", "#d1ccc2", "#c9cdd0", "#b9c2c8")
    for _ in range(60):
        b, d = rng.uniform(5, 40), rng.uniform(1500, 2600)
        x, y = polar(b, d)
        if x < shore_x(shore, y) + 40:
            continue
        h = rng.uniform(20, 70)
        if sl.ok(x, y, GROUND + h, 25):
            w = rng.uniform(20, 40)
            k.far.box(x - w / 2, y - w / 2, GROUND, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(walls), 0.05, rng))
    k.street_row(17.0, -40, 1600, walls, h=(20, 55), face="-x", band_p=0.4, sign_p=0.3)
    k.sidewalk(13.4, 17.0, y1=2600)
    for y in np.arange(-20, 800, 9.0):
        k.tree(5.9, y, rng.uniform(6, 8), spread=0.9)
    k.car(3.6, 10.0, "#2b3a55")
    k.car(MID(), 24.0, "#f1f0ec")
    k.car(3.6, 46.0, "#e8e3d4", "bus")
    for x, y, z, sz in ((-800, 1600, 300, 140), (-300, 2200, 420, 170), (400, 1800, 320, 120)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 大连

def suspension_bridge(k, a, b, deck=42.0, tower_h=118.0, colour="#e8e2d4"):
    s = k.land
    a, b = np.array(a, float), np.array(b, float)
    d = b - a
    n = d / np.linalg.norm(d)
    side = np.array([-n[1], n[0]]) * 13
    for t in np.linspace(0, 1, 40)[:-1]:
        p, q = a + d * t, a + d * (t + 1 / 39)
        s.box(min(p[0], q[0]) - 6, min(p[1], q[1]) - 6, GROUND + deck - 3, max(p[0], q[0]) + 6, max(p[1], q[1]) + 6, GROUND + deck,
              col("#9aa0a4"))
    towers = [a + d * 0.32, a + d * 0.68]
    for tp in towers:
        for sgn in (-1, 1):
            c = tp + side * sgn
            s.box(c[0] - 3, c[1] - 3, GROUND - 2, c[0] + 3, c[1] + 3, GROUND + tower_h, col(colour))
        for z in (deck + 8, tower_h - 6):
            s.tube([(*(tp - side), GROUND + z), (*(tp + side), GROUND + z)], 2.0, col(colour), seg=4)
    for sgn in (-1, 1):
        pts = []
        for t in np.linspace(0, 1, 60):
            p = a + d * t + side * sgn
            if t < 0.32:
                z = deck + (tower_h - deck) * (t / 0.32) ** 1.6
            elif t > 0.68:
                z = deck + (tower_h - deck) * ((1 - t) / 0.32) ** 1.6
            else:
                u = (t - 0.5) / 0.18
                z = deck + 6 + (tower_h - deck - 6) * u * u
            pts.append((p[0], p[1], GROUND + z))
        s.tube(pts, 0.9, col("#c74a3c"), seg=4)
    for tp in towers:
        s.box(tp[0] - 20, tp[1] - 20, GROUND - 3, tp[0] + 20, tp[1] + 20, GROUND + 2, col("#8a8f92"))


def dalian(root):
    """Xinghai Bay: the coast road, the sea on the left and the cross-sea bridge strung across the bay."""
    k = Kit("dalian", 91, dist=2000.0)
    rng = k.rng
    rht_avenue(k, line="#e8c23a")
    k.sidewalk(-16.0, -8.6, y1=2600, colour="#c9c4b8")
    k.rail(-15.7, -60, 1600, h=1.0, colour="#e8e6e0")
    k.sea(-9000, -60, -16.0, 12000, "#3a7896", z=GROUND - 2.0)
    k.solid.box(-18, -60, GROUND - 5, -16, 2600, GROUND + 0.1, col("#a9a49a"))
    a, b = polar(13.5, 1290), polar(61, 1440)
    suspension_bridge(k, a, b)
    sl = Sightline(*polar(31, 1230), half=7.0, top=0.5)
    for y in np.arange(-20, 900, 14.0):
        if sl.ok(-12.0, y, GROUND + 7, 3):
            k.tree(-12.0, y, rng.uniform(5.5, 7.5), spread=0.8)
    # the far shore beyond the bridge, hills behind the city
    walls = ("#efebe3", "#e2d6c4", "#d1ccc2", "#c9cdd0", "#e9e0cc", "#b9c2c8")
    for _ in range(80):
        b_, d = rng.uniform(-5, 60), rng.uniform(2200, 3400)
        x, y = polar(b_, d)
        h = rng.uniform(20, 120)
        w = rng.uniform(20, 40)
        k.far.box(x - w / 2, y - w / 2, GROUND - 2, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(walls), 0.05, rng))
    for i in range(14):
        x, y = polar(-10 + i * 6, rng.uniform(4500, 6500))
        k.mountain(x, y, rng.uniform(150, 350), rng.uniform(800, 1400), rock="#5f7450", grass="#55704a", z0=GROUND - 2)
    k.street_row(9.0, -40, 1600, walls, h=(30, 90), face="-x", band_p=0.4, sign_p=0.25)
    k.sidewalk(5.4, 9.0, y1=2600)
    k.car(3.6, 12.0, "#efefea")
    k.car(MID(), 30.0, "#7a2f2f")
    k.car(-3.4, 44.0, "#2b3a55")
    k.car(-6.0, 20.0, "#d9d4c8", "bus")
    for x, y, z, sz in ((-900, 1800, 320, 140), (-200, 2400, 420, 170), (500, 2000, 340, 130)):
        k.cloud(x, y, z, sz)
    k.build(root)


# ---------------------------------------------------------------- 长沙

def changsha(root):
    """湘江大道: the river on the left, 橘子洲 in midstream, 岳麓山 on the far bank, the IFS towers ahead."""
    k = Kit("changsha", 101, dist=1600.0, hstr=1.1)
    rng = k.rng
    rht_avenue(k, line="#e8c23a")
    k.sidewalk(-30.0, -8.6, y1=2600, colour="#bdb6a8")
    k.rail(-29.7, -60, 2000, h=1.0, colour="#d9d4c8")
    k.sea(-9000, -60, -30.0, 12000, "#5a7a7a", z=GROUND - 6.0)
    k.solid.box(-32, -60, GROUND - 8, -30, 2600, GROUND + 0.1, col("#9d978a"))
    sl = Sightline(*polar(30, 3000), half=6.0, top=1.5)
    for y in np.arange(-20, 1200, 10.0):
        for x in (-12.0, -22.0):
            h = rng.uniform(7, 10)
            if sl.ok(x, y, GROUND + h, 4):
                k.tree(x + rng.uniform(-1, 1), y, h, spread=0.9)
    # 橘子洲: a long low island of trees in midstream
    k.solid.box(-380, -200, GROUND - 6.5, -260, 3000, GROUND - 4.0, col("#8a9a5a"))
    for _ in range(320):
        x, y = rng.uniform(-370, -270), rng.uniform(-150, 2800)
        h = rng.uniform(8, 14)
        if sl.ok(x, y, GROUND - 4 + h, 6):
            k.tree(x, y, h, z=GROUND - 4.0, palette=[col("#3f6a2c"), col("#4f7a34"), col("#5d8a3c")])
    # the far bank and 岳麓山 with its tower
    k.solid.box(-3000, -200, GROUND - 8, -900, 6000, GROUND + 1.0, col("#7f8a64"))
    for i in range(10):
        x, y = polar(22 + i * 2.6 + rng.uniform(-1, 1), rng.uniform(3000, 3600))
        k.mountain(x, y, rng.uniform(170, 290), rng.uniform(700, 1100), rock="#4f6a3a", grass="#4a6436", rough=0.15)
    mx, my = polar(30, 3200)
    k.land.box(mx - 3, my - 3, GROUND + 270, mx + 3, my + 3, GROUND + 330, col("#d8d4cc"))
    walls = ("#e2ddd3", "#d1ccc2", "#c9cdd0", "#efe6d8", "#b9c2c8")
    for _ in range(90):
        x, y = rng.uniform(-1600, -920), rng.uniform(0, 3000)
        h = rng.uniform(15, 60)
        if sl.ok(x, y, GROUND + h, 15):
            w = rng.uniform(15, 35)
            k.far.box(x - w / 2, y - w / 2, GROUND, x + w / 2, y + w / 2, GROUND + h, col(rng.choice(walls), 0.05, rng))
    # a bridge across the river
    by = 900.0
    k.land.box(-920, by - 12, GROUND + 14, -30, by + 12, GROUND + 17, col("#d8d4cc"))
    for x in np.arange(-900, -40, 70.0):
        k.land.tube([(x, by, GROUND - 6), (x + 35, by, GROUND + 12), (x + 70, by, GROUND - 6)], 1.4, col("#e8e4dc"), seg=4)
    # IFS: two glass towers ahead on our bank
    for i, (dxi, h) in enumerate(((0, 452), (60, 375))):
        x, y = 180 + dxi, 3000 + dxi * 0.5
        k.land.box(x - 28, y - 28, GROUND, x + 28, y + 28, GROUND + h, col("#7b8a98"))
    k.street_row(9.0, -40, 1600, walls, h=(25, 80), face="-x", band_p=0.5, sign_p=0.4)
    k.sidewalk(5.4, 9.0, y1=2600)
    k.skyline(500, 1800, (300, 800), 60, (40, 160), walls)
    k.car(3.6, 12.0, "#efefea")
    k.car(MID(), 28.0, "#2b3a55")
    k.car(-3.4, 38.0, "#c9c2b0")
    k.car(-6.0, 18.0, "#3a7a5a", "bus")
    k.build(root)


DESTS = {
    # sun direction in the desk frame (towards the sun), strength, colour, sky key (nightcity.SKIES)
    "nagoya": {"build": nagoya, "sun": (0.55, -0.5, 0.62), "sun_strength": 4.2, "sun_col": (1.0, 0.9, 0.78), "sky": "nagoya"},
    "tbilisi": {"build": tbilisi, "sun": (0.55, -0.5, 0.55), "sun_strength": 4.4, "sun_col": (1.0, 0.86, 0.7), "sky": "tbilisi"},
    "batumi": {"build": batumi, "sun": (0.55, -0.5, 0.62), "sun_strength": 4.2, "sun_col": (1.0, 0.92, 0.82), "sky": "batumi"},
    "sayram": {"build": sayram, "sun": (0.55, -0.5, 0.75), "sun_strength": 4.8, "sun_col": (1.0, 0.96, 0.9), "sky": "sayram"},
    "doha": {"build": doha, "sun": (0.55, -0.5, 0.5), "sun_strength": 4.0, "sun_col": (1.0, 0.86, 0.68), "sky": "doha"},
    "hokkaido": {"build": hokkaido, "sun": (0.55, -0.5, 0.7), "sun_strength": 4.4, "sun_col": (1.0, 0.95, 0.88), "sky": "hokkaido"},
    "fukuoka": {"build": fukuoka, "sun": (0.55, -0.5, 0.62), "sun_strength": 4.2, "sun_col": (1.0, 0.92, 0.8), "sky": "fukuoka"},
    "dalian": {"build": dalian, "sun": (0.55, -0.5, 0.62), "sun_strength": 4.2, "sun_col": (1.0, 0.93, 0.84), "sky": "dalian"},
    "changsha": {"build": changsha, "sun": (0.55, -0.5, 0.58), "sun_strength": 3.8, "sun_col": (1.0, 0.9, 0.78), "sky": "changsha"},
    # painted only; the snowy Hokkaido road stands in until .cache/paint/harbin/radiance.png exists
    "harbin": {"build": hokkaido, "sun": (0.55, -0.5, 0.5), "sun_strength": 2.4, "sun_col": (0.78, 0.85, 1.0), "sky": "harbin"},
}


def sun_world(dest):
    d = DESTS[dest]["sun"]
    o = nightcity.desk_to_world(0, 0)
    return (nightcity.desk_to_world(d[0], d[1], d[2]) - o).normalized()
