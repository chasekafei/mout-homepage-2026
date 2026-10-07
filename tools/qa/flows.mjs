// Interaction QA: audio + waveform, keyboard access, Esc, unfinished states, no-WebGL fallback.
// Usage: node tools/qa/flows.mjs [baseUrl] [outDir]
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

const base = process.argv[2] ?? "http://localhost:5173";
const out = process.argv[3] ?? ".cache/qa";
const exe = process.env.CHROME ?? path.join(homedir(), "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
await mkdir(out, { recursive: true });

const results = [];
const check = (name, ok, extra = "") => { results.push(`${ok ? "PASS" : "FAIL"} ${name}${extra ? ` (${extra})` : ""}`); };

async function run(args, fn) {
  const browser = await chromium.launch({ executablePath: exe, args: ["--autoplay-policy=no-user-gesture-required", ...args] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try { await fn(page); } finally {
    if (errors.length) check("no page errors", false, errors.join(" | "));
    await browser.close();
  }
}

await run(["--use-angle=metal"], async (page) => {
  await page.goto(`${base}/create/podcast`, { waitUntil: "networkidle" });
  await page.waitForSelector(".app.is-ready");
  await page.click(".play");
  await page.waitForTimeout(2500);
  const t = await page.$eval(".track-title .meta", (e) => e.textContent);
  check("podcast plays", !/^0:00 \//.test(t ?? ""), t ?? "");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  check("Esc closes sheet", page.url().endsWith("/create") && !(await page.$(".sheet")));
  check("now-playing chip visible", !!(await page.$(".now-playing")));
  await page.screenshot({ path: path.join(out, "flow_playing.jpg"), type: "jpeg", quality: 82 });
  await page.click(".now-playing");
  await page.waitForTimeout(300);
  check("chip pauses", (await page.$eval(".now-playing", (e) => e.getAttribute("aria-label"))) === "继续播放播客");

  await page.goto(`${base}/create`, { waitUntil: "networkidle" });
  await page.waitForSelector(".app.is-ready");
  await page.keyboard.press("Tab");
  const firstStop = await page.evaluate(() => document.activeElement?.className ?? "");
  check("first Tab lands on the brand", firstStop.includes("brand"), firstStop);
  let first = "";
  for (let i = 0; i < 12 && !first.includes("："); i++) {
    await page.keyboard.press("Tab");
    first = await page.evaluate(() => (document.activeElement?.classList.contains("beacon") ? document.activeElement.getAttribute("aria-label") : "") ?? "");
  }
  check("Tab reaches scene objects after the nav", first.includes("："), first);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  check("Enter opens the focused object", /\/create\/\w+/.test(page.url()), page.url());
  await page.keyboard.press("Escape");

  await page.click("text=游戏");
  await page.waitForTimeout(300);
  check("unfinished state shows toast", await page.$eval(".toast", (e) => e.classList.contains("is-on")));
  await page.screenshot({ path: path.join(out, "flow_toast.jpg"), type: "jpeg", quality: 82 });

  await page.goto(`${base}/play`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  check("deep link to unfinished state redirects", page.url().endsWith("/now"), page.url());

  for (const r of ["agent", "social", "games", "brand", "gov", "cats/shaojiu", "window", "me"]) {
    await page.goto(`${base}/work/${r}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready");
    const sheet = await page.waitForSelector(".sheet", { timeout: 4000 }).then((e) => e.innerText(), () => "");
    check(`work deep link /work/${r}`, sheet.trim().length > 20 && page.url().endsWith(`/work/${r}`), sheet.slice(0, 24).replace(/\s+/g, " "));
  }
  await page.goto(`${base}/work/gov`, { waitUntil: "networkidle" });
  await page.click(".work-chain >> text=游戏");
  await page.waitForTimeout(500);
  check("career chain steps to the next stop", page.url().endsWith("/work/games") && !!(await page.$(".work-chain .is-on >> text=游戏")), page.url());
  await page.screenshot({ path: path.join(out, "flow_work_panel.jpg"), type: "jpeg", quality: 82 });

  for (const r of ["project", "thought", "cats/xiaoba", "cats/shaojiu", "window", "me"]) {
    await page.goto(`${base}/now/${r}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready");
    const sheet = await page.waitForSelector(".sheet", { timeout: 4000 }).then((e) => e.innerText(), () => "");
    check(`now deep link /now/${r}`, sheet.trim().length > 20 && page.url().endsWith(`/now/${r}`), sheet.slice(0, 24).replace(/\s+/g, " "));
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  check("Esc returns to /now", page.url().endsWith("/now") && !(await page.$(".sheet")), page.url());

  await page.click("nav >> text=创作");
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(out, "flow_switch_mid.jpg"), type: "jpeg", quality: 82 });
  await page.waitForTimeout(2500);
  const beacons = await page.$$eval(".beacon", (els) => els.map((e) => e.getAttribute("aria-label")).join(" "));
  check("nav switches 此刻 → 创作", page.url().endsWith("/create") && beacons.includes("日记"), page.url());
  await page.click("nav >> text=此刻");
  await page.waitForTimeout(2800);
  const back = await page.$$eval(".beacon", (els) => els.map((e) => e.getAttribute("aria-label")).join(" "));
  check("nav switches 创作 → 此刻", page.url().endsWith("/now") && back.includes("杯垫"), page.url());
  await page.screenshot({ path: path.join(out, "flow_switch_back.jpg"), type: "jpeg", quality: 82 });

  await page.goto(`${base}/create/writing/vol-01`, { waitUntil: "networkidle" });
  await page.waitForSelector(".reader-head h1");
  check("newsletter deep link renders", (await page.$eval(".reader-head h1", (e) => e.textContent))?.includes("VOL.01") ?? false);
});

await run(["--disable-webgl", "--disable-webgl2", "--disable-gpu"], async (page) => {
  for (const scene of ["now", "create", "work"]) {
    await page.goto(`${base}/${scene}`, { waitUntil: "networkidle" });
    const ready = await page.waitForSelector(".app.is-ready", { timeout: 10000 }).then(() => true, () => false);
    check(`no-WebGL fallback becomes ready (${scene})`, ready);
    check(`fallback uses <img> (${scene})`, !!(await page.$(".stage-img")));
    check(`fallback still has hotspots (${scene})`, (await page.$$(".beacon")).length > 4);
    await page.screenshot({ path: path.join(out, `flow_nowebgl_${scene}.jpg`), type: "jpeg", quality: 82 });
  }
});

console.log(results.join("\n"));
