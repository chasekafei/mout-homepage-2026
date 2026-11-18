import assert from "node:assert/strict";
import test from "node:test";
import type { AgentProviderPreference, ProviderEvent } from "@mout/agent-core";
import { config } from "../src/config.js";
import { streamProvider, type ProviderCall } from "../src/provider.js";

const encoder = new TextEncoder();
const request = (overrides: Partial<ProviderCall> = {}): ProviderCall => ({
  model: "gpt-6.1-sol",
  messages: [
    { role: "system", content: "使用第一人称，像朋友一样聊天。" },
    { role: "user", content: "我叫测试者。" },
    { role: "assistant", content: "你好，测试者。" },
    { role: "user", content: "你还记得我叫什么吗？" },
  ],
  stream: true,
  useWebSearch: false,
  ...overrides,
});

function sse(...payloads: unknown[]): Response {
  return new Response(payloads.map((payload) => `data: ${typeof payload === "string" ? payload : JSON.stringify(payload)}\n\n`).join(""), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

const answer = (text = "你好，测试者。") => sse({ choices: [{ delta: { content: text } }] }, "[DONE]");
const visibleText = (events: ProviderEvent[]) => events.filter((event) => event.type === "delta").map((event) => event.text).join("");

async function collect(preference: AgentProviderPreference = "auto", input = request()) {
  const events: ProviderEvent[] = [];
  for await (const event of streamProvider(preference, input)) events.push(event);
  return events;
}

async function fixture(run: () => Promise<void>) {
  const saved = {
    fetch: globalThis.fetch,
    vercel: { ...config.vercel },
    gptproto: { ...config.gptproto },
    deepseek: { ...config.deepseek },
    providerOrder: config.providerOrder,
    firstTokenTimeout: config.providerFirstTokenTimeoutMs,
    headerTimeout: config.upstreamHeaderTimeoutMs,
    streamTimeout: config.upstreamStreamTimeoutMs,
    idleTimeout: config.upstreamStreamIdleTimeoutMs,
  };
  Object.assign(config.vercel, { apiKey: "vercel-test-key", baseUrl: "https://vercel.test/v1" });
  Object.assign(config.gptproto, { apiKey: "gptproto-test-key", baseUrl: "https://gptproto.test/v1" });
  Object.assign(config.deepseek, { apiKey: "deepseek-test-key", baseUrl: "https://api.deepseek.com/v1" });
  config.providerOrder = ["vercel", "gptproto"];
  config.providerFirstTokenTimeoutMs = 500;
  config.upstreamHeaderTimeoutMs = 1_000;
  config.upstreamStreamTimeoutMs = 1_000;
  config.upstreamStreamIdleTimeoutMs = 500;
  try {
    await run();
  } finally {
    globalThis.fetch = saved.fetch;
    Object.assign(config.vercel, saved.vercel);
    Object.assign(config.gptproto, saved.gptproto);
    Object.assign(config.deepseek, saved.deepseek);
    config.providerOrder = saved.providerOrder;
    config.providerFirstTokenTimeoutMs = saved.firstTokenTimeout;
    config.upstreamHeaderTimeoutMs = saved.headerTimeout;
    config.upstreamStreamTimeoutMs = saved.streamTimeout;
    config.upstreamStreamIdleTimeoutMs = saved.idleTimeout;
  }
}

for (const failure of ["overloaded", "network"] as const) {
  test(`auto switches from Vercel ${failure} to GPTProto without changing the chosen model or history`, { timeout: 2_000 }, async () => fixture(async () => {
    const calls: Array<{ host: string; body: any }> = [];
    const input = request();
    globalThis.fetch = async (url, init) => {
      calls.push({ host: new URL(String(url)).host, body: JSON.parse(String(init?.body)) });
      if (calls.length === 1) {
        if (failure === "network") throw new TypeError("connection reset");
        return new Response("overloaded", { status: 429 });
      }
      return answer();
    };
    const events = await collect("auto", input);
    assert.deepEqual(calls.map(({ host, body }) => ({ host, model: body.model })), [
      { host: "vercel.test", model: "openai/gpt-6.1-sol" },
      { host: "gptproto.test", model: "gpt-6.1-sol" },
    ]);
    assert.deepEqual(calls[0].body.messages, input.messages);
    assert.deepEqual(calls[1].body.messages, input.messages);
    assert.equal(visibleText(events), "你好，测试者。");
    assert.equal(events.filter((event) => event.type === "done").length, 1);
    assert.equal(events.filter((event) => event.type === "provider_fallback").length, 1);
    assert.ok(!events.some((event) => event.type === "error"));
  }));
}

test("an explicit GPTProto preference can fail over to the exact Vercel wire model", async () => fixture(async () => {
  const calls: Array<{ host: string; model: string }> = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ host: new URL(String(url)).host, model: JSON.parse(String(init?.body)).model });
    return calls.length === 1 ? new Response("temporarily unavailable", { status: 503 }) : answer("备用供应商正常。" );
  };
  const events = await collect("gptproto");
  assert.deepEqual(calls, [
    { host: "gptproto.test", model: "gpt-6.1-sol" },
    { host: "vercel.test", model: "openai/gpt-6.1-sol" },
  ]);
  assert.equal(visibleText(events), "备用供应商正常。");
  assert.ok(!events.some((event) => event.type === "error"));
}));

