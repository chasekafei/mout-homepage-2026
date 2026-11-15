import assert from "node:assert/strict";
import test from "node:test";
import facts from "../../../content/agent-public/facts.json" with { type: "json" };
import { estimateTextTokens, retrieveFacts, selectHistoryWithinBudget } from "../src/retrieval.js";
import type { ChatMessage, PersonalFact } from "../src/types.js";

const corpus = facts as PersonalFact[];

test("Chinese paraphrases retrieve the intended personal fact", () => {
  const cases = [
    ["你做过哪些 AI 产品？", "agent-work"],
    ["你做过什么产品", "agent-work"],
    ["你做过什么 AI 项目", "agent-work"],
    ["你做过哪些应用", "agent-work"],
    ["你平时做什么", "identity"],
    ["你的职业经历是什么", "identity"],
    ["AI Agent 经历", "agent-work"],
    ["Super Intern 是什么产品", "agent-work"],
    ["为什么做 CrossPod", "crosspod"],
    ["你对 Agent 有什么看法", "agent-principle"],
    ["你从什么时候开始玩游戏", "games"],
  ] as const;

  for (const [query, expectedId] of cases) {
    assert.equal(retrieveFacts(query, corpus)[0]?.id, expectedId, query);
  }
});

test("recent user turns help resolve short follow-up questions", () => {
  const retrieved = retrieveFacts(["它当时为什么做？", "你做过什么 AI 项目"], corpus);
  assert.deepEqual(retrieved.map((fact) => fact.id), ["agent-work"]);
});

test("unrelated queries and private facts do not get recalled", () => {
  assert.deepEqual(retrieveFacts("量子纠缠是什么", corpus), []);
  const privateFact: PersonalFact = {
    id: "private-test",
    title: "测试隐私经历",
    body: "这个内容不应被公开检索",
    tags: ["秘密项目"],
    keywords: ["不公开"],
    queries: ["这是我的秘密项目吗"],
    source: "private source",
    visibility: "private",
  };
  assert.deepEqual(retrieveFacts("这是我的秘密项目吗", [privateFact]), []);
});

test("curated keywords and natural question aliases make a new fact easy to recall", () => {
  const fact: PersonalFact = {
    id: "prototype-project",
    title: "原型项目",
    body: "MouT 做了一个轻量实验。",
    tags: ["设计"],
    keywords: ["语音日记", "声音记录"],
    queries: ["你做过语音日记产品吗"],
    source: "new note",
    visibility: "public",
  };
  assert.equal(retrieveFacts("有没有做过声音记录工具", [fact])[0]?.id, fact.id);
});

test("history selection keeps newest complete turns within the estimate budget", () => {
  const history: ChatMessage[] = [];
  for (let index = 0; index < 5; index += 1) {
    history.push({ role: "user", content: `问题 ${index}` }, { role: "assistant", content: `回答 ${index}` });
  }
  const lastTurn = history.slice(-2);
  const budget = lastTurn.reduce((total, message) => total + estimateTextTokens(message.content) + 8, 0);
  assert.deepEqual(selectHistoryWithinBudget(history, budget).map((message) => message.content), ["问题 4", "回答 4"]);
});
