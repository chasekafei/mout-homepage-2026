"""Even out the two lanes of a painted 出发 center view.

The image model tends to widen the lane the car is in. Both lanes are LANE wide (paint_layout.road), so in the
picture the dashed centre line runs exactly halfway between the two edge lines. Here the three lines are
found (white paint on asphalt, Hough), and every row below the horizon is remapped horizontally, piecewise
linear with the edge lines fixed, so the dashed line lands on the middle. Pavements and everything beyond
the edge lines stay where they are.

    python3 tools/scene/paint_lanes.py dalian --pick 1     # center-01.png -> center-01-lanes.png (+ _lines.png)
    python3 tools/scene/paint_lanes.py hokkaido --pick 4 --edge 75.9      # right edge direction given
"""
from __future__ import annotations

import argparse
import math

import cv2
import numpy as np
from PIL import Image

import paint_layout as L


def paint_mask(a: np.ndarray):
    """White road paint: bright, unsaturated, with asphalt (the colour at the bottom centre) right beside it."""
    h, w = a.shape[:2]
    hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)
    lum = hsv[..., 2].astype(int)
    road = np.median(lum[int(h * 0.85):, int(w * 0.3):int(w * 0.45)])
    white = (lum > max(185, road + 70)) & (hsv[..., 1] < 70)
    dark = np.abs(lum - road) < 28
    k = max(3, w // 300)
    sh = lambda m, dx: np.roll(m, dx, axis=1)
    near_dark = sh(dark, k) | sh(dark, -k) | sh(dark, 2 * k) | sh(dark, -2 * k)
    m = white & near_dark
    m[: int(h * 0.53)] = False                     # below the horizon only, clear of the far vanishing mess
    return m.astype(np.uint8) * 255


def lines(a: np.ndarray, vp: tuple[float, float] | None = None, edge: float | None = None):
    """Left edge, dashed centre line and right edge as x(y), all through one vanishing point.

    The vanishing point comes from the strongest left- and right-going Hough lines; the three lines are then
    the peaks of the direction histogram of the paint pixels seen from it (dashes are too broken for Hough).
    A kerb or snow bank can outvote the edge line it runs beside: then the vanishing point and the right
    edge's direction are given (pick one of the printed candidates).
    """
    h, w = a.shape[:2]
    m = paint_mask(a)
    if vp:
        vx, vy = vp
    else:
        hl = cv2.HoughLines(m, 1, np.pi / 720, threshold=max(40, h // 12))
        if hl is None:
            raise SystemExit("no lane lines found")
        best = {}
        for rho, th in hl[:, 0]:
            if abs(math.cos(th)) < 1e-3:
                continue
            dxdy = -math.tan(th)
            if 0.3 < abs(dxdy) < 6:
                best.setdefault(dxdy < 0, lambda y, rho=rho, th=th: (rho - y * math.sin(th)) / math.cos(th))
        if len(best) < 2:
            raise SystemExit("no vanishing point: need lines on both sides")
        vy = vanish(best[True], best[False])
        vx = best[True](vy)
    ys, xs = np.nonzero(m)
    ok = ys > vy + 0.03 * h
    ang = np.degrees(np.arctan2(xs[ok] - vx, ys[ok] - vy))           # 0 straight down, + to the right
    wgt = (ys[ok] - vy).astype(float)                                # near pixels are better measured
    hist, edges = np.histogram(ang, bins=np.arange(-89, 89.01, 0.25), weights=wgt)
    hist = np.convolve(hist, np.ones(5) / 5, "same")
    mid = (edges[:-1] + edges[1:]) / 2

    slope = np.tan(np.radians(mid))

    def peaks(sel, n):
        """(direction, strength) of the strongest directions, each blanking its neighbours within a fixed
        sideways spread (in x per y), strongest first."""
        hh, out = np.where(sel, hist, 0), []
        for _ in range(n):
            i = int(hh.argmax())
            if hh[i] <= 0:
                break
            out.append((mid[i], hh[i]))
            hh[np.abs(slope - slope[i]) < 0.35] = 0
        return out

    lft = [d for d, _ in peaks(mid < 0, 1)]
    cand = peaks(mid > 0, 6)
    rgt = sorted(d for d, _ in cand[:2])
    if edge is not None and rgt:
        rgt = [rgt[0], edge]
    print(f"vanishing point ({vx:.0f}, {vy:.0f}), lines at {[round(d, 1) for d in lft]} / "
          f"{[round(d, 1) for d in rgt]} deg; right-hand candidates (deg, strength) "
          f"{[(round(d, 1), round(s / cand[0][1], 2)) for d, s in cand]}")
    if not lft or len(rgt) < 2:
        raise SystemExit("need a left edge, the dashed line and a right edge")
    line = lambda deg: (lambda y: vx + math.tan(math.radians(deg)) * (y - vy))
    return line(lft[0]), line(rgt[0]), line(rgt[1])


def vanish(f, g):
    """Row where two lines x = f(y), x = g(y) meet."""
    y0, y1 = 0.0, 1000.0
    a0, a1 = f(y0) - g(y0), f(y1) - g(y1)
    return y0 - a0 * (y1 - y0) / (a1 - a0)


def even(a: np.ndarray, le, da, re):
    h, w = a.shape[:2]
    vy = vanish(le, re)
    y_start = int(max(vy + 0.02 * h, 0))
    mapx = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    for y in range(y_start, h):
        xl, xd, xr = le(y), da(y), re(y)
        xt = (xl + xr) / 2
        # target -> source: [xl, xt] from [xl, xd], [xt, xr] from [xd, xr]
        xs = np.arange(w, dtype=np.float32)
        src = xs.copy()
        i1 = (xs >= xl) & (xs < xt)
        i2 = (xs >= xt) & (xs <= xr)
        src[i1] = xl + (xs[i1] - xl) * (xd - xl) / max(xt - xl, 1e-3)
        src[i2] = xd + (xs[i2] - xt) * (xr - xd) / max(xr - xt, 1e-3)
        # fade in over the first rows so the far end is untouched
        t = min(1.0, (y - y_start) / (0.04 * h))
        mapx[y] = xs + (src - xs) * t
    mapy = np.tile(np.arange(h, dtype=np.float32)[:, None], (1, w))
    return cv2.remap(a, mapx, mapy, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--vp", help="vanishing point X,Y in pixels, when the detected one is off")
    ap.add_argument("--edge", type=float, help="direction of the right edge line in degrees, when a kerb wins")
    a = ap.parse_args()
    out = L.OUT / a.dest
    img = np.asarray(Image.open(out / f"center-{a.pick:02d}.png").convert("RGB"))
    h, w = img.shape[:2]
    le, da, re = lines(img, tuple(map(float, a.vp.split(","))) if a.vp else None, a.edge)
    y = h - 1
    xl, xd, xr = le(y), da(y), re(y)
    print(f"bottom row: left {xl:.0f} dash {xd:.0f} right {xr:.0f} -> lanes {xd - xl:.0f} / {xr - xd:.0f} px "
          f"({(xr - xd) / (xd - xl):.0%}), horizon at {vanish(le, re):.0f}")
    dbg = img.copy()
    for f, c in ((le, (255, 0, 0)), (da, (0, 255, 0)), (re, (0, 0, 255))):
        cv2.line(dbg, (int(f(h * 0.5)), int(h * 0.5)), (int(f(h)), h), c, 2)
    Image.fromarray(dbg).save(out / f"center-{a.pick:02d}_lines.png")
    fixed = even(img, le, da, re)
    Image.fromarray(fixed).save(out / f"center-{a.pick:02d}-lanes.png")
    print(out / f"center-{a.pick:02d}-lanes.png")


if __name__ == "__main__":
    main()
