"""Layout stencils for the painted 出发 backdrops.

Every destination is painted (tools/scene/paint.py) over a stencil drawn here in the exact projection of the
backdrop camera: horizon, the lane the car is in, and a flat-coloured block where each landmark and the place
sign stand. Ground coordinates are metres in the camera's level frame: X to the right, Y down the road, Z up
from the road surface.

    python3 tools/scene/paint_layout.py nagoya        # -> .cache/paint/nagoya/layout_{center,wide,ext}.png

The framings share the backdrop camera's axis: ``wide`` is the whole backdrop plane (118 degrees), ``center``
the 90-degree middle of it that the windscreen actually shows, painted first at the model's full resolution,
``ext`` a wider margin the side views (paint.py) are cut from.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache" / "paint"
W, H = 3840, 2160
EYE = 1.3                     # camera height above the road
CAR_X = -0.29                 # car centreline, camera-relative
LANE = 3.5

SKY, GROUND = (150, 196, 236), (120, 150, 110)
ROAD, LINE, KERB, WALK = (70, 72, 78), (240, 240, 235), (190, 190, 186), (178, 170, 160)
SIGN = (250, 200, 30)


def backdrop():
    return json.loads((ROOT / ".cache" / "bake" / "depart" / "backdrop.json").read_text())


CENTER_HFOV = 90.0
EXT_HFOV = 130.0              # beyond the backdrop, so the turned side views always land on stencil
TH = TV = 1.0


def set_frame(hfov, aspect):
    global TH, TV
    TH = math.tan(math.radians(hfov / 2))
    TV = TH / aspect


def px(X, Y, Z=0.0):
    Y = max(Y, 0.05)
    return (0.5 + X / Y / TH * 0.5) * W, (0.5 - (Z - EYE) / Y / TV * 0.5) * H


def ground(d, pts, col):
    """Polygon on the road plane, clipped to Y >= 1 by subdividing long edges."""
    d.polygon([px(x, max(y, 1.0)) for x, y in pts], fill=col)


def strip(d, x0, x1, y0, y1, col, z=0.0):
    d.polygon([px(x0, y0, z), px(x1, y0, z), px(x1, y1, z), px(x0, y1, z)], fill=col)


def block(d, x0, x1, y, z0, z1, col):
    """A camera-facing rectangle standing at distance y."""
    (a, b), (c, e) = px(x0, y, z1), px(x1, y, z0)
    d.rectangle([a, b, c, e], fill=col)


def tower(d, x, y, h, base_w, col):
    """Lattice tower: tapering trunk with a deck two thirds up."""
    pts = [px(x - base_w / 2, y, 0), px(x - base_w * 0.12, y, h * 0.92), px(x, y, h), px(x + base_w * 0.12, y, h * 0.92),
           px(x + base_w / 2, y, 0)]
    d.polygon(pts, fill=col)
    block(d, x - base_w * 0.42, x + base_w * 0.42, y, h * 0.42, h * 0.5, col)


def road(d, left=-1.0, right=1.0, far=3000):
    """Lanes either side of the car: ``left``/``right`` count lanes beyond the car's own lane."""
    x0 = CAR_X - LANE / 2 - left * LANE
    x1 = CAR_X + LANE / 2 + right * LANE
    strip(d, x0, x1, 1, far, ROAD)
    for k in range(int(-left), int(right) + 2):
        xe = CAR_X - LANE / 2 + k * LANE
        edge = xe <= x0 + 0.01 or xe >= x1 - 0.01
        if edge:
            strip(d, xe - 0.08, xe + 0.08, 1, far, LINE)
        else:
            for y in range(4, far, 12):
                strip(d, xe - 0.07, xe + 0.07, y, y + 5, LINE)
    return x0, x1


class Stand:
    """Upright things, drawn far to near once the ground is down."""

    def __init__(self):
        self.items = []

    def block(self, x0, x1, y, z0, z1, col):
        self.items.append((y, lambda d: block(d, x0, x1, y, z0, z1, col)))

    def tower(self, x, y, h, w, col):
        self.items.append((y, lambda d: tower(d, x, y, h, w, col)))

    def wall(self, x, y0, y1, z0, z1, col):
        """A vertical face running along the road at X = x, from y0 to y1."""
        y0 = max(y0, 1.0)
        self.items.append((y1, lambda d: d.polygon([px(x, y0, z0), px(x, y1, z0), px(x, y1, z1), px(x, y0, z1)],
                                                     fill=col)))

    def sign(self, x_post, y, w=2.6, z0=2.7, z1=3.7):
        self.block(x_post - 0.08, x_post + 0.08, y, 0, z1, (60, 60, 60))
        self.items.append((y - 0.01, lambda d: block(d, x_post - w + 0.3, x_post + 0.3, y, z0, z1, SIGN)))

    def draw(self, d):
        for _, f in sorted(self.items, key=lambda t: -t[0]):
            f(d)


