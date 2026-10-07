"""Generate the 2D textures used by the 游戏 room (CRT, arcade and GBA screens, arcade marquee).

Run with the system python (needs Pillow):
    python3 tools/scene/textures_game.py
"""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFont

from textures import save

PX = ImageFont.load_default()


def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def sprite(d, x, y, rows, pal):
    """Draw a sprite given as strings; each char maps through ``pal`` ('.' = transparent)."""
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                d.point((x + i, y + j), fill=pal[ch])


HERO = ["..kkkk..", ".kkkkkk.", ".kssssk.", ".sgsgss.", "..ssss..", ".rrrrrr.", "rrrrrrrr", "srrrrrrs",
        "..nnnn..", ".nn..nn.", ".kk..kk."]
HERO_PAL = {"k": hx("#141418"), "s": hx("#f1c49c"), "g": hx("#141418"), "r": hx("#e8574a"), "n": hx("#2c2f3d")}
CAT = ["k...k...", "kk.kk...", "kgkgk..k", "kkkkk..k", ".kkkkkkk", ".kkkkkk.", ".k.k.k.k"]


def upscale(im, k, scan=True):
    big = im.resize((im.width * k, im.height * k), Image.NEAREST)
    if scan:
        d = ImageDraw.Draw(big)
        for y in range(k - 1, big.height, k):
            d.line((0, y, big.width, y), fill=(0, 0, 0))
        big = Image.blend(im.resize(big.size, Image.NEAREST), big, 0.45)
    return big


def crt():
    """Side-scrolling platformer: MouT in a coral shirt, a cat ahead of him, coins and floating blocks."""
    W, H = 160, 120
    im = Image.new("RGB", (W, H), hx("#6aa6ff"))
    d = ImageDraw.Draw(im)
    for y in range(0, 60):
        t = y / 60
        d.line((0, y, W, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(hx("#4f8df5"), hx("#9cc8ff"))))
    for cx, cy in ((24, 18), (98, 12), (140, 26)):
        for dx, dy, r in ((0, 0, 6), (7, -3, 7), (14, 0, 6)):
            d.ellipse((cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r), fill=(255, 255, 255))
    for cx, h, c in ((30, 30, "#3fa34d"), (110, 22, "#2f8f45")):
        d.ellipse((cx - 34, 96 - h, cx + 34, 96 + h), fill=hx(c))
    for x in range(0, W, 8):
        for y in (96, 104, 112):
            d.rectangle((x, y, x + 7, y + 7), fill=hx("#c4663a"))
            d.line((x, y, x + 7, y), fill=hx("#f0a070"))
            d.line((x, y, x, y + 7), fill=hx("#8e3f20"))
    for x in (56, 64, 72):
        d.rectangle((x, 60, x + 7, 67), fill=hx("#c4663a"))
        d.rectangle((x, 60, x + 7, 60), fill=hx("#f0a070"))
    d.rectangle((80, 60, 87, 67), fill=hx("#ffd34a"))
    d.rectangle((82, 62, 85, 65), fill=hx("#e8574a"))
    for x in (60, 70, 120, 128, 136):
        d.ellipse((x, 48 if x < 100 else 78, x + 4, (48 if x < 100 else 78) + 5), fill=hx("#ffd34a"))
    # pipe-like teal pillar
    d.rectangle((140, 74, 155, 95), fill=hx("#2fc9ab"))
    d.rectangle((138, 70, 157, 76), fill=hx("#5ff0d8"))
    sprite(d, 36, 85, HERO, HERO_PAL)
    sprite(d, 104, 89, CAT, {"k": hx("#5a3b27"), "g": hx("#e8d36a")})
    d.text((4, 2), "MOUT  004200", font=PX, fill=(255, 255, 255))
    d.text((112, 2), "W 1-3", font=PX, fill=(255, 255, 255))
    save(upscale(im, 4), "game_crt.png")


