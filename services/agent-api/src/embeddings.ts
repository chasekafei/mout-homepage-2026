import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import type { PersonalFact } from "@mout/agent-core";

export type EmbeddingConfig = {
  apiKey: string;
  baseUrl: string;
  model: string;
  version: string;
  dimensions: number;
  minSimilarity: number;
  timeoutMs: number;
  lexicalConfidenceThreshold?: number;
};

export type EmbeddingIndexManifest = {
  format: 1;
  model: string;
  version: string;
  dimensions: number;
  corpusHash: string;
  ids: string[];
  vectorFile: string;
};

export type EmbeddingIndex = {
  manifest: EmbeddingIndexManifest;
  vectors: Map<string, Float32Array>;
};

export type WeightedQueryVector = {
  vector: number[];
  weight: number;
};

export type EmbeddingRetryOptions = {
  maxAttempts: number;
  retryDelayMs: number;
  onAttempt?: (attempt: number) => void;
  onRetry?: (attempt: number, error: unknown) => void;
};

export class EmbeddingApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "EmbeddingApiError";
  }
}

export function isRetryableEmbeddingError(error: unknown): boolean {
  if (error instanceof EmbeddingApiError) return [408, 425, 429].includes(error.status) || error.status >= 500;
  if (!(error instanceof Error)) return false;
  return ["AbortError", "TimeoutError", "TypeError"].includes(error.name);
}

export function isOriginalSource(fact: PersonalFact): boolean {
  return fact.visibility === "public"
    && (fact.recordType === "blog" || fact.recordType === "resume_source" || fact.recordType === "oral_history" || fact.recordType === "industry_notes" || fact.recordType === "research");
}

export function embeddingText(fact: PersonalFact): string {
  // Keywords and tags may be curated from summaries; vectors use only source text.
  return [fact.title, fact.section, fact.body]
    .filter(Boolean)
    .join("\n");
}

export function embeddingCorpusHash(facts: PersonalFact[], version: string, dimensions: number): string {
  const rows = facts.filter(isOriginalSource).map((fact) => [fact.id, embeddingText(fact)]);
  return createHash("sha256").update(JSON.stringify({ version, dimensions, rows })).digest("hex");
}

export function normalizeVector(input: number[], expectedDimensions?: number): Float32Array {
  if (expectedDimensions !== undefined && input.length !== expectedDimensions) {
    throw new Error(`embedding dimension mismatch: expected ${expectedDimensions}, got ${input.length}`);
  }
  let normSquared = 0;
  for (const value of input) {
    if (!Number.isFinite(value)) throw new Error("embedding contains a non-finite value");
    normSquared += value * value;
  }
  const norm = Math.sqrt(normSquared);
  if (!norm) throw new Error("embedding vector has zero magnitude");
  return Float32Array.from(input, (value) => value / norm);
}

export async function createEmbeddings(
  inputs: string[],
  config: EmbeddingConfig,
  fetcher: typeof fetch = fetch,
): Promise<number[][]> {
  if (!config.apiKey) throw new Error("GPT Proto embedding API key is not configured");
  if (!inputs.length) return [];
  const response = await fetcher(`${config.baseUrl.replace(/\/+$/u, "")}/embeddings`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ model: config.model, input: inputs, dimensions: config.dimensions }),
    signal: AbortSignal.timeout(config.timeoutMs),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new EmbeddingApiError(`Embedding API returned HTTP ${response.status}${detail ? `: ${detail.slice(0, 300)}` : ""}`, response.status);
  }

  const payload = await response.json() as { data?: Array<{ index?: number; embedding?: number[] }> };
  if (!Array.isArray(payload.data) || payload.data.length !== inputs.length) {
    throw new Error("Embedding API returned an unexpected item count");
  }
  const ordered = [...payload.data].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  return ordered.map((item) => {
    if (!Array.isArray(item.embedding)) throw new Error("Embedding API omitted an embedding vector");
    normalizeVector(item.embedding, config.dimensions);
    return item.embedding;
  });
}

export async function createEmbeddingsWithRetry(
  inputs: string[],
  config: EmbeddingConfig,
  options: EmbeddingRetryOptions,
  fetcher: typeof fetch = fetch,
): Promise<number[][]> {
  const maxAttempts = Math.min(2, Math.max(1, Math.floor(options.maxAttempts)));
  const retryDelayMs = Math.max(0, options.retryDelayMs);
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    options.onAttempt?.(attempt);
    try {
      return await createEmbeddings(inputs, config, fetcher);
    } catch (error) {
      lastError = error;
      if (attempt >= maxAttempts || !isRetryableEmbeddingError(error)) throw error;
      options.onRetry?.(attempt, error);
      if (retryDelayMs) await new Promise<void>((resolve) => setTimeout(resolve, retryDelayMs * 2 ** (attempt - 1)));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Embedding request failed");
}

export async function loadEmbeddingIndex(
  root: string,
  facts: PersonalFact[],
  config: EmbeddingConfig,
): Promise<EmbeddingIndex | null> {
  try {
    const directory = `${root}/content/agent-public`;
    const manifest = JSON.parse(await readFile(`${directory}/embedding-index.json`, "utf8")) as EmbeddingIndexManifest;
    const originalSources = facts.filter(isOriginalSource);
    const expectedIds = originalSources.map((fact) => fact.id);
    if (manifest.format !== 1
      || manifest.version !== config.version
      || manifest.model !== config.model
      || manifest.dimensions !== config.dimensions
      || manifest.corpusHash !== embeddingCorpusHash(originalSources, config.version, config.dimensions)
      || manifest.ids.length !== expectedIds.length
      || manifest.ids.some((id, index) => id !== expectedIds[index])
      || manifest.vectorFile !== "embedding-index.f32.gz") return null;

    const data = gunzipSync(await readFile(`${directory}/${manifest.vectorFile}`));
    const expectedBytes = expectedIds.length * config.dimensions * Float32Array.BYTES_PER_ELEMENT;
    if (data.byteLength !== expectedBytes) return null;

    const vectors = new Map<string, Float32Array>();
    for (let row = 0; row < expectedIds.length; row += 1) {
      const vector = new Float32Array(config.dimensions);
      const offset = row * config.dimensions * Float32Array.BYTES_PER_ELEMENT;
      for (let column = 0; column < config.dimensions; column += 1) {
        vector[column] = data.readFloatLE(offset + column * Float32Array.BYTES_PER_ELEMENT);
      }
      vectors.set(expectedIds[row], vector);
    }
    return { manifest, vectors };
  } catch {
    return null;
  }
}

export function rankSemanticCandidates(
  queries: WeightedQueryVector[],
  index: EmbeddingIndex,
  limit = 24,
  minSimilarity = 0.2,
  eligibleIds?: ReadonlySet<string>,
): Array<{ id: string; score: number }> {
  const best = new Map<string, number>();
  for (const query of queries) {
    const normalizedQuery = normalizeVector(query.vector, index.manifest.dimensions);
    for (const [id, document] of index.vectors) {
      if (eligibleIds && !eligibleIds.has(id)) continue;
      let similarity = 0;
      for (let column = 0; column < normalizedQuery.length; column += 1) {
        similarity += normalizedQuery[column] * document[column];
      }
      const score = similarity * query.weight;
      if (score > (best.get(id) ?? Number.NEGATIVE_INFINITY)) best.set(id, score);
    }
  }
  return [...best]
    .filter(([, score]) => score >= minSimilarity)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([id, score]) => ({ id, score }));
}
