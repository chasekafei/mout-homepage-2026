// Optimises rendered scene passes and personal reference media for the web.
import { mkdir, copyFile, readFile, writeFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const P = (...p) => path.join(ROOT, ...p);
const only = process.argv[2];

async function exists(f) {
  try { await stat(f); return true; } catch { return false; }
}

async function scene() {
  const from = P(".cache/scene-src");
  const dir = P("public/scene/create");
  await mkdir(dir, { recursive: true });
  for (const cam of ["desktop", "mobile"]) {
    const src = path.join(from, `beauty_${cam}.png`);
    if (!(await exists(src))) { console.warn(`skip ${src}`); continue; }
    await copyFile(path.join(from, `mask_${cam}.png`), path.join(dir, `mask_${cam}.png`));
    await sharp(path.join(from, `depth_${cam}.png`)).resize({ width: cam === "desktop" ? 960 : 540 }).blur(0.8)
      .webp({ quality: 88 }).toFile(path.join(dir, `depth_${cam}.webp`));
    const widths = cam === "desktop" ? [1280, 1920, 2560] : [720, 1080, 1440];
    for (const w of widths) {
      const img = sharp(src).resize({ width: w });
      await img.clone().webp({ quality: 86, effort: 5 }).toFile(path.join(dir, `beauty_${cam}_${w}.webp`));
      await img.clone().avif({ quality: 62, effort: 5 }).toFile(path.join(dir, `beauty_${cam}_${w}.avif`));
    }
    await sharp(src).resize({ width: 48 }).blur(0.6).webp({ quality: 60 }).toFile(path.join(dir, `beauty_${cam}_lqip.webp`));
    console.log(`scene ${cam}: ${widths.join("/")}`);
  }
}

async function photos() {
  const out = P("public/media/cats");
  await mkdir(out, { recursive: true });
  const src = P("ref/烧酒小八照片");
  const list = [];
  for (const f of (await readdir(src)).sort()) {
    if (!/\.(jpe?g|png)$/i.test(f)) continue;
    const cat = f.startsWith("烧酒小八") ? "both" : f.startsWith("烧酒") ? "shaojiu" : "xiaoba";
    const n = list.filter((x) => x.cat === cat).length + 1;
    const name = `${cat}-${n}`;
    const meta = await sharp(path.join(src, f)).rotate().resize({ width: 1400, height: 1400, fit: "inside", withoutEnlargement: true })
      .webp({ quality: 82 }).toFile(path.join(out, `${name}.webp`));
    await sharp(path.join(src, f)).rotate().resize({ width: 480, height: 480, fit: "cover" }).webp({ quality: 76 }).toFile(path.join(out, `${name}-thumb.webp`));
    list.push({ cat, src: `/media/cats/${name}.webp`, thumb: `/media/cats/${name}-thumb.webp`, w: meta.width, h: meta.height });
  }
  await writeFile(path.join(out, "index.json"), JSON.stringify(list, null, 1));

  const me = P("public/media/me");
  await mkdir(me, { recursive: true });
  await sharp(P("ref/我的照片/我的像素风头像.png")).resize({ width: 512, kernel: "nearest" }).png().toFile(path.join(me, "avatar-pixel.png"));
  await sharp(P("ref/我的照片/我的像素风头像.png")).extract({ left: 200, top: 100, width: 300, height: 300 })
    .resize({ width: 150, kernel: "nearest" }).png().toFile(path.join(me, "avatar-face.png"));
  await sharp(P("ref/我的照片/我的真人照片.png")).resize({ width: 900, withoutEnlargement: true }).webp({ quality: 82 }).toFile(path.join(me, "photo.webp"));

  const vol = P("public/media/newsletter/vol-24");
  await mkdir(vol, { recursive: true });
  const posters = [];
  for (const f of (await readdir(P("ref/社思现场-Vol.24"))).sort()) {
    if (!/\.png$/i.test(f)) continue;
    const name = f.replace(/^\d+\.\s*/, "").replace(/\.png$/i, "").toLowerCase().replace(/\s+/g, "-");
    const meta = await sharp(P("ref/社思现场-Vol.24", f)).resize({ width: 1080, withoutEnlargement: true }).webp({ quality: 84 }).toFile(path.join(vol, `${name}.webp`));
    posters.push({ src: `/media/newsletter/vol-24/${name}.webp`, w: meta.width, h: meta.height });
  }
  await writeFile(path.join(vol, "index.json"), JSON.stringify(posters, null, 1));
  console.log(`photos: ${list.length} cats, ${posters.length} posters`);
}

async function audio() {
  await mkdir(P("public/audio"), { recursive: true });
  await copyFile(P("ref/CrossPod 串台节目/AI扯淡夜话局.mp3"), P("public/audio/crosspod-ai-night-talk.mp3"));
  console.log("audio: copied");
}

async function legacy() {
  const src = P("ref/MouT.me 老首页");
  const out = P("public/legacy");
  for (const sub of ["", "about/js", "images", "style"]) await mkdir(path.join(out, sub), { recursive: true });
  for (const f of ["about/js/jquery.js", "images/bg.jpg", "images/nav-line.png", "images/nav.png", "images/toolbar.png", "style/index.css"]) {
    await copyFile(path.join(src, f), path.join(out, f));
  }
  let html = await readFile(path.join(src, "index.html"), "utf8");
  html = html.replace(/<script type="text\/javascript">\s*var _bdhmProtocol[\s\S]*?<\/script>/, "");
  await writeFile(path.join(out, "index.html"), html);
  console.log("legacy: copied");
}

const tasks = { scene, photos, audio, legacy };
for (const [k, fn] of Object.entries(tasks)) if (!only || only === k) await fn();
