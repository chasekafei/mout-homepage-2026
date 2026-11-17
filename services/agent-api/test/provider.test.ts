import assert from "node:assert/strict";
import test from "node:test";
import type { ProviderRequest } from "@mout/agent-core";
import { config } from "../src/config.js";
import { providerModel, streamProvider } from "../src/provider.js";

test("provider reports a response-header timeout separately", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = config.gptproto.apiKey;
  const originalHeaderTimeout = config.upstreamHeaderTimeoutMs;
  const originalTotalTimeout = config.upstreamStreamTimeoutMs;
  config.gptproto.apiKey = "test-key";
  config.upstreamHeaderTimeoutMs = 5;
  config.upstreamStreamTimeoutMs = 100;
  globalThis.fetch = async (_input, init) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
  });
  const request: ProviderRequest = {
    messages: [{ role: "user", content: "hello" }],
    model: "gemini-3.8-flash",
    stream: true,
    useWebSearch: false,
  };
  try {
    const events = [];
    for await (const event of streamProvider("gptproto", request)) events.push(event);
    assert.equal(events.length, 1);
    assert.equal(events[0]?.type, "error");
    assert.ok(events[0]?.type === "error");
    assert.match(events[0].message, /响应头超时/);
  } finally {
    globalThis.fetch = originalFetch;
    config.gptproto.apiKey = originalKey;
    config.upstreamHeaderTimeoutMs = originalHeaderTimeout;
    config.upstreamStreamTimeoutMs = originalTotalTimeout;
  }
});

test("DeepSeek V4 Pro uses the official endpoint and streams final answers without reasoning or a false search status", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = config.deepseek.apiKey;
  const originalBaseUrl = config.deepseek.baseUrl;
  config.deepseek.apiKey = "test-deepseek-key";
  config.deepseek.baseUrl = "https://api.deepseek.com/v1/";
  const messages: ProviderRequest["messages"] = [
    { role: "system", content: "你是个人分身，使用第一人称回答。" },
    { role: "user", content: "我叫测试者" },
    { role: "assistant", content: "你好，测试者。" },
    { role: "user", content: "你还记得我叫什么吗？" },
  ];
  globalThis.fetch = async (input, init) => {
    assert.equal(String(input), "https://api.deepseek.com/v1/chat/completions");
    assert.equal(new Headers(init?.headers).get("Authorization"), "Bearer test-deepseek-key");
    assert.deepEqual(JSON.parse(String(init?.body)), {
      model: "deepseek-v4-pro",
      messages,
      stream: true,
      thinking: { type: "disabled" },
    });
    return new Response([
      'data: {"choices":[{"delta":{"reasoning_content":"内部思考不展示"}}]}',
      'data: {"choices":[{"delta":{"content":"你叫测试者。"}}]}',
      'data: [DONE]',
    ].join("\n\n") + "\n\n", { headers: { "Content-Type": "text/event-stream" } });
  };
  try {
    const events = [];
    for await (const event of streamProvider("deepseek", {
      messages, model: "deepseek-v4-pro", stream: true, useWebSearch: false,
    })) events.push(event);
    assert.deepEqual(events, [
      { type: "status", value: "answering", provider: "deepseek", model: "deepseek-v4-pro" },
      { type: "delta", text: "你叫测试者。" },
      { type: "done" },
    ]);
    assert.equal(providerModel("deepseek"), config.deepseek.model);
  } finally {
    globalThis.fetch = originalFetch;
    config.deepseek.apiKey = originalKey;
    config.deepseek.baseUrl = originalBaseUrl;
  }
});

