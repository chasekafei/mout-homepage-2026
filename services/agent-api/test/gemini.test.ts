import assert from "node:assert/strict";
import test from "node:test";
import type { ProviderRequest } from "@mout/agent-core";
import { geminiRequestBody, geminiStreamUrl, parseGeminiChunk, usesNativeGemini } from "../src/gemini.js";
import { config } from "../src/config.js";

const request = (overrides: Partial<ProviderRequest> = {}): ProviderRequest => ({
  model: "gemini-4-hydrogen",
  messages: [{ role: "user", content: "你好" }],
  stream: true,
  useWebSearch: false,
  ...overrides,
});

test("native Gemini model routes normalize the API suffix without losing a gateway prefix", () => {
  for (const suffix of ["", "/", "/v1", "/v1/", "/v1beta", "/v1beta/"]) {
    assert.equal(
      geminiStreamUrl(`https://example.test/gateway${suffix}`, "gemini-4-argon"),
      "https://example.test/gateway/v1beta/models/gemini-4-argon:streamGenerateContent?alt=sse",
    );
  }
  assert.ok(usesNativeGemini("gemini-4-hydrogen"));
  assert.ok(usesNativeGemini("gemini-4-argon"));
  assert.ok(!usesNativeGemini("gemini-3.8-flash"));
  assert.ok(!usesNativeGemini("claude-fable-5-2"));
});

test("native requests preserve system instructions and complete multi-turn text while excluding provider-specific history", () => {
  const body = geminiRequestBody(request({ messages: [
    { role: "system", content: "用第一人称，像朋友一样交流。" },
    { role: "developer", content: "个人记忆：\n我做过 Super Intern。" },
    { role: "user", content: "你可以叫我测试者。" },
    { role: "assistant", content: "你好，测试者。", deepseekToolCalls: [{
      index: 0, calls: [{ type: "deepseek_read_url", signature: "opaque-deepseek-signature" }],
    }] },
    { role: "assistant", content: " \n " },
    { role: "user", content: "你还记得我叫什么吗？\n请简单回答。" },
  ] }));
  assert.deepEqual(body, {
    systemInstruction: { parts: [{ text: "用第一人称，像朋友一样交流。\n\n个人记忆：\n我做过 Super Intern。" }] },
    contents: [
      { role: "user", parts: [{ text: "你可以叫我测试者。" }] },
      { role: "model", parts: [{ text: "你好，测试者。" }] },
      { role: "user", parts: [{ text: "你还记得我叫什么吗？\n请简单回答。" }] },
    ],
    generationConfig: { thinkingConfig: { thinkingLevel: config.geminiThinkingLevel } },
  });
  assert.ok(!JSON.stringify(body).includes("opaque-deepseek-signature"));
});

test("requests without conversational contents fail before sending an invalid upstream body", () => {
  assert.throws(() => geminiRequestBody(request({ messages: [
    { role: "system", content: "系统说明。" }, { role: "user", content: " \n " },
  ] })), /没有可发送的对话内容/);
});

test("search and URL reading use native tool declarations only when requested", () => {
  assert.ok(!("tools" in geminiRequestBody(request())));
  assert.deepEqual(geminiRequestBody(request({ useWebSearch: true })).tools, [{ google_search: {} }]);
  assert.deepEqual(geminiRequestBody(request({ useReadUrl: true })).tools, [{ url_context: {} }]);
  assert.deepEqual(geminiRequestBody(request({ useWebSearch: true, useReadUrl: true })).tools, [
    { google_search: {} }, { url_context: {} },
  ]);
});

