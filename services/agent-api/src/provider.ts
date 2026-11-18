import type { ChatMessage, ProviderEvent, ProviderRequest } from "@mout/agent-core";
import { config, type ProviderName } from "./config.js";
import { normalizeDeepSeekToolCalls, parseDeepSeekWebChunk } from "./deepseek-web.js";
import { geminiRequestBody, geminiStreamUrl, parseGeminiChunk, usesNativeGemini } from "./gemini.js";

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

function asChatMessages(messages: ChatMessage[], includeDeepSeekTools = false) {
  return messages.map((message) => {
    const toolCalls = includeDeepSeekTools && message.role === "assistant"
      ? normalizeDeepSeekToolCalls(message.deepseekToolCalls)
      : undefined;
    return {
      role: message.role,
      content: message.content,
      ...(toolCalls?.length ? { server_tool_calls: toolCalls } : {}),
    };
  });
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

function parseSseBlock(block: string, includeDeepSeekTools = false, nativeGemini = false): ProviderEvent[] {
  const data = block.split(/\r?\n/).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n").trim();
  if (!data || data === "[DONE]") return data === "[DONE]" ? [{ type: "done" }] : [];
  try {
    const payload = JSON.parse(data) as Record<string, any>;
    if (nativeGemini) return parseGeminiChunk(payload);
    if (payload.error) return [{ type: "error", message: String(payload.error.message || payload.error) }];
    const events = includeDeepSeekTools ? parseDeepSeekWebChunk(payload) : [];
    const annotation = payload.annotation ?? payload.url_citation ?? payload.response?.annotation;
    const citationUrl = annotation?.url ?? annotation?.url_citation?.url;
    if (typeof citationUrl === "string") {
      events.push({
        type: "citation",
        title: String(annotation.title ?? annotation.url_citation?.title ?? citationUrl),
        url: citationUrl,
      });
    }
    const choice = payload.choices?.[0];
    const chatDelta = textFromUnknown(choice?.delta?.content) ?? textFromUnknown(choice?.message?.content);
    const responseDelta = textFromUnknown(payload.delta) ?? textFromUnknown(payload.output_text_delta);
    const text = chatDelta ?? responseDelta;
    if (text) events.push({ type: "delta", text });
    if (payload.type === "response.web_search_call.in_progress" || payload.type === "response.web_search_call.searching") {
      events.push({ type: "status", value: "searching" });
    }
    if (payload.type === "response.completed") events.push({ type: "done" });
    return events;
  } catch {
    return [];
  }
}

class UpstreamStreamIdleTimeoutError extends Error {
  constructor(readonly timeoutMs: number) {
    super(`上游流式响应超过 ${timeoutMs}ms 没有新数据`);
    this.name = "UpstreamStreamIdleTimeoutError";
  }
}

async function readWithIdleTimeout(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  timeoutMs: number,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  if (timeoutMs <= 0) return reader.read();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      void reader.cancel();
      reject(new UpstreamStreamIdleTimeoutError(timeoutMs));
    }, timeoutMs);
    reader.read().then(
      (result) => {
        clearTimeout(timer);
        resolve(result);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

async function* parseStreamWithIdleTimeout(response: Response, idleTimeoutMs: number, includeDeepSeekTools: boolean, nativeGemini: boolean): AsyncGenerator<ProviderEvent> {
  if (!response.body) throw new Error("上游没有返回流");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const citations = new Set<string>();
  let buffer = "";
  while (true) {
    const { done, value } = await readWithIdleTimeout(reader, idleTimeoutMs);
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n+/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      for (const event of parseSseBlock(block, includeDeepSeekTools, nativeGemini)) {
        if (event.type === "citation") {
          if (citations.has(event.url)) continue;
          citations.add(event.url);
        }
        yield event;
      }
    }
    if (done) break;
  }
  for (const event of parseSseBlock(buffer, includeDeepSeekTools, nativeGemini)) {
    if (event.type === "citation" && citations.has(event.url)) continue;
    yield event;
  }
}

export function supportsDeepSeekWebTools(model: string): boolean {
  return model === "deepseek-flash";
}

export function hasDeepSeekReadContext(messages: ChatMessage[] | undefined): boolean {
  return (messages ?? []).some((message) => message.role === "assistant"
    && normalizeDeepSeekToolCalls(message.deepseekToolCalls)?.some((step) => (
      (step.calls as Array<Record<string, unknown>>).some((call) => call.kind === "read_link"
        && call.status === "completed" && typeof call.signature === "string" && call.signature.length > 0)
    )));
}

export async function* streamProvider(name: ProviderName, request: ProviderRequest): AsyncGenerator<ProviderEvent> {
  const provider = providerConfig(name);
  if (!provider.apiKey) {
    yield { type: "error", message: `${name} provider 尚未配置 API key` };
    return;
  }

  const nativeGemini = name === "gptproto" && usesNativeGemini(request.model);
  const useResponses = name === "gptproto" && request.useWebSearch && !nativeGemini;
  const useDeepSeekTools = name === "deepseek" && supportsDeepSeekWebTools(request.model);
  if (name === "deepseek" && !useDeepSeekTools && (request.useWebSearch || request.useReadUrl)) {
    yield { type: "error", message: "DeepSeek 托管搜索与链接阅读需要 deepseek-flash 模型" };
    return;
  }
  const baseUrl = provider.baseUrl.replace(/\/+$/u, "");
  const url = nativeGemini ? geminiStreamUrl(baseUrl, request.model)
    : useResponses ? `${baseUrl}/responses` : `${baseUrl}/chat/completions`;
  const body = nativeGemini ? geminiRequestBody(request) : useResponses
    ? {
        model: request.model,
        stream: true,
        input: asChatMessages(request.messages).map((message) => ({ role: message.role, content: [{ type: "input_text", text: message.content }] })),
        tools: [{ type: provider.webSearchTool || "web_search_preview" }],
      }
    : {
        model: request.model,
        messages: asChatMessages(request.messages, useDeepSeekTools),
        stream: true,
        // Personal conversation uses the same non-thinking behavior as the old
        // deepseek-chat integration; V4 Pro otherwise enables thinking by default.
        ...(name === "deepseek" ? { thinking: { type: "disabled" } } : {}),
        ...(useDeepSeekTools ? { tools: [{ type: "deepseek_web_search" }, { type: "deepseek_read_url" }] } : {}),
      };

  const controller = new AbortController();
  let headerTimedOut = false;
  let totalTimedOut = false;
  const headerTimer = setTimeout(() => {
    headerTimedOut = true;
    controller.abort();
  }, config.upstreamHeaderTimeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { method: "POST", headers: authHeaders(provider), body: JSON.stringify(body), signal: controller.signal });
  } catch (error) {
    clearTimeout(headerTimer);
    const message = headerTimedOut
      ? `上游响应头超时（${config.upstreamHeaderTimeoutMs}ms），${name === "deepseek" ? "DeepSeek" : "GPT Proto"} 尚未返回响应`
      : error instanceof Error ? error.message : "上游请求失败";
    yield { type: "error", message };
    return;
  }
  clearTimeout(headerTimer);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    yield { type: "error", message: `上游返回 ${response.status}${detail ? `：${detail.slice(0, 500)}` : ""}` };
    return;
  }
  const streamTimer = setTimeout(() => {
    totalTimedOut = true;
    controller.abort();
  }, config.upstreamStreamTimeoutMs);
  try {
    const initialStatus = nativeGemini && request.useReadUrl ? "reading" : useResponses || (nativeGemini && request.useWebSearch) ? "searching" : "answering";
    yield { type: "status", value: initialStatus, provider: name, model: request.model };
    let answering = initialStatus === "answering";
    let hasWebSources = false;
    let upstreamFailed = false;
    for await (const event of parseStreamWithIdleTimeout(response, config.upstreamStreamIdleTimeoutMs, useDeepSeekTools, nativeGemini)) {
      if (event.type === "search_evidence" && event.sourceUrls.length) hasWebSources = true;
      if (event.type === "error") upstreamFailed = true;
      if (event.type === "status") answering = event.value === "answering";
      if (event.type === "delta" && !answering) {
        yield { type: "status", value: "answering", provider: name, model: request.model };
        answering = true;
      }
      yield event;
    }
    if (nativeGemini && request.useWebSearch && !hasWebSources && !upstreamFailed) {
      yield { type: "tool_error", tool: "google_search", code: "search_evidence_unavailable" };
    }
  } catch (error) {
    const message = totalTimedOut
      ? `上游流式响应总时长超过 ${config.upstreamStreamTimeoutMs}ms`
      : error instanceof Error ? error.message : "上游流式响应失败";
    yield { type: "error", message };
  } finally {
    clearTimeout(streamTimer);
  }
}

export function providerModel(
  name: ProviderName,
  requested?: string,
  capabilities?: { useWebSearch?: boolean; useReadUrl?: boolean; history?: ChatMessage[] },
): string {
  const model = requested && /^[a-zA-Z0-9._:-]{2,100}$/.test(requested) ? requested : providerConfig(name).model;
  // The official hosted web tools currently require Flash. Keep Pro for ordinary
  // conversation, and use Flash for web work and follow-ups on signed webpages.
  if (name === "deepseek" && (capabilities?.useWebSearch || capabilities?.useReadUrl || hasDeepSeekReadContext(capabilities?.history))) {
    return "deepseek-flash";
  }
  return model;
}

export function sseEvent(event: ProviderEvent): Uint8Array {
  return encoder.encode(`data: ${JSON.stringify(event)}\n\n`);
}
