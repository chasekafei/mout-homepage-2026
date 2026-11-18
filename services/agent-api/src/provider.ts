import type { AgentProviderPreference, ChatMessage, ProviderEvent, ProviderRequest } from "@mout/agent-core";
import { config, type ProviderName } from "./config.js";
import { normalizeDeepSeekToolCalls, parseDeepSeekWebChunk } from "./deepseek-web.js";
import { geminiRequestBody, geminiStreamUrl, parseGeminiChunk, usesNativeGemini } from "./gemini.js";
import { VERCEL_MODEL_IDS, vercelRequestBody } from "./vercel.js";

type ProviderConfig = { apiKey: string; baseUrl: string; model: string; webSearchTool?: string };
export type ProviderCall = ProviderRequest & { signal?: AbortSignal };

const encoder = new TextEncoder();

function providerConfig(name: ProviderName): ProviderConfig {
  return name === "deepseek" ? config.deepseek : name === "vercel" ? config.vercel : config.gptproto;
}

type ProviderError = Extract<ProviderEvent, { type: "error" }>;
const retryableStatus = (status: number) => [408, 425, 429].includes(status) || status >= 500;
const networkError = (error: unknown) => error instanceof Error && ["TypeError", "TimeoutError", "AbortError", "ProviderFirstTokenTimeoutError"].includes(error.name);

export function providerChain(preference: AgentProviderPreference, model: string): ProviderName[] {
  if (preference === "deepseek" || (preference === "auto" && ["deepseek-v4-pro", "deepseek-flash"].includes(model))) {
    return config.deepseek.apiKey ? ["deepseek"] : [];
  }
  const order = config.providerOrder.length ? config.providerOrder : ["vercel", "gptproto"] as const;
  const candidates = preference === "auto" ? [...order] : [preference, ...order];
  return [...new Set(candidates)].filter((name) => {
    if (name === "vercel" && !Object.hasOwn(VERCEL_MODEL_IDS, model)) return false;
    return Boolean(providerConfig(name).apiKey);
  });
}

export function primaryProvider(preference: AgentProviderPreference, model: string): ProviderName {
  return providerChain(preference, model)[0]
    ?? (preference === "auto" ? (["deepseek-v4-pro", "deepseek-flash"].includes(model) ? "deepseek" : "vercel") : preference);
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
    if (payload.error) {
      const status = Number(payload.error.status ?? payload.error.code);
      const retryable = (Number.isFinite(status) && retryableStatus(status))
        || ["server_error", "rate_limit_exceeded", "overloaded_error", "rate_limit_error"].includes(payload.error.type ?? payload.error.code);
      return [{ type: "error", message: String(payload.error.message || payload.error), code: "upstream_stream_error", retryable }];
    }
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
    const refusal = choice?.delta?.refusal ?? choice?.message?.refusal;
    if (choice?.finish_reason === "content_filter" || refusal) {
      return [{ type: "error", message: typeof refusal === "string" ? refusal : "上游未能生成该问题的回答", code: "provider_refusal", retryable: false }];
    }
    const chatDelta = textFromUnknown(choice?.delta?.content) ?? textFromUnknown(choice?.message?.content);
    const responseDelta = textFromUnknown(payload.delta) ?? textFromUnknown(payload.output_text_delta);
    const text = chatDelta ?? responseDelta;
    if (text) events.push({ type: "delta", text });
    if (payload.type === "response.web_search_call.in_progress" || payload.type === "response.web_search_call.searching") {
      events.push({ type: "status", value: "searching" });
    }
    if (payload.type === "response.completed") events.push({ type: "done" });
    if (choice?.finish_reason === "stop") events.push({ type: "done" });
    if (choice?.finish_reason === "length") events.push({ type: "error", message: "回答达到模型输出上限，内容尚未完整。", code: "output_limit", retryable: false });
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

export async function* streamProviderAttempt(name: ProviderName, request: ProviderCall): AsyncGenerator<ProviderEvent> {
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
  const body = name === "vercel" ? vercelRequestBody(request) : nativeGemini ? geminiRequestBody(request) : useResponses
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
    const signal = request.signal ? AbortSignal.any([controller.signal, request.signal]) : controller.signal;
    response = await fetch(url, { method: "POST", headers: authHeaders(provider), body: JSON.stringify(body), signal });
  } catch (error) {
    clearTimeout(headerTimer);
    const message = headerTimedOut
      ? `上游响应头超时（${config.upstreamHeaderTimeoutMs}ms），${name === "deepseek" ? "DeepSeek" : name === "vercel" ? "Vercel AI Gateway" : "GPT Proto"} 尚未返回响应`
      : error instanceof Error ? error.message : "上游请求失败";
    yield { type: "error", message, code: headerTimedOut ? "header_timeout" : "network_error", retryable: headerTimedOut || networkError(error) };
    return;
  }
  clearTimeout(headerTimer);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    yield { type: "error", message: `上游返回 ${response.status}${detail ? `：${detail.slice(0, 500)}` : ""}`, status: response.status, code: `http_${response.status}`, retryable: retryableStatus(response.status) };
    return;
  }
  if (!response.body) {
    yield { type: "error", message: "上游没有返回响应流", code: "empty_response", retryable: true };
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
    yield { type: "error", message, code: totalTimedOut ? "stream_timeout" : "stream_error", retryable: totalTimedOut || error instanceof UpstreamStreamIdleTimeoutError || networkError(error) };
  } finally {
    clearTimeout(streamTimer);
  }
}