test("DeepSeek native search and link reading stream sources and replay signed pages on follow-ups", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = config.deepseek.apiKey;
  config.deepseek.apiKey = "test-deepseek-key";
  const call = {
    index: 0, id: "srvtoolu_rl_example", type: "deepseek_read_url", kind: "read_link",
    action: { type: "read_link", url: "https://example.com/post" }, status: "completed",
    page: { url: "https://example.com/post", title: "Example post" }, signature: "opaque-page-signature",
  };
  const context = [{ index: 0, calls: [call] }];
  let requestCount = 0;
  globalThis.fetch = async (_input, init) => {
    requestCount += 1;
    const body = JSON.parse(String(init?.body));
    assert.equal(body.model, "deepseek-flash");
    assert.deepEqual(body.thinking, { type: "disabled" });
    assert.deepEqual(body.tools, [{ type: "deepseek_web_search" }, { type: "deepseek_read_url" }]);
    assert.equal(body.tool_choice, undefined);
    assert.equal(body.web_search_options, undefined);
    if (requestCount === 2) assert.deepEqual(body.messages[2].server_tool_calls, context);
    const chunks = requestCount === 1 ? [
      { choices: [{ delta: {}, server_tool_event: { type: "call_started", step: 0, call } }] },
      { choices: [{ delta: {}, server_tool_event: { type: "call_completed", step: 0, call } }] },
      { choices: [{ delta: {
        content: "这篇文章谈产品设计。", server_tool_calls: context,
        annotations: [{ type: "url_citation", url_citation: { url: call.page.url, title: call.page.title } }],
      }, finish_reason: "stop" }] },
    ] : [{ choices: [{ delta: { content: "文章第一段谈的是用户的实际场景。" } }] }];
    // Split in the middle of a multibyte character/SSE block to exercise framing.
    const bytes = new TextEncoder().encode(chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`).join("") + "data: [DONE]\n\n");
    return new Response(new ReadableStream({ start(controller) {
      for (let i = 0; i < bytes.length; i += 17) controller.enqueue(bytes.slice(i, i + 17));
      controller.close();
    } }));
  };
  try {
    const messages: ProviderRequest["messages"] = [
      { role: "system", content: "我用第一人称聊天，以个人记忆为准。" },
      { role: "user", content: "总结 https://example.com/post" },
    ];
    const model = providerModel("deepseek", "deepseek-v4-pro", { useReadUrl: true });
    assert.equal(model, "deepseek-flash");
    assert.equal(providerModel("deepseek", "deepseek-v4-pro", { useWebSearch: true }), "deepseek-flash");
    assert.equal(providerModel("deepseek", "deepseek-v4-pro"), "deepseek-v4-pro");
    const events = [];
    for await (const event of streamProvider("deepseek", { messages, model, stream: true, useWebSearch: false, useReadUrl: true })) events.push(event);
    assert.deepEqual(events.filter((event) => event.type === "citation"), [{ type: "citation", title: call.page.title, url: call.page.url }]);
    assert.ok(events.some((event) => event.type === "status" && event.value === "reading"));
    assert.deepEqual(events.filter((event) => event.type === "delta"), [{ type: "delta", text: "这篇文章谈产品设计。" }]);
    const replay = events.find((event) => event.type === "provider_context");
    assert.ok(replay?.type === "provider_context");
    assert.deepEqual(replay.deepseekToolCalls, context);
    const history: ProviderRequest["messages"] = [...messages,
      { role: "assistant", content: "这篇文章谈产品设计。", deepseekToolCalls: replay.deepseekToolCalls },
    ];
    const followUpModel = providerModel("deepseek", "deepseek-v4-pro", { history });
    assert.equal(followUpModel, "deepseek-flash");
    const followUp = [];
    for await (const event of streamProvider("deepseek", {
      messages: [...history, { role: "user", content: "再解释第一段" }], model: followUpModel, stream: true, useWebSearch: false,
    })) followUp.push(event);
    assert.ok(followUp.some((event) => event.type === "delta" && event.text.includes("第一段")));
    assert.equal(requestCount, 2);
  } finally {
    globalThis.fetch = originalFetch;
    config.deepseek.apiKey = originalKey;
  }
});

test("GPTProto requests never receive DeepSeek-native context", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = config.gptproto.apiKey;
  config.gptproto.apiKey = "test-key";
  globalThis.fetch = async (_input, init) => {
    const body = JSON.parse(String(init?.body));
    assert.ok(body.messages.every((message: Record<string, unknown>) => !message.server_tool_calls && !message.deepseekToolCalls));
    return new Response('data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n');
  };
  try {
    const events = [];
    for await (const event of streamProvider("gptproto", {
      messages: [{ role: "assistant", content: "旧回答", deepseekToolCalls: [{ index: 0, calls: [] }] }, { role: "user", content: "hello" }],
      model: "gemini-3.8-flash", stream: true, useWebSearch: false,
    })) events.push(event);
    assert.ok(events.some((event) => event.type === "delta" && event.text === "hello"));
  } finally {
    globalThis.fetch = originalFetch;
    config.gptproto.apiKey = originalKey;
  }
});