TREE = (60, 120, 60)


def nagoya(d):
    x0, x1 = road(d, left=0, right=1)
    strip(d, x0 - 60, x0 - 3.5, 1, 3000, GROUND)                  # 久屋大通公园
    strip(d, x0 - 3.5, x0, 1, 3000, WALK)
    strip(d, x1, x1 + 5, 1, 3000, WALK)
    strip(d, x1 + 5, x1 + 400, 1, 3000, (150, 160, 120))
    strip(d, -16, -8, 20, 420, (90, 170, 220))                    # the long pool down the park to the tower
    s = Stand()
    s.tower(-12, 480, 180, 44, (200, 205, 215))                   # MIRAI TOWER straight down the pool
    for X, Y, w, h in ((-150, 700, 70, 60), (-250, 760, 90, 45), (120, 820, 60, 75), (200, 760, 70, 50)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, (205, 200, 190))   # city blocks
    s.block(-250, -175, 380, 30, 95, (150, 110, 90))              # 哈尔的移动城堡 over the park, left
    s.block(70, 110, 320, 0, 75, (130, 120, 95))                  # 天空之城 robot among the trees, right
    s.block(300, 380, 820, 20, 62, (60, 110, 80))                 # 名古屋城, far right
    s.block(x1 + 9, x1 + 26, 70, 0, 9, (120, 80, 50))             # 下吕-style wooden inn
    for y in range(40, 400, 30):
        s.block(x0 - 2.8, x0 - 1.0, y, 2.0, 7.5, TREE)
        s.block(x1 + 1.6, x1 + 3.6, y, 2.0, 8.0, TREE)
    s.block(-8.0, -7.4, 34, 0, 2.2, (25, 25, 30))                 # 无脸男 by the pool
    s.sign(x1 + 0.9, 14)
    s.draw(d)


WATER, SNOWCAP, HILL, SAND = (80, 160, 215), (225, 230, 238), (120, 135, 105), (215, 200, 165)
CITY, PALM, STONE = (205, 200, 190), (70, 130, 70), (165, 150, 130)

# The rest share Nagoya's road (our lane plus one to the right, both LANE wide) and its right-hand walk,
# so the place sign (paint_text.py) stands on the same spot of every painting. The stencils carry no
# sign: it is drawn afterwards.


def kerbs(d, x0, x1, left=None, right=None, walk_l=3.5, walk_r=5.0):
    strip(d, x0 - walk_l, x0, 1, 3000, WALK)
    strip(d, x1, x1 + walk_r, 1, 3000, WALK)
    if left:
        strip(d, x0 - 3000, x0 - walk_l, 1, 3000, left)
    if right:
        strip(d, x1 + walk_r, x1 + 3000, 1, 3000, right)


def tbilisi(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, STONE, STONE, walk_l=2.5)
    s = Stand()
    s.block(-200, 200, 1400, 0, 60, HILL)                          # the hillside the old town climbs
    s.block(-60, 40, 900, 0, 70, (150, 140, 110))                  # Sameba's hill
    s.block(-32, 12, 880, 70, 150, (225, 200, 120))                # 圣三一大教堂, gold dome on top
    for X, Y, w, h in ((-180, 700, 80, 45), (-110, 600, 50, 35), (90, 650, 70, 40), (170, 760, 90, 50)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, (210, 160, 130))    # old town roofs climbing the slope
    s.wall(x0 - 5, 50, 400, 3.5, 12, (190, 130, 100))             # houses above the wall
    s.wall(x0 - 2.5, 10, 400, 0, 3.5, (140, 125, 105))              # graffiti stone wall along the left
    s.wall(x1 + 5, 25, 400, 0, 12, (200, 150, 110))                # wooden-balcony houses, right
    s.draw(d)


