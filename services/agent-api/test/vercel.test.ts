import assert from "node:assert/strict";
import test from "node:test";
import type { ProviderRequest } from "@mout/agent-core";
import { VERCEL_MODEL_IDS, vercelModelId, vercelRequestBody } from "../src/vercel.js";

test("UI model IDs map to the exact official Gateway namespace and version", () => {
  const expected = [
    ["gemini-3.8-flash", "google/gemini-3.8-flash"],
    ["gemini-4-hydrogen", "google/gemini-4-hydrogen"],
    ["gemini-4-argon", "google/gemini-4-argon"],
    ["gpt-6.1-sol", "openai/gpt-6.1-sol"],
    ["claude-sonnet-5-5", "anthropic/claude-sonnet-5.5"],
    ["claude-fable-5-2", "anthropic/claude-fable-5.2"],
  ];
  assert.equal(Object.keys(VERCEL_MODEL_IDS).length, expected.length);
  for (const [id, gatewayId] of expected) assert.equal(vercelModelId(id), gatewayId);
});

test("DeepSeek and unrecognized IDs fail instead of silently switching to a similar model", () => {
  for (const model of ["deepseek-v4-pro", "deepseek-flash", "gemini-4", "google/gemini-4-hydrogen", "toString", "__proto__"]) {
    assert.throws(() => vercelModelId(model), /Vercel AI Gateway 未配置模型 ID/);
    assert.throws(() => vercelRequestBody({
      model, messages: [{ role: "user", content: "你好" }], stream: true, useWebSearch: false,
    }), /Vercel AI Gateway 未配置模型 ID/);
  }
});

test("Gateway requests preserve full conversation text and strip supplier-native tool context", () => {
  const request: ProviderRequest = {
    model: "gemini-4-hydrogen",
    messages: [
      { role: "system", content: "人设与个人记忆：\n我是 MouT。" },
      { role: "developer", content: "外部搜索资料：标题、日期和来源。" },
      { role: "user", content: "  你好，我叫测试者。\n" },
      { role: "assistant", content: "你好，测试者。", deepseekToolCalls: [{
        index: 0, calls: [{ type: "deepseek_read_url", signature: "deepseek-opaque-signature" }],
      }] },
      { role: "user", content: "你还记得我叫什么吗？" },
    ],
    stream: true,
    useWebSearch: true,
    useReadUrl: true,
  };
  const original = JSON.stringify(request);
  const body = vercelRequestBody(request);
  assert.deepEqual(body, {
    model: "google/gemini-4-hydrogen",
    messages: [
      { role: "system", content: "人设与个人记忆：\n我是 MouT。" },
      { role: "developer", content: "外部搜索资料：标题、日期和来源。" },
      { role: "user", content: "  你好，我叫测试者。\n" },
      { role: "assistant", content: "你好，测试者。" },
      { role: "user", content: "你还记得我叫什么吗？" },
    ],
    stream: true,
  });
  assert.ok(!JSON.stringify(body).includes("deepseek-opaque-signature"));
  assert.equal(JSON.stringify(request), original);
});