def arcade():
    """Vertical shooter: rows of pixel invaders over a star field."""
    W, H = 120, 160
    im = Image.new("RGB", (W, H), hx("#07081a"))
    d = ImageDraw.Draw(im)
    rng = random.Random(3)
    for _ in range(70):
        x, y = rng.randrange(W), rng.randrange(H)
        d.point((x, y), fill=rng.choice([(255, 255, 255), (150, 170, 255), (255, 220, 150)]))
    inv = ["..k..k..", "...kk...", "..kkkk..", ".kk.kk.k", "kkkkkkkk", "k.kkkk.k", "k.k..k.k", "...kk..."]
    for j, col in enumerate(("#e8574a", "#ffd34a", "#2fc9ab", "#b58cf0")):
        for i in range(6):
            sprite(d, 12 + i * 16, 24 + j * 14, inv, {"k": hx(col)})
    ship = ["...kk...", "...kk...", "..kkkk..", ".kkrrkk.", "kkkkkkkk", "kk.kk.kk"]
    sprite(d, 56, 140, ship, {"k": hx("#e9eef0"), "r": hx("#e8574a")})
    for y in range(90, 136, 9):
        d.line((60, y, 60, y + 4), fill=hx("#5ff0d8"))
    d.text((3, 2), "1UP 01980", font=PX, fill=(255, 255, 255))
    d.text((74, 2), "HI 52010", font=PX, fill=hx("#ffd34a"))
    save(upscale(im, 4), "game_arcade.png")


def marquee():
    W, H = 96, 24
    im = Image.new("RGB", (W, H), hx("#141418"))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 6):
        d.point((x + 2, 2), fill=hx("#ffd34a"))
        d.point((x + 2, H - 3), fill=hx("#ffd34a"))
    d.text((12, 6), "MOUT ARCADE", font=PX, fill=hx("#e8574a"))
    d.text((13, 6), "MOUT ARCADE", font=PX, fill=hx("#ff8a6e"))
    save(upscale(im, 8, scan=False), "game_marquee.png")


def gba():
    """The wedding invitation: a little hall with a red carpet, the couple, the cat and a banner."""
    W, H = 120, 80
    im = Image.new("RGB", (W, H), hx("#f3e6c8"))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 10):
        for y in range(28, H, 10):
            d.rectangle((x, y, x + 9, y + 9), fill=hx("#e9d6ad") if (x + y) // 10 % 2 else hx("#f3e6c8"))
    d.rectangle((0, 0, W, 27), fill=hx("#bfe3dc"))
    for x in range(4, W, 14):
        d.rectangle((x, 6, x + 8, 22), fill=hx("#e9f6f2"))
    d.rectangle((52, 28, 68, H), fill=hx("#d9534a"))
    d.rectangle((30, 2, 90, 13), fill=hx("#e8574a"))
    d.text((38, 2), "WEDDING", font=PX, fill=(255, 255, 255))
    sprite(d, 46, 44, HERO, HERO_PAL)
    bride = ["..bbbb..", ".bbbbbb.", ".bssssb.", ".sgsgss.", "..ssss..", ".wwwwww.", "wwwwwwww", "swwwwwws",
             ".wwwwww.", "wwwwwwww", ".ww..ww."]
    sprite(d, 66, 44, bride, {"b": hx("#5a3b27"), "s": hx("#f1c49c"), "g": hx("#141418"), "w": (255, 255, 255)})
    sprite(d, 86, 62, CAT, {"k": hx("#5a3b27"), "g": hx("#e8d36a")})
    heart = [".r.r.", "rrrrr", "rrrrr", ".rrr.", "..r.."]
    for x, y in ((58, 34), (20, 40), (100, 38)):
        sprite(d, x, y, heart, {"r": hx("#e8574a")})
    d.rectangle((4, 62, 50, 76), fill=(255, 255, 255), outline=hx("#141418"))
    d.text((7, 63), "PRESS A", font=PX, fill=hx("#141418"))
    save(upscale(im, 4), "game_gba.png")


def rug():
    """Graphite rug with a coral border and a field of teal pixel diamonds."""
    N = 128
    im = Image.new("RGB", (N, N), hx("#34363c"))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, N - 1, N - 1), outline=hx("#d9604e"), width=6)
    d.rectangle((9, 9, N - 10, N - 10), outline=hx("#ffd34a"), width=1)
    for cy in range(22, N - 16, 21):
        for cx in range(22 + (cy // 21 % 2) * 10, N - 16, 21):
            d.polygon([(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)], fill=hx("#2fc9ab"))
            d.point((cx, cy), fill=hx("#34363c"))
    save(im.resize((1024, 1024), Image.NEAREST), "game_rug.png")


def main():
    rug()
    crt()
    arcade()
    marquee()
    gba()


if __name__ == "__main__":
    main()
