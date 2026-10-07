// Preview an encoded-radiance PNG (backdrop / atlas) through the scene LUT, like the runtime does.
// usage: node tools/qa/view-encoded.mjs <in.png> <out.jpg> [K=0.6]
import sharp from "sharp";
import fs from "node:fs";

const [src, dst, kArg] = process.argv.slice(2);
const K = Number(kArg ?? 0.6);
const lutPath = new URL("../../.cache/bake/lut.png", import.meta.url).pathname;
const meta = JSON.parse(fs.readFileSync(new URL("../../.cache/bake/room.json", import.meta.url), "utf8"));
const { n: N, lo: LO, hi: HI } = meta.lut;

const lut = await sharp(lutPath).raw().toBuffer({ resolveWithObject: true });
const L = (r, g, b, c) => lut.data[((N - 1 - g) * lut.info.width + b * N + r) * lut.info.channels + c];
const img = await sharp(src).raw().toBuffer({ resolveWithObject: true });
const { width: w, height: h, channels: ch } = img.info;
const out = Buffer.alloc(w * h * 3);
const coord = (x) => {
  const t = Math.min(1, Math.max(0, (Math.log2(Math.max(x, 1e-6)) - LO) / (HI - LO))) * (N - 1);
  const i = Math.min(N - 2, Math.floor(t));
  return [i, t - i];
};
for (let p = 0; p < w * h; p++) {
  const rad = [0, 1, 2].map((c) => {
    const e = img.data[p * ch + c] / 255, y = Math.min(e * e, 0.9995);
    return (K * y) / (1 - y);
  });
  const [[r0, fr], [g0, fg], [b0, fb]] = rad.map(coord);
  for (let c = 0; c < 3; c++) {
    let v = 0;
    for (let k = 0; k < 8; k++) {
      const dr = k & 1, dg = (k >> 1) & 1, db = (k >> 2) & 1;
      const wgt = (dr ? fr : 1 - fr) * (dg ? fg : 1 - fg) * (db ? fb : 1 - fb);
      v += wgt * L(r0 + dr, g0 + dg, b0 + db, c);
    }
    out[p * 3 + c] = Math.round(v);
  }
}
await sharp(out, { raw: { width: w, height: h, channels: 3 } }).jpeg({ quality: 90 }).toFile(dst);
console.log(dst, w, h);
