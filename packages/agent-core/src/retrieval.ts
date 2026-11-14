import type { PersonalFact } from "./types.js";

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

export function shouldSearch(query: string): boolean {
  return /(今天|昨日|昨天|最新|刚刚|现在|当前|本周|本月|最近(?:更新|发布|消息|新闻)|价格|发布|新闻|榜单|官网|链接|查一下|搜索|latest|today|current|recent|price|news)/iu.test(query);
}
