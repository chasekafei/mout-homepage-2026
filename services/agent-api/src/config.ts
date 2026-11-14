export type ProviderName = "gptproto" | "deepseek";

const csv = (value: string | undefined, fallback: string[]) =>
  (value ? value.split(",") : fallback).map((item) => item.trim()).filter(Boolean);

export const config = {
  port: Number(process.env.PORT || 8787),
  allowedOrigins: csv(process.env.ALLOWED_ORIGINS, ["http://localhost:5173", "http://localhost:5174"]),
  defaultProvider: (process.env.DEFAULT_PROVIDER || "gptproto") as ProviderName,
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
  maxHistoryMessages: Number(process.env.MAX_HISTORY_MESSAGES || 16),
  maxContextFacts: Number(process.env.MAX_CONTEXT_FACTS || 5),
  upstreamTimeoutMs: Number(process.env.UPSTREAM_TIMEOUT_MS || 60_000),
};
