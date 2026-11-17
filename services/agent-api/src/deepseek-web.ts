import type { DeepSeekToolStep, ProviderEvent } from "@mout/agent-core";

const DEEPSEEK_WEB_TOOLS = new Set(["deepseek_web_search", "deepseek_read_url"]);
const MAX_TOOL_STEPS = 24;
const MAX_TOOL_CALLS = 64;
const MAX_TOOL_CONTEXT_CHARS = 400_000;

function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function isIndex(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

/** Preserve DeepSeek's opaque page signatures and complete tool records for replay. */
export function normalizeDeepSeekToolCalls(value: unknown): DeepSeekToolStep[] | undefined {
  if (!Array.isArray(value) || value.length > MAX_TOOL_STEPS) return undefined;
  let count = 0;
  for (const rawStep of value) {
    const step = record(rawStep);
    if (!step || !isIndex(step.index) || !Array.isArray(step.calls)) return undefined;
    count += step.calls.length;
    if (count > MAX_TOOL_CALLS) return undefined;
    for (const rawCall of step.calls) {
      const call = record(rawCall);
      if (!call || !isIndex(call.index)
        || typeof call.id !== "string" || !call.id.trim()
        || typeof call.type !== "string" || !DEEPSEEK_WEB_TOOLS.has(call.type)) return undefined;
    }
  }
  try {
    if (JSON.stringify(value).length > MAX_TOOL_CONTEXT_CHARS) return undefined;
  } catch {
    return undefined;
  }
  // Do not pick fields or regenerate these records: kind and signature are
  // required to restore previously read webpages on a later user turn.
  return value as DeepSeekToolStep[];
}

function citation(value: unknown): ProviderEvent | undefined {
  const source = record(value);
  if (!source || typeof source.url !== "string") return undefined;
  try {
    const url = new URL(source.url);
    if (url.protocol !== "http:" && url.protocol !== "https:") return undefined;
    return {
      type: "citation",
      title: typeof source.title === "string" && source.title.trim() ? source.title : url.href,
      url: url.href,
    };
  } catch {
    return undefined;
  }
}

function completedCallEvents(call: Record<string, unknown>): ProviderEvent[] {
  if (typeof call.type !== "string" || !DEEPSEEK_WEB_TOOLS.has(call.type)) return [];
  if (call.status === "failed") {
    const error = record(call.error);
    return [{
      type: "tool_error",
      tool: call.type,
      code: typeof error?.code === "string" ? error.code : "unknown_error",
    }];
  }
  if (call.status !== "completed") return [];
  return [
    ...(Array.isArray(call.sources) ? call.sources : []),
    ...(call.page ? [call.page] : []),
  ].flatMap((source) => {
    const event = citation(source);
    return event ? [event] : [];
  });
}

/** Decode only the native web-tool extensions, leaving text deltas to the caller. */
export function parseDeepSeekWebChunk(payload: unknown): ProviderEvent[] {
  const parsed = record(payload);
  if (!parsed || !Array.isArray(parsed.choices)) return [];
  const events: ProviderEvent[] = [];
  for (const rawChoice of parsed.choices) {
    const choice = record(rawChoice);
    if (!choice) continue;
    const toolEvent = record(choice.server_tool_event);
    const call = record(toolEvent?.call);
    if (call && typeof call.type === "string" && DEEPSEEK_WEB_TOOLS.has(call.type)) {
      if (toolEvent?.type === "call_started") {
        const action = record(call.action);
        const reading = call.type === "deepseek_read_url"
          || call.kind === "read_link"
          || action?.type === "open_page"
          || action?.type === "find_in_page"
          || action?.type === "read_link";
        events.push({ type: "status", value: reading ? "reading" : "searching" });
      } else if (toolEvent?.type === "call_completed") {
        events.push(...completedCallEvents(call));
      }
    }

    const delta = record(choice.delta) ?? record(choice.message);
    if (!delta) continue;
    const toolCalls = normalizeDeepSeekToolCalls(delta.server_tool_calls);
    if (toolCalls?.length) {
      for (const rawStep of toolCalls) {
        const step = record(rawStep);
        if (!Array.isArray(step?.calls)) continue;
        for (const rawCall of step.calls) {
          const completedCall = record(rawCall);
          if (completedCall) events.push(...completedCallEvents(completedCall));
        }
      }
      events.push({ type: "provider_context", deepseekToolCalls: toolCalls });
    }
    if (Array.isArray(delta.annotations)) {
      for (const rawAnnotation of delta.annotations) {
        const annotation = record(rawAnnotation);
        if (annotation?.type !== "url_citation") continue;
        const event = citation(annotation.url_citation);
        if (event) events.push(event);
      }
    }
  }
  return events;
}
