"""Generate the 2D textures used by the 工作 study (agent tool icons, module name plates).

Run with the system python (needs Pillow):
    python3 tools/scene/textures_work.py
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from textures import save
from textures_now import BOLD_CN, SANS_CN, ttf

TEAL = (96, 238, 214)
RED = (236, 72, 64)
TILE = (16, 24, 30)


def icon(name: str, draw):
    """32 px pixel icon on a dark tile, upscaled without filtering."""
    im = Image.new("RGB", (32, 32), TILE)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 31, 31), outline=(40, 70, 76))
    draw(d)
    save(im.resize((128, 128), Image.NEAREST), f"work_tool_{name}.png")


def search(d):
    d.ellipse((7, 6, 20, 19), outline=TEAL, width=3)
    d.line((18, 18, 25, 25), fill=TEAL, width=4)


def doc(d):
    d.polygon([(9, 5), (19, 5), (24, 10), (24, 27), (9, 27)], outline=TEAL)
    d.line((19, 5, 19, 10, 24, 10), fill=TEAL)
    for y in (14, 18, 22):
        d.line((12, y, 21, y), fill=TEAL, width=2)


def image(d):
    d.rectangle((5, 7, 26, 25), outline=TEAL, width=2)
    d.polygon([(7, 23), (13, 15), (17, 20), (20, 17), (24, 23)], fill=TEAL)
    d.ellipse((18, 9, 22, 13), fill=(240, 200, 90))


def mail(d):
    d.rectangle((5, 9, 26, 23), outline=TEAL, width=2)
    d.line((6, 10, 16, 17, 25, 10), fill=TEAL, width=2)


def database(d):
    for y in (6, 13, 20):
        d.ellipse((8, y, 23, y + 6), outline=TEAL, width=2)
    d.line((8, 9, 8, 23), fill=TEAL, width=2)
    d.line((23, 9, 23, 23), fill=TEAL, width=2)


def calendar(d):
    d.rectangle((6, 8, 25, 25), outline=TEAL, width=2)
    d.rectangle((6, 8, 25, 12), fill=TEAL)
    d.line((11, 5, 11, 9), fill=TEAL, width=2)
    d.line((20, 5, 20, 9), fill=TEAL, width=2)
    for x in (10, 15, 20):
        for y in (16, 20):
            d.rectangle((x, y, x + 1, y + 1), fill=TEAL)
    d.rectangle((20, 20, 21, 21), fill=RED)


def plate(name: str, title: str, sub: str, accent):
    """Name plate on the front of each career module: title, one quiet line, an accent pip."""
    W, H = 512, 112
    im = Image.new("RGB", (W, H), (30, 33, 38))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=(58, 63, 70), width=3)
    d.rectangle((22, 38, 40, 56), fill=accent)
    d.text((58, 18), title, font=ttf(BOLD_CN, 44), fill=(238, 236, 230))
    d.text((60, 70), sub, font=ttf(SANS_CN, 24), fill=(150, 158, 166))
    save(im, f"work_plate_{name}.png")


def main():
    for name, fn in (("search", search), ("doc", doc), ("image", image), ("mail", mail), ("database", database),
                     ("calendar", calendar)):
        icon(name, fn)
    plate("gov", "电子政务", "政务上微信 · 小程序", (120, 150, 170))
    plate("brand", "品牌营销", "H5 · 游戏化互动 campaign", (236, 180, 60))
    plate("games", "游戏", "定制小游戏 · 自研 · 互动营销", (120, 200, 110))
    plate("social", "社交", "语音房 · TIYA · 社思现场", (150, 130, 240))
    plate("agent", "AI Agent", "Super Intern · Skill · 工具调用", TEAL)


if __name__ == "__main__":
    main()
