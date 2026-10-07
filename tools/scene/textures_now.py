"""Generate the 2D textures used by the 此刻 café (laptop screen, coaster, latte, menu, signs, terrazzo).

Run with the system python (needs Pillow):
    python3 tools/scene/textures_now.py
The laptop screen is a screenshot of the site itself; it is taken from .cache/qa3d/desktop_default.jpg
(written by tools/qa/room3d.mjs) when present, otherwise the committed texture is kept.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from textures import INK, OUT, ROOT, font, heart, paper, save, wobble_line

HAND_CN = "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/a3c69464b629577766c23bcdb12ffbfe3759b923.asset/AssetData/Hanzipen.ttc"
SANS_CN = str(Path.home() / "Library/Fonts/AlibabaPuHuiTi-2-65-Medium.otf")
BOLD_CN = str(Path.home() / "Library/Fonts/AlibabaPuHuiTi-2-85-Bold.otf")
rng = random.Random(21)


def ttf(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return font("cn", size)


def laptop_screen():
    shot = ROOT / ".cache/qa3d/desktop_default.jpg"
    if not shot.exists():
        print("skip laptop screen: no", shot)
        return
    W, H = 1600, 1000
    im = Image.new("RGB", (W, H), (236, 234, 230))
    d = ImageDraw.Draw(im)
    bar = 64
    d.rectangle([0, 0, W, bar], fill=(228, 226, 222))
    for i, c in enumerate([(236, 106, 94), (244, 190, 80), (98, 196, 98)]):
        d.ellipse([24 + i * 30, 22, 44 + i * 30, 42], fill=c)
    d.rounded_rectangle([W * 0.3, 14, W * 0.7, bar - 14], 12, fill=(250, 249, 247))
    d.text((W / 2, bar / 2), "mout.me/create", font=ttf(SANS_CN, 24), fill=(90, 88, 84), anchor="mm")
    page = Image.open(shot).convert("RGB").resize((W, H - bar), Image.LANCZOS)
    im.paste(page, (0, bar))
    save(im, "now_laptop_screen.png")


def coaster():
    """Square kraft coaster with the current question written on it."""
    S = 900
    im = paper(S, S, base=(214, 186, 146), grain=8)
    d = ImageDraw.Draw(im)
    c = S / 2
    ring = (176, 146, 108)
    d.rounded_rectangle([34, 34, S - 34, S - 34], 60, outline=ring, width=6)
    f = ttf(HAND_CN, 92)
    lines = ["什么才是", "值得做的？"]
    y = c - 150
    for line in lines:
        d.text((c + rng.uniform(-8, 8), y), line, font=f, fill=INK, anchor="mm")
        y += 128
    wobble_line(d, c - 210, y - 40, c + 190, y - 30, width=5, color=(60, 52, 44))
    heart(d, c + 230, y - 60, 2.0)
    d.text((c, S - 150), "— 2026.10", font=ttf(HAND_CN, 54), fill=(84, 70, 56), anchor="mm")
    save(im, "now_coaster.png")


def latte():
    """Foam with a rosetta-ish heart, mapped onto the cup's liquid disc."""
    S = 512
    im = Image.new("RGB", (S, S), (150, 96, 58))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.ellipse([c - 230, c - 230, c + 230, c + 230], fill=(176, 118, 74))
    foam = (244, 232, 214)
    for k in range(5):
        r = 150 - k * 24
        cy = c + 80 - k * 34
        d.ellipse([c - r, cy - r * 0.55, c + r, cy + r * 0.55], fill=foam)
        d.ellipse([c - r + 10, cy - r * 0.55 + 14, c + r - 10, cy + r * 0.55 - 4], fill=(196, 140, 92))
    heart(d, c, c - 110, 4.2, color=foam)
    d.line([(c, c - 150), (c, c + 170)], fill=(196, 140, 92), width=6)
    save(im.filter(ImageFilter.GaussianBlur(2.0)), "now_latte.png")


def chalk(d, xy, text, f, fill=(238, 236, 228), anchor="la"):
    x, y = xy
    for k in range(3):
        d.text((x + rng.uniform(-1.2, 1.2), y + rng.uniform(-1.2, 1.2)), text, font=f, fill=fill, anchor=anchor)


