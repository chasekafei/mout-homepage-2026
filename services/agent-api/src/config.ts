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
  deepseek: {
    apiKey: process.env.DEEPSEEK_API_KEY || "",
    baseUrl: process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com/v1",
    model: process.env.DEEPSEEK_MODEL || "deepseek-chat",
  },
  maxContextTokens: Number(process.env.MAX_CONTEXT_TOKENS || 128_000),
  contextOutputReserveTokens: Number(process.env.CONTEXT_OUTPUT_RESERVE_TOKENS || 8_192),
  contextSafetyMarginTokens: Number(process.env.CONTEXT_SAFETY_MARGIN_TOKENS || 2_048),
  maxHistoryMessages: 256,
  maxContextFacts: Number(process.env.MAX_CONTEXT_FACTS || 8),
  upstreamTimeoutMs: Number(process.env.UPSTREAM_TIMEOUT_MS || 60_000),
};