test("a stream failure after visible text never replays the reply through another supplier", async () => fixture(async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    let sent = false;
    return new Response(new ReadableStream({ pull(controller) {
      if (!sent) {
        sent = true;
        controller.enqueue(encoder.encode('data: {"choices":[{"delta":{"content":"已经显示的正文。"}}]}\n\n'));
      } else controller.error(new TypeError("connection reset after visible text"));
    } }));
  };
  const events = await collect();
  assert.equal(visibleText(events), "已经显示的正文。");
  assert.equal(calls, 1);
  assert.equal(events.filter((event) => event.type === "error").length, 1);
  assert.ok(!events.some((event) => event.type === "provider_fallback" || event.type === "done"));
}));

const emptyReplies: Array<{ name: string; response: () => Response }> = [
  { name: "empty HTTP 200 body", response: () => new Response("") },
  { name: "whitespace without visible text", response: () => sse({ choices: [{ delta: { content: "  \n" } }] }, "[DONE]") },
  { name: "reasoning without visible text", response: () => sse({ choices: [{ delta: { reasoning_content: "内部推理不应展示" } }] }, "[DONE]") },
  { name: "citation followed by DONE without text", response: () => sse({ annotation: { url: "https://failed.example/source", title: "失败供应商的来源" } }, "[DONE]") },
  { name: "citation followed by a retryable stream error", response: () => sse(
    { annotation: { url: "https://failed.example/source", title: "失败供应商的来源" } },
    { error: { type: "server_error", message: "generation failed" } },
  ) },
];

for (const scenario of emptyReplies) {
  test(`${scenario.name} cannot leak metadata or completion from a failed attempt`, async () => fixture(async () => {
    let calls = 0;
    globalThis.fetch = async () => ++calls === 1 ? scenario.response() : answer("这份正文只显示一次。" );
    const events = await collect();
    assert.equal(calls, 2);
    assert.equal(visibleText(events), "这份正文只显示一次。");
    assert.equal(events.filter((event) => event.type === "done").length, 1);
    assert.ok(!events.some((event) => event.type === "citation" || event.type === "error"));
  }));
}

