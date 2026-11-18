import type { AgentProvider, AgentProviderPreference } from "@mout/agent-core";
export type ProviderName = AgentProvider;

const csv = (value: string | undefined, fallback: string[]) =>
  (value ? value.split(",") : fallback).map((item) => item.trim()).filter(Boolean);
const duration = (value: string | undefined, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

export const config = {
  port: Number(process.env.PORT || 8787),
  allowedOrigins: csv(process.env.ALLOWED_ORIGINS, ["http://localhost:5173", "http://localhost:5174"]),
  defaultProvider: (process.env.DEFAULT_PROVIDER || "auto") as AgentProviderPreference,
  providerOrder: csv(process.env.AGENT_PROVIDER_ORDER, ["vercel", "gptproto"])
    .filter((name): name is "vercel" | "gptproto" => name === "vercel" || name === "gptproto"),
  providerFirstTokenTimeoutMs: duration(process.env.UPSTREAM_FIRST_TOKEN_TIMEOUT_MS, 120_000),
  timeZone: process.env.AGENT_TIMEZONE || "Asia/Shanghai",
  databaseUrl: process.env.DATABASE_URL || "",
  adminPassword: process.env.ADMIN_PASSWORD || "",
  adminSessionSecret: process.env.ADMIN_SESSION_SECRET || "",
  gptproto: {
    apiKey: process.env.GPTPROTO_API_KEY || "",
    baseUrl: process.env.GPTPROTO_BASE_URL || "https://gptproto.com/v1",
    model: process.env.GPTPROTO_MODEL || "gemini-4-hydrogen",
    webSearchTool: process.env.GPTPROTO_WEB_SEARCH_TOOL || "web_search_preview",
  },
  vercel: {
    apiKey: process.env.VERCEL_AI_API_KEY || process.env.AI_GATEWAY_API_KEY || "",
    baseUrl: process.env.VERCEL_AI_BASE_URL || "https://ai-gateway.vercel.sh/v1",
    model: process.env.GPTPROTO_MODEL || "gemini-4-hydrogen",
  },
  embeddings: {
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
    lexicalConfidenceThreshold: Number(process.env.AGENT_EMBEDDING_LEXICAL_CONFIDENCE_THRESHOLD || 80),
  },
  deepseek: {
    apiKey: process.env.DEEPSEEK_API_KEY || "",
    baseUrl: process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com/v1",
    model: process.env.DEEPSEEK_MODEL || "deepseek-v4-pro",
  },
  maxContextTokens: Number(process.env.MAX_CONTEXT_TOKENS || 128_000),
  contextOutputReserveTokens: Number(process.env.CONTEXT_OUTPUT_RESERVE_TOKENS || 8_192),
  contextSafetyMarginTokens: Number(process.env.CONTEXT_SAFETY_MARGIN_TOKENS || 2_048),
  // Optional retrieval must not delay the first model token indefinitely.
  embeddingSoftTimeoutMs: Number(process.env.AGENT_EMBEDDING_SOFT_TIMEOUT_MS || 5_000),
  embeddingMaxAttempts: Math.min(2, Math.max(1, Number(process.env.AGENT_EMBEDDING_MAX_ATTEMPTS || 2))),
  embeddingRetryDelayMs: Math.max(0, Number(process.env.AGENT_EMBEDDING_RETRY_DELAY_MS || 250)),
  maxHistoryMessages: 256,
  maxContextFacts: Number(process.env.MAX_CONTEXT_FACTS || 20),
  // Keep previously deployed values from silently restoring the shorter limits
  // while GPTProto's Gemini route is being investigated.
  upstreamHeaderTimeoutMs: Math.max(120_000, duration(process.env.UPSTREAM_HEADER_TIMEOUT_MS, 120_000)),
  upstreamStreamTimeoutMs: Math.max(300_000, duration(process.env.UPSTREAM_STREAM_TIMEOUT_MS || process.env.UPSTREAM_TIMEOUT_MS, 300_000)),
  upstreamStreamIdleTimeoutMs: Math.max(90_000, duration(process.env.UPSTREAM_STREAM_IDLE_TIMEOUT_MS, 90_000)),
};
