import type { ChatMessage, PersonalFact } from "./types.js";

const normalize = (value: string) => value.toLocaleLowerCase("zh-CN").replace(/\s+/g, " ");
const compact = (value: string) => normalize(value).replace(/[^\p{L}\p{N}]+/gu, "");
const STOP_BIGRAMS = new Set([
  "你是", "我是", "什么", "怎么", "如何", "可以", "这个", "那个", "一下", "吗", "呢",
  "是什", "做什", "么产", "你平", "平时", "时做", "当时", "为什", "什么", "做过",
]);
const STOP_TRIGRAMS = new Set(["是什么", "什么产品", "什么项目", "什么应用", "做什么", "为什么", "你平时", "平时做", "时做什", "当时为", "时为什"]);

function terms(value: string): Set<string> {
  const result = new Set<string>();
  const segments = normalize(value).match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\u3000-\u303f\uff00-\uffef]+|[a-z0-9]+/giu) ?? [];
  for (const segment of segments) {
    if (/^[a-z0-9]+$/iu.test(segment)) {
      if (segment.length > 1) result.add(segment);
      continue;
    }
    const chars = Array.from(segment);
    for (const char of chars) if (char.length > 1) result.add(char);
    for (let i = 0; i < chars.length - 1; i += 1) {
      const bigram = chars[i] + chars[i + 1];
      if (!STOP_BIGRAMS.has(bigram)) result.add(bigram);
    }
    for (let i = 0; i < chars.length - 2; i += 1) {
      const trigram = chars.slice(i, i + 3).join("");
      if (!STOP_TRIGRAMS.has(trigram)) result.add(trigram);
    }
  }
  return result;
}

export type RankedFact = { fact: PersonalFact; score: number };
export type SemanticFactScore = { id: string; score: number };
export const DEFAULT_SEMANTIC_LEXICAL_CONFIDENCE = 80;

function isSelfIntroductionQuery(query: string | string[]): boolean {
  const text = (Array.isArray(query) ? query[0] : query).toLocaleLowerCase("zh-CN");
  return /(介绍一下自己|简单介绍|自我介绍|你是谁|你平时做什么|你的个人简介|你的职业经历|你的工作经历|about yourself|introduce yourself)/iu.test(text);
}

function isProductOverviewQuery(query: string | string[]): boolean {
  const text = (Array.isArray(query) ? query[0] : query).replace(/\s+/gu, " ").toLocaleLowerCase("zh-CN");
  // Listing products needs coverage across projects. A question naming one
  // project ("Super Intern 是什么产品") still uses ordinary relevance ranking.
  return /你(?:都|曾经|以前|之前|自己|独立|个人|还|也|主要|一共|至今|最近|近几年)*(?:做过|做了|开发过|参与过|负责过)(?:哪些|什么|多少|几个|的)?(?:ai\s*|人工智能|独立|个人|自己的)?(?:产品|项目|应用|作品)/iu.test(text)
    || /你有(?:哪些|什么)(?:ai\s*|人工智能|独立|个人)?(?:产品|项目|应用|作品)/iu.test(text)
    || /(?:介绍|盘点|列举|列出|说说|展示)(?:一下)?你(?:的|做过的|参与过的)(?:ai\s*|人工智能|独立|个人)?(?:产品|项目|应用|作品)/iu.test(text)
    || /(?:what (?:products?|projects?|apps?) have you (?:built|worked on)|(?:show|list) (?:me )?your (?:products?|projects?|work))/iu.test(text);
}

