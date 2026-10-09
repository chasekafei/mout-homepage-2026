"""Paint the view outside the Model Y for one 出发 destination with GPT Image 2 (through sub2api).

The model returns ~1.6 MP whatever size is asked for (and re-frames instead of outpainting a shrunk inset),
so the 118-degree backdrop plane is painted as three 90-degree views and composited:
  center   the middle the windscreen shows, from layout_center.png + the design reference
  side     the views turned SIDE_YAW left and right, each three quarters center painting (reprojected), one
           quarter stencil, repainted whole                        -> side_l-XX.png, side_r-XX.png
  compose  sides mapped onto the plane by a homography fitted on their overlap with the center, the
           full-resolution center feathered on top                -> composed.png
The center's lanes are evened out in paint_lanes.py, lettering the model gets wrong is fixed on it and the place
sign drawn on the composite in paint_text.py.

    python3 tools/scene/paint.py nagoya center [--n 2]    # -> .cache/paint/nagoya/center-XX.png
    python3 tools/scene/paint.py nagoya side --pick 1     # from center-01.png
    python3 tools/scene/paint.py nagoya compose --pick 1 --left 1 --right 1

Credentials: SUB2API_BASE_URL / SUB2API_API_KEY, from the environment or the sub2api skill's .env.
"""
from __future__ import annotations

import argparse
import base64
import io
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import paint_layout as L

ROOT = Path(__file__).resolve().parents[2]
SKILL = Path(os.environ.get("SUB2API_SKILL", Path.home() / ".codex/skills/sub2api-4k-image-generator-ts"))
REF = ROOT / "design" / "出发场景参考"
OUT_W = 2816    # composite width: the center keeps its native resolution

COMMON = """You are painting the scenery outside a car for a 3D web scene. Images are attached in order.

IMAGE 1 is a LAYOUT STENCIL rendered from the exact camera: a wide ({fov} degree) rectilinear view straight
down the road from the driver's eye, 1.3 m above the asphalt. Keep its geometry exactly: the horizon is the
horizontal line through the middle of the image, the car's lane runs from the bottom centre to the
vanishing point in the middle, lane lines and kerbs stay where they are. Each flat coloured block marks
where one element stands and how big it is on screen: paint the element inside its block (same position,
same top edge), never move or enlarge it. Above the blocks there is only sky. The stencil is only
geometry: replace every flat colour with detailed scenery.

IMAGE 2 is the art-direction reference. Match its style exactly: a bright, highly detailed voxel /
blocky miniature world (like a premium voxel diorama render), crisp sunlight with soft shadows, rich
saturated but natural colours, dense believable detail. Take the landmarks' look from it. IGNORE the car
in IMAGE 2 completely.

Output: only the outdoor scene, full bleed, as if there were no car at all: no dashboard, no bonnet, no
windscreen frame, no pillars, no mirrors, no steering wheel, no screen, no UI, no watermark, no border.
The bottom third (road near the camera) can stay simple asphalt with lane lines. No text anywhere except
the text asked for below.
"""

SIDE = """IMAGE 1 is a view outside a car, turned a little to the {side}. The {keep} three quarters already hold a
finished painting. The {fill} quarter is a flat-coloured layout stencil (horizon, road, kerbs, blocks marking
trees, buildings and park). Repaint the whole frame as one seamless picture: keep everything in the finished
part exactly as it is (same objects, positions, sizes, colours, light), and paint the stencil part as its
natural continuation, following the stencil's geometry and the perspective exactly (same horizon, the road
and kerbs keep their lines). Same voxel diorama style and lighting (IMAGE 2 is the art-direction reference;
ignore its car). Do not add new landmarks, signs or text in the stencil part. Full bleed, no car parts, no
border.
{place}
"""
SIDE_YAW = 16.0

ROAD = """
Road: exactly two lanes, ours on the left and one more on the right, BOTH EXACTLY THE SAME WIDTH. Paint
the edge lines and the dashed centre line precisely on the stencil's white lines (the dashed line meets
the bottom edge of the image where the stencil's does); do not widen our lane or squeeze the right one.
No road signs, no sign boards and no posts by the right kerb: a place sign is added there later.
"""

