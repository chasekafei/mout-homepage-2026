"""Lettering on the painted 出发 backdrops, set in real fonts instead of the image model's.

  center  re-letter what the model misspells on the chosen center painting (a flat-coloured panel found in a
          search box is repainted and the text set again)            center-XX.png -> center-XX-text.png
  sign    draw the place sign, the same yellow board in every destination, on the composite (with its
          paint_edit.py repaints); the model's own sign (if it drew one) is painted out first
                                                     composed.png / composed-edit.png -> painted.png

Boxes are fractions of the image they apply to.

    python3 tools/scene/paint_text.py nagoya center --pick 1
    python3 tools/scene/paint_text.py nagoya sign
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import paint_layout as L

LATIN_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
CN_BOLD = str(Path.home() / "Library/Fonts/AlibabaPuHuiTi-2-105-Heavy.otf")

FIXES = {
    # vertical blue banner on MIRAI TOWER, read top to bottom
    "nagoya": [dict(box=(0.45, 0.32, 0.53, 0.52), match=lambda r, g, b: (b > 140) & (r < 80) & (b - g > 70),
                    text="Aichi-Nagoya 2026", vertical=True, fill=(255, 255, 255), font=LATIN_BOLD, inset=0.1)],
}
# 长沙's gymnasium sign is repainted in perspective by the model instead (paint_edit.py)

# board (x0, y0, x1, y1) on the composite, post x and foot y; ``erase`` = (box, dx): the model's own sign,
# covered by the patch dx to its right
SIGNS = {
    "nagoya": dict(text="名古屋", board=(0.533, 0.452, 0.637, 0.503), post=0.6325, foot=0.6,
                   erase=[(0.62, 0.452, 0.66, 0.503, 0.042)]),
}
# the others are painted without a sign (paint.ROAD) and get the board on Nagoya's spot, the same in every view
for _dest, _name in (("tbilisi", "第比利斯"), ("batumi", "巴统"), ("sayram", "赛里木湖"), ("doha", "多哈"),
                     ("hokkaido", "北海道"), ("fukuoka", "福冈"), ("dalian", "大连"), ("changsha", "长沙"),
                     ("harbin", "哈尔滨")):
    SIGNS[_dest] = dict(SIGNS["nagoya"], text=_name, erase=[])

FRAME, FACE, INK, POST = (52, 55, 61), (247, 196, 28), (22, 22, 24), (88, 92, 99)


def panel(img: np.ndarray, box, match):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    sub = img[y0:y1, x0:x1].astype(int)
    m = match(sub[..., 0], sub[..., 1], sub[..., 2])
    if m.sum() < 50:
        raise SystemExit(f"no panel in {box}")
    # keep the rows/columns that are mostly panel
    cols = np.nonzero(m.sum(0) > 0.4 * m.sum(0).max())[0]
    rows = np.nonzero(m.sum(1) > 0.4 * m.sum(1).max())[0]
    return x0 + cols[0], y0 + rows[0], x0 + cols[-1] + 1, y0 + rows[-1] + 1, sub[m].mean(0)


def fit_font(d, text, path, box_w, box_h, frac):
    size = int(box_h * frac)
    font = ImageFont.truetype(path, size)
    while d.textlength(text, font=font) > box_w and size > 8:
        size -= 2
        font = ImageFont.truetype(path, size)
    return font


def overlay(im: Image.Image, fix):
    W, H = im.size
    x0, y0, x1, y1 = (int(fix["box"][0] * W), int(fix["box"][1] * H), int(fix["box"][2] * W), int(fix["box"][3] * H))
    S = 6
    tile = Image.new("RGBA", ((x1 - x0) * S, (y1 - y0) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    font = fit_font(d, fix["text"], fix["font"], tile.width * (1 - 2 * fix["inset"]), tile.height, 0.8)
    d.text((tile.width / 2, tile.height / 2), fix["text"], font=font, fill=fix["fill"] + (235,), anchor="mm")
    tile = tile.resize((x1 - x0, y1 - y0), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.35))
    im.paste(tile, (x0, y0), tile)
    print(f"overlaid {fix['text']!r} at {x0},{y0} {x1 - x0}x{y1 - y0}")
    return im


def letter(im: Image.Image, fix):
    if fix.get("overlay"):
        return overlay(im, fix)
    a = np.asarray(im.convert("RGB"))
    x0, y0, x1, y1, col = panel(a, fix["box"], fix["match"])
    pw, ph = x1 - x0, y1 - y0
    S = 6
    long_, short = (ph, pw) if fix["vertical"] else (pw, ph)
    tile = Image.new("RGB", (long_ * S, short * S), tuple(int(c) for c in col))
    d = ImageDraw.Draw(tile)
    font = fit_font(d, fix["text"], fix["font"], long_ * S * (1 - 2 * fix["inset"]), short * S, 0.62)
    d.text((long_ * S / 2, short * S / 2), fix["text"], font=font, fill=fix["fill"], anchor="mm")
    if fix["vertical"]:
        tile = tile.rotate(-90, expand=True)
    tile = tile.resize((pw, ph), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.35))
    im.paste(tile, (x0, y0))
    print(f"lettered {fix['text']!r} at {x0},{y0} {pw}x{ph}")
    return im


def draw_sign(im: Image.Image, spec):
    W, H = im.size
    for x0, y0, x1, y1, dx in spec.get("erase", []):
        # clone a neighbouring patch over the model's sign, seams softened by a small inpaint
        X0, Y0, X1, Y1, DX = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H), int(dx * W)
        a = np.asarray(im.convert("RGB")).copy()
        a[Y0:Y1, X0:X1] = a[Y0:Y1, X0 + DX:X1 + DX]
        seam = np.zeros(a.shape[:2], np.uint8)
        seam[Y0 - 2:Y1 + 2, X0 - 2:X1 + 2] = 255
        seam[Y0 + 2:Y1 - 2, X0 + 2:X1 - 2] = 0
        a = cv2.inpaint(a[..., ::-1].copy(), seam, 3, cv2.INPAINT_TELEA)[..., ::-1]
        im = Image.fromarray(a.copy())
    bx0, by0, bx1, by1 = (int(spec["board"][0] * W), int(spec["board"][1] * H), int(spec["board"][2] * W),
                          int(spec["board"][3] * H))
    bw, bh = bx1 - bx0, by1 - by0
    px, foot = int(spec["post"] * W), int(spec["foot"] * H)
    pw = max(6, round(bh * 0.2))
    S = 4
    d = ImageDraw.Draw(im)
    # post: lit edge on the right (the sun is behind the car, to the right)
    d.rectangle((px - pw // 2, by1 - 2, px + pw // 2, foot), fill=POST)
    d.rectangle((px + pw // 2 - max(2, pw // 4), by1 - 2, px + pw // 2, foot), fill=(126, 130, 137))
    d.rectangle((px - pw, foot - 3, px + pw, foot + 1), fill=(70, 72, 78))
    tile = Image.new("RGBA", (bw * S, bh * S), (0, 0, 0, 0))
    t = ImageDraw.Draw(tile)
    r = bh * S * 0.12
    t.rounded_rectangle((0, 0, bw * S - 1, bh * S - 1), radius=r, fill=FRAME)
    m = round(bh * S * 0.09)
    t.rounded_rectangle((m, m, bw * S - 1 - m, bh * S - 1 - m), radius=r * 0.6, fill=FACE)
    # faint voxel grain and a top-lit gradient on the face
    rng = random.Random(len(spec["text"]))
    cell = max(4, round(bh * S * 0.08))
    for y in range(m, bh * S - m, cell):
        for x in range(m, bw * S - m, cell):
            k = rng.uniform(-0.035, 0.035) + 0.05 * (0.5 - y / (bh * S))
            c = tuple(int(min(255, max(0, v * (1 + k)))) for v in FACE)
            t.rectangle((x, y, min(x + cell - 1, bw * S - 1 - m), min(y + cell - 1, bh * S - 1 - m)), fill=c)
    font = fit_font(t, spec["text"], CN_BOLD, (bw * S - 2 * m) * 0.84, bh * S - 2 * m, 0.66)
    t.text((bw * S / 2, bh * S / 2 + bh * S * 0.02), spec["text"], font=font, fill=INK, anchor="mm")
    tile = tile.resize((bw, bh), Image.LANCZOS)
    im.paste(tile, (bx0, by0), tile)
    print(f"sign {spec['text']!r} at {bx0},{by0} {bw}x{bh}")
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("stage", choices=("center", "sign"))
    ap.add_argument("--pick", type=int, default=1)
    a = ap.parse_args()
    out = L.OUT / a.dest
    if a.stage == "center":
        src = out / f"center-{a.pick:02d}-lanes.png"
        im = Image.open(src if src.exists() else out / f"center-{a.pick:02d}.png").convert("RGB")
        for fix in FIXES.get(a.dest, []):
            im = letter(im, fix)
        dst = out / f"center-{a.pick:02d}-text.png"
    else:
        src = out / "composed-edit.png"
        im = draw_sign(Image.open(src if src.exists() else out / "composed.png").convert("RGB"), SIGNS[a.dest])
        dst = out / "painted.png"
    im.save(dst)
    print(dst)


if __name__ == "__main__":
    main()