/** Lexical retrieval with Chinese n-grams, curated aliases, field weighting, and term rarity. */
export function rankFacts(query: string | string[], facts: PersonalFact[]): RankedFact[] {
  const queries = (Array.isArray(query) ? query : [query])
    .map((text) => ({ text: normalize(text), compactText: compact(text), terms: terms(text) }))
    .filter((item) => item.terms.size > 0 || item.compactText.length >= 4);
  if (!queries.length) return [];
  const publicFacts = facts.filter((fact) => fact.visibility === "public");
  const termFrequency = new Map<string, number>();
  for (const fact of publicFacts) {
    const docTerms = new Set([
      ...terms(fact.title),
      ...terms(fact.body),
      ...terms(fact.tags.join(" ")),
      ...terms(fact.keywords?.join(" ") ?? ""),
      ...(fact.queries ?? []).flatMap((phrase) => [...terms(phrase)]),
    ]);
    for (const term of docTerms) termFrequency.set(term, (termFrequency.get(term) ?? 0) + 1);
  }

  return publicFacts
    .map((fact) => {
      const titleTerms = terms(fact.title);
      const tagTerms = terms(fact.tags.join(" "));
      const keywordTerms = terms(fact.keywords?.join(" ") ?? "");
      const bodyTerms = terms(fact.body);
      let score = 0;
      for (let index = 0; index < queries.length; index += 1) {
        const query = queries[index];
        const recencyWeight = index === 0 ? 1 : Math.max(0.35, 0.65 / index);
        for (const term of query.terms) {
          const df = termFrequency.get(term) ?? 0;
          if (!df) continue;
          const idf = Math.log(1 + (publicFacts.length - df + 0.5) / (df + 0.5));
          score += recencyWeight * idf * (
            (titleTerms.has(term) ? 7 : 0)
            + (keywordTerms.has(term) ? 6 : 0)
            + (tagTerms.has(term) ? 4 : 0)
            + (bodyTerms.has(term) ? (fact.recordType === "resume_source" ? 2 : 1) : 0)
          );
        }
        for (const phrase of fact.queries ?? []) {
          const normalizedPhrase = compact(phrase);
          if (normalizedPhrase.length < 4 || query.compactText.length < 4) continue;
          if (query.compactText === normalizedPhrase) score += recencyWeight * 80;
          else if ((query.compactText.includes(normalizedPhrase) || normalizedPhrase.includes(query.compactText))
            && Math.min(query.compactText.length, normalizedPhrase.length) / Math.max(query.compactText.length, normalizedPhrase.length) >= 0.72) {
            score += recencyWeight * 14;
          }
        }
      }
      if (fact.recordType === "resume_source" && score > 0) {
        score += fact.sourceVersion === "2026" ? 32 : fact.sourceVersion === "2024" ? 16 : 0;
      }
      return { fact, score };
    })
    .sort((a, b) => b.score - a.score
      || (b.fact.sourceVersion ?? "").localeCompare(a.fact.sourceVersion ?? "")
      || a.fact.id.localeCompare(b.fact.id))
}

/** Weighted reciprocal-rank fusion keeps exact lexical matches dominant while adding semantic candidates. */
export function rankFactsHybrid(
  query: string | string[],
  facts: PersonalFact[],
  semanticScores: SemanticFactScore[],
): RankedFact[] {
  const lexical = rankFacts(query, facts);
  const lexicalRelevant = lexical.filter(({ score }) => score >= 1.5);
  const protectedLexical = lexicalRelevant.slice(0, 3);
  const protectedIds = new Set(protectedLexical.map(({ fact }) => fact.id));
  const lexicalRanks = new Map(lexicalRelevant
    .filter(({ fact }) => !protectedIds.has(fact.id))
    .map(({ fact }, index) => [fact.id, index + 4]));
  const semanticRanks = new Map([...semanticScores]
    .filter((item) => Number.isFinite(item.score) && item.score >= 0.2)
    .sort((a, b) => b.score - a.score)
    .map((item, index) => [item.id, index + 1]));
  const byId = new Map(facts.filter((fact) => fact.visibility === "public").map((fact) => [fact.id, fact]));
  const ids = new Set([...lexicalRanks.keys(), ...semanticRanks.keys()]);

  const fused = [...ids]
    .filter((id) => !protectedIds.has(id))
    .flatMap((id) => {
      const fact = byId.get(id);
      if (!fact) return [];
      const lexicalRank = lexicalRanks.get(id);
      const semanticRank = semanticRanks.get(id);
      const score = (lexicalRank ? 0.7 / (60 + lexicalRank) : 0)
        + (semanticRank ? 0.3 / (60 + semanticRank) : 0);
      return [{ fact, score }];
    })
    .sort((a, b) => b.score - a.score
      || (b.fact.sourceVersion ?? "").localeCompare(a.fact.sourceVersion ?? "")
      || a.fact.id.localeCompare(b.fact.id));
  return [...protectedLexical, ...fused];
}

export function shouldUseSemanticRetrieval(
  query: string | string[],
  facts: PersonalFact[],
  minimumLexicalConfidence = DEFAULT_SEMANTIC_LEXICAL_CONFIDENCE,
): boolean {
  return (rankFacts(query, facts)[0]?.score ?? 0) < minimumLexicalConfidence;
}

