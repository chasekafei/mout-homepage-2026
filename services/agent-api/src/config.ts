export type ProviderName = "gptproto" | "deepseek";

const csv = (value: string | undefined, fallback: string[]) =>
  (value ? value.split(",") : fallback).map((item) => item.trim()).filter(Boolean);

export const config = {
  port: Number(process.env.PORT || 8787),
  allowedOrigins: csv(process.env.ALLOWED_ORIGINS, ["http://localhost:5173", "http://localhost:5174"]),
  defaultProvider: (process.env.DEFAULT_PROVIDER || "gptproto") as ProviderName,
  timeZone: process.env.AGENT_TIMEZONE || "Asia/Shanghai",
  databaseUrl: process.env.DATABASE_URL || "",
  adminPassword: process.env.ADMIN_PASSWORD || "",
  adminSessionSecret: process.env.ADMIN_SESSION_SECRET || "",
  gptproto: {
    apiKey: process.env.GPTPROTO_API_KEY || "",
    baseUrl: process.env.GPTPROTO_BASE_URL || "https://gptproto.com/v1",
    model: process.env.GPTPROTO_MODEL || "gemini-3.8-flash",
    webSearchTool: process.env.GPTPROTO_WEB_SEARCH_TOOL || "web_search_preview",
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
    model: process.env.DEEPSEEK_MODEL || "deepseek-chat",
  },
  maxContextTokens: Number(process.env.MAX_CONTEXT_TOKENS || 128_000),
  contextOutputReserveTokens: Number(process.env.CONTEXT_OUTPUT_RESERVE_TOKENS || 8_192),
  contextSafetyMarginTokens: Number(process.env.CONTEXT_SAFETY_MARGIN_TOKENS || 2_048),
  maxHistoryMessages: 256,
  maxContextFacts: Number(process.env.MAX_CONTEXT_FACTS || 20),
  upstreamTimeoutMs: Number(process.env.UPSTREAM_TIMEOUT_MS || 60_000),
};
