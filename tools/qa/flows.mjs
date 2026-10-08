// Interaction QA: audio + waveform, keyboard access, Esc, deep links, 出发 destinations, no-WebGL fallback.
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

  await page.click("nav >> text=出发");
  await page.waitForTimeout(2800);
  const departBeacons = await page.$$eval(".beacon", (els) => els.map((e) => e.getAttribute("aria-label")).join(" "));
  check("nav switches 创作 → 出发", page.url().endsWith("/depart") && departBeacons.includes("中控屏导航"), page.url());

  for (const r of ["nav", "nav/tbilisi", "window", "pingpong", "passport", "cinema", "cats/xiaoba", "me"]) {
    await page.goto(`${base}/depart/${r}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready");
    const sheet = await page.waitForSelector(".sheet", { timeout: 4000 }).then((e) => e.innerText(), () => "");
    check(`depart deep link /depart/${r}`, sheet.trim().length > 20 && page.url().endsWith(`/depart/${r}`), sheet.slice(0, 24).replace(/\s+/g, " "));
  }
  await page.goto(`${base}/depart/nav`, { waitUntil: "networkidle" });
  await page.waitForSelector(".app.is-ready");
  await page.click(".dest-list >> text=福冈");
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, "flow_depart_switch_mid.jpg"), type: "jpeg", quality: 82 });
  await page.waitForTimeout(2500);
  check("picking a destination opens its card", page.url().endsWith("/depart/nav/fukuoka"), page.url());
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(out, "flow_depart_fukuoka.jpg"), type: "jpeg", quality: 82 });
  await page.click('.beacon[aria-label^="车窗外"]');
  await page.waitForTimeout(700);
  const outside = await page.waitForSelector(".sheet", { timeout: 4000 }).then((e) => e.innerText(), () => "");
  check("the window shows the destination driven to", page.url().endsWith("/depart/window") && outside.includes("FUKUOKA"), outside.slice(0, 30).replace(/\s+/g, " "));
  await page.keyboard.press("Escape");

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

  for (const r of ["tv", "gba", "archive", "handhelds", "arcade", "cats/shaojiu", "cats/xiaoba", "window", "me"]) {
    await page.goto(`${base}/play/${r}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".app.is-ready");
    const sheet = await page.waitForSelector(".sheet", { timeout: 4000 }).then((e) => e.innerText(), () => "");
    check(`play deep link /play/${r}`, sheet.trim().length > 20 && page.url().endsWith(`/play/${r}`), sheet.slice(0, 24).replace(/\s+/g, " "));
  }
  await page.goto(`${base}/play/tv`, { waitUntil: "networkidle" });
  await page.click(".sheet >> text=后来游戏变成了工作");
  await page.waitForTimeout(2800);
  check("TV panel leads into the games stop at work", page.url().endsWith("/work/games"), page.url());
  await page.screenshot({ path: path.join(out, "flow_play_to_work.jpg"), type: "jpeg", quality: 82 });

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
  for (const scene of ["now", "create", "work", "play", "depart"]) {
    await page.goto(`${base}/${scene}`, { waitUntil: "networkidle" });
    const ready = await page.waitForSelector(".app.is-ready", { timeout: 10000 }).then(() => true, () => false);
    check(`no-WebGL fallback becomes ready (${scene})`, ready);
    check(`fallback uses <img> (${scene})`, !!(await page.$(".stage-img")));
    check(`fallback still has hotspots (${scene})`, (await page.$$(".beacon")).length > 4);
    await page.screenshot({ path: path.join(out, `flow_nowebgl_${scene}.jpg`), type: "jpeg", quality: 82 });
  }
  await page.goto(`${base}/depart/nav/doha`, { waitUntil: "networkidle" });
  await page.waitForSelector(".app.is-ready");
  await page.waitForTimeout(1500);
  const src = await page.$eval(".stage-img", (e) => e.currentSrc || e.getAttribute("src") || "");
  check("fallback swaps the view outside (doha)", src.includes("/depart/doha/"), src.split("/").slice(-2).join("/"));
  await page.screenshot({ path: path.join(out, "flow_nowebgl_depart_doha.jpg"), type: "jpeg", quality: 82 });
});

console.log(results.join("\n"));
