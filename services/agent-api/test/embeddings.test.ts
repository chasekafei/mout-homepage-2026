import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gzipSync } from "node:zlib";
import type { PersonalFact } from "@mout/agent-core";
import {
  createEmbeddings,
  createEmbeddingsWithRetry,
  embeddingCorpusHash,
  loadEmbeddingIndex,
  rankSemanticCandidates,
  type EmbeddingConfig,
} from "../src/embeddings.js";

const config: EmbeddingConfig = {
  apiKey: "test-key",
  baseUrl: "https://api.gptproto.com/v1/",
  model: "text-embedding-3-large",
  version: "gptproto-text-embedding-3-large-1024-v1",
  dimensions: 3,
  minSimilarity: 0.2,
  timeoutMs: 1_000,
};

const fact = (id: string, title = id): PersonalFact => ({
  id,
  title,
  body: `Body ${title}`,
  recordType: "blog",
  tags: ["public"],
  keywords: ["alias"],
  source: "test",
  visibility: "public",
});

test("GPT Proto embeddings use the configured compatible endpoint, dimensions, and input order", async () => {
  let requestUrl = "";
  let requestBody: Record<string, unknown> = {};
  let authorization = "";
  const vectors = await createEmbeddings(["first", "second"], config, async (input, init) => {
    requestUrl = String(input);
    requestBody = JSON.parse(String(init?.body));
    authorization = new Headers(init?.headers).get("Authorization") || "";
    return new Response(JSON.stringify({
      data: [
        { index: 1, embedding: [0, 2, 0] },
        { index: 0, embedding: [3, 0, 0] },
      ],
    }), { status: 200 });
  });

  assert.equal(requestUrl, "https://api.gptproto.com/v1/embeddings");
  assert.equal(authorization, "Bearer test-key");
  assert.deepEqual(requestBody, { model: "text-embedding-3-large", input: ["first", "second"], dimensions: 3 });
  assert.deepEqual(vectors, [[3, 0, 0], [0, 2, 0]]);
});

test("embedding index validates its corpus fingerprint and finds cosine neighbors", async () => {
  const facts = [fact("podcast", "CrossPod"), fact("game", "AI 游戏社交")];
  const directory = await mkdtemp(join(tmpdir(), "agent-embedding-index-"));
  const corpusDirectory = join(directory, "content", "agent-public");
  await mkdir(corpusDirectory, { recursive: true });
  const vectorData = Buffer.alloc(2 * config.dimensions * Float32Array.BYTES_PER_ELEMENT);
  [1, 0, 0, 0, 1, 0].forEach((value, index) => vectorData.writeFloatLE(value, index * Float32Array.BYTES_PER_ELEMENT));
  const manifest = {
    format: 1,
    model: config.model,
    version: config.version,
    dimensions: config.dimensions,
    corpusHash: embeddingCorpusHash(facts, config.version, config.dimensions),
    ids: facts.map(({ id }) => id),
    vectorFile: "embedding-index.f32.gz",
  };
  await writeFile(join(corpusDirectory, manifest.vectorFile), gzipSync(vectorData));
  await writeFile(join(corpusDirectory, "embedding-index.json"), JSON.stringify(manifest));

  try {
    const index = await loadEmbeddingIndex(directory, facts, config);
    assert.ok(index);
    const hits = rankSemanticCandidates([{ vector: [0.99, 0.01, 0], weight: 1 }], index, 2, 0.2);
    assert.equal(hits[0]?.id, "podcast");
    assert.ok(hits[0].score > 0.99);
    assert.equal(await loadEmbeddingIndex(directory, [fact("podcast", "changed")], config), null);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("embedding fingerprints use original source records instead of generated summaries", () => {
  const source = fact("source", "口述原文");
  const summary: PersonalFact = { ...fact("summary", "摘要"), recordType: "fact" };
  const originalHash = embeddingCorpusHash([source], config.version, config.dimensions);
  assert.equal(embeddingCorpusHash([source, summary], config.version, config.dimensions), originalHash);
  const aliasedSource = { ...source, keywords: ["只用于关键词检索的摘要别名"] };
  assert.equal(embeddingCorpusHash([source], config.version, config.dimensions), embeddingCorpusHash([aliasedSource], config.version, config.dimensions));
});

test("embedding API failures are safe to fall back from", async () => {
  await assert.rejects(
    createEmbeddings(["query"], config, async () => new Response("no", { status: 401 })),
    /HTTP 401/,
  );
  await assert.rejects(createEmbeddings(["query"], { ...config, apiKey: "" }), /API key is not configured/);
});

test("transient embedding failures retry once and then succeed", async () => {
  let attempts = 0;
  const vectors = await createEmbeddingsWithRetry(["query"], config, { maxAttempts: 2, retryDelayMs: 0 }, async () => {
    attempts += 1;
    if (attempts === 1) throw new TypeError("network reset");
    return new Response(JSON.stringify({ data: [{ index: 0, embedding: [1, 0, 0] }] }), { status: 200 });
  });
  assert.equal(attempts, 2);
  assert.deepEqual(vectors, [[1, 0, 0]]);
});

test("embedding authentication failures do not retry", async () => {
  let attempts = 0;
  await assert.rejects(
    createEmbeddingsWithRetry(["query"], config, { maxAttempts: 2, retryDelayMs: 0 }, async () => {
      attempts += 1;
      return new Response("invalid key", { status: 401 });
    }),
    /HTTP 401/,
  );
  assert.equal(attempts, 1);
});