/** At most one alternate supplier; visible text is the no-replay boundary. */
export async function* streamProvider(preference: AgentProviderPreference, request: ProviderCall): AsyncGenerator<ProviderEvent> {
  const chain = providerChain(preference, request.model);
  if (!chain.length) {
    yield { type: "error", message: preference === "deepseek" ? "DeepSeek 官方 API key 尚未配置" : "没有为当前模型配置可用的 API provider", code: "provider_not_configured", retryable: false };
    return;
  }
  for (let index = 0; index < chain.length; index += 1) {
    if (request.signal?.aborted) return;
    const name = chain[index];
    yield { type: "provider_attempt", provider: name, model: request.model, attempt: index + 1 };
    const controller = new AbortController();
    let firstTokenExpired = false;
    const timer = setTimeout(() => {
      firstTokenExpired = true;
      const error = new Error(`等待首段正文超时（${config.providerFirstTokenTimeoutMs}ms）`);
      error.name = "ProviderFirstTokenTimeoutError";
      controller.abort(error);
    }, config.providerFirstTokenTimeoutMs);
    const signal = request.signal ? AbortSignal.any([request.signal, controller.signal]) : controller.signal;
    let committed = false;
    let failure: ProviderError | undefined;
    let completed: Extract<ProviderEvent, { type: "done" }> | undefined;
    const pending: ProviderEvent[] = [];
    try {
      for await (const event of streamProviderAttempt(name, { ...request, signal })) {
        if (event.type === "error") { failure = event; break; }
        if (event.type === "done") { completed = event; continue; }
        if (event.type === "status") { yield event; continue; }
        if (event.type === "delta") {
          if (!event.text) continue;
          if (!committed && !event.text.trim()) { pending.push(event); continue; }
          if (!committed) {
            committed = true;
            clearTimeout(timer);
            for (const buffered of pending) yield buffered;
            pending.length = 0;
          }
          yield event;
        } else if (committed) yield event;
        else pending.push(event);
      }
    } catch (error) {
      failure = { type: "error", message: error instanceof Error ? error.message : "上游请求失败", code: "provider_exception", retryable: networkError(error) };
    } finally {
      clearTimeout(timer);
      controller.abort();
    }
    if (request.signal?.aborted) return;
    if (firstTokenExpired) failure = { type: "error", message: `等待首段正文超时（${config.providerFirstTokenTimeoutMs}ms）`, code: "first_token_timeout", retryable: true };
    failure ??= !committed ? { type: "error", message: "上游未返回有效正文", code: "empty_response", retryable: true }
      : !completed ? { type: "error", message: "上游响应流提前结束，回答可能不完整", code: "incomplete_stream", retryable: true } : undefined;
    if (!failure) { yield completed!; return; }
    const next = chain[index + 1];
    if (!committed && failure.retryable && next) {
      yield { type: "provider_fallback", from: name, to: next, model: request.model, code: failure.code ?? "upstream_error" };
      continue;
    }
    yield failure;
    return;
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
