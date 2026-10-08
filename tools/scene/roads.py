"""The road outside the car, one builder per destination.

Everything is built in the desk frame (+Y = straight down the road) and parented to the car root, in the
``exterior`` collection, so it only shows up in the backdrop. The car sits in the left lane with its
centreline at x = ``car.MID_X``; the road surface is ``GROUND`` below the cabin floor.
"""
from __future__ import annotations

import math
import random

import numpy as np
from mathutils import Vector

import blib as B
import nightcity
from blib import srgb
from exterior import Batch, vmat

GROUND = -0.32
ASPHALT = srgb("#5d5f62")
LINE = srgb("#e9e7e0")


def col(h, jitter=0.0, rng=None):
    c = np.array(srgb(h))
    if jitter and rng:
        c = c * rng.uniform(1 - jitter, 1 + jitter)
    return c


class Kit:
    """A handful of batches (solid, windows facade, glow, leaves) shared by every destination."""

    def __init__(self, name, seed, windows=(1.9, 3.4, 0.5), dist=900.0, hstr=1.0):
        self.rng = random.Random(seed)
        self.np = np.random.default_rng(seed)
        self.solid = Batch(f"{name}_solid", vmat(f"{name}_solid", 0.8, 0.25, dist, hstr))
        self.facade = Batch(f"{name}_facade", vmat(f"{name}_facade", 0.6, 0.35, dist, hstr, windows=windows))
        self.glow = Batch(f"{name}_glow", nightcity.plain_mat(f"{name}_glow", 0.5, emit=4.0))
        self.leaf = Batch(f"{name}_leaf", vmat(f"{name}_leaf", 0.75, 0.2, dist, hstr), smooth=True)
        self.far = Batch(f"{name}_far", vmat(f"{name}_far", 0.9, 0.1, dist * 0.6, hstr))
        self.land = Batch(f"{name}_land", vmat(f"{name}_land", 0.6, 0.35, dist * 3.5, hstr))
        self.water = Batch(f"{name}_water", vmat(f"{name}_water", 0.05, 0.9, dist * 2.0, hstr))
        self.hills = Batch(f"{name}_hills", vmat(f"{name}_hills", 0.9, 0.15, dist * 3.0, hstr), smooth=True)

    def build(self, root):
        for b in (self.solid, self.facade, self.glow, self.leaf, self.far, self.land, self.water, self.hills):
            o = b.build()
            if o is not None:
                o.parent = root

    # ------------------------------------------------------------ pieces

    def road(self, x0, x1, y0=-60.0, y1=900.0, lanes=(), dashes=(), z=GROUND, colour=ASPHALT):
        s = self.solid
        s.box(x0, y0, z - 0.4, x1, y1, z, colour)
        for x in lanes:
            s.box(x - 0.075, y0, z, x + 0.075, y1, z + 0.004, LINE)
        for x in dashes:
            for y in np.arange(y0, y1, 12.0):
                s.box(x - 0.075, y, z, x + 0.075, y + 5.0, z + 0.004, LINE)

    def sidewalk(self, x0, x1, y0=-60.0, y1=900.0, colour="#b8b2a6", kerb=0.15):
        s = self.solid
        s.box(x0, y0, GROUND - 0.4, x1, y1, GROUND + kerb, col(colour))
        kx = x0 if x0 > 0 else x1 - 0.22
        s.box(kx, y0, GROUND + kerb, kx + 0.22, y1, GROUND + kerb + 0.01, col("#d4cfc4"))

    def crosswalk(self, x0, x1, y, depth=4.0):
        for x in np.arange(x0 + 0.3, x1 - 0.3, 0.9):
            self.solid.box(x, y, GROUND, x + 0.45, y + depth, GROUND + 0.005, LINE)
        self.solid.box(x0, y - 1.2, GROUND, x1, y - 0.9, GROUND + 0.005, LINE)

    def tree(self, x, y, h, spread=1.0, palette=None, z=GROUND, trunk="#6a5544"):
        rng = self.rng
        pal = palette or [srgb(c) for c in ("#5c8a38", "#6c9a40", "#4d7a30", "#79a548", "#638f3a")]
        self.solid.cyl(x, y, z, z + h * 0.55, 0.06 * h ** 0.6, col(trunk), seg=7)
        for _ in range(rng.randint(5, 9)):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.0, 0.32) * h * spread
            c = (x + r * math.cos(a), y + r * math.sin(a), z + h * rng.uniform(0.55, 0.85))
            rad = h * rng.uniform(0.22, 0.32) * spread
            self.leaf.blob(c, (rad, rad, rad * 0.8), np.array(rng.choice(pal)), self.np, sub=2, amp=0.28)

    def building(self, x0, y0, x1, y1, h, colour, z=GROUND, roof=None, band=None, sign=None, face="+x"):
        """A block with a world-space window grid; ``band`` = ground-floor shopfront colour, ``sign`` = vertical sign."""
        f = self.facade
        f.box(x0, y0, z - 0.4, x1, y1, z + h, colour)
        if roof is not None:
            self.solid.box(x0 + 0.3, y0 + 0.3, z + h, x1 - 0.3, y1 - 0.3, z + h + 0.5, roof)
        fx = x1 if face == "+x" else x0
        sx = 1 if face == "+x" else -1
        if band is not None:
            self.solid.box(min(fx, fx + sx * 0.12), y0 + 0.2, z, max(fx, fx + sx * 0.12), y1 - 0.2, z + 3.6,
                           col("#2b2d30"))
            self.solid.box(min(fx, fx + sx * 0.25), y0 + 0.2, z + 3.0, max(fx, fx + sx * 0.25), y1 - 0.2, z + 3.9, band)
            self.solid.box(min(fx, fx + sx * 0.13), y0 + 0.6, z + 0.4, max(fx, fx + sx * 0.13), y1 - 0.6, z + 2.8,
                           col("#3b4652"))
        if sign is not None:
            sy = self.rng.uniform(y0 + 0.5, y1 - 0.5)
            top = min(z + h - 0.5, z + self.rng.uniform(9, 16))
            self.solid.box(min(fx, fx + sx * 1.1), sy - 0.06, top - 6.0, max(fx, fx + sx * 1.1), sy + 0.06, top,
                           sign)
            self.solid.box(min(fx, fx + sx * 0.2), sy - 0.1, top - 6.0, max(fx, fx + sx * 0.2), sy + 0.1, top, col("#55585c"))

    def street_row(self, x_face, y0, y1, palette, h=(9, 30), depth=(14, 22), face="+x", band_p=0.6, sign_p=0.5,
                   signs=("#c93b35", "#2f6db0", "#e0a630", "#2f8a5a", "#f4f1ea"), gap=(0.0, 1.5), roof="#7b7e82",
                   bands=("#3d6fa8", "#d46a3a", "#f4f1ea", "#3a8a5c", "#b23a3a")):
        rng = self.rng
        y = y0
        while y < y1:
            w = rng.uniform(7, 18)
            d = rng.uniform(*depth)
            hh = rng.uniform(*h) * (1.6 if rng.random() < 0.12 else 1.0)
            c = col(rng.choice(palette), 0.05, rng)
            if face == "+x":
                bx0, bx1 = x_face - d, x_face
            else:
                bx0, bx1 = x_face, x_face + d
            self.building(bx0, y, bx1, y + w, hh, c, roof=col(roof),
                          band=col(rng.choice(bands)) if rng.random() < band_p else None,
                          sign=col(rng.choice(signs)) if rng.random() < sign_p else None, face=face)
            y += w + rng.uniform(*gap)

    def skyline(self, cx, cy, spread, n, h, palette, z=GROUND, depth=(20, 50)):
        rng = self.rng
        for _ in range(n):
            x = cx + rng.uniform(-spread[0], spread[0])
            y = cy + rng.uniform(-spread[1], spread[1])
            w, d = rng.uniform(*depth), rng.uniform(*depth)
            self.far.box(x - w / 2, y - d / 2, z - 1, x + w / 2, y + d / 2, z + rng.uniform(*h), col(rng.choice(palette), 0.06, rng))

    def pole_line(self, x, y0, y1, step=32.0, h=11.0, wires=3, colour="#8c8a84"):
        s = self.solid
        ys = list(np.arange(y0, y1, step))
        for y in ys:
            s.cyl(x, y, GROUND, GROUND + h, 0.16, col(colour), seg=10)
            s.box(x - 0.9, y - 0.06, GROUND + h - 0.8, x + 0.9, y + 0.06, GROUND + h - 0.65, col("#6e6c66"))
            s.cyl(x + 0.4, y + 0.25, GROUND + h - 2.6, GROUND + h - 1.6, 0.25, col("#7d7b74"), seg=8)
        for k in range(wires):
            dx = -0.8 + 1.6 * k / max(wires - 1, 1)
            for a, b in zip(ys[:-1], ys[1:]):
                pts = [(x + dx, a + (b - a) * t, GROUND + h - 0.7 - 0.7 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 9)]
                s.tube(pts, 0.012, col("#2a2a2a"), seg=4)

    def signal_jp(self, x, y, arm, h=5.6):
        """Japanese horizontal three-lamp signal on an arm reaching over the road (blue lit)."""
        s, g = self.solid, self.glow
        s.cyl(x, y, GROUND, GROUND + h + 0.4, 0.13, col("#9a9890"), seg=10)
        s.box(x, y - 0.06, GROUND + h - 0.06, x + arm, y + 0.06, GROUND + h + 0.06, col("#9a9890"))
        for k, ax in enumerate((arm * 0.55, arm)):
            s.box(x + ax - 1.25, y - 0.2, GROUND + h - 0.35, x + ax + 0.05, y + 0.12, GROUND + h + 0.35, col("#7a7a76"))
            for j, (lc, on) in enumerate((("#21a27a", True), ("#d9a830", False), ("#c8322c", False))):
                lx = x + ax - 1.05 + j * 0.42
                if on:
                    g.box(lx - 0.15, y - 0.22, GROUND + h - 0.15, lx + 0.15, y - 0.2, GROUND + h + 0.15, col("#4fe8c0"))
                else:
                    s.box(lx - 0.15, y - 0.22, GROUND + h - 0.15, lx + 0.15, y - 0.2, GROUND + h + 0.15, col(lc) * 0.35)

    def car(self, x, y, colour, kind="sedan", lights=True):
        s, g = self.solid, self.glow
        body = col(colour)
        L, W = (4.6, 1.8) if kind == "sedan" else (3.4, 1.48) if kind == "kei" else (11.0, 2.5)
        H = 1.45 if kind == "sedan" else 1.75 if kind == "kei" else 3.1
        z = GROUND + 0.28
        s.box(x - W / 2, y, z, x + W / 2, y + L, z + (0.62 if kind != "bus" else H - 0.3), body)
        if kind == "sedan":
            s.box(x - W / 2 + 0.12, y + 1.0, z + 0.62, x + W / 2 - 0.12, y + 3.4, z + H - 0.28, col("#2b3440"))
            s.box(x - W / 2 + 0.14, y + 1.15, z + H - 0.3, x + W / 2 - 0.14, y + 3.2, z + H - 0.26, body)
        elif kind == "kei":
            s.box(x - W / 2 + 0.06, y + 0.3, z + 0.62, x + W / 2 - 0.06, y + L - 0.6, z + H - 0.3, col("#2b3440"))
            s.box(x - W / 2 + 0.06, y + 0.3, z + H - 0.3, x + W / 2 - 0.06, y + L - 0.6, z + H - 0.22, body)
        else:
            s.box(x - W / 2 - 0.01, y + 0.4, z + 1.0, x + W / 2 + 0.01, y + L - 0.4, z + 2.2, col("#2b3440"))
        for sx in (-1, 1):
            s.cyl(x + sx * (W / 2 - 0.1), y + 0.8, GROUND, GROUND + 0.01, 0.3, col("#1a1a1a"), seg=8)
            if lights:
                g.box(x + sx * (W / 2 - 0.35) - 0.18, y - 0.02, z + 0.4, x + sx * (W / 2 - 0.35) + 0.18, y, z + 0.55,
                      col("#ff3a2a") * 0.6)
        s.box(x - 0.3, y - 0.03, z + 0.2, x + 0.3, y, z + 0.35, col("#e8e6df"))

    def cloud(self, x, y, z, size, colour="#f7f5f0"):
        rng = self.rng
        for _ in range(rng.randint(4, 7)):
            c = (x + rng.uniform(-1, 1) * size, y + rng.uniform(-0.4, 0.4) * size, z + rng.uniform(-0.1, 0.25) * size)
            r = size * rng.uniform(0.35, 0.6)
            self.far.blob(c, (r, r * 0.8, r * 0.55), col(colour), self.np, sub=2, amp=0.3, shade=(0.78, 1.05), floor=z - size * 0.15)

    def banner(self, x, y, z, colour, w=0.6, h=1.6):
        self.solid.box(x - 0.02, y - w / 2, z - h, x + 0.02, y + w / 2, z, col(colour))

    def sea(self, x0, y0, x1, y1, colour, z=GROUND - 1.2):
        self.water.box(x0, y0, z - 2, x1, y1, z, col(colour))

    def mountain(self, cx, cy, h, r, rock="#7d7468", grass=None, snow=None, snowline=0.62, z0=None, rings=12, segs=28,
                 rough=0.22, aspect=1.0):
        """Noisy cone; colour bands by height: grass at the foot, rock, snow above ``snowline`` of the height."""
        if math.hypot(cx - EYE[0], cy - EYE[1]) < r * max(1.0, aspect) * (1 + rough * 0.6) + 25:
            return
        rng = self.np
        z0 = GROUND if z0 is None else z0
        ph = rng.uniform(0, 6.3, 4)
        v, c = [], []
        for i in range(rings + 1):
            t = i / rings
            for j in range(segs):
                a = 2 * math.pi * j / segs
                n = (math.sin(a * 3 + ph[0]) * 0.5 + math.sin(a * 7 + ph[1]) * 0.3 + math.sin(a * 13 + ph[2]) * 0.2)
                rr = r * t * (1 + rough * 0.6 * n)
                zz = h * (1 - t) ** 1.5 * (1 + rough * 0.5 * math.sin(a * 5 + t * 9 + ph[3])) if i < rings else -2.0
                if i == 0:
                    zz = h
                v.append((cx + rr * math.cos(a) * aspect, cy + rr * math.sin(a), z0 + zz))
                f = zz / h
                streak = 0.08 * math.sin(a * 11 + ph[1])
                if snow and f > snowline + streak:
                    c.append(srgb(snow))
                elif grass and f < 0.28 + streak:
                    c.append(srgb(grass))
                else:
                    c.append(np.array(srgb(rock)) * (0.85 + 0.25 * f))
        faces = []
        for i in range(rings):
            for j in range(segs):
                j2 = (j + 1) % segs
                faces.append([i * segs + j, i * segs + j2, (i + 1) * segs + j2, (i + 1) * segs + j])
        self.hills.add(np.array(v), faces, np.array(c, dtype=np.float64))

    def palm(self, x, y, h, lean=(0.0, 0.0)):
        rng = self.rng
        top = np.array([x + lean[0] * h, y + lean[1] * h, GROUND + h])
        pts = [np.array([x, y, GROUND]) * (1 - t) + top * t + np.array([0, 0, 0]) for t in np.linspace(0, 1, 5)]
        for k, p in enumerate(pts[1:-1], 1):
            p[0] += lean[0] * h * 0.15 * math.sin(math.pi * k / 4)
        self.solid.tube(pts, 0.17, col("#8a7560"), seg=6)
        green = [col(c) for c in ("#4f7f3a", "#5d8f42", "#46733a")]
        for k in range(9):
            a = 2 * math.pi * k / 9 + rng.uniform(-0.2, 0.2)
            L = h * rng.uniform(0.32, 0.42)
            d = np.array([math.cos(a), math.sin(a), 0.0])
            side = np.array([-math.sin(a), math.cos(a), 0.0])
            v, f = [], []
            for i, t in enumerate(np.linspace(0, 1, 6)):
                p = top + d * L * t + np.array([0, 0, L * (0.25 * t - 0.75 * t * t)])
                w = 0.55 * math.sin(math.pi * min(1.0, t * 1.2 + 0.08)) + 0.05
                v += [p - side * w, p + side * w]
                if i:
                    f.append([2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i])
            self.leaf.add(np.array(v), f, rng.choice(green))

    def rail(self, x, y0, y1, h=1.0, colour="#c9c7c0", step=2.5):
        s = self.solid
        for y in np.arange(y0, y1, step):
            s.box(x - 0.05, y - 0.05, GROUND, x + 0.05, y + 0.05, GROUND + h, col(colour))
        s.box(x - 0.06, y0, GROUND + h - 0.08, x + 0.06, y1, GROUND + h, col(colour))
        s.box(x - 0.04, y0, GROUND + h * 0.5 - 0.04, x + 0.04, y1, GROUND + h * 0.5, col(colour))

    def boat(self, x, y, length=12.0, colour="#a97b4f", mast=True, z=GROUND - 1.2):
        s = self.solid
        w = length * 0.28
        s.box(x - w / 2, y - length / 2, z - 0.4, x + w / 2, y + length / 2, z + 1.4, col(colour))
        s.box(x - w / 2 + 0.3, y - length / 2 + 0.6, z + 1.4, x + w / 2 - 0.3, y + length / 2 - 2.0, z + 1.6, col("#7b5a3a"))
        s.box(x - w / 3, y - length / 2 + 1.2, z + 1.6, x + w / 3, y - length / 2 + 4.0, z + 3.2, col("#efe9dc"))
        if mast:
            s.tube([(x, y + length * 0.1, z + 1.4), (x, y + length * 0.1, z + 1.4 + length * 0.9)], 0.12, col("#5e4630"), seg=5)


# ---------------------------------------------------------------- sight lines

EYE = (0.9, -0.69, 1.42)      # desktop camera in the desk frame


def bearing(x, y):
    """Degrees left of straight ahead, seen from the desktop camera."""
    return math.degrees(math.atan2(EYE[0] - x, y - EYE[1]))


def elevation(x, y, z):
    return math.degrees(math.atan2(z - EYE[2], math.hypot(x - EYE[0], y - EYE[1])))


class Sightline:
    """Keeps a landmark visible: nothing within ``half`` degrees of its bearing may rise above ``top`` degrees.

    ``r`` is the object's horizontal reach (a tree crown), which widens the cone it blocks.
    """

    def __init__(self, x, y, half=5.0, top=1.2):
        self.b, self.half, self.top = bearing(x, y), half, top

    def ok(self, x, y, z, r=0.0):
        d = max(math.hypot(x - EYE[0], y - EYE[1]), 0.1)
        return abs(bearing(x, y) - self.b) > self.half + math.degrees(math.atan2(r, d)) or elevation(x, y, z) < self.top


def MID():
    import car
    return car.MID_X
