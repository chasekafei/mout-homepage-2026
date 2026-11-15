import { selectHistoryWithinBudget } from "@mout/agent-core";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  pending?: boolean;
  sources?: AgentSource[];
  contactPrompt?: boolean;
};

export type AgentSource = {
  id: string;
  title: string;
  kind: "profile" | "project" | "web";
  detail?: string;
  url?: string;
  source?: string;
  project?: { name: string; href: string; image?: string; eyebrow?: string };
};

export type AgentMode = "profile" | "current";

export type AgentEvent =
  | { type: "meta"; mode: AgentMode; provider?: string; model?: string; searching?: boolean }
  | { type: "delta"; text: string }
  | { type: "source"; source: AgentSource }
  | { type: "fact_sources"; sources: AgentSource[] }
  | { type: "contact_prompt" }
  | { type: "archive_warning"; message: string }
  | { type: "done" }
  | { type: "error"; message: string };

type ChatRequest = {
  conversationId: string;
  messages: Array<{ role: ChatRole; content: string }>;
  mode: AgentMode;
  source: "im" | "homepage";
};

const API_URL = (import.meta.env.VITE_AGENT_API_URL as string | undefined)?.replace(/\/$/, "");
const MOCK = import.meta.env.VITE_AGENT_MOCK !== "false" && !API_URL;
let warmupPromise: Promise<void> | null = null;

export async function warmAgentBackend() {
  if (!API_URL) return;
  warmupPromise ??= (async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4_000);
    try {
      await fetch(`${API_URL}/v1/warmup`, { signal: controller.signal, cache: "no-store" });
    } catch {
      // Warmup is opportunistic; the chat request remains the source of truth.
    } finally {
      window.clearTimeout(timeout);
    }
  })();
  await warmupPromise;
}

function mockAnswer(input: string): { answer: string; sources: AgentSource[]; searching: boolean } {
  const q = input.toLowerCase();
  if (q.includes("agent") || q.includes("分身")) {
    return {
      answer: "我一直觉得，Agent 最重要的不是工具数量，而是它能不能进入真实的 context。做 Super Intern 的时候，我更在意 Agent 能不能待在用户已经在用的 Discord、Telegram 和工作流里，而不是让大家再搬去一个新的聊天窗口。",
      sources: [
        { id: "agent-work", title: "AI Agent 经历", kind: "project", detail: "个人经历 · AI 产品负责人", source: "src/content/site.ts / WORK.agent", project: { name: "AI Agent 与 Super Intern", href: "/work/agent", eyebrow: "AI 产品经历" } },
      ],
      searching: false,
    };
  }
  if (q.includes("产品") || q.includes("项目") || q.includes("ai")) {
    return {
      answer: "我做过的 AI 产品大致分成几条线：起司是 AI 拍照社交，热情小美是 AI VTuber，fakers 是帮用户筛选 AI 信息的社区，Super Intern 则是能在 Discord 和 Telegram 里调用工具的通用 Agent。它们看起来跨度很大，但我一直在追同一个问题：AI 怎么进入人已经在用的场景。",
      sources: [
        { id: "agent-work", title: "AI 产品经历", kind: "project", detail: "公开资料 · 超参数与 Super Intern", source: "src/content/site.ts / WORK.agent", project: { name: "AI Agent 与 Super Intern", href: "/work/agent", eyebrow: "AI 产品经历" } },
      ],
      searching: false,
    };
  }
  if (q.includes("做什么") || q.includes("经历") || q.includes("工作")) {
    return {
      answer: "我是 MouT 的个人分身。你可以把我理解成一个只对我的经历和观点负责的入口：我做过电子政务、品牌营销小游戏、游戏创业和熟人社交，后来一直在做 AI 产品与 AI Agent。比起把所有事情都讲全，我更愿意从具体项目讲我怎么做判断。",
      sources: [
        { id: "profile-timeline", title: "我的经历", kind: "profile", detail: "公开资料 · 工作时间线" },
        { id: "homepage-work", title: "工作场景：AI Agent 核心", kind: "project", detail: "MouT.me" },
      ],
      searching: false,
    };
  }
  if (q.includes("最新") || q.includes("今天") || q.includes("最近")) {
    return {
      answer: "这个问题需要实时信息。我会先查一下公开来源，再把搜索结果和我自己的判断分开写。当前演示模式没有接入实时搜索；正式服务会在这里显示来源。",
      sources: [],
      searching: true,
    };
  }
  return {
    answer: "可以从我的经历、AI 产品、Agent 设计，或者我为什么做这个网站开始问。你也可以直接问一个具体项目，我会尽量用当时的背景和取舍来回答；如果资料里没有，我会明确说不知道。",
    sources: [{ id: "welcome", title: "MouT.me 个人资料库", kind: "profile", detail: "公开资料模式" }],
    searching: false,
  };
}

