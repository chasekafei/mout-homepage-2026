// Realtime room QA: default view, orbit extremes and hover, plus console errors.
// Usage: [SCENE=now] node tools/qa/room3d.mjs [baseUrl] [outDir]
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

const base = process.argv[2] ?? "http://localhost:5173";
const out = process.argv[3] ?? ".cache/qa3d";
const SCENE = process.env.SCENE ?? "create";
const exe = process.env.CHROME ?? path.join(homedir(), "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
const VIEWS = [
  { name: "desktop", width: 1440, height: 900, dpr: 1, mobile: false },
  { name: "phone", width: 390, height: 844, dpr: 2, mobile: true },
].filter((v) => !process.env.VIEWS || process.env.VIEWS.split(",").includes(v.name));
const DRAGS = (process.env.DRAGS ?? "left:-400:0,right:400:0,up:0:-300,down:0:300").split(",").map((s) => {
  const [name, dx, dy] = s.split(":");
  return { name, dx: +dx, dy: +dy };
});

await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const errors = [];
for (const v of VIEWS) {
  const ctx = await browser.newContext({ viewport: { width: v.width, height: v.height }, deviceScaleFactor: v.dpr, isMobile: v.mobile, hasTouch: v.mobile });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(`[${v.name}] ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`[${v.name}] ${e.message}`));
  await page.goto(`${base}/${SCENE}` + (process.env.QUERY ? "?" + process.env.QUERY : ""), { waitUntil: "networkidle" });
  await page.waitForSelector(".app.is-ready", { timeout: 20000 }).catch(() => errors.push(`[${v.name}] not ready`));
  await page.waitForTimeout(1500);
  const mode = await page.$eval(".stage", (e) => (e.classList.contains("stage-3d") ? "3d" : "2d"));
  console.log(`${v.name}: stage ${mode}`);
  const shot = async (n) => {
    const file = path.join(out, `${SCENE === "create" ? "" : SCENE + "_"}${v.name}_${n}.jpg`);
    await page.screenshot({ path: file, type: "jpeg", quality: 85 });
    console.log(file);
  };
  await shot("default");
  const cx = v.width / 2, cy = v.height / 2;
  for (const d of v.mobile ? [] : DRAGS) {
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(cx + (d.dx * i) / 10, cy + (d.dy * i) / 10);
    await page.mouse.up();
    await page.mouse.move(v.width / 2, v.height / 2);
    await page.waitForTimeout(900);
    await shot(`drag_${d.name}`);
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(cx - (d.dx * i) / 10, cy - (d.dy * i) / 10);
    await page.mouse.up();
  }
  if (!v.mobile && process.env.HOVER !== "0") {
    await page.waitForTimeout(900);
    const beacons = await page.$$eval(".beacon", (els) => els.map((e) => {
      const r = e.getBoundingClientRect();
      return { label: e.getAttribute("aria-label").split("：")[0], x: r.x + r.width / 2, y: r.y + r.height / 2, vis: e.style.visibility !== "hidden" };
    }));
    for (const b of beacons.filter((b) => b.vis).slice(0, Number(process.env.HOVERS ?? 3))) {
      await page.mouse.move(b.x + 14, b.y + 10);
      await page.waitForTimeout(500);
      await shot(`hover_${b.label.replace(/[^\w\u4e00-\u9fa5.]/g, "")}`);
    }
  }
  await ctx.close();
}
await browser.close();
console.log(errors.length ? `ERRORS:\n${errors.join("\n")}` : "NO_CONSOLE_ERRORS");
