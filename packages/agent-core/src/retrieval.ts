import type { ChatMessage, PersonalFact } from "./types.js";

const normalize = (value: string) => value.toLocaleLowerCase("zh-CN").replace(/\s+/g, " ");
const compact = (value: string) => normalize(value).replace(/[^\p{L}\p{N}]+/gu, "");
const STOP_BIGRAMS = new Set(["你是", "我是", "什么", "怎么", "如何", "可以", "这个", "那个", "一下", "吗", "呢"]);

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
    for (let i = 0; i < chars.length - 2; i += 1) result.add(chars.slice(i, i + 3).join(""));
  }
  return result;
}

export type RankedFact = { fact: PersonalFact; score: number };

/** Lexical retrieval with Chinese n-grams, curated aliases, field weighting, and term rarity. */
export function rankFacts(query: string | string[], facts: PersonalFact[]): RankedFact[] {
  const queries = (Array.isArray(query) ? query : [query]).map((text) => ({ text: normalize(text), terms: terms(text) })).filter((item) => item.terms.size > 0);
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
            + (bodyTerms.has(term) ? 1 : 0)
          );
        }
        const normalizedQuery = compact(query.text);
        for (const phrase of fact.queries ?? []) {
          const normalizedPhrase = compact(phrase);
          if (normalizedPhrase.length >= 4 && (normalizedQuery.includes(normalizedPhrase) || normalizedPhrase.includes(normalizedQuery))) {
            score += recencyWeight * 10;
          }
        }
      }
      return { fact, score };
    })
    .sort((a, b) => b.score - a.score || a.fact.id.localeCompare(b.fact.id))
}

/** Avoids filling the prompt with weak matches when only a few facts are relevant. */
export function retrieveFacts(query: string | string[], facts: PersonalFact[], limit = 5): PersonalFact[] {
  const ranked = rankFacts(query, facts);
  const best = ranked[0]?.score ?? 0;
  if (best < 1.5) return [];
  return ranked
    .filter(({ score }) => score >= Math.max(1.5, best * 0.68))
    .slice(0, limit)
    .map(({ fact }) => fact);
}

export function factContext(facts: PersonalFact[]): string[] {
  return facts.map((fact) => `${fact.title}：${fact.body}（来源：${fact.source}）`);
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
  return estimateTextTokens(message.content) + 8;
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
  return /(今天|昨日|昨天|最新|刚刚|现在|当前|本周|本月|最近(?:更新|发布|消息|新闻)|价格|发布|新闻|榜单|官网|链接|查一下|搜索|latest|today|current|recent|price|news)/iu.test(query);
}
