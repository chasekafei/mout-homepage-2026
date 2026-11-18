import type { ProviderEvent, ProviderRequest } from "@mout/agent-core";

/** These GPTProto routes currently require Gemini's native contents protocol. */
export function usesNativeGemini(model: string): boolean {
  return model === "gemini-4-hydrogen" || model === "gemini-4-argon";
}

export function geminiStreamUrl(baseUrl: string, model: string): string {
  const root = baseUrl.replace(/\/+$/u, "").replace(/\/v1(?:beta)?$/u, "");
  return `${root}/v1beta/models/${encodeURIComponent(model)}:streamGenerateContent?alt=sse`;
}

export function geminiRequestBody(request: ProviderRequest) {
  const system = request.messages.filter((message) => message.role === "system" || message.role === "developer")
    .map((message) => message.content).join("\n\n");
  const contents = request.messages.filter((message) => message.role === "user" || message.role === "assistant")
    .filter((message) => message.content.trim())
    .map((message) => ({ role: message.role === "assistant" ? "model" : "user", parts: [{ text: message.content }] }));
  if (!contents.length) throw new Error("没有可发送的对话内容");
  const tools = [
    ...(request.useWebSearch ? [{ google_search: {} }] : []),
    ...(request.useReadUrl ? [{ url_context: {} }] : []),
  ];
  return {
    ...(system ? { systemInstruction: { parts: [{ text: system }] } } : {}),
    contents,
    ...(tools.length ? { tools } : {}),
  };
}

function searchEvidence(data: Record<string, any>, candidate: Record<string, any> | undefined): ProviderEvent | undefined {
  const metadata = candidate?.groundingMetadata;
  const metadataPresent = Boolean(metadata) && typeof metadata === "object" && !Array.isArray(metadata);
  const tokens = data.usageMetadata?.toolUsePromptTokenCount;
  const toolUsePromptTokens = typeof tokens === "number" && Number.isFinite(tokens) && tokens >= 0 ? tokens : undefined;
  if (!metadataPresent && toolUsePromptTokens === undefined) return undefined;
  const queries: string[] = Array.isArray(metadata?.webSearchQueries)
    ? metadata.webSearchQueries.filter((value: unknown): value is string => typeof value === "string" && Boolean(value.trim())) : [];
  const sourceUrls: string[] = [];
  for (const chunk of Array.isArray(metadata?.groundingChunks) ? metadata.groundingChunks : []) {
    if (typeof chunk?.web?.uri !== "string") continue;
    try {
      const url = new URL(chunk.web.uri);
      if (url.protocol === "http:" || url.protocol === "https:") sourceUrls.push(url.href);
    } catch { /* Malformed URLs cannot establish search evidence. */ }
  }
  return {
    type: "search_evidence", metadataPresent, queries, sourceUrls,
    supportCount: Array.isArray(metadata?.groundingSupports) ? metadata.groundingSupports.length : 0,
    hasSearchEntryPoint: Boolean(metadata?.searchEntryPoint),
    ...(toolUsePromptTokens === undefined ? {} : { toolUsePromptTokens }),
  };
}

/** Decode Gemini SSE without turning thought parts into visible assistant text. */
export function parseGeminiChunk(payload: unknown): ProviderEvent[] {
  if (Array.isArray(payload)) return payload.flatMap(parseGeminiChunk);
  if (!payload || typeof payload !== "object") return [];
  const data = payload as Record<string, any>;
  if (data.error) {
    const status = Number(data.error.code);
    const retryable = [408, 425, 429].includes(status) || status >= 500
      || ["UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED"].includes(data.error.status);
    return [{ type: "error", message: String(data.error.message || data.error), code: "upstream_stream_error", retryable,
      ...(Number.isFinite(status) ? { status } : {}),
    }];
  }
  if (data.promptFeedback?.blockReason) return [{ type: "error", message: `上游未生成回答：${data.promptFeedback.blockReason}` }];
  const candidate = data.candidates?.[0];
  const evidence = searchEvidence(data, candidate);
  if (!candidate) return evidence ? [evidence] : [];
  if (["SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"].includes(candidate.finishReason)) {
    return [{ type: "error", message: `上游未完成回答：${candidate.finishReason}` }];
  }
  const events: ProviderEvent[] = [];
  for (const part of candidate.content?.parts ?? []) {
    if (typeof part.text === "string" && part.text && !part.thought) events.push({ type: "delta", text: part.text });
  }
  for (const chunk of candidate.groundingMetadata?.groundingChunks ?? []) {
    const source = chunk.web ?? chunk.retrievedContext;
    if (typeof source?.uri !== "string") continue;
    try {
      const url = new URL(source.uri);
      if (url.protocol === "http:" || url.protocol === "https:") {
        events.push({ type: "citation", title: typeof source.title === "string" && source.title ? source.title : url.href, url: url.href });
      }
    } catch { /* Ignore malformed source URLs. */ }
  }
  if (evidence) events.push(evidence);
  if (candidate.finishReason === "MAX_TOKENS") events.push({ type: "error", message: "回答达到模型输出上限，内容尚未完整。" });
  else if (candidate.finishReason === "STOP") {
    const usage = data.usageMetadata;
    events.push({ type: "done", ...(usage ? { usage: {
      promptTokens: usage.promptTokenCount,
      completionTokens: usage.candidatesTokenCount,
      totalTokens: usage.totalTokenCount,
    } } : {}) });
  } else if (candidate.finishReason) events.push({ type: "error", message: `上游未完成回答：${candidate.finishReason}` });
  return events;
}