DESTS = {
    "nagoya": dict(ref="出发-名古屋.png", prompt="""
Place: Nagoya, Japan, a sunny early-autumn morning, clear blue sky with a few chunky voxel clouds.
- Light grey tapering block in the middle (above the vanishing point): the silver-grey steel lattice MIRAI
  TOWER (Nagoya TV tower, NOT red, NOT Tokyo Tower), observation deck where the block widens. Its spire
  tip ends exactly at the top of the grey block; the sky above it stays empty. On the tower's middle a
  tall vertical blue banner with white letters reading exactly: Aichi-Nagoya 2026
- Blue strip on the left running towards the tower: the long shallow reflecting pool with mist fountains
  of Hisaya-odori Park, pointing at the tower base; park lawns, paths and rows of round trees around it.
- Green blocks along both kerbs: rows of voxel street trees (zelkova) and street lamps.
- Pale blocks: Nagoya city buildings, mid-rise offices, glass and concrete.
- Brown block upper left: Howl's Moving Castle (Studio Ghibli) walking over the park, chimney smoke.
- Tall brown block right of the tower: the moss-covered Laputa robot soldier (Castle in the Sky) among
  trees, as at Ghibli Park.
- Dark green block far right: Nagoya Castle, white walls, green roofs, golden shachihoko.
- Brown block near the right kerb: a small traditional wooden Japanese inn (Gero onsen / Takayama style)
  with lanterns and a little hot-spring steam.
- Small dark block by the pool: No-Face (Kaonashi), small, standing quietly.
- Yellow rectangle on the grey post at the right kerb: a yellow road sign with a dark frame and black
  bold Chinese text: 名古屋 (exactly these three characters, nothing else on the sign).
"""),
    "tbilisi": dict(ref="出发-第比利斯.png", prompt="""
Place: Tbilisi, Georgia, a warm late-afternoon in early autumn, clear Caucasus sky, golden sunlight from
behind the camera on the right.
- The road climbs gently between old-town houses; cobbled pavements on both sides.
- Yellow block in the middle, high on the hill: the Holy Trinity Cathedral (Sameba), pale stone, tall
  central drum with a big shining GOLD dome and a gold cross, smaller domes around it; it sits on top of
  the brownish hill block, clearly above the road and the old town.
- Green block behind: the hillside of Tbilisi densely covered with houses with red-brown roofs, cypress
  trees, a TV mast on the far ridge.
- Brown wall face along the left: an old stone retaining wall with a big colourful graffiti mural (abstract
  shapes and a heart, NO legible words), ivy hanging over it; above and behind it, old houses with carved
  wooden balconies painted blue and turquoise.
- Orange face along the right: three-storey old Tbilisi houses with deep carved wooden balconies (brown,
  green, white), vines, a Georgian flag (white with five red crosses) on one balcony, street lamps.
- Small reddish blocks: old-town roofs climbing the slope towards the cathedral.
""" + ROAD),
    "batumi": dict(ref="出发-巴统.png", prompt="""
Place: Batumi, Georgia, on the Black Sea boulevard, a bright sunny summer day, deep blue sky with a few
chunky voxel clouds.
- Blue area on the left: the Black Sea, turquoise near the shore, deep blue further out, a couple of small
  white sailboats; a wide seaside promenade with tiles, benches and voxel palm trees along our left kerb.
- Grey block left of centre on the seafront: the Ali and Nino statue, two tall slender dark-steel
  figures made of stacked horizontal slices, a man and a woman leaning towards each other, on a small
  plinth in the open promenade by the water (not among buildings).
- Small white block right of the vanishing point, far: the Batumi lighthouse, white tower with a red
  lantern top, at the end of the boulevard by the port.
- Pale blocks on the right: Batumi skyline, the tall Alphabetic Tower (a DNA-like spiral), glass towers,
  ornate belle-époque buildings and the clock-tower façade of Europe Square.
- Green blocks: palm trees along both kerbs; flowering oleanders on the right.
- Distant green mountains across the bay on the far left.
""" + ROAD),
    "sayram": dict(ref="出发-赛里木湖.png", prompt="""
Place: Sayram Lake (赛里木湖) in Xinjiang, a clear high-altitude summer midday: deep blue sky, white
clouds, strong sunlight.
- Blue area on the left: the huge lake, intensely turquoise to sapphire, a narrow pebble beach along it,
  covering the whole left half to the horizon.
- Brown face along the left kerb: a low weathered wooden fence between the road and the beach.
- Pale wide block across the horizon: the Tianshan range, a continuous wall of jagged SNOW-CAPPED
  mountains with dark rocky flanks, its foot on the far lake shore, spanning the whole width.
- Green area on the right: golden-green alpine meadow full of yellow and purple wildflowers, rolling up to
  low green hills with dark spruce on their slopes.
- White blocks on the right: white Kazakh yurts with patterned bands.
- Small brown blocks: grazing horses; a few sheep further away.
""" + ROAD),
    "doha": dict(ref="出发-多哈.png", refs=["饺子皮.jpeg"], prompt="""
IMAGE 3 shows La'eeb, the Qatar 2022 mascot sculpture on the Corniche: copy its look for the sculpture.

Place: Doha, Qatar, on the Corniche at golden sunset: orange-pink sky, the sun low on the horizon over the
water left of centre, glowing reflections on the sea.
- Blue area on the left: the calm bay, a few wooden dhow boats; a palm-lined promenade along our left kerb.
- Pale block left of centre at the end of the water: the Museum of Islamic Art, stacked cream-white
  geometric cubic volumes on its own little island by the sea, warm lights.
- Three red blocks over the bay: three LARGE hot-air balloons in Qatar maroon and white, clearly
  recognisable balloons with baskets, near the setting sun.
- White block on the right promenade: the La'eeb sculpture (IMAGE 3): a giant white floating headdress
  shape with a cheerful face, pouring Arabic coffee from a gold dallah into a cup, on a round base.
- Gold block far right: Lusail Stadium, a golden bowl with a latticed facade.
- Pale towers: the West Bay skyline in the haze, glass towers lit by the sunset.
- Green blocks: date palms along both kerbs, warm street lamps.
""" + ROAD),
    "hokkaido": dict(ref="出发-北海道.png", prompt="""
Place: Noboribetsu, Hokkaido, a crisp sunny winter morning, blue sky, fresh snow everywhere.
- Ochre area upper left: Jigokudani (Hell Valley), a crater valley of bare orange, yellow and white volcanic
  rock with sulphur vents; thick white STEAM rising from it into the sky (the white block above it).
- Dark face along the left kerb: black volcanic boulders with snow on top, a rustic wooden fence.
- Big pale block across the horizon: snowy mountains closing the valley, dark forest on their lower slopes.
- Brown block right: a traditional Japanese onsen ryokan, dark wood, snow on its roofs, glowing warm
  paper lanterns at the entrance, a little steam from a hot spring.
- Dark green blocks: tall snow-laden conifers (Ezo spruce) along the right.
- Snow banks on both pavements; the road itself is cleared dark asphalt, slightly wet.
- Far away on a hillside, tiny warm city lights twinkling like a distant memory of the Hakodate night view
  (very small, the scene stays daytime).
""" + ROAD),
    "fukuoka": dict(ref="出发-福冈.png", prompt="""
Place: Fukuoka, Japan, a bright early-spring day, blue sky with chunky voxel clouds.
- Thin pale-blue tower left of centre: Fukuoka Tower, a tall slender triangular tower clad in mirror glass,
  silver-blue, observation deck near the top and a thin antenna; it stands by the sea, clearly separate
  from everything else.
- Blue area on the far left: Hakata Bay, a ferry and small boats; low green mountains behind.
- Pale blocks: modern Momochi seaside buildings around the tower.
- Red block on the right: a big vermilion torii of Dazaifu Tenmangu with a black top beam; behind it (brown
  block) the shrine hall with sweeping grey-green tiled roofs, stone lanterns and a low white wall.
- Pink blocks: plum trees in full pink and white blossom along both pavements.
- The torii must not overlap the tower: tower on the left, shrine on the right.
""" + ROAD),
    "dalian": dict(ref="出发-大连.png", prompt="""
Place: Dalian, China, at Xinghai Square (星海广场), a bright breezy summer day, blue sky.
- Beige area on the left: the vast Xinghai Square, an enormous open plaza of patterned paving with
  circular and radiating stripes, far wider than the road, with small groups of people and flower beds.
- White block on the square: its tall white marble Huabiao column at the centre of a round plaza,
  monumental.
- Blue area beyond: the sea, a seawall with chains and lamp posts at the square's edge.
- Long pale block on the far left horizon: the Xinghai Bay suspension bridge across the bay.
- Pale towers right of centre: the Dalian skyline, green hills behind.
- Blue block on the right kerb: a small seafood stall with a blue awning, ice boxes of crabs and shellfish,
  picture boards of sea-urchin rice bowls (no legible text).
- Small white blocks in the sky: MANY seagulls, big and clearly drawn near the camera, smaller further
  away, flying in from the sea.
""" + ROAD),
    "changsha": dict(ref="出发-长沙.png", prompt="""
Place: Changsha, China, a warm golden evening, sunset glow in a peach and lilac sky.
- Big pale block on the left: the Central South University gymnasium (中南大学体育馆), a large modern
  stadium with a white curved steel roof and ribbed facade, a blank light panel along its front; trees in
  front of it. It is the clearest building of the picture.
- Blue area on the right: the Xiang River beyond a stone balustrade, gleaming with sunset reflections, a
  small river cruise boat.
- Long green block in the river: Orange Isle (橘子洲), a long tree-covered island; at its tip a large pale
  stone monument; a long bridge crosses the river behind it.
- Pale towers right: the Changsha skyline across the river, the tallest one IFS, neon signs starting to
  glow, red lanterns on lamp posts along the river.
- Green blocks: camphor trees along the left pavement; a few small street-food carts with warm lights.
""" + ROAD),
    "harbin": dict(ref="出发-哈尔滨.png", prompt="""
Place: Harbin Ice and Snow World at blue hour, deep blue winter sky with a few stars, the whole park
glowing with cyan, blue, violet and white lights.
- Pale block upper left: a giant white Ferris wheel with a glowing snowflake pattern at its hub.
- Blue block in the middle: an ice clock tower built of glowing blue ice blocks, a big round clock face
  near the top and a large thermometer below it with a red column and a °C scale.
- White block on the right: the famous giant snowman, round white body, red knitted hat with a white
  bobble, a deep red scarf and two red hearts on its belly, smiling.
- Violet blocks: ice castles and towers lit in violet, pink and cyan.
- The road is packed snow with faint lane markings, snow banks on both sides, small visitors in thick
  winter coats walking on the pavements, glowing ice lanterns.
""" + ROAD),
}


