import assert from "node:assert/strict";
import test from "node:test";
import type { ProviderEvent } from "@mout/agent-core";
import { config } from "../src/config.js";
import { streamProvider, type ProviderCall } from "../src/provider.js";

function sse(...payloads: unknown[]): Response {
  const encoder = new TextEncoder();
  // Heartbeats count as first bytes, but do not imply that reasoning or text arrived.
  const parts = [": heartbeat\n\n", ...payloads.map((payload) => `data: ${typeof payload === "string" ? payload : JSON.stringify(payload)}\n\n`)];
  return new Response(new ReadableStream({ start(controller) {
    for (const part of parts) controller.enqueue(encoder.encode(part));
    controller.close();
  } }));
}

async function fixture(run: () => Promise<void>) {
  const saved = { fetch: globalThis.fetch, vercel: { ...config.vercel }, gptproto: { ...config.gptproto }, order: config.providerOrder };
  Object.assign(config.vercel, { apiKey: "test-vercel", baseUrl: "https://vercel.test/v1" });
  Object.assign(config.gptproto, { apiKey: "test-gptproto", baseUrl: "https://gptproto.test/v1" });
  config.providerOrder = ["vercel", "gptproto"];
  try { await run(); }
  finally {
    globalThis.fetch = saved.fetch;
    Object.assign(config.vercel, saved.vercel);
    Object.assign(config.gptproto, saved.gptproto);
    config.providerOrder = saved.order;
  }
}

async function collect(preference: "auto" | "gptproto" = "auto", overrides: Partial<ProviderCall> = {}) {
  const events: ProviderEvent[] = [];
  for await (const event of streamProvider(preference, {
    model: "gemini-4-hydrogen", messages: [{ role: "user", content: "你好" }],
    stream: true, useWebSearch: false, ...overrides,
  })) events.push(event);
  return events;
}

test("Gateway diagnostics separate headers, first bytes and first reasoning without exposing reasoning text", async () => fixture(async () => {
  globalThis.fetch = async () => sse(
    { id: "gen_example", choices: [{ delta: { reasoning: "不能展示的内部思考" } }] },
    { id: "gen_example", choices: [{ delta: { reasoning: "后续思考" } }] },
    { id: "gen_example", choices: [{ delta: { content: "你好呀。" }, finish_reason: "stop" }] },
    { id: "gen_example", choices: [], usage: { prompt_tokens: 100, completion_tokens: 80, total_tokens: 180, completion_tokens_details: { reasoning_tokens: 72 } } },
    "[DONE]",
  );
  const events = await collect();
  const diagnostics = events.filter((event) => event.type === "provider_diagnostics");
  assert.equal(diagnostics.filter((event) => event.headersMs !== undefined).length, 1);
  assert.equal(diagnostics.filter((event) => event.firstByteMs !== undefined).length, 1);
  assert.equal(diagnostics.filter((event) => event.firstReasoningMs !== undefined).length, 1);
  assert.equal(diagnostics.filter((event) => event.responseId === "gen_example").length, 1);
  assert.ok(diagnostics.every((event) => event.provider === "vercel" && event.model === "gemini-4-hydrogen"));
  assert.ok(!JSON.stringify(events).includes("内部思考"));
  assert.ok(!JSON.stringify(events).includes("后续思考"));
  assert.deepEqual(events.filter((event) => event.type === "delta"), [{ type: "delta", text: "你好呀。" }]);
  // The usage-only frame follows finish_reason and survives the final [DONE].
  assert.deepEqual(events.filter((event) => event.type === "done"), [{ type: "done", usage: { promptTokens: 100, completionTokens: 80, totalTokens: 180, reasoningTokens: 72 } }]);
}));

test("native Gemini late usage and thought-token counts survive a separate final frame", async () => fixture(async () => {
  globalThis.fetch = async () => sse(
    { responseId: "native_response", candidates: [{ content: { parts: [{ thought: true, text: "私有思考" }] } }] },
    { responseId: "native_response", candidates: [{ content: { parts: [{ text: "这是正文。" }] }, finishReason: "STOP" }] },
    { usageMetadata: { promptTokenCount: 20, candidatesTokenCount: 7, totalTokenCount: 39, thoughtsTokenCount: 12 } },
    "[DONE]",
  );
  const events = await collect("gptproto");
  assert.ok(events.some((event) => event.type === "provider_diagnostics" && event.provider === "gptproto" && event.responseId === "native_response" && event.firstReasoningMs !== undefined));
  assert.ok(!JSON.stringify(events).includes("私有思考"));
  assert.deepEqual(events.filter((event) => event.type === "done"), [{ type: "done", usage: { promptTokens: 20, completionTokens: 7, totalTokens: 39, reasoningTokens: 12 } }]);
}));

test("failed-attempt IDs and usage remain scoped to diagnostics while completion uses backup usage", async () => fixture(async () => {
  let calls = 0;
  globalThis.fetch = async () => ++calls === 1 ? sse(
    { id: "gen_failed", choices: [{ delta: { reasoning: "失败供应商内部推理" } }], usage: { total_tokens: 900, completion_tokens_details: { reasoning_tokens: 800 } } },
    { error: { type: "server_error", message: "temporarily unavailable" } },
  ) : sse(
    { responseId: "backup_response", candidates: [{ content: { parts: [{ text: "备用回复。" }] }, finishReason: "STOP" }], usageMetadata: { promptTokenCount: 20, candidatesTokenCount: 5, totalTokenCount: 25 } },
  );
  const events = await collect();
  assert.equal(calls, 2);
  assert.ok(events.some((event) => event.type === "provider_diagnostics" && event.provider === "vercel" && event.responseId === "gen_failed"));
  assert.ok(events.some((event) => event.type === "provider_diagnostics" && event.provider === "gptproto" && event.responseId === "backup_response"));
  const publicEvents = events.filter((event) => event.type !== "provider_diagnostics");
  assert.ok(!JSON.stringify(publicEvents).includes("gen_failed"));
  assert.ok(!JSON.stringify(publicEvents).includes("900"));
  assert.ok(!JSON.stringify(events).includes("失败供应商内部推理"));
  assert.deepEqual(events.filter((event) => event.type === "done"), [{ type: "done", usage: { promptTokens: 20, completionTokens: 5, totalTokens: 25 } }]);
}));

test("malformed IDs and invalid token counts cannot become diagnostic log text", async () => fixture(async () => {
  globalThis.fetch = async () => sse(
    { id: "gen_bad\nFAKE LOG", choices: [{ delta: { content: "正文。" }, finish_reason: "stop" }], usage: { prompt_tokens: -1, completion_tokens: "20", total_tokens: 2.5, completion_tokens_details: { reasoning_tokens: -2 } } },
    "[DONE]",
  );
  const events = await collect();
  assert.ok(!JSON.stringify(events).includes("FAKE LOG"));
  assert.ok(events.filter((event) => event.type === "provider_diagnostics").every((event) => !event.responseId && !event.usage));
  assert.deepEqual(events.filter((event) => event.type === "done"), [{ type: "done" }]);
}));
