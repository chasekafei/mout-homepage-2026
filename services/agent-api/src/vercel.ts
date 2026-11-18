import type { ProviderRequest } from "@mout/agent-core";
import { config } from "./config.js";

/** Verified AI Gateway IDs; keep UI IDs stable across suppliers. */
export const VERCEL_MODEL_IDS = {
  "gemini-3.8-flash": "google/gemini-3.8-flash",
  "gemini-4-hydrogen": "google/gemini-4-hydrogen",
  "gemini-4-argon": "google/gemini-4-argon",
  "gpt-6.1-sol": "openai/gpt-6.1-sol",
  "claude-sonnet-5-5": "anthropic/claude-sonnet-5.5",
  "claude-fable-5-2": "anthropic/claude-fable-5.2",
} as const;

export function vercelModelId(model: string): string {
  if (!Object.prototype.hasOwnProperty.call(VERCEL_MODEL_IDS, model)) {
    throw new Error(`Vercel AI Gateway 未配置模型 ID：${model}`);
  }
  return VERCEL_MODEL_IDS[model as keyof typeof VERCEL_MODEL_IDS];
}

/** Gateway normalizes the provider protocol; only send Chat Completions fields. */
export function vercelRequestBody(request: ProviderRequest) {
  return {
    model: vercelModelId(request.model),
    messages: request.messages.map(({ role, content }) => ({ role, content })),
    stream: true as const,
    stream_options: { include_usage: true },
    ...(request.model.startsWith("gemini-") ? { reasoning: { effort: config.geminiThinkingLevel } } : {}),
  };
}
