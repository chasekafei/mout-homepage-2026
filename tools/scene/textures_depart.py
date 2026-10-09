"""Generate the 2D textures used by the 出发 car (centre screen, tickets, passport).

Run with the system python (needs Pillow):
    python3 tools/scene/textures_depart.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from textures import save
from textures_now import BOLD_CN, SANS_CN, ttf

rng = random.Random(33)

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "design" / "出发场景参考"
# name, English name, the line under it (src/content/site.ts TRIPS), design reference, cover crop of the
# painted view (fractions; the reference's upper middle while there is no painting)
SCREENS = {
    "nagoya": ("名古屋", "NAGOYA", "亚运会的乒乓球，顺路往北去了金泽、高山和下吕。", "名古屋", (0.3, 0.2, 0.7, 0.56)),
    "tbilisi": ("第比利斯", "TBILISI", "在格鲁吉亚待了 13 天。", "第比利斯", (0.33, 0.15, 0.75, 0.57)),
    "batumi": ("巴统", "BATUMI", "格鲁吉亚的 13 天里，黑海边的那一站。", "巴统", (0.33, 0.2, 0.71, 0.57)),
    "sayram": ("赛里木湖", "SAYRAM LAKE", "自驾走完北疆大环线：阿勒泰、伊犁、赛里木湖。", "赛里木湖", (0.36, 0.18, 0.86, 0.56)),
    "doha": ("多哈", "DOHA", "", "多哈", (0.36, 0.14, 0.8, 0.58)),
    "hokkaido": ("北海道", "HOKKAIDO", "", "北海道", (0.25, 0.12, 0.8, 0.56)),
    "fukuoka": ("福冈", "FUKUOKA", "", "福冈", (0.31, 0.15, 0.73, 0.57)),
    "dalian": ("大连", "DALIAN", "", "大连", (0.24, 0.18, 0.66, 0.57)),
    "changsha": ("长沙", "CHANGSHA", "", "长沙", (0.24, 0.15, 0.8, 0.57)),
    "harbin": ("哈尔滨", "HARBIN", "", "哈尔滨", (0.28, 0.14, 0.72, 0.57)),
}


def cover(dest):
    *_, ref, box = SCREENS[dest]
    painted = ROOT / ".cache" / "paint" / dest / "painted.png"
    im, box = (Image.open(painted), box) if painted.exists() and box else (Image.open(REF / f"出发-{ref}.png"),
                                                                           (0.25, 0.05, 0.75, 0.45))
    w, h = im.size
    return im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))


def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def wrap(d, text, font, width):
    """Break CJK/Latin text into lines no wider than ``width``."""
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > width and cur:
            lines.append(cur)
            cur = ch.lstrip()
        else:
            cur += ch
    return lines + [cur] if cur else lines


def road_view(im, box, S):
    """Tesla-style live visualisation: the lanes ahead in perspective, a car in front, ours from behind."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(im)
    cx, hz = (x0 + x1) / 2, y0 + (y1 - y0) * 0.36
    bot = y1
    # road surface fading into the dark towards the horizon
    for k in range(64):
        t0, t1 = k / 64, (k + 1) / 64
        ya, yb = hz + (bot - hz) * t0 ** 1.6, hz + (bot - hz) * t1 ** 1.6
        g = int(24 + 22 * t1)
        wa, wb = 40 * S + (x1 - x0) * 0.75 * t0 ** 1.6, 40 * S + (x1 - x0) * 0.75 * t1 ** 1.6
        d.polygon([(cx - wa, ya), (cx + wa, ya), (cx + wb, yb), (cx - wb, yb)], fill=(g, g + 2, g + 6))

    def at(lane, t):
        """Screen point of a lane coordinate (-1.5..1.5, ego lane centred on 0) at depth parameter t (0 far, 1 near)."""
        e = t ** 1.6
        w = 40 * S + (x1 - x0) * 0.75 * e
        return cx + lane / 1.5 * w, hz + (bot - hz) * e

    # our lane's path in Autopilot blue, then the lane lines
    pts = [at(-0.5, t) for t in (0.02, 1.0)] + [at(0.5, t) for t in (1.0, 0.02)]
    d.polygon(pts, fill=hx("#1f3d75"))
    for lane in (-1.5, 1.5):
        d.line([at(lane, 0.02), at(lane, 1.0)], fill=hx("#9aa3ad"), width=int(5 * S))
    for lane in (-0.5, 0.5):
        for k in range(10):
            ta, tb = k / 10 + 0.02, k / 10 + 0.06
            d.line([at(lane, ta), at(lane, tb)], fill=hx("#d6dbe0"), width=int(4 * S + 3 * S * tb))

    def car(lane, t, col, glass):
        px, py = at(lane, t)
        s = (40 * S + (x1 - x0) * 0.75 * t ** 1.6) / 1.5 * 0.4    # a little over half a lane wide
        w, h = s, s * 0.78
        d.rounded_rectangle((px - w, py - h, px + w, py), radius=s * 0.22, fill=col)
        d.rounded_rectangle((px - w * 0.78, py - h * 1.42, px + w * 0.78, py - h * 0.62), radius=s * 0.26, fill=col)
        d.rounded_rectangle((px - w * 0.64, py - h * 1.28, px + w * 0.64, py - h * 0.74), radius=s * 0.16, fill=glass)
        d.rectangle((px - w * 0.92, py - h * 0.52, px + w * 0.92, py - h * 0.42), fill=hx("#d9473f"))
        d.ellipse((px - w * 1.02, py - h * 0.08, px + w * 1.02, py + h * 0.16), fill=(14, 15, 18))

    car(1.0, 0.36, hx("#6f7782"), hx("#3a4048"))
    car(0.0, 0.52, hx("#8a929c"), hx("#454c55"))
    car(0.0, 0.86, hx("#f3f4f6"), hx("#2b3036"))


