/** Explicit model IDs shared by the test picker and the API allowlist. */
export const AGENT_CHAT_MODELS = [
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash", provider: "gptproto" },
  { id: "gemini-4-hydrogen", label: "Gemini 4 Hydrogen", provider: "gptproto" },
  { id: "gemini-4-argon", label: "Gemini 4 Argon", provider: "gptproto" },
  { id: "gpt-6.1-sol", label: "GPT 6.1 Sol", provider: "gptproto" },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5", provider: "gptproto" },
  { id: "claude-fable-5-2", label: "Claude Fable 5.2", provider: "gptproto" },
  { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro", provider: "deepseek" },
] as const;

export type AgentChatModelId = typeof AGENT_CHAT_MODELS[number]["id"];
export const DEFAULT_AGENT_CHAT_MODEL: AgentChatModelId = "gemini-4-hydrogen";

export function isAgentChatModelId(value: unknown): value is AgentChatModelId {
  return typeof value === "string" && AGENT_CHAT_MODELS.some((model) => model.id === value);
}
