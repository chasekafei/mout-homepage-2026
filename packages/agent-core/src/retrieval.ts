import type { ChatMessage, PersonalFact } from "./types.js";

const normalize = (value: string) => value.toLocaleLowerCase("zh-CN").replace(/\s+/g, " ");

/** A deliberately small lexical retriever for the first public corpus. */
export function retrieveFacts(query: string, facts: PersonalFact[], limit = 5): PersonalFact[] {
  const normalizedQuery = normalize(query);
  const terms = normalizedQuery.split(/[^\p{L}\p{N}]+/u).filter((term) => term.length > 1);
  return facts
    .filter((fact) => fact.visibility === "public")
    .map((fact) => {
      const haystack = normalize(`${fact.title} ${fact.body} ${fact.tags.join(" ")}`);
      const score = terms.reduce((total, term) => total + (haystack.includes(term) ? 1 : 0), 0);
      return { fact, score };
    })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
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
export function selectHistoryWithinBudget(
  history: ChatMessage[] | undefined,
  tokenBudget: number,
  maxMessages = 256,
  maxMessageChars = 32_000,
): ChatMessage[] {
  if (!history || tokenBudget <= 0) return [];
  const normalized = history
    .filter((message): message is ChatMessage => Boolean(message)
      && (message.role === "user" || message.role === "assistant")
      && typeof message.content === "string")
    .map((message) => ({ role: message.role, content: message.content.trim().slice(0, maxMessageChars) }))
    .filter((message) => message.content.length > 0)
    .slice(-maxMessages);

  const turns: ChatMessage[][] = [];
  const addCompleteTurn = (turn: ChatMessage[] | undefined) => {
    if (turn?.some((message) => message.role === "assistant")) turns.push(turn);
  };
  let current: ChatMessage[] | undefined;
  for (const message of normalized) {
    if (message.role === "user") {
      addCompleteTurn(current);
      current = [message];
    } else if (current) {
      current.push(message);
    }
  }
  addCompleteTurn(current);

  const selected: ChatMessage[][] = [];
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
