// Decodes a saved CDP Page.captureScreenshot response into an image file.
// Usage: node tools/qa/cdp-shot.mjs <response.json> <out.jpg>
import { readFileSync, writeFileSync } from "node:fs";

const [src, out] = process.argv.slice(2);
const json = JSON.parse(readFileSync(src, "utf8"));
const data = json.data ?? json.result?.data;
if (!data) throw new Error("no screenshot data in response");
writeFileSync(out, Buffer.from(data, "base64"));
console.log(out);