test("the first-text deadline still expires while the supplier emits heartbeats and statuses", { timeout: 2_000 }, async () => fixture(async () => {
  config.providerFirstTokenTimeoutMs = 15;
  let calls = 0;
  let aborted = 0;
  globalThis.fetch = async (_url, init) => {
    calls += 1;
    if (calls === 2) return answer("首字超时后成功切换。" );
    return new Response(new ReadableStream({ start(controller) {
      controller.enqueue(encoder.encode(': heartbeat\n\ndata: {"type":"response.web_search_call.searching"}\n\n'));
      const timer = setInterval(() => controller.enqueue(encoder.encode(": heartbeat\n\n")), 2);
      init?.signal?.addEventListener("abort", () => {
        aborted += 1;
        clearInterval(timer);
        controller.error(init.signal?.reason ?? new DOMException("aborted", "AbortError"));
      }, { once: true });
    } }));
  };
  const events = await collect();
  assert.equal(calls, 2);
  assert.equal(aborted, 1);
  assert.equal(visibleText(events), "首字超时后成功切换。");
  assert.ok(events.some((event) => event.type === "provider_fallback" && event.code === "first_token_timeout"));
  assert.ok(!events.some((event) => event.type === "error"));
}));

for (const status of [400, 401]) {
  test(`terminal HTTP ${status} does not use another supplier`, async () => fixture(async () => {
    let calls = 0;
    globalThis.fetch = async () => { calls += 1; return new Response("invalid request or credentials", { status }); };
    const events = await collect();
    assert.equal(calls, 1);
    const errors = events.filter((event) => event.type === "error");
    assert.equal(errors.length, 1);
    assert.equal(errors[0].status, status);
    assert.equal(errors[0].retryable, false);
    assert.ok(!events.some((event) => event.type === "provider_fallback" || event.type === "done"));
  }));
}

test("two unsuccessful suppliers end with one error and no false completion", async () => fixture(async () => {
  let calls = 0;
  globalThis.fetch = async () => new Response("unavailable", { status: ++calls === 1 ? 429 : 503 });
  const events = await collect();
  assert.equal(calls, 2);
  const errors = events.filter((event) => event.type === "error");
  assert.equal(errors.length, 1);
  assert.equal(errors[0].status, 503);
  assert.equal(events.filter((event) => event.type === "provider_fallback").length, 1);
  assert.ok(!events.some((event) => event.type === "done" || event.type === "delta"));
}));

test("an explicit upstream refusal is terminal rather than an empty-response failover", async () => fixture(async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return sse({ choices: [{ delta: {}, finish_reason: "content_filter" }] }, "[DONE]");
  };
  const events = await collect();
  assert.equal(calls, 1);
  assert.ok(events.some((event) => event.type === "error" && event.code === "provider_refusal" && !event.retryable));
  assert.ok(!events.some((event) => event.type === "provider_fallback"));
}));

test("DeepSeek stays on its official endpoint for both auto and explicit routing", async () => fixture(async () => {
  const calls: Array<{ url: string; model: string }> = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), model: JSON.parse(String(init?.body)).model });
    return answer("官方 DeepSeek 回复。" );
  };
  for (const preference of ["auto", "deepseek"] as const) {
    const events = await collect(preference, request({ model: "deepseek-v4-pro" }));
    assert.equal(visibleText(events), "官方 DeepSeek 回复。");
    assert.ok(!events.some((event) => event.type === "provider_fallback"));
  }
  assert.deepEqual(calls, Array.from({ length: 2 }, () => ({ url: "https://api.deepseek.com/v1/chat/completions", model: "deepseek-v4-pro" })));
}));

test("client cancellation aborts the in-flight supplier without opening a backup request", { timeout: 2_000 }, async () => fixture(async () => {
  const client = new AbortController();
  let calls = 0;
  globalThis.fetch = async (_url, init) => new Promise<Response>((_resolve, reject) => {
    calls += 1;
    init?.signal?.addEventListener("abort", () => reject(init.signal?.reason ?? new DOMException("aborted", "AbortError")), { once: true });
    queueMicrotask(() => client.abort());
  });
  const events = await collect("auto", request({ signal: client.signal }));
  assert.equal(calls, 1);
  assert.ok(!events.some((event) => event.type === "provider_fallback" || event.type === "delta" || event.type === "done"));
  const cancelledEvents = await collect("auto", request({ signal: client.signal }));
  assert.deepEqual(cancelledEvents, []);
  assert.equal(calls, 1);
}));
