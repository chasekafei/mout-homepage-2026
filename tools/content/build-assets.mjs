// Optimises rendered scene passes and personal reference media for the web.
import { mkdir, copyFile, readFile, writeFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const P = (...p) => path.join(ROOT, ...p);
// node build-assets.mjs [task] [scene]; scene tasks default to every scene that has source files.
const only = process.argv[2];
const SCENES = process.argv[3] ? [process.argv[3]] : ["now", "create", "work"];

async function exists(f) {
  try { await stat(f); return true; } catch { return false; }
}

async function scene() {
  for (const id of SCENES) await scene2d(id);
}

async function scene2d(id) {
  const from = P(".cache/scene-src", id);
  const dir = P("public/scene", id);
  for (const cam of ["desktop", "mobile"]) {
    const src = path.join(from, `beauty_${cam}.png`);
    if (!(await exists(src))) { console.warn(`skip ${src}`); continue; }
    await mkdir(dir, { recursive: true });
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
    console.log(`scene ${id} ${cam}: ${widths.join("/")}`);
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

async function scene3d() {
  for (const id of SCENES) await publish3d(id);
}

async function publish3d(id) {
  const from = P(".cache/bake", id);
  const dir = P("public/scene", id, "3d");
  if (!(await exists(path.join(from, "room.json")))) { console.warn(`skip ${id}: no bake in ${from}`); return; }
  await mkdir(dir, { recursive: true });
  console.log(`scene3d ${id}`);
  const { execFileSync } = await import("node:child_process");
  execFileSync(P("node_modules/.bin/gltfpack"), ["-i", path.join(from, "room.glb"), "-o", path.join(dir, "room.glb"),
    // -cc garbles thin stacked layers (laptop deck, screen); 16-bit positions step ~1 mm over the street's bounds
    "-c", "-kn", "-ke", "-kv", "-vpf", "-vtf", "-vc", "8"], { stdio: "inherit" });
  // atlas and backdrop hold encoded radiance: keep chroma at full resolution
  for (const [name, widths] of [["atlas", [4096, 2048]], ["backdrop", [2560, 1600]]]) {
    const src = path.join(from, `${name}.png`);
    if (!(await exists(src))) { console.warn(`skip ${src}`); continue; }
    for (const w of widths) {
      const img = sharp(src).resize({ width: w, kernel: "lanczos3" });
      await img.clone().avif({ quality: 72, effort: 6, chromaSubsampling: "4:4:4" }).toFile(path.join(dir, `${name}_${w}.avif`));
      await img.clone().webp({ quality: 92, effort: 5, smartSubsample: true }).toFile(path.join(dir, `${name}_${w}.webp`));
    }
  }
  await sharp(path.join(from, "lut.png")).toColourspace("srgb").png({ compressionLevel: 9 }).toFile(path.join(dir, "lut.png"));
  const room = JSON.parse(await readFile(path.join(from, "room.json"), "utf8"));
  const bd = path.join(from, "backdrop.json");
  if (await exists(bd)) room.backdrop = JSON.parse(await readFile(bd, "utf8"));
  await writeFile(path.join(dir, "scene.json"), JSON.stringify(room));
  for (const f of (await readdir(dir)).sort()) console.log(`  ${f} ${((await stat(path.join(dir, f))).size / 1024).toFixed(0)} KB`);
}

const tasks = { scene, scene3d, photos, audio, legacy };
for (const [k, fn] of Object.entries(tasks)) if (!only || only === k) await fn();
