"""Local repaints of a composited 出发 backdrop with GPT Image 2: only a region is sent, only part of it kept.

The model re-renders the whole picture it gets, so a 16:9 crop around the spot goes out (upscaled to the
model's size), the answer is aligned back onto the crop (SIFT similarity) and only ``keep`` is pasted, feathered.

  gen    crop ``box`` of composed.png -> edit_<name>-XX.png (the model's answer, at its own size)
  apply  paste the picked answers of every edit of the destination      composed.png -> composed-edit.png
         (paint_text.py sign takes composed-edit.png when it exists)

Boxes are fractions of the composite. An edit without ``keep`` is not pasted: another tool consumes it
(paint_birds.py takes the bird-free sky as the plate under the birds it cuts out).

    python3 tools/scene/paint_edit.py changsha gen gym --n 2
    python3 tools/scene/paint_edit.py changsha apply --pick gym=1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import paint
import paint_layout as L

KEEP_ALL = """
Change nothing else: same framing, same composition, every other object, colour, light and detail stays
exactly as it is, pixel for pixel. No new objects, no text other than asked, no border."""

EDITS = {
    "changsha": {
        "gym": dict(box=(0.25, 0.2, 0.53, 0.48), keep=(0.33, 0.31, 0.47, 0.395), prompt="""
This is a crop of a voxel-style painting. Edit ONLY the light panel on the front of the big white stadium
(the Central South University gymnasium): it carries a sign reading exactly 中南大学体育馆 (these seven Chinese
characters, one line, left to right), bold red characters on the light panel, lying flat on the facade in its
exact perspective, the same voxel style. If the panel is too narrow for seven characters, make the panel
longer and a little lower so the line fits with a small margin; keep it centred where it is now.
""" + KEEP_ALL),
    },
    "dalian": {
        "sky": dict(box=(0.2, 0.06, 0.66, 0.52), prompt="""
This is a crop of a voxel-style painting. Remove EVERY seagull and bird from the sky, big and small. Where a
bird was, paint the sky and the clouds that are behind it, continuing them seamlessly.
""" + KEEP_ALL),
    },
}


def crop_px(size, box):
    W, H = size
    return int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)


def align(src: np.ndarray, ans: np.ndarray):
    """``ans`` (the model's answer) warped onto ``src`` (the crop it was given), by a RANSAC similarity."""
    a = cv2.resize(ans, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_AREA)
    ps, pa = paint.matches(src, a)
    S, inl = cv2.estimateAffinePartial2D(pa, ps, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    print(f"  aligned on {int(inl.sum())}/{len(ps)} matches, scale {np.hypot(S[0, 0], S[1, 0]):.4f} "
          f"shift {S[0, 2]:.1f},{S[1, 2]:.1f}px")
    return cv2.warpAffine(a, S, (src.shape[1], src.shape[0]), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)


def answer(dest: str, name: str, pick: int, base: Image.Image):
    """The picked answer of an edit, aligned onto the region of ``base`` it replaces, and that region's box."""
    e = EDITS[dest][name]
    x0, y0, x1, y1 = crop_px(base.size, e["box"])
    src = np.asarray(base.convert("RGB"))[y0:y1, x0:x1]
    ans = np.asarray(Image.open(L.OUT / dest / f"edit_{name}-{pick:02d}.png").convert("RGB"))
    return align(src, ans), (x0, y0, x1, y1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("stage", choices=("gen", "apply"))
    ap.add_argument("name", nargs="?")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--pick", nargs="*", default=[], help="apply: name=XX per edit (default 1)")
    a = ap.parse_args()
    out = L.OUT / a.dest
    base = Image.open(out / "composed.png").convert("RGB")
    if a.stage == "gen":
        e = EDITS[a.dest][a.name]
        x0, y0, x1, y1 = crop_px(base.size, e["box"])
        crop = base.crop((x0, y0, x1, y1)).resize((1536, round(1536 * (y1 - y0) / (x1 - x0))), Image.LANCZOS)
        crop.save(out / f"edit_{a.name}_input.png")
        paint.generate(e["prompt"], [crop], out, f"edit_{a.name}", a.n)
        return
    picks = dict(p.split("=") for p in a.pick)
    img = np.asarray(base).astype(np.float32)
    W, H = base.size
    for name, e in EDITS[a.dest].items():
        if "keep" not in e:
            continue
        ans, (x0, y0, x1, y1) = answer(a.dest, name, int(picks.get(name, 1)), base)
        k0, k1, k2, k3 = crop_px((W, H), e["keep"])
        m = np.zeros((y1 - y0, x1 - x0), np.float32)
        m[k1 - y0:k3 - y0, k0 - x0:k2 - x0] = 1
        r = max(3, (k3 - k1) // 6)
        m = cv2.GaussianBlur(cv2.erode(m, np.ones((r, r), np.uint8)), (0, 0), r / 2)[..., None]
        img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - m) + ans.astype(np.float32) * m
        print(f"pasted {name} at {k0},{k1} {k2 - k0}x{k3 - k1}")
    dst = out / "composed-edit.png"
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(dst)
    print(dst)


if __name__ == "__main__":
    main()