def menu():
    W, H = 1200, 1500
    im = Image.new("RGB", (W, H), (44, 50, 47))
    px = im.load()
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            n = rng.randint(-5, 5)
            r, g, b = px[x, y]
            px[x, y] = (r + n, g + n, b + n)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(im)
    chalk(d, (W / 2, 120), "此刻 COFFEE", ttf(HAND_CN, 120), anchor="mm")
    wobble_line(d, 220, 210, W - 220, 214, width=4, color=(220, 210, 190))
    items = [("美式 Americano", "22"), ("拿铁 Latte", "28"), ("燕麦拿铁 Oat Latte", "30"), ("手冲 Pour Over", "32"),
             ("冷萃 Cold Brew", "30"), ("可颂 Croissant", "18"), ("巴斯克 Basque", "26")]
    f = ttf(HAND_CN, 64)
    y = 320
    for name, price in items:
        chalk(d, (130, y), name, f)
        chalk(d, (W - 130, y), price, f, fill=(244, 214, 120), anchor="ra")
        y += 128
    chalk(d, (W / 2, H - 150), "Wi-Fi: stay-curious", ttf(HAND_CN, 54), fill=(170, 214, 196), anchor="mm")
    heart(d, W - 200, H - 150, 1.8, color=(230, 120, 110))
    save(im, "now_menu.png")



def shop_sign(text, sub, bg, fg, name, w=1400, h=320):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([14, 14, w - 14, h - 14], outline=fg, width=6)
    d.text((w / 2, h * 0.44), text, font=ttf(BOLD_CN, int(h * 0.42)), fill=fg, anchor="mm")
    if sub:
        d.text((w / 2, h * 0.8), sub, font=font("sans", int(h * 0.14), 1), fill=fg, anchor="mm")
    save(im, name)


def a_board():
    W, H = 600, 900
    im = Image.new("RGB", (W, H), (40, 44, 42))
    d = ImageDraw.Draw(im)
    chalk(d, (W / 2, 140), "今日", ttf(HAND_CN, 110), anchor="mm")
    chalk(d, (W / 2, 300), "桂花拿铁", ttf(HAND_CN, 96), fill=(244, 214, 120), anchor="mm")
    chalk(d, (W / 2, 470), "猫猫可以进来", ttf(HAND_CN, 70), anchor="mm")
    heart(d, W / 2, 640, 3.0, color=(230, 120, 110))
    save(im, "now_aboard.png")


def tiles():
    """Terrazzo: warm off-white with coloured chips."""
    S = 1024
    im = Image.new("RGB", (S, S), (232, 226, 214))
    d = ImageDraw.Draw(im)
    chips = [(206, 150, 124), (156, 170, 150), (196, 188, 176), (150, 148, 146), (226, 204, 160), (248, 246, 240)]
    for _ in range(5200):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        r = rng.uniform(1.2, 4.0) * (1.8 if rng.random() < 0.06 else 1.0)
        c = rng.choice(chips)
        pts = [(x + r * math.cos(a) * rng.uniform(0.6, 1.2), y + r * math.sin(a) * rng.uniform(0.6, 1.2))
               for a in [i * math.pi * 2 / 6 + rng.uniform(-0.3, 0.3) for i in range(6)]]
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                d.polygon([(px + ox, py + oy) for px, py in pts], fill=c)
    save(im.filter(ImageFilter.GaussianBlur(0.7)), "now_terrazzo.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    laptop_screen()
    coaster()
    latte()
    menu()
    a_board()
    tiles()
    shop_sign("面包房", "BAKERY · SINCE 1998", (232, 214, 182), (120, 72, 46), "now_sign_bakery.png")
    shop_sign("小书店", "BOOKS & ZINES", (52, 78, 70), (236, 226, 200), "now_sign_books.png")
    shop_sign("花", "FLOWERS", (246, 240, 232), (196, 92, 84), "now_sign_flowers.png", w=900)
    shop_sign("洗衣房", "LAUNDRY 24H", (70, 112, 160), (246, 246, 240), "now_sign_laundry.png")


if __name__ == "__main__":
    main()
