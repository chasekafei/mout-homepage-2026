"""Generate the 2D textures used by the creation room (posters, notes, prints).

Run with the system python (needs Pillow):
    python3 tools/scene/textures.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools" / "scene" / "build" / "tex"
REF = ROOT / "ref"

FONTS = {
    "hand": "/System/Library/Fonts/Noteworthy.ttc",
    "chalk": "/System/Library/Fonts/Supplemental/ChalkboardSE.ttc",
    "bradley": "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "sans": "/System/Library/Fonts/Avenir Next.ttc",
    "pixel": str(Path.home() / "Library/Fonts/IPix.ttf"),
    "cn": str(Path.home() / "Library/Fonts/AlibabaPuHuiTi-2-65-Medium.otf"),
}

INK = (38, 36, 34)
PAPER = (246, 242, 233)
RED = (214, 64, 58)
YELLOW = (255, 214, 64)

rng = random.Random(7)


def font(kind: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS[kind], size, index=index)


def paper(w: int, h: int, base=PAPER, grain=6) -> Image.Image:
    im = Image.new("RGB", (w, h), base)
    px = im.load()
    for y in range(h):
        for x in range(w):
            n = rng.randint(-grain, grain)
            r, g, b = base
            px[x, y] = (r + n, g + n, b + n)
    return im.filter(ImageFilter.GaussianBlur(0.6))


def heart(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=RED):
    pts = []
    for i in range(64):
        t = i / 64 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy - y * s))
    d.polygon(pts, fill=color)


def wobble_line(d, x0, y0, x1, y1, width=3, color=INK, amp=1.2):
    steps = max(2, int(math.hypot(x1 - x0, y1 - y0) / 6))
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((x0 + (x1 - x0) * t + rng.uniform(-amp, amp), y0 + (y1 - y0) * t + rng.uniform(-amp, amp)))
    d.line(pts, fill=color, width=width, joint="curve")


def wobble_rect(d, x0, y0, x1, y1, width=3, color=INK):
    wobble_line(d, x0, y0, x1, y0, width, color)
    wobble_line(d, x1, y0, x1, y1, width, color)
    wobble_line(d, x1, y1, x0, y1, width, color)
    wobble_line(d, x0, y1, x0, y0, width, color)


def scribble(d, x0, y0, w, rows, gap, color=INK, width=2):
    for r in range(rows):
        y = y0 + r * gap
        x = x0
        end = x0 + w * rng.uniform(0.55, 1.0)
        while x < end:
            seg = rng.uniform(14, 46)
            wobble_line(d, x, y, min(end, x + seg), y + rng.uniform(-1, 1), width, color, 0.8)
            x += seg + rng.uniform(6, 12)


def poster_text(lines, size=(900, 1200), fsize=120, kind="hand", base=PAPER, heart_pos=None, lh=1.05, left=110, top=150):
    im = paper(*size, base=base)
    d = ImageDraw.Draw(im)
    f = font(kind, fsize)
    y = top
    for line in lines:
        d.text((left + rng.uniform(-6, 6), y), line, font=f, fill=INK)
        y += int(fsize * lh)
    if heart_pos:
        heart(d, *heart_pos)
    return im


def save(im: Image.Image, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / name)
    print("tex", name, im.size)


def wireframe_sheet(seed: int, size=(700, 940)):
    r = random.Random(seed)
    im = paper(*size)
    d = ImageDraw.Draw(im)
    w, h = size
    scribble(d, 60, 70, w - 140, 2, 34, width=3)
    y = 170
    for _ in range(r.randint(2, 3)):
        bh = r.randint(150, 230)
        wobble_rect(d, 60, y, w - 60, y + bh, 3)
        # inner layout blocks
        wobble_rect(d, 85, y + 25, 85 + (w - 170) * 0.42, y + bh - 25, 3)
        wobble_line(d, 85, y + 25, 85 + (w - 170) * 0.42, y + bh - 25, 2)
        wobble_line(d, 85 + (w - 170) * 0.42, y + 25, 85, y + bh - 25, 2)
        scribble(d, 85 + (w - 170) * 0.5, y + 40, (w - 170) * 0.48, 3, 32, width=2)
        y += bh + 40
    scribble(d, 60, y + 10, w - 140, 3, 34, width=2)
    return im


def main():
    # --- corkboard notes -------------------------------------------------
    save(poster_text(["Small", "Creators", "Brighter", "Tomorrow"], (760, 1100), 118, "hand",
                     heart_pos=(560, 960, 2.4), top=110, left=80), "note_small_creators.png")
    save(poster_text(["Better", "Tools", "A Kinder", "Web"], (640, 960), 100, "hand",
                     heart_pos=(140, 800, 1.6), top=90, left=70), "note_better_tools.png")
    for i in range(3):
        save(wireframe_sheet(11 + i), f"note_wire_{i}.png")
    for i, base in enumerate([(244, 205, 92), (240, 196, 80)]):
        im = paper(520, 620, base=base, grain=5)
        d = ImageDraw.Draw(im)
        scribble(d, 50, 80, 400, 6, 70, color=(70, 56, 30), width=4)
        save(im, f"note_sticky_{i}.png")
    # simple flowchart note
    im = paper(560, 640)
    d = ImageDraw.Draw(im)
    for (x, y) in [(80, 90), (300, 90), (190, 300), (80, 470), (300, 470)]:
        wobble_rect(d, x, y, x + 170, y + 110, 3)
    for a, b in [((165, 200), (275, 300)), ((385, 200), (275, 300)), ((275, 410), (165, 470)), ((275, 410), (385, 470))]:
        wobble_line(d, *a, *b, 3)
    save(im, "note_flow.png")

    # illustrated landscape photo (pinned) - painterly trees and house
    def landscape(seed, size=(900, 700)):
        r = random.Random(seed)
        w, h = size
        im = Image.new("RGB", size, (190, 214, 222))
        d = ImageDraw.Draw(im)
        for y in range(h):
            t = y / h
            c = (int(176 + 50 * t), int(206 + 30 * t), int(222 + 6 * t))
            d.line([(0, y), (w, y)], fill=c)
        d.rectangle([0, int(h * 0.62), w, h], fill=(132, 160, 96))
        d.rectangle([0, int(h * 0.78), w, h], fill=(112, 142, 82))
        d.rectangle([int(w * 0.52), int(h * 0.42), int(w * 0.78), int(h * 0.66)], fill=(232, 222, 204))
        d.polygon([(int(w * 0.49), int(h * 0.43)), (int(w * 0.65), int(h * 0.30)), (int(w * 0.81), int(h * 0.43))], fill=(150, 92, 70))
        d.rectangle([int(w * 0.62), int(h * 0.54), int(w * 0.67), int(h * 0.66)], fill=(110, 84, 64))
        for _ in range(7):
            x = r.randint(30, w - 30)
            base_y = int(h * r.uniform(0.6, 0.75))
            th = r.randint(140, 260)
            d.rectangle([x - 6, base_y - th * 0.4, x + 6, base_y], fill=(92, 70, 52))
            for k in range(4):
                rr = th * (0.32 - k * 0.05)
                cy = base_y - th * (0.45 + k * 0.17)
                d.ellipse([x - rr, cy - rr, x + rr, cy + rr], fill=(66 + k * 10, 104 + k * 12, 64 + k * 6))
        return im.filter(ImageFilter.GaussianBlur(1.2))

    save(landscape(3), "photo_landscape.png")
    save(landscape(9, (700, 900)), "photo_park.png")

    # --- newsletter pages (real 社思现场 pages) ---------------------------
    vol = REF / "社思现场-Vol.24"
    for i, name in enumerate(["00. Index.png", "03. Page 03.png"]):
        p = vol / name
        if p.exists():
            im = Image.open(p).convert("RGB")
            im = im.resize((450, 974), Image.LANCZOS)
            save(im, f"news_page_{i}.png")

    # --- posters ----------------------------------------------------------
    save(poster_text(["Still", "Write", "Still", "Build", "Still", "Curious"], (800, 1180), 128, "hand",
                     heart_pos=(150, 1080, 1.7), top=60, left=110, lh=0.98), "poster_still.png")
    save(poster_text(["A", "Calmer", "Brighter", "Internet"], (860, 1100), 138, "hand",
                     heart_pos=(560, 960, 2.0), top=90, left=90), "poster_calmer.png")

    # --- mug print (wraps around cylinder; text sits in a band) ----------
    im = Image.new("RGB", (2048, 512), (22, 22, 24))
    d = ImageDraw.Draw(im)
    f = font("hand", 92)
    for i, line in enumerate(["Good", "Ideas", "A Kinder", "Internet"]):
        d.text((560, 30 + i * 108), line, font=f, fill=(236, 206, 104))
    save(im, "mug_print.png")

    # --- journal pages ---------------------------------------------------
    im = paper(2000, 1400, base=(244, 236, 216), grain=5)
    d = ImageDraw.Draw(im)
    for page in range(2):
        x0 = 90 + page * 1000
        for row in range(18):
            d.line([(x0, 140 + row * 66), (x0 + 820, 140 + row * 66)], fill=(214, 206, 190), width=2)
        scribble(d, x0 + 20, 120, 760, 3, 66, width=4)
        wobble_rect(d, x0 + 30, 340, x0 + 380, 600, 3)
        wobble_rect(d, x0 + 430, 340, x0 + 780, 470, 3)
        scribble(d, x0 + 450, 520, 320, 2, 66, width=3)
        scribble(d, x0 + 20, 700, 760, 6 if page == 0 else 4, 66, width=4)
        if page == 1:
            wobble_rect(d, x0 + 30, 1000, x0 + 500, 1220, 3)
            wobble_line(d, x0 + 60, 1180, x0 + 160, 1080, 3)
            wobble_line(d, x0 + 160, 1080, x0 + 260, 1140, 3)
            wobble_line(d, x0 + 260, 1140, x0 + 380, 1040, 3)
    # gutter shade
    for i in range(80):
        a = int(60 * (1 - i / 80))
        d.line([(1000 - i, 0), (1000 - i, 1400)], fill=(244 - a, 236 - a, 216 - a))
        d.line([(1000 + i, 0), (1000 + i, 1400)], fill=(244 - a, 236 - a, 216 - a))
    save(im, "journal_pages.png")

    # --- book spines -------------------------------------------------------
    spines = [
        ("Write", (238, 236, 230), INK),
        ("Podcast", (70, 72, 76), (240, 238, 232)),
        ("Prototype", (236, 192, 58), INK),
        ("A Kinder Internet", (242, 240, 234), INK),
    ]
    for i, (txt, bg, fg) in enumerate(spines):
        im = paper(1400, 260, base=bg, grain=4)
        d = ImageDraw.Draw(im)
        f = font("sans", 130 if len(txt) < 12 else 112, index=1)
        d.text((70, 52), txt, font=f, fill=fg)
        save(im, f"spine_{i}.png")

    # --- cardboard box label ------------------------------------------------
    im = Image.new("RGB", (900, 700), (196, 158, 112))
    px = im.load()
    for y in range(700):
        for x in range(900):
            n = rng.randint(-7, 7)
            px[x, y] = (196 + n, 158 + n, 112 + n)
    d = ImageDraw.Draw(im)
    f = font("hand", 92)
    for i, line in enumerate(["Good", "Ideas", "Longer", "Lives"]):
        d.text((140, 80 + i * 118), line, font=f, fill=(48, 38, 30))
    heart(d, 600, 560, 1.4)
    save(im.filter(ImageFilter.GaussianBlur(0.5)), "box_label.png")

    # --- sweatshirt back print (transparent) ------------------------------
    im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # pixel T: yellow bar with red stem tip, as in the avatar brand
    u = 34
    ox, oy = 512 - 3 * u, 140
    for i in range(6):
        d.rectangle([ox + i * u, oy, ox + (i + 1) * u - 1, oy + u - 1], fill=(255, 214, 0, 255))
        d.rectangle([ox + i * u, oy + u, ox + (i + 1) * u - 1, oy + 2 * u - 1], fill=(255, 214, 0, 255))
    for j in range(2, 5):
        color = (255, 214, 0, 255) if j < 3 else (232, 58, 46, 255)
        d.rectangle([ox + 2 * u, oy + j * u, ox + 4 * u - 1, oy + (j + 1) * u - 1], fill=color)
    f = font("pixel", 150)
    txt = "永结童心"
    tw = d.textlength(txt, font=f)
    d.text((512 - tw / 2, 400), txt, font=f, fill=(226, 214, 186, 255))
    save(im, "shirt_print.png")

    # --- cartridge icons (white on transparent) ---------------------------
    def icon(name, draw_fn, fg=(236, 234, 228, 255)):
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        draw_fn(d, fg)
        save(im, f"icon_{name}.png")

    icon("muse", lambda d, c: (d.polygon([(48, 196), (128, 70), (208, 196)], fill=c),
                               d.polygon([(110, 98), (128, 70), (146, 98), (128, 112)], fill=(30, 30, 32, 255))))
    icon("inn", lambda d, c: (d.rounded_rectangle([60, 60, 196, 196], 46, fill=c),
                              d.rounded_rectangle([96, 96, 160, 196], 30, fill=(30, 30, 32, 255)),
                              d.ellipse([136, 140, 148, 152], fill=c)))
    icon("stp", lambda d, c: [d.rectangle([54 + i * 52, 54 + j * 52, 54 + i * 52 + 34, 54 + j * 52 + 34], fill=(40, 40, 42, 255))
                              for i in range(3) for j in range(3) if (i, j) != (2, 0)])

    # --- cat pillow print --------------------------------------------------
    im = paper(800, 600, base=(238, 232, 220), grain=4)
    d = ImageDraw.Draw(im)
    g = (58, 58, 62)
    u = 24
    cat = [
        "..X.........X..",
        "..XX.......XX..",
        "..XXXXXXXXXXX..",
        ".XXXXXXXXXXXXX.",
        ".XX..XXXXX..XX.",
        ".XXXXXXXXXXXXX.",
        ".XXXXXX.XXXXXX.",
        "..XXXXXXXXXXX..",
        "...XXXXXXXXX...",
    ]
    ox, oy = 400 - len(cat[0]) * u // 2, 190
    for j, row in enumerate(cat):
        for i, ch in enumerate(row):
            if ch == "X":
                d.rectangle([ox + i * u, oy + j * u, ox + (i + 1) * u - 1, oy + (j + 1) * u - 1], fill=g)
    save(im, "pillow_cat.png")

    # --- rug pattern (pixel pepita in gray/cream) -----------------------
    im = Image.new("RGB", (512, 512), (226, 222, 212))
    d = ImageDraw.Draw(im)
    u = 16
    for j in range(32):
        for i in range(32):
            if ((i // 2 + j // 2) % 2 == 0 and (i + j) % 3 != 0) or (i % 4 == 0 and j % 4 == 1):
                d.rectangle([i * u, j * u, i * u + u - 1, j * u + u - 1], fill=(98, 96, 94))
    save(im, "rug.png")

    # --- small labels for the shelf boxes and the old-web cube ---------
    im = paper(600, 220, base=(232, 228, 220))
    d = ImageDraw.Draw(im)
    d.rectangle([220, 90, 380, 130], fill=(40, 40, 42))
    save(im, "box_front.png")


if __name__ == "__main__":
    main()
