import assert from "node:assert/strict";
import test from "node:test";
import { normalizeDeepSeekToolCalls, parseDeepSeekWebChunk } from "../src/deepseek-web.js";

const readCall = {
  index: 0,
  id: "srvtoolu_rl_00_example",
  type: "deepseek_read_url",
  kind: "read_link",
  action: { type: "read_link", url: "https://example.com/post" },
  status: "completed",
  page: { url: "https://example.com/post", title: "Example post", published_at: null },
  signature: "opaque-webpage-signature-with-+/=",
};

test("native search progress and completed sources are decoded from choice.server_tool_event", () => {
  const call = {
    index: 0,
    id: "srvtoolu_s_00_example",
    type: "deepseek_web_search",
    kind: "search",
    action: { type: "search", queries: ["DeepSeek news"] },
  };
  assert.deepEqual(parseDeepSeekWebChunk({ choices: [{
    delta: {}, server_tool_event: { type: "call_started", step: 0, call },
  }] }), [{ type: "status", value: "searching" }]);
  assert.deepEqual(parseDeepSeekWebChunk({ choices: [{
    delta: {},
    server_tool_event: { type: "call_completed", step: 0, call: {
      ...call,
      status: "completed",
      sources: [{ type: "url", url: "https://example.com/news", title: "News", snippet: "not part of the answer" }],
    } },
  }] }), [{ type: "citation", title: "News", url: "https://example.com/news" }]);
});

test("native link reading has a distinct status and exposes the actual page source", () => {
  assert.deepEqual(parseDeepSeekWebChunk({ choices: [{
    server_tool_event: { type: "call_started", step: 0, call: readCall },
  }] }), [{ type: "status", value: "reading" }]);
  assert.deepEqual(parseDeepSeekWebChunk({ choices: [{
    server_tool_event: { type: "call_completed", step: 0, call: readCall },
  }] }), [{ type: "citation", title: "Example post", url: "https://example.com/post" }]);
});

test("final chunk can carry answer text, annotations and replay context together without losing any extension", () => {
  const serverToolCalls = [{ index: 0, reasoning_content: "", calls: [readCall], custom_field: "preserved" }];
  const events = parseDeepSeekWebChunk({ choices: [{
    finish_reason: "stop",
    delta: {
      content: "The page explains product design.",
      annotations: [{ type: "url_citation", url_citation: {
        url: "https://example.com/post#details", title: "Details", start_index: 0, end_index: 32,
      } }],
      server_tool_calls: serverToolCalls,
    },
  }] });
  assert.deepEqual(events, [
    { type: "citation", title: "Example post", url: "https://example.com/post" },
    { type: "provider_context", deepseekToolCalls: serverToolCalls },
    { type: "citation", title: "Details", url: "https://example.com/post#details" },
  ]);
  assert.equal(normalizeDeepSeekToolCalls(serverToolCalls), serverToolCalls);
  assert.equal(serverToolCalls[0].calls[0].signature, readCall.signature);
  assert.ok(events.every((event) => event.type !== "delta"));
});

test("failed native calls are observable and never exposed as successful citations", () => {
  assert.deepEqual(parseDeepSeekWebChunk({ choices: [{
    server_tool_event: { type: "call_completed", step: 0, call: {
      ...readCall, status: "failed", error: { code: "fetch_failed" },
    } },
  }] }), [{ type: "tool_error", tool: "deepseek_read_url", code: "fetch_failed" }]);
});

test("untrusted source protocols and unrelated payloads do not produce events", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,hello", "file:///etc/passwd", "not a URL"]) {
    assert.deepEqual(parseDeepSeekWebChunk({ choices: [{ delta: {
      annotations: [{ type: "url_citation", url_citation: { url, title: "invalid" } }],
    } }] }), []);
  }
  for (const payload of [null, {}, { choices: [null] }, { choices: [{ delta: { reasoning_content: "not a public reply" } }] }]) {
    assert.deepEqual(parseDeepSeekWebChunk(payload), []);
  }
});

test("native replay records are bounded and reject malformed or unsupported tool records", () => {
  assert.deepEqual(normalizeDeepSeekToolCalls([]), []);
  const validStep = { index: 0, calls: [readCall] };
  const invalid = [
    null,
    {},
    [{ ...validStep, index: -1 }],
    [{ ...validStep, index: "0" }],
    [{ index: 0, calls: {} }],
    [{ index: 0, calls: [{ ...readCall, id: "" }] }],
    [{ index: 0, calls: [{ ...readCall, type: "function" }] }],
    [{ index: 0, calls: [{ ...readCall, index: -1 }] }],
    Array.from({ length: 25 }, (_, index) => ({ ...validStep, index })),
    [{ index: 0, calls: Array.from({ length: 65 }, (_, index) => ({ ...readCall, index })) }],
    [{ index: 0, calls: [{ ...readCall, signature: "x".repeat(400_000) }] }],
  ];
  for (const value of invalid) assert.equal(normalizeDeepSeekToolCalls(value), undefined);
  const cyclic = [{ ...validStep, extra: {} as Record<string, unknown> }];
  cyclic[0].extra.self = cyclic;
  assert.equal(normalizeDeepSeekToolCalls(cyclic), undefined);
});
