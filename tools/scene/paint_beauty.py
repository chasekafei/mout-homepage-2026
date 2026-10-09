"""Lay a painted 出发 backdrop under a beauty render, the way the 3D viewer shows it.

Cycles renders the cabin lit by the painting (scene_depart.build_painted) but its view of the painting goes
through AgX like everything else and loses the painting's colours. Here the painting is projected into the
view camera, tinted where the glass roof is in between (x * t + r on linear colour, as Room3D does), and laid
under the cabin coverage from ``bake.py --stage guide --cam <cam>``.

    python3 tools/scene/paint_beauty.py nagoya desktop beauty_desktop_cabin.png beauty_desktop.png
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

from paint_radiance import from_srgb, to_srgb

ROOT = Path(__file__).resolve().parents[2]
BAKE = ROOT / ".cache" / "bake" / "depart"


def main():
    dest, cam, src, dst = sys.argv[1:5]
    painted = ROOT / ".cache" / "paint" / dest / "painted.png"
    if not painted.exists():
        shutil.copyfile(src, dst)
        return
    beauty = cv2.imread(src, cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255
    H, W = beauty.shape[:2]
    guide = cv2.imread(str(BAKE / f"guide_{cam}.png"), cv2.IMREAD_UNCHANGED)
    a = cv2.resize(guide[..., 3], (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
    c = json.loads((BAKE / f"guide_{cam}.json").read_text())
    b = json.loads((BAKE / "backdrop.json").read_text())
    P, F, R, U = (np.array(c[k]) for k in ("pos", "fwd", "right", "up"))
    sx = (np.arange(W) + 0.5) / W * 2 - 1
    sy = 1 - (np.arange(H) + 0.5) / H * 2
    d = F + sx[None, :, None] * c["tan_h"] * R + sy[:, None, None] * c["tan_v"] * U

    bF, bR, bU = (np.array(b[k]) for k in ("fwd", "right", "up"))
    C = np.array(b["pos"]) + bF * b["dist"]
    hw = b["dist"] * math.tan(math.radians(b["hfov"] / 2))
    hh = hw / b["aspect"]
    t = ((C - P) @ bF) / (d @ bF)
    hit = P + d * t[..., None] - C
    paint = cv2.imread(str(painted), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255
    ph, pw = paint.shape[:2]
    mx = (((hit @ bR) / hw) * 0.5 + 0.5) * pw - 0.5
    my = (0.5 - ((hit @ bU) / hh) * 0.5) * ph - 0.5
    view = cv2.remap(paint, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    x = from_srgb(view)
    g = b.get("glass")
    if g:
        O, Q1, Q3 = (np.array(g["quad"][i]) for i in (0, 1, 3))
        u, v = Q1 - O, Q3 - O
        tg = (O[1] - P[1]) / d[..., 1]
        h = P + d * tg[..., None] - O
        qu, qv = (h @ u) / (u @ u), (h @ v) / (v @ v)
        under = (tg > 0) & (tg < t) & (qu >= 0) & (qu <= 1) & (qv >= 0) & (qv <= 1)
        x = np.where(under[..., None], x * np.array(g["t"]) + g["r"], x)
    shown = to_srgb(np.clip(x, 0, 1))
    out = beauty * a + shown * (1 - a)
    cv2.imwrite(dst, np.round(np.clip(out, 0, 1) * 255).astype(np.uint8)[..., ::-1])
    print(dst, (W, H))


if __name__ == "__main__":
    main()
