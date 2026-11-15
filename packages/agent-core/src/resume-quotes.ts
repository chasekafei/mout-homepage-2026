import type { PersonalFact } from "./types.js";

const compactWhitespace = (value: string) => value.replace(/\s+/gu, " ").trim();

export function hasVerbatimResumeQuote(answer: string, sources: PersonalFact[]): boolean {
  const quoteTexts = [...answer.matchAll(/[“「『"]([^”」』"]+)[”」』"]/gu)]
    .map((match) => compactWhitespace(match[1]))
    .filter((quote) => Array.from(quote).length >= 16);
  if (!quoteTexts.length) return false;

  const sourceTexts = sources
    .filter((fact) => fact.recordType === "resume_source")
    .map((fact) => compactWhitespace(fact.body));
  return quoteTexts.every((quote) => sourceTexts.some((source) => source.includes(quote)));
}

export function fallbackResumeQuote(source: PersonalFact): string {
  const format = source.sourceFormat === "html" ? "HTML" : "PDF";
  return `简历原文（${source.sourceVersion} 版，${format} 第 ${source.page} 页）：\n\n「${source.body}」`;
}
