import { createHash } from "node:crypto";
import { readFile, writeFile, rename } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)));
const outputDir = join(root, "content/agent-public");
const model = process.env.ROLEPLAY_EMBEDDING_MODEL
  || process.env.GPTPROTO_EMBEDDING_MODEL
  || "text-embedding-3-large";
const version = process.env.ROLEPLAY_EMBEDDING_VERSION
  || process.env.GPTPROTO_EMBEDDING_VERSION
  || "gptproto-text-embedding-3-large-1024-v1";
const dimensions = Number(process.env.ROLEPLAY_EMBEDDING_DIMENSIONS
  || process.env.GPTPROTO_EMBEDDING_DIMENSIONS
  || 1_024);
const baseUrl = (process.env.ROLEPLAY_EMBEDDING_BASE_URL
  || process.env.GPTPROTO_EMBEDDING_BASE_URL
  || "https://api.gptproto.com/v1").replace(/\/+$/u, "");
const apiKey = process.env.GPTPROTO_API_KEY;
const batchSize = 24;

if (!apiKey) throw new Error("Set GPTPROTO_API_KEY to build the semantic index.");
if (!Number.isInteger(dimensions) || dimensions < 1) throw new Error("Embedding dimensions must be a positive integer.");

const files = ["blog.json", "resume-source.json", "oral-history.json"];
const records = (await Promise.all(files.map(async (file) =>
  JSON.parse(await readFile(join(outputDir, file), "utf8")),
))).flat().filter((record) => record.visibility === "public");
const ids = records.map((record) => record.id);
if (new Set(ids).size !== ids.length) throw new Error("The corpus contains duplicate IDs.");

const texts = records.map((record) => [
  record.title,
  record.section,
  record.body,
].filter(Boolean).join("\n"));
const corpusHash = createHash("sha256")
  .update(JSON.stringify({ version, dimensions, rows: records.map((record, index) => [record.id, texts[index]]) }))
  .digest("hex");

const vectors = [];
for (let offset = 0; offset < texts.length; offset += batchSize) {
  const input = texts.slice(offset, offset + batchSize);
  let response;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      response = await fetch(`${baseUrl}/embeddings`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ model, input, dimensions }),
        signal: AbortSignal.timeout(60_000),
      });
    } catch (error) {
      if (attempt === 2) throw error;
      response = undefined;
    }
    if (response?.ok) break;
    if (response) {
      const status = response.status;
      await response.body?.cancel();
      if (status < 500 && status !== 429) throw new Error(`Embedding API returned HTTP ${status}`);
      response = undefined;
    }
    if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
  }
  if (!response?.ok) throw new Error("Embedding API request failed after retries.");

  const payload = await response.json();
  if (!Array.isArray(payload.data) || payload.data.length !== input.length) {
    throw new Error(`Embedding API returned an unexpected batch size at offset ${offset}.`);
  }
  const ordered = [...payload.data].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  for (const item of ordered) {
    if (!Array.isArray(item.embedding) || item.embedding.length !== dimensions) {
      throw new Error(`Embedding API returned a vector with an unexpected dimension at offset ${offset}.`);
    }
    let normSquared = 0;
    for (const value of item.embedding) {
      if (!Number.isFinite(value)) throw new Error("Embedding API returned a non-finite vector value.");
      normSquared += value * value;
    }
    const norm = Math.sqrt(normSquared);
    if (!norm) throw new Error("Embedding API returned a zero vector.");
    vectors.push(Float32Array.from(item.embedding, (value) => value / norm));
  }
  process.stdout.write(`Embedded ${Math.min(offset + input.length, texts.length)}/${texts.length}\n`);
}

const rawVectors = Buffer.allocUnsafe(vectors.length * dimensions * Float32Array.BYTES_PER_ELEMENT);
let cursor = 0;
for (const vector of vectors) {
  for (const value of vector) {
    rawVectors.writeFloatLE(value, cursor);
    cursor += Float32Array.BYTES_PER_ELEMENT;
  }
}

const vectorFile = "embedding-index.f32.gz";
const manifest = {
  format: 1,
  model,
  version,
  dimensions,
  corpusHash,
  ids,
  vectorFile,
};
const vectorPath = join(outputDir, vectorFile);
const manifestPath = join(outputDir, "embedding-index.json");
const vectorTemp = `${vectorPath}.tmp`;
const manifestTemp = `${manifestPath}.tmp`;
await writeFile(vectorTemp, gzipSync(rawVectors, { level: 9 }));
await writeFile(manifestTemp, `${JSON.stringify(manifest, null, 2)}\n`);
await rename(vectorTemp, vectorPath);
await rename(manifestTemp, manifestPath);
console.log(`Wrote ${vectors.length} ${dimensions}-dimensional vectors (${basename(vectorPath)}).`);
