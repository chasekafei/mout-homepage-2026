"""Turn a painted 出发 backdrop (display sRGB) into the encoded radiance the viewer expects.

Everything on screen, the backdrop included, goes radiance -> colour balance -> display LUT (AgX + look,
tools/scene/bake.py stage_lut). A painting has to be pushed back through that chain so it comes out looking
like itself: the LUT is inverted numerically on a 65^3 grid of display colours (nearest dense forward sample,
then Gauss-Newton on the trilinear LUT), the colour balance analytically. Colours AgX cannot reach land on
the closest ones it can.

    python3 tools/scene/paint_radiance.py nagoya   # .cache/paint/nagoya/painted.png -> radiance.png (16 bit)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
BAKE = ROOT / ".cache" / "bake" / "depart"
G = 65


def to_srgb(c):
    c = np.maximum(c, 0)
    return np.where(c < 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def from_srgb(c):
    c = np.maximum(c, 0)
    return np.where(c < 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def load_lut(n):
    a = cv2.imread(str(BAKE / "lut.png"), cv2.IMREAD_UNCHANGED)[..., ::-1].astype(np.float64) / 65535.0
    # strip layout: x = b * n + r, y = g growing upwards  ->  lut[r, g, b]
    return a[::-1].reshape(n, n, n, 3).transpose(2, 0, 1, 3)


def trilinear(lut, l):
    n = lut.shape[0]
    p = np.clip(l, 0, 1) * (n - 1)
    i = np.minimum(np.floor(p).astype(int), n - 2)
    f = p - i
    out = 0
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = (f[:, 0] if dr else 1 - f[:, 0]) * (f[:, 1] if dg else 1 - f[:, 1]) * (f[:, 2] if db else 1 - f[:, 2])
                out = out + w[:, None] * lut[i[:, 0] + dr, i[:, 1] + dg, i[:, 2] + db]
    return out


def invert_lut(lut, targets):
    n = lut.shape[0]
    k = 4 * (n - 1) + 1
    g = np.linspace(0, 1, k)
    dense = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    fwd = trilinear(lut, dense)
    _, idx = cKDTree(fwd).query(targets, workers=-1)
    l = dense[idx]
    h = 1e-3
    for _ in range(8):
        f0 = trilinear(lut, l)
        J = np.stack([(trilinear(lut, l + h * e) - f0) / h for e in np.eye(3)], -1)   # (m, 3 out, 3 in)
        r = targets - f0
        JT = J.transpose(0, 2, 1)
        A = JT @ J + 1e-6 * np.eye(3)
        step = np.linalg.solve(A, (JT @ r[..., None]))[..., 0]
        l = np.clip(l + step, 0, 1)
    err = np.abs(trilinear(lut, l) - targets).max(1)
    return l, err


def main():
    dest = sys.argv[1]
    meta = json.loads((ROOT / "public" / "scene" / "depart" / "3d" / "scene.json").read_text())
    lo, hi, n = meta["lut"]["lo"], meta["lut"]["hi"], meta["lut"]["n"]
    K = meta["encodeK"]
    gain, lift = np.array(meta["grade"]["gain"]), np.array(meta["grade"]["lift"])
    lut = load_lut(n)
    g = np.linspace(0, 1, G)
    targets = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    l, err = invert_lut(lut, targets)
    print(f"LUT inverse: median err {np.median(err):.4f}, 99% {np.percentile(err, 99):.4f} (out of gamut colours clamp)")
    y = 2.0 ** (lo + l * (hi - lo))
    s = (to_srgb(y) / gain - 1) / (2 - lift) + 1
    x = from_srgb(s).reshape(G, G, G, 3)

    src = ROOT / ".cache" / "paint" / dest / "painted.png"
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float64) / 255.0
    H, W = img.shape[:2]
    p = img.reshape(-1, 3) * (G - 1)
    i = np.minimum(np.floor(p).astype(int), G - 2)
    f = p - i
    rad = 0
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = (f[:, 0] if dr else 1 - f[:, 0]) * (f[:, 1] if dg else 1 - f[:, 1]) * (f[:, 2] if db else 1 - f[:, 2])
                rad = rad + w[:, None] * x[i[:, 0] + dr, i[:, 1] + dg, i[:, 2] + db]
    enc = np.sqrt(rad / (rad + K)).reshape(H, W, 3)
    out = ROOT / ".cache" / "paint" / dest / "radiance.png"
    cv2.imwrite(str(out), np.round(enc[..., ::-1] * 65535).astype(np.uint16))
    # round trip on a sample: radiance -> colour balance -> LUT, against the painting
    sample = rad[:: max(1, len(rad) // 200000)]
    s2 = ((to_srgb(sample) - 1) * (2 - lift) + 1) * gain
    ll = np.clip((np.log2(np.maximum(from_srgb(s2), 1e-6)) - lo) / (hi - lo), 0, 1)
    back = trilinear(lut, ll)
    ref = img.reshape(-1, 3)[:: max(1, len(rad) // 200000)]
    d = np.abs(back - ref) * 255
    print(f"round trip: mean {d.mean():.2f}/255, 99% {np.percentile(d, 99):.1f}/255")
    print(out, (W, H))


if __name__ == "__main__":
    main()
