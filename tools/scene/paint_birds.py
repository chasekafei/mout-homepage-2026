"""Cut the birds out of a painted 出发 backdrop, so the viewer flies each at its own depth instead of on the sky.

paint_edit.py's bird-free answer for ``sky`` is the clean plate: where it differs from the painting is a bird
(difference keying against a known background gives the soft edge too). Each bird goes into an RGBA atlas and
gets a depth from its size on screen, so it covers the same pixels from the desktop camera and parallaxes as
the camera orbits.

    python3 tools/scene/paint_birds.py dalian --pick 1
      .cache/paint/dalian/plate.png    painted.png without the birds: the 3D backdrop (beauty keeps painted.png)
      .cache/paint/dalian/birds.png    the cut-outs, straight alpha, colours bled into the clear pixels
      .cache/paint/dalian/birds.json   per bird: atlas uv and backdrop rect (fractions, top left origin), depth (m)
      .cache/paint/dalian/birds_check.png
"""
from __future__ import annotations

import argparse
import json
import math

import cv2
import numpy as np
from PIL import Image

import paint_edit as E
import paint_layout as L

NEAR, FAR = 5.0, 30.0
DEPTH_POW = 0.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--sky", type=float, default=0.44, help="birds are above this (fraction of the height)")
    ap.add_argument("--min-area", type=int, default=40)
    ap.add_argument("--drop", type=int, nargs="*", default=[], help="components to leave on the sky")
    a = ap.parse_args()
    out = L.OUT / a.dest
    base = Image.open(out / "painted.png").convert("RGB")
    W, H = base.size
    clean, (x0, y0, x1, y1) = E.answer(a.dest, "sky", a.pick, base)
    src = np.asarray(base)[y0:y1, x0:x1].astype(np.float32)
    cln = clean.astype(np.float32)
    d = np.abs(cv2.GaussianBlur(src, (0, 0), 0.8) - cv2.GaussianBlur(cln, (0, 0), 0.8)).max(-1)
    d[max(0, int(a.sky * H) - y0):] = 0

    n, lab, stats, _ = cv2.connectedComponentsWithStats((d > 45).astype(np.uint8), 8)
    birds, alpha = [], np.zeros(d.shape, np.float32)
    check = src.copy()
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area < a.min_area or i in a.drop:
            continue
        # matte: the component grown into its faint fringe, holes filled, solid inside and soft only at the rim
        # (a ratio matte would read the bird's own pale shading as see-through)
        p = max(6, int(max(bw, bh) * 0.15))
        sx0, sy0, sx1, sy1 = max(0, bx - p), max(0, by - p), min(d.shape[1], bx + bw + p), min(d.shape[0], by + bh + p)
        core = (lab[sy0:sy1, sx0:sx1] == i).astype(np.uint8)
        near = cv2.dilate(core, np.ones((5, 5), np.uint8), iterations=2) > 0
        solid = ((d[sy0:sy1, sx0:sx1] > 16) & near).astype(np.uint8)
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        ff = np.pad(solid, 1).copy()
        cv2.floodFill(ff, None, (0, 0), 1)
        solid = solid | (1 - ff[1:-1, 1:-1])
        al = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 0.7)
        alpha[sy0:sy1, sx0:sx1] = np.maximum(alpha[sy0:sy1, sx0:sx1], al)
        birds.append(dict(i=i, box=(sx0, sy0, sx1, sy1), size=max(bw, bh)))
    # the biggest bird NEAR, the others further the smaller they are; compressed (power < 1) from true scale,
    # which would put the small ones so far that they barely move against the sky
    big = max(b["size"] for b in birds)
    for b in birds:
        b["depth"] = round(float(np.clip(NEAR * (big / b["size"]) ** DEPTH_POW, NEAR, FAR)), 2)
        sx0, sy0, sx1, sy1 = b["box"]
        cv2.rectangle(check, (sx0, sy0), (sx1, sy1), (255, 0, 0), 2)
        cv2.putText(check, f"{b['i']}:{b['depth']:.0f}m", (sx0, max(12, sy0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    print(f"{len(birds)} birds, depths {sorted(b['depth'] for b in birds)}")

    # plate: the clean answer under every bird (a little wider), feathered into the painting
    m = cv2.GaussianBlur(cv2.dilate((alpha > 0).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32), (0, 0), 2)[..., None]
    plate = np.asarray(base).astype(np.float32).copy()
    plate[y0:y1, x0:x1] = src * (1 - m) + cln * m
    Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).save(out / "plate.png")

    # the painting's own pixels: the soft rim only reaches a pixel or so into the sky, which matches what is behind
    fg = src
    pad, shelf_h, cx, cy, ATLAS_W = 6, 0, 0, 0, 1024
    placed = []
    for b in sorted(birds, key=lambda b: -(b["box"][3] - b["box"][1])):
        sx0, sy0, sx1, sy1 = b["box"]
        w, h = sx1 - sx0, sy1 - sy0
        if cx + w + 2 * pad > ATLAS_W:
            cx, cy, shelf_h = 0, cy + shelf_h, 0
        placed.append((b, cx + pad, cy + pad))
        cx += w + 2 * pad
        shelf_h = max(shelf_h, h + 2 * pad)
    AH = 1 << max(4, math.ceil(math.log2(cy + shelf_h)))
    rgb = np.zeros((AH, ATLAS_W, 3), np.float32)
    al = np.zeros((AH, ATLAS_W), np.float32)
    items = []
    for b, ax, ay in placed:
        sx0, sy0, sx1, sy1 = b["box"]
        w, h = sx1 - sx0, sy1 - sy0
        rgb[ay:ay + h, ax:ax + w] = fg[sy0:sy1, sx0:sx1]
        al[ay:ay + h, ax:ax + w] = alpha[sy0:sy1, sx0:sx1]
        items.append(dict(
            uv=[round(ax / ATLAS_W, 5), round(ay / AH, 5), round((ax + w) / ATLAS_W, 5), round((ay + h) / AH, 5)],
            at=[round((x0 + sx0) / W, 5), round((y0 + sy0) / H, 5), round((x0 + sx1) / W, 5), round((y0 + sy1) / H, 5)],
            depth=b["depth"]))
    # bleed colours outwards so filtering at the edges never pulls in black
    have = al > 0.02
    for _ in range(12):
        num = cv2.blur(rgb * have[..., None], (3, 3))
        den = cv2.blur(have.astype(np.float32), (3, 3))[..., None]
        grow = (den[..., 0] > 0) & ~have
        rgb[grow] = (num / np.maximum(den, 1e-6))[grow]
        have |= grow
    Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(al * 255, 0, 255)]).astype(np.uint8), "RGBA").save(out / "birds.png")
    (out / "birds.json").write_text(json.dumps(items, indent=1))
    Image.fromarray(check.astype(np.uint8)).save(out / "birds_check.png")
    print(out / "plate.png", out / "birds.png", f"{ATLAS_W}x{AH}")


if __name__ == "__main__":
    main()
