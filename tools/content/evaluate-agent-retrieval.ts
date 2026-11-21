import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  planEvidenceRetrieval,
  rankFacts,
  rankFactsHybrid,
  retrieveFacts,
  shouldUseSemanticRetrieval,
} from "../../packages/agent-core/src/retrieval.js";
import type { PersonalFact } from "../../packages/agent-core/src/types.js";
import { createEmbeddings, loadEmbeddingIndex, rankSemanticCandidates, type EmbeddingConfig } from "../../services/agent-api/src/embeddings.js";

type EvalCase = {
  query: string;
  expectedIds?: string[];
  expectedGroupIds?: string[];
};

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const embeddingConfig: EmbeddingConfig = {
  apiKey: process.env.GPTPROTO_API_KEY || "",
  baseUrl: process.env.ROLEPLAY_EMBEDDING_BASE_URL
    || process.env.GPTPROTO_EMBEDDING_BASE_URL
    || "https://api.gptproto.com/v1",
  model: process.env.ROLEPLAY_EMBEDDING_MODEL
    || process.env.GPTPROTO_EMBEDDING_MODEL
    || "text-embedding-3-large",
  version: process.env.ROLEPLAY_EMBEDDING_VERSION
    || process.env.GPTPROTO_EMBEDDING_VERSION
    || "gptproto-text-embedding-3-large-1024-v1",
  dimensions: Number(process.env.ROLEPLAY_EMBEDDING_DIMENSIONS || process.env.GPTPROTO_EMBEDDING_DIMENSIONS || 1_024),
  minSimilarity: Number(process.env.AGENT_EMBEDDING_MIN_SIMILARITY || 0.2),
  timeoutMs: Number(process.env.AGENT_EMBEDDING_TIMEOUT_MS || 12_000),
};

async function readCorpus(): Promise<PersonalFact[]> {
  const files = ["facts.json", "blog.json", "resume-source.json", "oral-history.json", "research.json"];
  const values = await Promise.all(files.map((file) => readFile(resolve(root, `content/agent-public/${file}`), "utf8")));
  return values.flatMap((value) => JSON.parse(value) as PersonalFact[]);
}

function matches(fact: PersonalFact, sample: EvalCase): boolean {
  return sample.expectedIds?.includes(fact.id) === true
    || sample.expectedGroupIds?.includes(fact.groupId ?? "") === true;
}

function metrics(rows: Array<{ reciprocalRank: number; hitAt3: boolean; hitAt5: boolean }>) {
  return {
    mrr: Number((rows.reduce((sum, row) => sum + row.reciprocalRank, 0) / rows.length).toFixed(3)),
    hitAt3: Number((rows.filter((row) => row.hitAt3).length / rows.length).toFixed(3)),
    hitAt5: Number((rows.filter((row) => row.hitAt5).length / rows.length).toFixed(3)),
  };
}

const corpus = await readCorpus();
const samples = JSON.parse(await readFile(resolve(root, "packages/agent-core/test/semantic-retrieval-eval.json"), "utf8")) as EvalCase[];
const index = await loadEmbeddingIndex(root, corpus, embeddingConfig);
const semanticEnabled = Boolean(index && embeddingConfig.apiKey);
const queryVectors = semanticEnabled
  ? await createEmbeddings(samples.map((sample) => sample.query), embeddingConfig)
  : [];
const baselineRows = [];
const hybridRows = [];
const report = [];

for (let indexInEval = 0; indexInEval < samples.length; indexInEval += 1) {
  const sample = samples[indexInEval];
  const lanes = planEvidenceRetrieval(sample.query, corpus, 20).map((lane) => {
    const lexicalRanked = rankFacts(sample.query, lane.facts).filter(({ score }) => score > 0).map(({ fact }) => fact);
    const useSemantic = semanticEnabled && shouldUseSemanticRetrieval(sample.query, lane.facts, 80);
    const semanticScores = useSemantic
      ? rankSemanticCandidates([{ vector: queryVectors[indexInEval], weight: 1 }], index!, 24, embeddingConfig.minSimilarity, new Set(lane.facts.map((fact) => fact.id)))
      : [];
    return {
      lexicalRanked,
      hybridRanked: useSemantic ? rankFactsHybrid(sample.query, lane.facts, semanticScores).map(({ fact }) => fact) : lexicalRanked,
      surfaced: retrieveFacts(sample.query, lane.facts, lane.limit, semanticScores),
    };
  });
  const lexicalRanked = lanes.flatMap((lane) => lane.lexicalRanked);
  const hybridRanked = lanes.flatMap((lane) => lane.hybridRanked);
  const lexicalPosition = lexicalRanked.findIndex((fact) => matches(fact, sample));
  const hybridPosition = hybridRanked.findIndex((fact) => matches(fact, sample));
  const topSourceIds = lanes.flatMap((lane) => lane.surfaced.map(({ id }) => id));
  baselineRows.push({
    reciprocalRank: lexicalPosition < 0 ? 0 : 1 / (lexicalPosition + 1),
    hitAt3: lexicalPosition >= 0 && lexicalPosition < 3,
    hitAt5: lexicalPosition >= 0 && lexicalPosition < 5,
  });
  hybridRows.push({
    reciprocalRank: hybridPosition < 0 ? 0 : 1 / (hybridPosition + 1),
    hitAt3: hybridPosition >= 0 && hybridPosition < 3,
    hitAt5: hybridPosition >= 0 && hybridPosition < 5,
  });
  report.push({ query: sample.query, lexicalRank: lexicalPosition < 0 ? null : lexicalPosition + 1, hybridRank: hybridPosition < 0 ? null : hybridPosition + 1, retrieved: topSourceIds });
}

process.stdout.write(`${JSON.stringify({
  model: embeddingConfig.model,
  version: embeddingConfig.version,
  dimensions: embeddingConfig.dimensions,
  semanticIndexAvailable: Boolean(index),
  count: samples.length,
  lexical: metrics(baselineRows),
  hybrid: metrics(hybridRows),
  cases: report,
}, null, 2)}\n`);
