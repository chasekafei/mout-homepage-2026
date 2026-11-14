export type AgentMode = "about" | "work" | "opinion" | "casual";

export type ChatRole = "system" | "user" | "assistant" | "developer";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type PersonalFact = {
  id: string;
  title: string;
  body: string;
  tags: string[];
  source: string;
  visibility: "public" | "private";
};

export type AgentRequest = {
  message: string;
  history?: ChatMessage[];
  mode?: AgentMode;
  provider?: "gptproto" | "deepseek";
  model?: string;
  source?: "homepage" | "im";
};

export type ProviderRequest = {
  messages: ChatMessage[];
  model: string;
  stream: true;
  useWebSearch: boolean;
};

export type ProviderEvent =
  | { type: "delta"; text: string }
  | { type: "citation"; title: string; url: string }
  | { type: "status"; value: "searching" | "answering" }
  | { type: "done"; usage?: { promptTokens?: number; completionTokens?: number; totalTokens?: number } }
  | { type: "error"; message: string };
