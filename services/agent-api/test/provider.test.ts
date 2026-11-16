import assert from "node:assert/strict";
import test from "node:test";
import type { ProviderRequest } from "@mout/agent-core";
import { config } from "../src/config.js";
import { streamProvider } from "../src/provider.js";

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
    assert.match(events[0]?.message ?? "", /响应头超时/);
  } finally {
    globalThis.fetch = originalFetch;
    config.gptproto.apiKey = originalKey;
    config.upstreamHeaderTimeoutMs = originalHeaderTimeout;
    config.upstreamStreamTimeoutMs = originalTotalTimeout;
  }
});