const sleep = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

async function streamMock(request: ChatRequest, onEvent: (event: AgentEvent) => void) {
  const latestQuestion = request.messages.at(-1)?.content ?? "";
  const { answer, sources, searching } = mockAnswer(latestQuestion);
  onEvent({ type: "meta", mode: searching ? "current" : "profile", provider: "gptproto", model: "gemini-3.8-flash", searching });
  if (searching) await sleep(280);
  if (sources.length) onEvent({ type: "fact_sources", sources });
  if (/(求职|找工作|应聘|岗位|面试|内推|合作|项目合作|联系你|工作机会|collaborat|job opportunity)/iu.test(latestQuestion)) onEvent({ type: "contact_prompt" });
  for (const word of answer.split(/(?<=[，。！？；：])/u)) {
    onEvent({ type: "delta", text: word });
    await sleep(28);
  }
  onEvent({ type: "done" });
}

function parseEventLine(line: string): AgentEvent | null {
  if (!line.startsWith("data:")) return null;
  const value = line.slice(5).trim();
  if (!value || value === "[DONE]") return { type: "done" };
  try {
    const payload = JSON.parse(value) as Record<string, unknown>;
    if (payload.type === "status") {
      const status = payload.value === "searching";
      return { type: "meta", mode: status ? "current" : "profile", provider: "gptproto", model: "gemini-3.8-flash", searching: status };
    }
    if (payload.type === "citation" && typeof payload.title === "string" && typeof payload.url === "string") {
      return { type: "source", source: { id: payload.url, title: payload.title, kind: "web", detail: "实时来源", url: payload.url } };
    }
    if (payload.type === "fact_sources" && Array.isArray(payload.sources)) {
      const sources = payload.sources.filter((source): source is AgentSource => Boolean(source)
        && typeof source === "object"
        && typeof (source as AgentSource).id === "string"
        && typeof (source as AgentSource).title === "string"
        && ((source as AgentSource).kind === "profile" || (source as AgentSource).kind === "project"));
      return { type: "fact_sources", sources };
    }
    if (payload.type === "contact_prompt") return { type: "contact_prompt" };
    if (payload.type === "done") return { type: "done" };
    if (payload.type === "archive_warning") return { type: "archive_warning", message: typeof payload.message === "string" ? payload.message : "本轮对话没有写入收件箱" };
    if (payload.type === "error") return { type: "error", message: typeof payload.message === "string" ? payload.message : "上游请求失败" };
    if (payload.type === "delta" && typeof payload.text === "string") return { type: "delta", text: payload.text };
    return null;
  } catch {
    return null;
  }
}

export async function streamChat(request: ChatRequest, onEvent: (event: AgentEvent) => void, signal?: AbortSignal) {
  if (MOCK) {
    await streamMock(request, onEvent);
    return;
  }

  const lastUserIndex = request.messages.map((message) => message.role).lastIndexOf("user");
  const message = lastUserIndex >= 0 ? request.messages[lastUserIndex].content : "";
  const history = selectHistoryWithinBudget(
    request.messages.slice(0, lastUserIndex >= 0 ? lastUserIndex : request.messages.length).map(({ role, content }) => ({ role, content })),
    116_000,
  );
  const response = await fetch(`${API_URL}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ conversationId: request.conversationId, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, message, history, mode: request.mode === "current" ? "casual" : "about", source: request.source }),
    signal,
  });
  if (!response.ok) throw new Error(`Agent API ${response.status}`);
  if (!response.body) throw new Error("Agent API 没有返回流");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseEventLine(line.trim());
      if (event) onEvent(event);
    }
    if (done) break;
  }
  const last = parseEventLine(buffer.trim());
  if (last) onEvent(last);
}

export const isMockMode = MOCK;
