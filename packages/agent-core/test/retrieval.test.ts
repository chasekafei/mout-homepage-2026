import assert from "node:assert/strict";
import test from "node:test";
import facts from "../../../content/agent-public/facts.json" with { type: "json" };
import blogs from "../../../content/agent-public/blog.json" with { type: "json" };
import resumes from "../../../content/agent-public/resume-source.json" with { type: "json" };
import oralHistory from "../../../content/agent-public/oral-history.json" with { type: "json" };
import semanticEval from "./semantic-retrieval-eval.json" with { type: "json" };
import { buildSystemPrompt } from "../src/persona.js";
import { fallbackResumeQuote, hasVerbatimResumeQuote } from "../src/resume-quotes.js";
import { estimateTextTokens, factContext, rankFactsHybrid, retrieveFacts, selectHistoryWithinBudget } from "../src/retrieval.js";
import type { ChatMessage, PersonalFact } from "../src/types.js";

const corpus = [...facts, ...blogs, ...resumes, ...oralHistory] as PersonalFact[];

test("Chinese paraphrases retrieve the intended personal fact", () => {
  const cases = [
    ["你平时做什么", "identity"],
    ["你的职业经历是什么", "identity"],
    ["Super Intern 是什么产品", "super-intern"],
    ["为什么做 CrossPod", "crosspod"],
    ["你对 Agent 有什么看法", "product-principle-context"],
  ] as const;

  for (const [query, expectedId] of cases) {
    assert.ok(retrieveFacts(query, corpus).some((fact) => fact.id === expectedId), query);
  }

  for (const query of ["你做过什么产品", "你做过哪些 AI 产品？", "你做过什么 AI 项目", "你做过哪些应用", "AI Agent 经历", "你从什么时候开始玩游戏"]) {
    assert.ok(retrieveFacts(query, corpus).some((fact) => fact.recordType === "resume_source" || fact.recordType === "oral_history"), query);
  }
});

test("latest resume dates win without guessing current employment", () => {
  const timeline = corpus.find((fact) => fact.id === "career-timeline");
  const identity = corpus.find((fact) => fact.id === "identity");
  assert.ok(timeline?.body.includes("广州灵创产品合伙人（2018.07–2021.07）"));
  assert.ok(identity?.body.includes("资料没有说明 2026 年 4 月之后的任职状态"));
  const latestJob = retrieveFacts("你最近一份工作是什么", corpus);
  assert.ok(latestJob.some((fact) => fact.id === "ammo-role"));
  assert.ok(latestJob.some((fact) => fact.recordType === "resume_source" && fact.sourceVersion === "2026"));
});

test("recent user turns help resolve short follow-up questions", () => {
  const retrieved = retrieveFacts(["它当时为什么做？", "你做过什么 AI 项目"], corpus);
  assert.ok(retrieved.some((fact) => fact.recordType === "oral_history" || fact.recordType === "resume_source"));
});

test("semantic eval cases reference existing corpus records and fusion surfaces semantic matches", () => {
  for (const sample of semanticEval) {
    const exists = (sample.expectedIds ?? []).some((id) => corpus.some((fact) => fact.id === id))
      || (sample.expectedGroupIds ?? []).some((groupId) => corpus.some((fact) => fact.groupId === groupId));
    assert.ok(exists, sample.query);
  }

  const query = "AI 写小说时怎样让角色设定和伏笔前后保持一致";
  const semanticScores = [
    { id: "find-muse", score: 0.82 },
    { id: "resume-2026-html-20", score: 0.78 },
    { id: "fakers", score: 0.31 },
  ];
  const hybridRanked = rankFactsHybrid(query, corpus, semanticScores);
  assert.ok(["find-muse", "oral-history-001-个人网站资料-我的个人经历-108"].includes(hybridRanked[0]?.fact.id ?? ""));
  assert.ok(retrieveFacts(query, corpus, 8, semanticScores).some((fact) => fact.id === "find-muse"));

  const exactLexical = rankFactsHybrid("Super Intern 是什么产品", corpus, [
    { id: "crosspod", score: 0.99 },
  ]);
  assert.ok(["super-intern", "resume-2026-html-03"].includes(exactLexical[0]?.fact.id ?? ""));
  assert.ok(!rankFactsHybrid(query, corpus, [{ id: "private-test", score: 0.99 }]).some(({ fact }) => fact.id === "private-test"));
});