def screen(dest, name, en, line, cover: Image.Image):
    """Centre screen in dark mode, the 多哈 reference layout: on the left the speed over the live road
    visualisation, on the right a card for the destination (cover picture, name, a line)."""
    S = 2
    W, H = 1600 * S, 1000 * S
    im = Image.new("RGB", (W, H), hx("#0d0f12"))
    d = ImageDraw.Draw(im)
    split = 700 * S
    road_view(im, (0, 0, split, H), S)
    d.text((48 * S, 34 * S), "P R N", font=ttf(SANS_CN, 30 * S), fill=hx("#5b616a"))
    d.text((48 * S + d.textlength("P R N ", font=ttf(SANS_CN, 30 * S)), 34 * S), "D", font=ttf(BOLD_CN, 30 * S),
           fill=hx("#f2f2f2"))
    d.text((48 * S, 86 * S), "48", font=ttf(BOLD_CN, 150 * S), fill=hx("#f4f4f4"))
    d.text((54 * S, 258 * S), "km/h", font=ttf(SANS_CN, 32 * S), fill=hx("#9aa0a8"))
    bx = split - 210 * S
    d.text((bx, 36 * S), "82%", font=ttf(SANS_CN, 30 * S), fill=hx("#9aa0a8"))
    d.rounded_rectangle((bx + 76 * S, 40 * S, bx + 160 * S, 66 * S), radius=5 * S, outline=hx("#6b7280"), width=3 * S)
    d.rounded_rectangle((bx + 80 * S, 44 * S, bx + 146 * S, 62 * S), radius=3 * S, fill=hx("#3fbf8a"))
    # destination card
    cx0, cy0, cx1, cy1 = split + 30 * S, 30 * S, W - 30 * S, H - 30 * S
    d.rounded_rectangle((cx0, cy0, cx1, cy1), radius=28 * S, fill=hx("#1a1d22"))
    iw, ih = cx1 - cx0 - 40 * S, 500 * S
    pic = cover.convert("RGB")
    r = max(iw / pic.width, ih / pic.height)
    pic = pic.resize((math.ceil(pic.width * r), math.ceil(pic.height * r)), Image.LANCZOS)
    pic = pic.crop(((pic.width - iw) // 2, (pic.height - ih) // 2, (pic.width - iw) // 2 + iw, (pic.height - ih) // 2 + ih))
    m = Image.new("L", (iw, ih), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, iw - 1, ih - 1), radius=20 * S, fill=255)
    im.paste(pic, (cx0 + 20 * S, cy0 + 20 * S), m)
    ty = cy0 + 20 * S + ih + 34 * S
    d.text((cx0 + 36 * S, ty), name, font=ttf(BOLD_CN, 76 * S), fill=hx("#ffffff"))
    d.text((cx0 + 36 * S + d.textlength(name, font=ttf(BOLD_CN, 76 * S)) + 24 * S, ty + 38 * S), en,
           font=ttf(SANS_CN, 30 * S), fill=hx("#8a9099"))
    f = ttf(SANS_CN, 32 * S)
    for k, ln in enumerate(wrap(d, line, f, cx1 - cx0 - 72 * S)[:3]):
        d.text((cx0 + 36 * S, ty + 116 * S + k * 50 * S), ln, font=f, fill=hx("#c9ccd1"))
    save(im.resize((W // S, H // S), Image.LANCZOS), f"depart_screen_{dest}.png")


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
    for k, (name, en, line, *_) in SCREENS.items():
        screen(k, name, en, line, cover(k))
    ticket_games()
    ticket_cinema()
    passport()
