import assert from "node:assert/strict";
import test from "node:test";
import facts from "../../../content/agent-public/facts.json" with { type: "json" };
import research from "../../../content/agent-public/research.json" with { type: "json" };
import { buildSystemPrompt } from "../src/persona.js";
import { buildResearchContext, factContext, planEvidenceRetrieval, retrieveFacts } from "../src/retrieval.js";
import type { PersonalFact } from "../src/types.js";

const corpus = [...facts, ...research] as PersonalFact[];
function select(query: string, limit = 20) {
  return planEvidenceRetrieval(query, corpus, limit).flatMap((lane) => retrieveFacts(query, lane.facts, lane.limit));
}

test("a claimed affiliation in the question cannot route external research into personal experience", () => {
  for (const query of ["你做过哪些 AI Roleplay 产品？", "你当时在 JanitorAI 负责什么？", "Did you work on Nomi?"]) {
    const lanes = planEvidenceRetrieval(query, corpus, 20);
    assert.deepEqual(lanes.map((lane) => lane.kind), ["personal"], query);
    assert.ok(lanes[0].facts.every((fact) => !["research", "industry_notes", "blog", "opinion"].includes(fact.recordType ?? "")), query);
  }
});

test("the expanded corpus is reachable by product aliases, technical topics and comparable metrics", () => {
  for (const [query, expected] of [
    ["Tipsy 的蓝宝石和长记忆怎么收费？", "research-tipsy"],
    ["キャラぷ的日本角色创作者有什么特色？", "research-kyarapu"],
    ["C.ai 和 CHAI 的全球移动内购怎么比较？", "research-chai-vs-characterai-iap"],
    ["酒馆的上下文长度、缓存和每轮成本怎么估算？", "research-runtime-turn-cost"],
    ["Roletopia 的预制分支怎么跟局部 AI 共演结合？", "research-roletopia"],
  ]) {
    const selected = select(query);
    assert.ok(selected.some((fact) => fact.id === expected), `${query}: ${selected.map((fact) => fact.id)}`);
    assert.ok(selected.every((fact) => fact.recordType === "research"), query);
  }
});

test("an explicit comparison budgets separate pools and labels the external prompt", () => {
  const query = "你做过的产品，与 SillyTavern 的角色创作有什么区别？";
  const plan = planEvidenceRetrieval(query, corpus, 20);
  assert.deepEqual(plan.map((lane) => lane.kind), ["personal", "research"]);
  assert.equal(plan.reduce((sum, lane) => sum + lane.limit, 0), 20);
  const selected = select(query);
  const internal = factContext(selected);
  const external = buildResearchContext(selected);
  assert.ok(external.context.some((line) => line.includes("SillyTavern")));
  assert.ok(!internal.some((line) => line.includes("SillyTavern 的创作控制")));
  assert.match(buildSystemPrompt("work", internal, "", external.context), /外部调研[\s\S]+对象：SillyTavern/);
  assert.ok([...external.sources.values()].some((source) => source.url.startsWith("https://docs.sillytavern.app/")));
  assert.ok(![...external.sources.values()].some((source) => /notion/i.test(new URL(source.url).hostname)));
});