test("oral-history retrieval uses and exposes the original source passage", () => {
  const source = oralHistory.find((fact) => fact.body.includes("老板需要我跟着一起去给客户解答问题"));
  assert.ok(source);
  assert.equal(source.recordType, "oral_history");
  assert.ok(source.body.includes("客户"));
  assert.ok(factContext([source]).join("\n").includes(source.body));
  assert.match(factContext([source]).join("\n"), /记忆·我的经历·原话/);
  assert.equal(retrieveFacts("政府客户需要什么、我们能做到什么程度", corpus).some((fact) => fact.id === source.id), true);
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

test("detailed project queries retrieve the specific project fact", () => {
  const cases = [
    ["Super Intern 有多少付费团队", "super-intern-results"],
    ["TIYA 的有效互动提升多少", "tiya-product"],
    ["热情小美的直播有多少弹幕", "xiaomei-vtuber"],
    ["Fakers 是什么产品", "resume-2026-html-04"],
    ["Ammonad 是什么", "ammonad"],
  ] as const;
  for (const [query, expectedId] of cases) {
    assert.ok(retrieveFacts(query, corpus).some((fact) => fact.id === expectedId), query);
  }
  assert.ok(retrieveFacts("你为什么做个人 Agent", corpus).some((fact) => fact.recordType === "oral_history"));
});

test("resume-backed answers retrieve exact excerpts and keep the 2026 wording", () => {
  const skillQuestion = retrieveFacts("Super Intern 用户创建了多少 Skill", corpus);
  const original = skillQuestion.find((fact) => fact.recordType === "resume_source" && fact.sourceVersion === "2026");
  assert.ok(original);
  assert.equal(original.sourceFormat, "html");
  assert.ok((original.page ?? 0) > 0);
  assert.ok(original.body.includes("吸引用户创建专业领域 Skill 上千个"));
  assert.ok(factContext([original]).join("\n").includes(original.body));
  assert.match(factContext([original]).join("\n"), /记忆·我的经历·原文/);
  assert.doesNotMatch(factContext([original]).join("\n"), /PDF|HTML|来源|2026/);
  assert.ok(hasVerbatimResumeQuote("简历写道：“吸引用户创建专业领域 Skill 上千个”", [original]));
  assert.equal(hasVerbatimResumeQuote("简历写道：“用户创建了数千 Skills”", [original]), false);
  assert.equal(hasVerbatimResumeQuote("用户做了很多 Skill。", [original]), false);
  assert.ok(fallbackResumeQuote(original).includes(original.body));

  const vtuberQuestion = retrieveFacts("你做过 AI 主播吗", corpus);
  assert.ok(vtuberQuestion.some((fact) => fact.recordType === "resume_source"
    && fact.sourceVersion === "2026"
    && fact.sourceFormat === "html"));

  const fakers = resumes.find((fact) => fact.sourceFormat === "html" && fact.title.startsWith("Fakers"));
  assert.ok(fakers?.body.includes("通过 Multi-Agent 与人类互动、追问和反馈"));
  assert.ok(fakers?.body.includes("高情感关联的 AI Buddy"));
  assert.match(fallbackResumeQuote(fakers as PersonalFact), /HTML 第 1 页/);

  const allResumeText = resumes.map((fact) => fact.body).join("\n");
  assert.doesNotMatch(allResumeText, /[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/u);
  assert.doesNotMatch(allResumeText, /QQ\s*\/\s*WeChat\s*[:：]/iu);
  const currentResumeText = resumes.filter((fact) => fact.sourceVersion === "2026").map((fact) => fact.body).join("\n");
  assert.ok(resumes.filter((fact) => fact.sourceVersion === "2026").every((fact) => fact.sourceFormat === "html"));
  assert.doesNotMatch(currentResumeText, /LINK RESERVED|广州 \/ 深圳|把前沿模型能力/u);
});

test("resume source rules prohibit paraphrasing index summaries as quotations", () => {
  const prompt = buildSystemPrompt("about", factContext([
    resumes.find((fact) => fact.sourceVersion === "2026") as PersonalFact,
    corpus.find((fact) => fact.id === "super-intern-results") as PersonalFact,
  ]));
  assert.match(prompt, /口述经历和简历原文是我的个人经历与项目细节/);
  assert.match(prompt, /始终使用第一人称/);
  assert.match(prompt, /不要对外提到/);
  assert.match(prompt, /不要向访客解释这些记忆来自哪里/);
  assert.match(prompt, /逐字引用对应记忆中的句子/);
  const summaryMemory = factContext([corpus.find((fact) => fact.id === "super-intern-results") as PersonalFact]).join("\n");
  assert.doesNotMatch(summaryMemory, /2026 年简历记载|旧版简历|来源：|根据资料/);
  assert.match(summaryMemory, /我/);
});

test("sensitive personal blog material needs an explicit matching query", () => {
  const sensitiveFact: PersonalFact = {
    id: "family-memory",
    title: "关于奶奶的记忆",
    body: "一段个人家庭回忆。",
    recordType: "blog",
    groupId: "family-memory",
    sensitivity: "personal",
    tags: ["个人经历"],
    keywords: ["奶奶", "家庭"],
    source: "personal blog",
    visibility: "public",
  };
  assert.deepEqual(retrieveFacts("你怎么看社交产品", [sensitiveFact]), []);
  assert.equal(retrieveFacts("你写过关于奶奶的文章吗", [sensitiveFact])[0]?.id, sensitiveFact.id);
});

test("blog context identifies historical material and its date", () => {
  const blogFact: PersonalFact = {
    id: "old-opinion",
    title: "一篇旧博客",
    body: "当时的产品判断。",
    recordType: "blog",
    publishedAt: "2012",
    dateConfidence: "uncertain",
    groupId: "old-opinion",
    tags: [],
    source: "ref/Blog/2012/example.md",
    visibility: "public",
  };
  const [context] = factContext([blogFact]);
  assert.match(context, /记忆·我曾经形成的观点/);
  assert.match(context, /2012/);
  assert.match(context, /日期不确定/);
  assert.doesNotMatch(context, /来源|ref\/Blog|PDF/);
});

test("imported blogs preserve source dates and retrieve contemporary aliases", () => {
  const characterAi = retrieveFacts("Character.AI 为什么破产", corpus);
  assert.ok(characterAi.some((fact) => fact.recordType === "blog" && fact.publishedAt === "2026"));
  assert.ok(characterAi.some((fact) => fact.source.includes("Google 抽魂")));

  const chainLetter = retrieveFacts("微信群接龙为什么容易传播", corpus);
  assert.ok(chainLetter.some((fact) => fact.source.includes("微信更新接龙功能的思考") && fact.publishedAt === "2019"));

  const familyMemory = blogs.filter((fact) => fact.sensitivity === "personal") as PersonalFact[];
  assert.ok(familyMemory.length > 0);
  assert.deepEqual(retrieveFacts("你对 Agent 产品有什么看法", familyMemory), []);
  assert.ok(retrieveFacts("你写过关于奶奶的文章吗", familyMemory).length > 0);
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

test("history selection preserves client metadata while trimming token content", () => {
  const history = [
    { id: "u1", role: "user" as const, content: "项目是什么？" },
    { id: "a1", role: "assistant" as const, content: "它是一个 AI 产品。", sources: [{ id: "fact-1", title: "项目事实" }], contactPrompt: true },
  ];
  const budget = history.reduce((total, message) => total + estimateTextTokens(message.content) + 8, 0);
  const selected = selectHistoryWithinBudget(history, budget);
  assert.equal(selected[1].id, "a1");
  assert.deepEqual(selected[1].sources, [{ id: "fact-1", title: "项目事实" }]);
  assert.equal(selected[1].contactPrompt, true);
});