/** Avoids filling the prompt with weak matches when only a few facts are relevant. */
export function retrieveFacts(
  query: string | string[],
  facts: PersonalFact[],
  limit = 5,
  semanticScores: SemanticFactScore[] = [],
): PersonalFact[] {
  if (limit <= 0) return [];
  const hasSemanticScores = semanticScores.length > 0 && shouldUseSemanticRetrieval(query, facts);
  const ranked = hasSemanticScores ? rankFactsHybrid(query, facts, semanticScores) : rankFacts(query, facts);
  const bestScore = ranked[0]?.score ?? 0;
  const productOverview = isProductOverviewQuery(query);
  if (!productOverview && bestScore < (hasSemanticScores ? 0.001 : 1.5)) return [];
  const selected: PersonalFact[] = [];
  const blogGroupCounts = new Map<string, number>();
  const resumePageCounts = new Map<string, number>();
  let resumeSourceCount = 0;
  let oralHistoryCount = 0;
  const selfIntroduction = isSelfIntroductionQuery(query);
  const resumeSourceLimit = productOverview ? limit : selfIntroduction ? 10 : 3;
  const oralHistoryLimit = selfIntroduction ? 6 : 3;
  const queryTerms = (Array.isArray(query) ? query : [query]).map((text) => terms(text));
  const addCandidate = (fact: PersonalFact): boolean => {
    if (selected.length >= limit) return false;
    if (selected.some((item) => item.id === fact.id)) return false;
    if (selfIntroduction && fact.recordType === "resume_source" && fact.sourceVersion !== "2026") return false;
    if (selfIntroduction && (fact.recordType === "blog" || fact.recordType === "industry_notes")) return false;
    if (fact.sensitivity === "personal") {
      const explicitTerms = new Set([...terms(fact.title), ...terms(fact.keywords?.join(" ") ?? "")]);
      const explicitlyRequested = queryTerms[0]?.size
        && [...explicitTerms].some((term) => term.length > 1 && queryTerms[0].has(term));
      if (!explicitlyRequested) return false;
    }
    if (fact.recordType === "blog") {
      const groupId = fact.groupId ?? fact.id;
      const count = blogGroupCounts.get(groupId) ?? 0;
      if (count >= (selfIntroduction ? 3 : 2)) return false;
      blogGroupCounts.set(groupId, count + 1);
    }
    if (fact.recordType === "oral_history") {
      if (oralHistoryCount >= oralHistoryLimit) return false;
      oralHistoryCount += 1;
    }
    if (fact.recordType === "resume_source") {
      if (resumeSourceCount >= resumeSourceLimit) return false;
      const groupId = fact.groupId ?? fact.id;
      const count = resumePageCounts.get(groupId) ?? 0;
      if (count >= (selfIntroduction ? 3 : 2)) return false;
      resumePageCounts.set(groupId, count + 1);
      resumeSourceCount += 1;
    }
    selected.push(fact);
    return true;
  };

  if (productOverview) {
    const currentQuery = (Array.isArray(query) ? query[0] : query).toLocaleLowerCase("zh-CN");
    const independentOnly = /独立|个人(?:的)?(?:产品|项目|应用|作品)|independent|side project/iu.test(currentQuery);
    const aiOnly = /\bai\b|人工智能/iu.test(currentQuery);
    const resumes = facts.filter((fact) => fact.visibility === "public" && fact.recordType === "resume_source");
    const latestVersion = resumes.map((fact) => fact.sourceVersion ?? "").sort().at(-1);
    const latest = resumes.filter((fact) => fact.sourceVersion === latestVersion);
    const currentResume = latest.some((fact) => fact.sourceFormat === "html")
      ? latest.filter((fact) => fact.sourceFormat === "html")
      : latest;
    // These section labels come from the source document, not generated prose.
    // Keep product entries ahead of employer/role context and cover independent
    // products as well as company projects before filling the remaining slots.
    const portfolio = currentResume.filter((fact) => /experience|products/iu.test(fact.section ?? ""))
      .filter((fact) => !aiOnly || /\bai\b|agent|llm|aigc|skill|人工智能/iu.test(`${fact.title} ${fact.body}`));
    const independent = portfolio.filter((fact) => /independent products/iu.test(fact.section ?? ""));
    const workProjects = portfolio.filter((fact) => !independent.includes(fact) && fact.groupId?.endsWith(fact.title));
    if (independentOnly) {
      for (const fact of independent) addCandidate(fact);
    } else {
      for (let index = 0; index < Math.max(workProjects.length, independent.length); index += 1) {
        if (workProjects[index]) addCandidate(workProjects[index]);
        if (independent[index]) addCandidate(independent[index]);
      }
      for (const fact of facts.filter((fact) => fact.visibility === "public" && fact.tags.includes("项目总览"))) addCandidate(fact);
      for (const fact of portfolio) addCandidate(fact);
    }
    if (selected.length) return selected;
  }

  if (selfIntroduction) {
    for (const fact of facts.filter((item) => item.id === "identity" && item.visibility === "public")) addCandidate(fact);
    const resumeBudget = Math.min(10, limit - selected.length);
    const currentResume = facts
      .filter((fact) => fact.recordType === "resume_source" && fact.sourceVersion === "2026")
      .sort((a, b) => {
        const priority = (fact: PersonalFact) => {
          const title = fact.title;
          if (/个人简介|能力/u.test(title)) return 0;
          if (/AMMO AI/u.test(title)) return 1;
          if (/Super Intern/u.test(title)) return 2;
          if (/Fakers/u.test(title)) return 3;
          if (/Ammonad/u.test(title)) return 4;
          if (/超参数/u.test(title)) return 5;
          return 6;
        };
        return priority(a) - priority(b) || a.id.localeCompare(b.id);
      });
    for (const fact of currentResume) {
      addCandidate(fact);
      if (resumeSourceCount >= resumeBudget) break;
    }
    const currentOralHistory = facts
      .filter((fact) => fact.recordType === "oral_history")
      .filter((fact) => /Super Intern|TIYA|超参数|AI 产品|Agent|语音社交|游戏 AI|产品探索/u.test(`${fact.body} ${fact.keywords?.join(" ") ?? ""}`))
      .sort((a, b) => {
        const priority = (fact: PersonalFact) => {
          const text = `${fact.body} ${fact.keywords?.join(" ") ?? ""}`;
          if (/Super Intern/u.test(text)) return 0;
          if (/TIYA|语音社交/u.test(text)) return 1;
          if (/超参数|AI 产品|Agent/u.test(text)) return 2;
          return 3;
        };
        return priority(a) - priority(b) || a.id.localeCompare(b.id);
      });
    for (const fact of currentOralHistory) {
      addCandidate(fact);
      if (selected.length >= limit || oralHistoryCount >= oralHistoryLimit) break;
    }
    for (const fact of facts.filter((item) => ["identity", "ai-portfolio-overview"].includes(item.id))) {
      addCandidate(fact);
      if (selected.length >= limit) break;
    }
  }

  const resumeSourceScores = new Map<string, { fact: PersonalFact; score: number }>();
  for (const { fact, score } of ranked) {
    if (fact.recordType !== "resume_source") continue;
    resumeSourceScores.set(fact.id, { fact, score });
  }

  const bestIndexedScore = ranked.find(({ fact }) => fact.recordType !== "resume_source")?.score ?? 0;
  const normalThreshold = hasSemanticScores
    ? Math.max(0.001, bestIndexedScore * 0.28)
    : Math.max(1.5, bestIndexedScore * 0.68);
  const resumeBackedSummaries = ranked
    .filter(({ fact, score }) => score >= normalThreshold
      && fact.recordType !== "resume_source"
      && /\.pdf(?:#|$)/iu.test(fact.source))
    .slice(0, 8)
    .flatMap(({ fact }) => [fact.title, ...(fact.keywords ?? []), ...(fact.queries ?? [])])
    .slice(0, 40);
  if (resumeBackedSummaries.length) {
    for (const { fact, score } of rankFacts(resumeBackedSummaries, facts)) {
      if (fact.recordType !== "resume_source") continue;
      const current = resumeSourceScores.get(fact.id);
      if (!current || score > current.score) resumeSourceScores.set(fact.id, { fact, score });
    }
  }

  const sourceCandidates = [...resumeSourceScores.values()].sort((a, b) => b.score - a.score
    || (b.fact.sourceVersion ?? "").localeCompare(a.fact.sourceVersion ?? "")
    || a.fact.id.localeCompare(b.fact.id));
  const bestResumeSourceScore = sourceCandidates[0]?.score ?? 0;
  const resumeSourceThreshold = hasSemanticScores
    ? Math.max(0.001, bestResumeSourceScore * 0.48)
    : Math.max(5, bestResumeSourceScore * 0.48);
  for (const { fact, score } of sourceCandidates) {
    if (score < resumeSourceThreshold) break;
    addCandidate(fact);
    if (resumeSourceCount >= Math.min(limit, 3)) break;
  }

  for (const { fact, score } of ranked) {
    if (score < normalThreshold) break;
    addCandidate(fact);
    if (selected.length >= limit) break;
  }
  return selected;
}

export function factContext(facts: PersonalFact[]): string[] {
  const summaryAsMemory = (value: string) => value
    .replace(/(?:根据|按|来自)?\s*(?:2026|2024|2021)\s*年(?:\s*\d{1,2}\s*月)?\s*(?:版)?\s*简历(?:中)?\s*(?:记载|写到|提到|称|自述)?[，：:、]?/gu, "")
    .replace(/(?:旧版|早期)简历(?:中)?(?:记载|写到|提到|称|自述)?[，：:、]?/gu, "")
    .replace(/(?:项目|这些|相关)?数据(?:来自|源自)(?:简历|旧版简历|资料)[，：:、]?/gu, "")
    .replace(/资料没有说明/gu, "我没有公开说明")
    .replace(/闫宇琨/gu, "我")
    .replace(/本人/gu, "我")
    .replace(/\s{2,}/gu, " ")
    .trim();

  return facts.map((fact) => {
    if (fact.recordType === "resume_source") {
      return `记忆·我的经历·原文：\n${fact.title}\n${fact.body}`;
    }
    if (fact.recordType === "blog") {
      const date = fact.publishedAt
        ? `·${fact.publishedAt}${fact.dateConfidence === "uncertain" ? "·日期不确定" : ""}`
        : "";
      return `记忆·我曾经形成的观点${date}：${fact.title}\n${fact.body}`;
    }
    if (fact.recordType === "oral_history") {
      return `记忆·我的经历·原话：\n${fact.body}`;
    }
    if (fact.recordType === "industry_notes") {
      const date = fact.publishedAt ? `·${fact.publishedAt}` : "";
      return `记忆·我的行业观察·口述整理${date}：${fact.title}\n${fact.body}`;
    }
    const label = fact.recordType === "opinion"
      ? "记忆·我的观点"
      : "记忆·我的背景";
    return `${label}：${fact.title}\n${summaryAsMemory(fact.body)}`;
  });
}

const CJK_CHAR = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\u3000-\u303f\uff00-\uffef]/u;
const ASCII_WORD_CHAR = /[a-zA-Z0-9]/u;

/** Conservative multilingual estimate; actual tokenization is provider/model specific. */
export function estimateTextTokens(text: string): number {
  let cjk = 0;
  let asciiWord = 0;
  let symbols = 0;
  for (const char of text) {
    if (CJK_CHAR.test(char)) cjk += 1;
    else if (/\s/u.test(char)) continue;
    else if (ASCII_WORD_CHAR.test(char)) asciiWord += 1;
    else symbols += 1;
  }
  return cjk + symbols + Math.ceil(asciiWord / 3.2);
}

export function estimateMessageTokens(message: ChatMessage): number {
  const toolContext = message.role === "assistant" && message.deepseekToolCalls
    ? estimateTextTokens(JSON.stringify(message.deepseekToolCalls))
    : 0;
  return estimateTextTokens(message.content) + toolContext + 8;
}

/** Selects the newest complete user/assistant turns that fit the estimated input budget. */
export function selectHistoryWithinBudget<T extends ChatMessage>(
  history: T[] | undefined,
  tokenBudget: number,
  maxMessages = 256,
  maxMessageChars = 32_000,
): T[] {
  if (!history || tokenBudget <= 0) return [];
  const normalized = history
    .filter((message): message is T => Boolean(message)
      && (message.role === "user" || message.role === "assistant")
      && typeof message.content === "string")
    .map((message) => ({ ...message, content: message.content.trim().slice(0, maxMessageChars) }))
    .filter((message) => message.content.length > 0)
    .slice(-maxMessages);

  const turns: T[][] = [];
  const addCompleteTurn = (turn: T[] | undefined) => {
    if (turn?.some((message) => message.role === "assistant")) turns.push(turn);
  };
  let current: T[] | undefined;
  for (const message of normalized) {
    if (message.role === "user") {
      addCompleteTurn(current);
      current = [message];
    } else if (current) {
      current.push(message);
    }
  }
  addCompleteTurn(current);

  const selected: T[][] = [];
  let used = 0;
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    const cost = turn.reduce((total, message) => total + estimateMessageTokens(message), 0);
    if (used + cost > tokenBudget) break;
    selected.push(turn);
    used += cost;
  }
  return selected.reverse().flat();
}

export function shouldSearch(query: string): boolean {
  return /(今天|昨日|昨天|最新|刚刚|现在|当前|本周|本月|最近(?:更新|发布|消息|新闻)|价格|发布|新闻|榜单|官网|链接|查一下|查查|帮我查|搜索|搜一下|帮我搜|上网|联网|latest|today|current|recent|price|news|search|look up|browse)/iu.test(query);
}