def batumi(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, None, (150, 160, 120), walk_l=8.0)
    strip(d, x0 - 3000, x0 - 8, 1, 3000, WATER)                     # the Black Sea
    s = Stand()
    s.block(-2400, -300, 5000, 0, 380, HILL)                        # hills across the bay
    s.block(-46, -30, 230, 0, 46, (95, 100, 110))                   # 阿里和尼诺 on the seafront
    s.block(26, 34, 650, 0, 55, (240, 240, 235))                    # 巴统灯塔, far right
    for X, Y, w, h in ((70, 500, 30, 90), (120, 620, 40, 120), (200, 560, 50, 70), (300, 700, 70, 100),
                       (95, 380, 25, 45)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, CITY)                # Batumi towers
    for y in range(36, 400, 26):
        s.block(x0 - 6.5, x0 - 4.5, y, 3.0, 9.0, PALM)              # palms on the promenade
        s.block(x1 + 2.0, x1 + 4.0, y, 3.0, 9.5, PALM)
    s.draw(d)


def sayram(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, None, (150, 175, 100), walk_l=1.5, walk_r=1.5)
    strip(d, x0 - 3000, x0 - 4, 1, 3000, WATER)                     # 赛里木湖
    strip(d, x0 - 4, x0 - 1.5, 1, 3000, SAND)
    s = Stand()
    s.block(-6000, 6000, 8000, 0, 2200, SNOWCAP)                   # 天山, a continuous range
    s.block(30, 40, 160, 0, 6, (245, 245, 240))                     # 毡房
    s.block(70, 82, 240, 0, 7, (245, 245, 240))
    s.block(16, 19, 70, 0, 2.2, (120, 80, 50))                       # horses
    s.block(24, 27, 95, 0, 2.2, (120, 80, 50))
    s.wall(x0 - 1.2, 3, 600, 0, 1.0, (150, 120, 90))                 # wooden fence along the lake
    s.draw(d)


def doha(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, None, SAND, walk_l=6.0)
    strip(d, x0 - 3000, x0 - 6, 1, 3000, WATER)                     # the bay at sunset
    s = Stand()
    s.block(-70, -15, 520, 0, 60, (230, 215, 190))                  # 伊斯兰艺术博物馆 at the end of the water
    for X, Y, z in ((-160, 600, 110), (-95, 520, 150), (-230, 700, 70)):
        s.block(X - 18, X + 18, Y, z, z + 44, (170, 40, 70))        # big hot-air balloons over the bay
    s.block(x1 + 6, x1 + 14, 70, 0, 12, (245, 245, 240))            # La'eeb sculpture on the promenade
    s.block(120, 300, 1300, 0, 70, (220, 190, 120))                 # Lusail stadium, far right
    for X, Y, w, h in ((60, 900, 30, 130), (100, 1000, 35, 170), (340, 1200, 50, 110), (420, 1100, 40, 150)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, CITY)                # West Bay towers
    for y in range(40, 400, 26):
        s.block(x0 - 4.5, x0 - 2.5, y, 3.0, 9.0, PALM)
        s.block(x1 + 2.0, x1 + 4.0, y, 3.0, 9.5, PALM)
    s.draw(d)


def hokkaido(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, (235, 238, 242), (235, 238, 242), walk_l=1.5, walk_r=5.0)
    s = Stand()
    s.block(-1500, 1500, 4000, 0, 700, SNOWCAP)                     # snow mountains closing the valley
    s.block(-300, -12, 260, 0, 90, (200, 150, 90))                  # 地狱谷: ochre crater walls, left
    s.block(-160, -40, 240, 90, 140, (240, 240, 240))               # sulphur steam rising from it
    s.wall(x0 - 2.5, 4, 260, 0, 1.6, (60, 55, 55))                  # black volcanic rock along the left
    s.block(x1 + 6, x1 + 22, 50, 0, 10, (120, 80, 50))              # 温泉旅馆 with lanterns, right
    for y in range(70, 400, 18):
        s.block(x1 + 1.5, x1 + 4.0, y, 0, 12, (40, 90, 60))         # snowy conifers
    s.draw(d)


def fukuoka(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, None, (150, 160, 120), walk_l=4.0)
    strip(d, x0 - 3000, x0 - 30, 1, 3000, WATER)                    # Hakata Bay
    s = Stand()
    s.block(-1500, -200, 3000, 0, 260, HILL)
    s.tower(-70, 900, 234, 22, (150, 180, 215))                     # 福冈塔, slim and silver-blue
    for X, Y, w, h in ((-160, 1100, 50, 70), (-20, 1200, 60, 90), (60, 1000, 40, 60)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, CITY)                # Momochi buildings by the sea
    s.block(x1 + 8, x1 + 22, 55, 0, 14, (200, 50, 40))              # 太宰府 red torii, right
    s.block(x1 + 18, x1 + 40, 90, 0, 12, (110, 80, 60))             # shrine hall behind it
    for y in range(34, 300, 20):
        s.block(x0 - 3.5, x0 - 1.5, y, 1.5, 6.0, (235, 170, 190))   # plum blossom trees
        s.block(x1 + 1.6, x1 + 3.6, y, 1.5, 6.0, (235, 170, 190))
    s.draw(d)