def env():
    url, key = os.environ.get("SUB2API_BASE_URL"), os.environ.get("SUB2API_API_KEY")
    if not (url and key) and (SKILL / ".env").exists():
        for line in (SKILL / ".env").read_text().splitlines():
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
        url, key = os.environ.get("SUB2API_BASE_URL"), os.environ.get("SUB2API_API_KEY")
    if not (url and key):
        sys.exit("SUB2API_BASE_URL / SUB2API_API_KEY missing")
    return url.rstrip("/"), key


def data_url(img: Image.Image, width=1792):
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def generate(prompt, images, out: Path, stem: str, n: int):
    sys.path.insert(0, str(SKILL))
    import openai_4k_image_request as R  # streaming + SSE parsing from the sub2api skill

    url, key = env()
    content = [{"type": "input_text", "text": prompt}] + [{"type": "input_image", "image_url": data_url(i)} for i in images]
    payload = {
        "model": os.environ.get("PAINT_RESPONSES_MODEL", "gpt-5.5"),
        "input": [{"type": "message", "role": "user", "content": content}],
        "tools": [{"type": "image_generation", "model": "gpt-image-2", "size": "1536x864", "quality": "high",
                   "output_format": "png"}],
        "tool_choice": {"type": "image_generation"},
        "stream": True,
    }
    for _ in range(n):
        t0 = time.time()
        # the gateway allows about two images at a time and its upstream drops streams now and then
        res = None
        for wait in (30, 60, 90, 120, 180, 240, 300, 300, 300, 0):
            try:
                res = R.request_stream(f"{url}/v1/responses", key, payload, 360, R.DEFAULT_USER_AGENT)
                break
            except (R.RequestFailed, OSError) as e:
                print(f"{stem}: {str(e)[:80]}; " + (f"retrying in {wait}s" if wait else "giving up"),
                      file=sys.stderr, flush=True)
                time.sleep(wait)
        if res is None:
            continue
        imgs = list(R.iter_b64_images(res))
        if not imgs:
            print("no image", R.response_summary(res), file=sys.stderr)
            continue
        k = len(list(out.glob(f"{stem}-*.png"))) + 1
        p = out / f"{stem}-{k:02d}.png"
        p.write_bytes(base64.b64decode(imgs[0]))
        print(f"{p} {Image.open(p).size} {time.time() - t0:.0f}s", flush=True)


