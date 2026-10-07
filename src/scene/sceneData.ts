import { SCENES, type SceneId } from "../content/site";

export type Variant = "desktop" | "mobile";

export const SCENE = {
  base: (id: SceneId) => `/scene/${id}`,
  aspect: { desktop: 16 / 9, mobile: 9 / 16 },
  widths: { desktop: [1280, 1920, 2560], mobile: [720, 1080, 1440] },
  focus: { desktop: [0.47, 0.56], mobile: [0.56, 0.5] } as Record<Variant, [number, number]>,
  /** Teal waveform beside the microphone head, in image uv (scenes with a microphone only). */
  wave: {
    create: {
      desktop: { x0: 0.584, x1: 0.644, y: 0.488, h: 0.05 },
      mobile: { x0: 0.608, x1: 0.683, y: 0.471, h: 0.026 },
    },
  } as Partial<Record<SceneId, Record<Variant, { x0: number; x1: number; y: number; h: number }>>>,
};

/** x0..y1 cover every pixel of the id; cx/cy and the b* bounds describe its largest connected blob. */
export type Region = {
  id: number; x0: number; y0: number; x1: number; y1: number; cx: number; cy: number; area: number;
  bx0: number; by0: number; bx1: number; by1: number;
};

export type Lookup = {
  width: number;
  height: number;
  ids: Uint8Array;
  depthW: number;
  depthH: number;
  depth: Uint8Array;
  regions: Region[];
};

export function pickVariant(w: number, h: number): Variant {
  return w / h < 0.9 ? "mobile" : "desktop";
}

export function beautyUrl(scene: SceneId, v: Variant, cssW: number, cssH: number, dpr: number) {
  const need = Math.max(cssW, cssH * SCENE.aspect[v]) * Math.min(dpr, 2);
  const list = SCENE.widths[v];
  const w = list.find((x) => x >= need * 0.9) ?? list[list.length - 1];
  return `${SCENE.base(scene)}/beauty_${v}_${w}`;
}

async function bitmap(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return createImageBitmap(await res.blob(), { colorSpaceConversion: "none", premultiplyAlpha: "none" });
}

function pixels(bmp: ImageBitmap) {
  const c = new OffscreenCanvas(bmp.width, bmp.height);
  const ctx = c.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(bmp, 0, 0);
  const rgba = ctx.getImageData(0, 0, bmp.width, bmp.height).data;
  const out = new Uint8Array(bmp.width * bmp.height);
  for (let i = 0, j = 0; j < out.length; i += 4, j++) out[j] = rgba[i];
  return out;
}

function regions(ids: Uint8Array, w: number, h: number, n: number): Region[] {
  const S = 4;
  const gw = Math.floor(w / S), gh = Math.floor(h / S);
  const grid = new Uint8Array(gw * gh);
  for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) grid[y * gw + x] = ids[(y * S + S / 2) * w + x * S + S / 2];

  const out: Region[] = Array.from({ length: n }, (_, id) => ({ id, x0: 1, y0: 1, x1: 0, y1: 0, cx: 0.5, cy: 0.5, area: 0, bx0: 0, by0: 0, bx1: 0, by1: 0 }));
  const best = new Array(n).fill(0);
  const seen = new Uint8Array(gw * gh);
  const stack: number[] = [];
  for (let start = 0; start < grid.length; start++) {
    const id = grid[start];
    if (id === 255 || seen[start]) continue;
    let count = 0, sx = 0, sy = 0, lx = gw, ly = gh, hx = 0, hy = 0;
    const r = out[id];
    stack.push(start);
    seen[start] = 1;
    while (stack.length) {
      const i = stack.pop()!;
      const x = i % gw, y = (i - x) / gw;
      count++; sx += x; sy += y;
      if (x < lx) lx = x; if (x > hx) hx = x;
      if (y < ly) ly = y; if (y > hy) hy = y;
      const u = x / gw, v = y / gh;
      if (u < r.x0) r.x0 = u; if (u > r.x1) r.x1 = u;
      if (v < r.y0) r.y0 = v; if (v > r.y1) r.y1 = v;
      for (const j of [i - 1, i + 1, i - gw, i + gw]) {
        if (j < 0 || j >= grid.length || seen[j] || grid[j] !== id) continue;
        if ((j === i - 1 && x === 0) || (j === i + 1 && x === gw - 1)) continue;
        seen[j] = 1;
        stack.push(j);
      }
    }
    r.area += count / (gw * gh);
    if (count > best[id]) {
      best[id] = count;
      r.cx = (sx / count + 0.5) / gw; r.cy = (sy / count + 0.5) / gh;
      r.bx0 = lx / gw; r.by0 = ly / gh; r.bx1 = (hx + 1) / gw; r.by1 = (hy + 1) / gh;
    }
  }
  for (const r of out) { r.x1 += 1 / gw; r.y1 += 1 / gh; }
  return out;
}

export async function loadPasses(scene: SceneId, v: Variant) {
  const base = SCENE.base(scene);
  const n = SCENES[scene].hotspots.length;
  const [mask, depth] = await Promise.all([bitmap(`${base}/mask_${v}.png`), bitmap(`${base}/depth_${v}.webp`)]);
  const raw = pixels(mask);
  const ids = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    const id = Math.round(raw[i] / 16) - 1;
    ids[i] = id >= 0 && id < n ? id : 255;
  }
  const lookup: Lookup = {
    width: mask.width, height: mask.height, ids,
    depthW: depth.width, depthH: depth.height, depth: pixels(depth),
    regions: regions(ids, mask.width, mask.height, n),
  };
  return { mask, depth, lookup };
}

/** `stem` has no extension; avif is tried first, webp is the fallback. */
export async function loadBeauty(stem: string) {
  try { return await bitmap(`${stem}.avif`); } catch { return bitmap(`${stem}.webp`); }
}

export function depthAt(l: Lookup, u: number, v: number) {
  const x = Math.min(l.depthW - 1, Math.max(0, Math.floor(u * l.depthW)));
  const y = Math.min(l.depthH - 1, Math.max(0, Math.floor(v * l.depthH)));
  return l.depth[y * l.depthW + x] / 255;
}

export function idAt(l: Lookup, u: number, v: number) {
  if (u < 0 || v < 0 || u >= 1 || v >= 1) return -1;
  const id = l.ids[Math.floor(v * l.height) * l.width + Math.floor(u * l.width)];
  return id === 255 ? -1 : id;
}

export function parallaxShift(d: number, p: [number, number]): [number, number] {
  const t = Math.min(1, Math.max(0, d / 0.85));
  const k = (1 - t * t * (3 - 2 * t)) * 0.9;
  return [p[0] * k, p[1] * k];
}
