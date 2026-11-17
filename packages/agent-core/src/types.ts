export type AgentMode = "about" | "work" | "opinion" | "casual";

export type ChatRole = "system" | "user" | "assistant" | "developer";

// DeepSeek's opaque tool records must retain kind/signature for later turns.
export type DeepSeekToolStep = Record<string, unknown>;

export type ChatMessage = {
  role: ChatRole;
  content: string;
  deepseekToolCalls?: DeepSeekToolStep[];
};

export type PersonalFact = {
  id: string;
  title: string;
  body: string;
  recordType?: "fact" | "opinion" | "blog" | "resume_source" | "oral_history";
  publishedAt?: string;
  dateConfidence?: "uncertain";
  groupId?: string;
  sensitivity?: "personal";
  sourceVersion?: "2021" | "2024" | "2026";
  sourceFormat?: "pdf" | "html";
  page?: number;
  section?: string;
  tags: string[];
  keywords?: string[];
  queries?: string[];
  project?: {
    name: string;
    href: string;
    image?: string;
    eyebrow?: string;
  };
  source: string;
  visibility: "public" | "private";
};

export type FactSource = {
  id: string;
  title: string;
  source: string;
  kind: "profile" | "project";
  project?: PersonalFact["project"];
};

export type AgentRequest = {
  message: string;
  conversationId?: string;
  timezone?: string;
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
  useReadUrl?: boolean;
};

export type ProviderEvent =
  | { type: "delta"; text: string }
  | { type: "fact_sources"; sources: FactSource[] }
  | { type: "contact_prompt" }
  | { type: "citation"; title: string; url: string }
  | { type: "status"; value: "searching" | "reading" | "answering"; provider?: "gptproto" | "deepseek"; model?: string }
  | { type: "provider_context"; deepseekToolCalls: DeepSeekToolStep[] }
  | { type: "tool_error"; tool: string; code: string }
  | { type: "archive_warning"; message: string }
  | { type: "done"; usage?: { promptTokens?: number; completionTokens?: number; totalTokens?: number } }
  | { type: "error"; message: string };