def center_box(w, h, hfov=None):
    """Where the center framing sits inside a wider one (same axis, same aspect)."""
    hfov = hfov or L.backdrop()["hfov"]
    s = math.tan(math.radians(L.CENTER_HFOV / 2)) / math.tan(math.radians(hfov / 2))
    cw, ch = round(w * s), round(h * s)
    return (w - cw) // 2, (h - ch) // 2, cw, ch


def K(w, h, hfov):
    f = w / 2 / math.tan(math.radians(hfov / 2))
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


def turn(deg):
    """Rays of a view turned ``deg`` to the right, in the backdrop camera's frame (x right, y down, z ahead)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def side_input(center: Image.Image, ext: Image.Image, yaw: float, size=(1792, 1008)):
    """The turned view cut from the ext stencil with the center painting pasted in."""
    import cv2

    x, y, cw, ch = center_box(*ext.size, hfov=L.EXT_HFOV)
    src = ext.convert("RGB").copy()
    src.paste(center.convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
    M = K(*size, L.CENTER_HFOV) @ turn(yaw).T @ np.linalg.inv(K(*ext.size, L.EXT_HFOV))
    return Image.fromarray(cv2.warpPerspective(np.asarray(src), M, size, flags=cv2.INTER_AREA))


def matches(a: np.ndarray, b: np.ndarray):
    import cv2

    sift = cv2.SIFT_create(6000)
    g = lambda im: cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    k1, d1 = sift.detectAndCompute(g(a), None)
    k2, d2 = sift.detectAndCompute(g(b), None)
    good = [m for m, n in cv2.BFMatcher().knnMatch(d1, d2, k=2) if m.distance < 0.75 * n.distance]
    return np.float32([k1[m.queryIdx].pt for m in good]), np.float32([k2[m.trainIdx].pt for m in good])


def apply(H, pts):
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    return (p[:, :2] / p[:, 2:]).astype(np.float32)


def feather(w, h, edge=0.06):
    fx, fy = np.linspace(0, 1, w), np.linspace(0, 1, h)
    ramp = lambda t: np.clip(np.minimum(t, 1 - t) / edge, 0, 1)
    m = np.outer(ramp(fy), ramp(fx)).astype(np.float32)
    return m * m * (3 - 2 * m)


def fill_holes(img: np.ndarray, w: np.ndarray):
    """Normalised blur at growing radii until every pixel has a value (sky above, road below the views)."""
    import cv2

    out, have = img.copy(), w > 1e-3
    for sigma in (8, 24, 64, 160, 400):
        num = cv2.GaussianBlur(img * w[..., None], (0, 0), sigma)
        den = cv2.GaussianBlur(w, (0, 0), sigma)[..., None]
        ok = (den[..., 0] > 1e-4) & ~have
        out[ok] = (num / np.maximum(den, 1e-6))[ok]
        have |= ok
    return out


def compose(center: Image.Image, sides: dict):
    import cv2

    hfov = L.backdrop()["hfov"]
    W = OUT_W
    H = round(W / L.backdrop()["aspect"])
    x, y, cw, ch = center_box(W, H)
    ca = np.asarray(center.convert("RGB"))
    C = np.array([[cw / ca.shape[1], 0, x], [0, ch / ca.shape[0], y], [0, 0, 1.0]])   # center px -> canvas
    acc, wsum = np.zeros((H, W, 3), np.float32), np.zeros((H, W), np.float32)
    for yaw, im in sides.items():
        sa = np.asarray(im.convert("RGB"))
        th, tw = sa.shape[:2]
        A = K(W, H, hfov) @ turn(yaw) @ np.linalg.inv(K(tw, th, L.CENTER_HFOV))      # side px -> canvas, ideal
        # the model drifts a little from the stencil: a similarity on top, fitted where side and center overlap
        pc, ps = matches(ca, sa)
        S, inl = cv2.estimateAffinePartial2D(apply(A, ps), apply(C, pc), method=cv2.RANSAC, ransacReprojThreshold=4.0)
        T = np.vstack([S, [0, 0, 1]]) @ A
        print(f"side {yaw:+.0f}: {int(inl.sum())}/{len(pc)} matches, correction scale "
              f"{math.hypot(S[0, 0], S[1, 0]):.3f} shift {S[0, 2]:.0f},{S[1, 2]:.0f}px")
        wt = cv2.warpPerspective(feather(tw, th, 0.08), T, (W, H), flags=cv2.INTER_LINEAR)
        acc += cv2.warpPerspective(sa.astype(np.float32), T, (W, H), flags=cv2.INTER_LANCZOS4) * wt[..., None]
        wsum += wt
    base = fill_holes(acc / np.maximum(wsum, 1e-6)[..., None], np.minimum(wsum, 1))
    m = feather(cw, ch)[..., None]
    c = np.asarray(center.convert("RGB").resize((cw, ch), Image.LANCZOS), dtype=np.float32)
    base[y:y + ch, x:x + cw] = base[y:y + ch, x:x + cw] * (1 - m) + c * m
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("stage", choices=("center", "side", "compose"))
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--pick", type=int, default=1, help="center-XX to build on")
    ap.add_argument("--only", choices=("l", "r"), help="side: paint one side only")
    ap.add_argument("--left", type=int, default=1, help="side_l-XX to compose with")
    ap.add_argument("--right", type=int, default=1, help="side_r-XX to compose with")
    ap.add_argument("--extra", default="", help="appended to the prompt")
    a = ap.parse_args()
    spec = DESTS[a.dest]
    out = L.OUT / a.dest
    ref = Image.open(REF / spec["ref"])
    # the center as fixed up: lanes evened (paint_lanes.py), then re-lettered (paint_text.py)
    fixed = next((p for p in (out / f"center-{a.pick:02d}-{s}.png" for s in ("text", "lanes")) if p.exists()),
                 out / f"center-{a.pick:02d}.png")
    if a.stage == "center":
        prompt = COMMON.format(fov=int(L.CENTER_HFOV)) + spec["prompt"] + a.extra
        extra = [Image.open(REF / r) for r in spec.get("refs", [])]
        generate(prompt, [Image.open(out / "layout_center.png"), ref] + extra, out, "center", a.n)
    elif a.stage == "side":
        center = Image.open(fixed)
        place = next(l for l in spec["prompt"].splitlines() if l.startswith("Place:"))
        for k, yaw, side, keep, fill in (("l", -SIDE_YAW, "left", "right", "left"), ("r", SIDE_YAW, "right", "left", "right")):
            if a.only and a.only != k:
                continue
            src = side_input(center, Image.open(out / "layout_ext.png"), yaw)
            src.save(out / f"side_{k}_input.png")
            prompt = SIDE.format(side=side, keep=keep, fill=fill, place=place) + a.extra
            generate(prompt, [src, ref], out, f"side_{k}", a.n)
    else:
        center = Image.open(fixed)
        sides = {-SIDE_YAW: Image.open(out / f"side_l-{a.left:02d}.png"),
                 SIDE_YAW: Image.open(out / f"side_r-{a.right:02d}.png")}
        img = compose(center, sides)
        img.save(out / "composed.png")
        print(out / "composed.png", img.size)


if __name__ == "__main__":
    main()
