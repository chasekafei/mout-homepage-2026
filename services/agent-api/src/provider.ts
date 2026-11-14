import type { ChatMessage, ProviderEvent, ProviderRequest } from "@mout/agent-core";
import { config, type ProviderName } from "./config.js";

type ProviderConfig = { apiKey: string; baseUrl: string; model: string; webSearchTool?: string };

const encoder = new TextEncoder();

function providerConfig(name: ProviderName): ProviderConfig {
  return name === "deepseek" ? config.deepseek : config.gptproto;
}

function authHeaders(provider: ProviderConfig): Record<string, string> {
  return {
    Authorization: `Bearer ${provider.apiKey}`,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
}

function asChatMessages(messages: ChatMessage[]) {
  return messages.map((message) => ({ role: message.role, content: message.content }));
}

function textFromUnknown(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return undefined;
  const record = value as Record<string, unknown>;
  for (const key of ["text", "content", "delta", "output_text"]) {
    const candidate = record[key];
    if (typeof candidate === "string") return candidate;
  }
  return undefined;
}

function parseSseBlock(block: string): ProviderEvent | null {
  const data = block.split(/\r?\n/).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n").trim();
  if (!data || data === "[DONE]") return data === "[DONE]" ? { type: "done" } : null;
  try {
    const payload = JSON.parse(data) as Record<string, any>;
    const annotation = payload.annotation ?? payload.url_citation ?? payload.response?.annotation;
    const citationUrl = annotation?.url ?? annotation?.url_citation?.url;
    if (typeof citationUrl === "string") {
      return {
        type: "citation",
        title: String(annotation.title ?? annotation.url_citation?.title ?? citationUrl),
        url: citationUrl,
      };
    }
    const choice = payload.choices?.[0];
    const chatDelta = textFromUnknown(choice?.delta?.content) ?? textFromUnknown(choice?.message?.content);
    const responseDelta = textFromUnknown(payload.delta) ?? textFromUnknown(payload.output_text_delta);
    const text = chatDelta ?? responseDelta;
    if (text) return { type: "delta", text };
    if (payload.type === "response.web_search_call.in_progress" || payload.type === "response.web_search_call.searching") {
      return { type: "status", value: "searching" };
    }
    if (payload.type === "response.output_text.delta") return { type: "delta", text: String(payload.delta || "") };
    if (payload.type === "response.completed") return { type: "done" };
    if (payload.error) return { type: "error", message: String(payload.error.message || payload.error) };
    return null;
  } catch {
    return null;
  }
}

async function* parseStream(response: Response): AsyncGenerator<ProviderEvent> {
  if (!response.body) throw new Error("上游没有返回流");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n+/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) yield event;
    }
    if (done) break;
  }
  const event = parseSseBlock(buffer);
  if (event) yield event;
}

function timeoutSignal(ms: number): AbortSignal {
  return AbortSignal.timeout ? AbortSignal.timeout(ms) : (() => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), ms);
    return controller.signal;
  })();
}

export async function* streamProvider(name: ProviderName, request: ProviderRequest): AsyncGenerator<ProviderEvent> {
  const provider = providerConfig(name);
  if (!provider.apiKey) {
    yield { type: "error", message: `${name} provider 尚未配置 API key` };
    return;
  }

  const useResponses = name === "gptproto" && request.useWebSearch;
  const url = useResponses ? `${provider.baseUrl}/responses` : `${provider.baseUrl}/chat/completions`;
  const body = useResponses
    ? {
        model: request.model,
        stream: true,
        input: asChatMessages(request.messages).map((message) => ({ role: message.role, content: [{ type: "input_text", text: message.content }] })),
        tools: [{ type: provider.webSearchTool || "web_search_preview" }],
      }
    : { model: request.model, messages: asChatMessages(request.messages), stream: true };

  let response: Response;
  try {
    response = await fetch(url, { method: "POST", headers: authHeaders(provider), body: JSON.stringify(body), signal: timeoutSignal(config.upstreamTimeoutMs) });
  } catch (error) {
    yield { type: "error", message: error instanceof Error ? error.message : "上游请求失败" };
    return;
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    yield { type: "error", message: `上游返回 ${response.status}${detail ? `：${detail.slice(0, 500)}` : ""}` };
    return;
  }
  yield { type: "status", value: request.useWebSearch ? "searching" : "answering" };
  yield* parseStream(response);
}

export function providerModel(name: ProviderName, requested?: string): string {
  if (requested && /^[a-zA-Z0-9._:-]{2,100}$/.test(requested)) return requested;
  return providerConfig(name).model;
}

export function sseEvent(event: ProviderEvent): Uint8Array {
  return encoder.encode(`data: ${JSON.stringify(event)}\n\n`);
}
