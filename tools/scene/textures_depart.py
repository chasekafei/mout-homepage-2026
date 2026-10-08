"""Generate the 2D textures used by the 出发 car (centre screen, tickets, passport).

Run with the system python (needs Pillow):
    python3 tools/scene/textures_depart.py
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

from textures import save
from textures_now import BOLD_CN, SANS_CN, ttf

rng = random.Random(33)

# Order matches src/content/site.ts DESTS; the centre screen lists them all.
DESTS = ["名古屋", "第比利斯", "巴统", "北疆 · 赛里木湖", "多哈", "北海道", "福冈", "大连", "长沙"]


def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def screen():
    """Landscape centre screen in dark mode: the car and road on the left, a map with the route on the right."""
    W, H = 1600, 1000
    im = Image.new("RGB", (W, H), hx("#14161a"))
    d = ImageDraw.Draw(im)
    split = 560
    # left: car status, the road ahead
    d.rectangle((0, 0, split, H), fill=hx("#1b1e23"))
    d.text((48, 40), "P R N D", font=ttf(SANS_CN, 34), fill=hx("#6b7280"))
    d.text((48 + 3 * 46, 40), "D", font=ttf(BOLD_CN, 34), fill=hx("#f2f2f2"))
    d.text((48, 96), "48", font=ttf(BOLD_CN, 150), fill=hx("#f4f4f4"))
    d.text((52, 268), "km/h", font=ttf(SANS_CN, 34), fill=hx("#9aa0a8"))
    for i in range(14):
        t = i / 13
        y = 360 + t * 560
        half = 40 + t * 210
        d.line((split / 2 - half, y, split / 2 - half - 6, y + 40), fill=hx("#3a3f47"), width=6)
        d.line((split / 2 + half, y, split / 2 + half + 6, y + 40), fill=hx("#3a3f47"), width=6)
    d.polygon([(split / 2 - 70, 900), (split / 2 + 70, 900), (split / 2 + 52, 760), (split / 2 - 52, 760)], fill=hx("#e9e9ea"))
    d.rectangle((split / 2 - 44, 780, split / 2 + 44, 820), fill=hx("#2b2f36"))
    d.text((48, H - 70), "82%", font=ttf(SANS_CN, 34), fill=hx("#9aa0a8"))
    d.rectangle((140, H - 58, 300, H - 38), outline=hx("#6b7280"), width=3)
    d.rectangle((143, H - 55, 143 + 129, H - 41), fill=hx("#3fbf8a"))
    # right: map
    mx0 = split
    d.rectangle((mx0, 0, W, H), fill=hx("#20242b"))
    for _ in range(70):
        x0, y0 = rng.uniform(mx0, W), rng.uniform(0, H)
        a = rng.uniform(0, math.pi)
        L = rng.uniform(200, 900)
        d.line((x0, y0, x0 + L * math.cos(a), y0 + L * math.sin(a)), fill=hx("#2c3139"), width=rng.choice((4, 6, 10)))
    for _ in range(14):
        x0, y0 = rng.uniform(mx0, W), rng.uniform(0, H)
        d.ellipse((x0, y0, x0 + rng.uniform(60, 180), y0 + rng.uniform(40, 120)), fill=hx("#1d2a26"))
    route = [(mx0 + 220, 900), (mx0 + 260, 700), (mx0 + 420, 610), (mx0 + 470, 420), (mx0 + 640, 330), (mx0 + 700, 150)]
    d.line(route, fill=hx("#2f8cff"), width=22, joint="curve")
    d.line(route, fill=hx("#5aa8ff"), width=10, joint="curve")
    cx, cy = route[0]
    d.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=hx("#ffffff"))
    d.polygon([(cx, cy - 18), (cx + 13, cy + 14), (cx, cy + 6), (cx - 13, cy + 14)], fill=hx("#2f8cff"))
    px, py = route[-1]
    d.ellipse((px - 22, py - 22, px + 22, py + 22), fill=hx("#e8574a"))
    d.ellipse((px - 8, py - 8, px + 8, py + 8), fill=hx("#ffffff"))
    # destination list over the map
    lx0, ly0 = W - 470, 40
    d.rounded_rectangle((lx0, ly0, W - 40, ly0 + 70 + 82 * len(DESTS)), radius=22, fill=hx("#2a2f37"))
    d.text((lx0 + 30, ly0 + 22), "目的地", font=ttf(BOLD_CN, 34), fill=hx("#f2f2f2"))
    for i, name in enumerate(DESTS):
        y = ly0 + 86 + i * 82
        if i == 0:
            d.rounded_rectangle((lx0 + 14, y - 10, W - 54, y + 62), radius=14, fill=hx("#2f8cff"))
        d.ellipse((lx0 + 32, y + 16, lx0 + 52, y + 36), fill=hx("#ffffff") if i == 0 else hx("#6b7280"))
        d.text((lx0 + 72, y + 4), name, font=ttf(SANS_CN, 36), fill=hx("#ffffff") if i == 0 else hx("#c9ccd1"))
    # top bar
    d.text((mx0 + 30, 26), "17:42", font=ttf(SANS_CN, 32), fill=hx("#c9ccd1"))
    save(im, "depart_screen.png")


def ticket_games():
    """Table tennis ticket for the Asian Games in Aichi-Nagoya."""
    W, H = 900, 400
    im = Image.new("RGB", (W, H), hx("#f4f1ea"))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 110), fill=hx("#2fc9ab"))
    d.text((40, 22), "ASIAN GAMES 2026", font=ttf(BOLD_CN, 54), fill=hx("#ffffff"))
    d.text((40, 140), "AICHI-NAGOYA", font=ttf(BOLD_CN, 44), fill=hx("#24262b"))
    d.text((40, 200), "TABLE TENNIS · 乒乓球", font=ttf(SANS_CN, 40), fill=hx("#24262b"))
    d.text((40, 270), "ADMISSION · 1", font=ttf(SANS_CN, 34), fill=hx("#6b6f78"))
    for x in range(660, W - 40, 14):
        d.rectangle((x, 160, x + rng.choice((4, 6, 8)), 340), fill=hx("#24262b"))
    d.line((620, 120, 620, H), fill=hx("#c9c4b8"), width=3)
    d.ellipse((560, 300, 600, 340), fill=hx("#ff8a3d"))
    save(im, "depart_ticket_games.png")


def ticket_cinema():
    W, H = 640, 300
    im = Image.new("RGB", (W, H), hx("#ffd34a"))
    d = ImageDraw.Draw(im)
    d.rectangle((14, 14, W - 14, H - 14), outline=hx("#24262b"), width=4)
    d.text((40, 34), "CINEMA", font=ttf(BOLD_CN, 60), fill=hx("#24262b"))
    d.text((40, 120), "周三 10:30 · 3 号厅", font=ttf(SANS_CN, 38), fill=hx("#24262b"))
    d.text((40, 180), "ADMIT ONE · 全场 1 人", font=ttf(SANS_CN, 34), fill=hx("#24262b"))
    for y in range(30, H - 30, 26):
        d.ellipse((W - 70, y, W - 56, y + 14), fill=hx("#e8574a"))
    save(im, "depart_ticket_cinema.png")


def passport():
    """Passport cover with boarding passes sticking out of it (top face)."""
    W, H = 700, 980
    im = Image.new("RGB", (W, H), hx("#5b1f2a"))
    d = ImageDraw.Draw(im)
    gold = hx("#d9b36a")
    d.ellipse((W / 2 - 150, 330, W / 2 + 150, 630), outline=gold, width=10)
    d.ellipse((W / 2 - 60, 420, W / 2 + 60, 540), outline=gold, width=8)
    d.text((W / 2, 180), "PASSPORT", font=ttf(BOLD_CN, 74), fill=gold, anchor="mm")
    d.text((W / 2, 780), "MouT", font=ttf(BOLD_CN, 60), fill=gold, anchor="mm")
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    save(im, "depart_passport.png")
    bp = Image.new("RGB", (900, 360), hx("#f4f6f8"))
    d = ImageDraw.Draw(bp)
    d.rectangle((0, 0, 900, 90), fill=hx("#2f6fd6"))
    d.text((36, 18), "BOARDING PASS", font=ttf(BOLD_CN, 50), fill=hx("#ffffff"))
    d.text((36, 120), "TO  NGO · 名古屋", font=ttf(BOLD_CN, 70), fill=hx("#24262b"))
    d.text((36, 230), "SEAT 32A · GATE 17", font=ttf(SANS_CN, 40), fill=hx("#6b6f78"))
    save(bp, "depart_boarding.png")


if __name__ == "__main__":
    screen()
    ticket_games()
    ticket_cinema()
    passport()
