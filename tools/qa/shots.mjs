// Visual QA: screenshots of the scene and its panels at desktop and phone sizes.
// Usage: node tools/qa/shots.mjs [baseUrl] [outDir]
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

const base = process.argv[2] ?? "http://localhost:5173";
const out = process.argv[3] ?? ".cache/qa";
const exe = process.env.CHROME ?? path.join(homedir(), "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");

const VIEWS = [
  { name: "desktop", width: 1440, height: 900, dpr: 1, mobile: false },
  { name: "laptop", width: 1280, height: 720, dpr: 1, mobile: false },
  { name: "phone", width: 390, height: 844, dpr: 2, mobile: true },
];

const ROUTES = (process.env.ROUTES ?? "/create,/create/writing,/create/writing/vol-24,/create/podcast,/create/products/find-muse,/create/legacy,/create/cats/xiaoba,/create/me,/chat").split(",");

await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const errors = [];
for (const v of VIEWS.filter((x) => !process.env.VIEWS || process.env.VIEWS.split(",").includes(x.name))) {
  const ctx = await browser.newContext({ viewport: { width: v.width, height: v.height }, deviceScaleFactor: v.dpr, isMobile: v.mobile, hasTouch: v.mobile });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(`[${v.name}] ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`[${v.name}] ${e.message}`));
  for (const r of ROUTES) {
    await page.goto(base + r, { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready", { timeout: 15000 }).catch(() => errors.push(`[${v.name}] not ready: ${r}`));
    await page.waitForTimeout(r === "/create" ? 1200 : 900);
    const file = path.join(out, `${v.name}${r.replace(/\//g, "_")}.jpg`);
    await page.screenshot({ path: file, type: "jpeg", quality: 82 });
    console.log(file);
  }
  if (!v.mobile && process.env.HOVER !== "0") {
    await page.goto(base + "/create", { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready");
    const beacons = await page.$$eval(".beacon", (els) => els.map((e) => ({ label: e.getAttribute("aria-label").split("：")[0], x: parseFloat(e.style.left), y: parseFloat(e.style.top) })));
    for (const b of beacons) {
      await page.mouse.move(b.x + 6, b.y + 6);
      await page.waitForTimeout(450);
      const file = path.join(out, `${v.name}_hover_${b.label.replace(/[^\w\u4e00-\u9fa5.]/g, "")}.jpg`);
      await page.screenshot({ path: file, type: "jpeg", quality: 82 });
      console.log(file);
    }
  }
  await ctx.close();
}
await browser.close();
console.log(errors.length ? `ERRORS:\n${errors.join("\n")}` : "NO_CONSOLE_ERRORS");