def dalian(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, None, (150, 160, 120), walk_l=4.0)
    strip(d, x0 - 160, x0 - 4, 30, 700, (215, 200, 180))           # 星海广场, far wider than the road
    strip(d, x0 - 3000, x0 - 160, 1, 3000, WATER)
    strip(d, x0 - 160, x0 - 4, 1, 30, (215, 200, 180))
    s = Stand()
    s.block(-1800, -500, 2600, 0, 60, (200, 205, 210))              # 星海湾大桥 across the bay
    s.block(-62, -50, 320, 0, 60, (240, 238, 230))                  # the square's central monument
    for X, Y, w, h in ((40, 1200, 50, 150), (110, 1300, 60, 190), (200, 1100, 70, 120), (-5, 1500, 40, 110)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, CITY)                # Dalian skyline
    s.block(x1 + 6, x1 + 16, 40, 0, 4.0, (40, 80, 160))             # seafood stall, right
    for X, Y, z in ((-60, 120, 30), (-25, 90, 22), (-110, 200, 46), (10, 150, 34), (-80, 300, 70)):
        s.block(X - 1.5, X + 1.5, Y, z, z + 1.2, (250, 250, 250))   # gulls
    s.draw(d)


def changsha(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, (150, 160, 120), None, walk_l=4.0, walk_r=3.0)
    strip(d, x1 + 3, x1 + 3000, 1, 3000, WATER)                     # 湘江, right
    s = Stand()
    s.block(-130, x0 - 12, 160, 0, 38, (225, 225, 220))             # 中南大学体育馆, left
    s.block(10, 300, 900, 0, 14, (70, 120, 70))                     # 橘子洲 in the river
    for X, Y, w, h in ((260, 1400, 60, 300), (360, 1500, 50, 200), (480, 1300, 70, 160), (60, 1800, 50, 150),
                       (-160, 1600, 60, 120)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, CITY)                # skyline, IFS on the right
    for y in range(40, 300, 18):
        s.block(x0 - 3.5, x0 - 1.5, y, 2.0, 8.0, TREE)
    s.draw(d)


def harbin(d):
    x0, x1 = road(d, left=0, right=1)
    kerbs(d, x0, x1, (225, 232, 245), (225, 232, 245), walk_l=4.0)
    s = Stand()
    s.block(-130, -50, 320, 8, 88, (230, 240, 250))                 # 摩天轮, left
    s.block(-9, 9, 260, 0, 64, (120, 190, 240))                     # ice thermometer clock tower, centre
    s.block(26, 56, 210, 0, 36, (245, 245, 245))                    # 大雪人, right
    for X, Y, w, h in ((-200, 500, 60, 40), (-40, 480, 40, 50), (90, 500, 50, 45), (170, 420, 60, 60)):
        s.block(X - w / 2, X + w / 2, Y, 0, h, (160, 140, 220))     # ice castles
    s.draw(d)


LAYOUTS = {"nagoya": nagoya, "tbilisi": tbilisi, "batumi": batumi, "sayram": sayram, "doha": doha,
           "hokkaido": hokkaido, "fukuoka": fukuoka, "dalian": dalian, "changsha": changsha, "harbin": harbin}


def render(dest, hfov):
    b = backdrop()
    set_frame(hfov, b["aspect"])
    img = Image.new("RGB", (W, H), SKY)
    d = ImageDraw.Draw(img)
    hz = px(0, 1e6)[1]
    d.rectangle([0, hz, W, H], fill=GROUND)
    LAYOUTS[dest](d)
    return img


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "nagoya"
    out = OUT / dest
    out.mkdir(parents=True, exist_ok=True)
    for name, hfov in (("center", CENTER_HFOV), ("wide", backdrop()["hfov"]), ("ext", EXT_HFOV)):
        render(dest, hfov).save(out / f"layout_{name}.png")
        print(out / f"layout_{name}.png")


if __name__ == "__main__":
    main()