test("native chunks expose final text without thought parts and retain safe grounding sources and usage", () => {
  assert.deepEqual(parseGeminiChunk({
    candidates: [{
      content: { parts: [
        { text: "内部推理不应该展示。", thought: true },
        { text: "你好，" }, { text: "很高兴认识你。", thought: false },
      ] },
      groundingMetadata: { groundingChunks: [
        { web: { uri: "https://example.com/article", title: "文章" } },
        { retrievedContext: { uri: "http://example.com/reference" } },
        { web: { uri: "javascript:alert(1)", title: "不安全链接" } },
        { web: { uri: "not a URL" } },
      ] },
      finishReason: "STOP",
    }],
    usageMetadata: { promptTokenCount: 20, candidatesTokenCount: 7, totalTokenCount: 27 },
  }), [
    { type: "delta", text: "你好，" },
    { type: "delta", text: "很高兴认识你。" },
    { type: "citation", title: "文章", url: "https://example.com/article" },
    { type: "citation", title: "http://example.com/reference", url: "http://example.com/reference" },
    { type: "search_evidence", metadataPresent: true, queries: [], sourceUrls: ["https://example.com/article"], supportCount: 0, hasSearchEntryPoint: false },
    { type: "done", usage: { promptTokens: 20, completionTokens: 7, totalTokens: 27 } },
  ]);
});

test("upstream failures, blocked replies and incomplete generation never produce successful completion", () => {
  const cases = [
    { error: { code: 400, message: "contents is not specified" } },
    { promptFeedback: { blockReason: "SAFETY" }, candidates: [{ content: { parts: [{ text: "blocked text" }] } }] },
    { candidates: [{ content: { parts: [{ text: "blocked text" }] }, finishReason: "SAFETY" }] },
    { candidates: [{ content: { parts: [{ text: "未完成的正文" }] }, finishReason: "MAX_TOKENS" }] },
    { candidates: [{ finishReason: "MALFORMED_FUNCTION_CALL" }] },
  ];
  for (const payload of cases) {
    const events = parseGeminiChunk(payload);
    assert.ok(events.some((event) => event.type === "error"), JSON.stringify(payload));
    assert.ok(events.every((event) => event.type !== "done"), JSON.stringify(payload));
  }
  assert.deepEqual(parseGeminiChunk(cases[0]), [{ type: "error", message: "contents is not specified", status: 400, code: "upstream_stream_error", retryable: false }]);
  assert.ok(!parseGeminiChunk(cases[1]).some((event) => event.type === "delta"));
  assert.ok(!parseGeminiChunk(cases[2]).some((event) => event.type === "delta"));
  assert.ok(parseGeminiChunk(cases[3]).some((event) => event.type === "delta" && event.text === "未完成的正文"));
});

test("native array payloads preserve chunk order and empty provider frames stay silent", () => {
  assert.deepEqual(parseGeminiChunk([
    { candidates: [{ content: { parts: [{ text: "第一段" }] } }] },
    { candidates: [{ content: { parts: [{ text: "第二段" }] }, finishReason: "STOP" }] },
  ]), [{ type: "delta", text: "第一段" }, { type: "delta", text: "第二段" }, { type: "done" }]);
  for (const payload of [null, {}, { candidates: [] }, { candidates: [{}] }]) {
    assert.deepEqual(parseGeminiChunk(payload), []);
  }
});

test("grounding evidence distinguishes omitted metadata, empty metadata, partial sources and generic tool usage", () => {
  assert.deepEqual(parseGeminiChunk({ candidates: [{}] }), []);
  assert.deepEqual(parseGeminiChunk({ candidates: [{ groundingMetadata: {} }] }), [{
    type: "search_evidence", metadataPresent: true, queries: [], sourceUrls: [], supportCount: 0, hasSearchEntryPoint: false,
  }]);
  assert.deepEqual(parseGeminiChunk({ candidates: [], usageMetadata: { toolUsePromptTokenCount: 12 } }), [{
    type: "search_evidence", metadataPresent: false, queries: [], sourceUrls: [], supportCount: 0, hasSearchEntryPoint: false, toolUsePromptTokens: 12,
  }]);
  const events = parseGeminiChunk({ candidates: [{ groundingMetadata: {
    webSearchQueries: ["AI releases today", "", null],
    groundingChunks: [{ web: { uri: "https://example.com/news" } }],
    groundingSupports: [{ groundingChunkIndices: [0] }], searchEntryPoint: { renderedContent: "search" },
  } }] });
  assert.ok(events.some((event) => event.type === "search_evidence" && event.queries.length === 1
    && event.sourceUrls[0] === "https://example.com/news" && event.supportCount === 1 && event.hasSearchEntryPoint));
});
