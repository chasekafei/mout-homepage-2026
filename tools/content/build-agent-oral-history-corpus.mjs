import { readFile, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)));
const sourcePath = join(root, "docs/个人网站资料-我的个人经历.md");
const outputPath = join(root, "content/agent-public/oral-history.json");
const factsPath = join(root, "content/agent-public/facts.json");
const maxChars = 1_600;
const slug = (value) => value.toLocaleLowerCase("zh-CN")
  .replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-+|-+$/gu, "").slice(0, 80) || "section";

function splitLongParagraph(paragraph) {
  const parts = [];
  let remaining = paragraph;
  while (remaining.length > maxChars) {
    let splitAt = remaining.lastIndexOf("\n", maxChars);
    if (splitAt < maxChars * 0.5) {
      splitAt = remaining.lastIndexOf("。", maxChars);
      if (splitAt >= maxChars * 0.5) splitAt += 1;
    }
    if (splitAt < maxChars * 0.5) splitAt = maxChars;
    parts.push(remaining.slice(0, splitAt));
    remaining = remaining.slice(splitAt);
  }
  if (remaining) parts.push(remaining);
  return parts;
}

const raw = (await readFile(sourcePath, "utf8"))
  .replace(/【目录：\s*`[^`]+`\s*】/gu, "");
const facts = JSON.parse(await readFile(factsPath, "utf8"));
const anchorFrequency = new Map();
for (const fact of facts) {
  const anchors = new Set([fact.title, ...(fact.keywords ?? []), ...(fact.tags ?? [])]
    .map((term) => term.toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "")));
  for (const anchor of anchors) anchorFrequency.set(anchor, (anchorFrequency.get(anchor) ?? 0) + 1);
}
const records = [];
let heading = "我的个人经历";
let paragraphs = [];
let paragraphLines = [];
let sectionIndex = 0;

const addParagraph = () => {
  const text = paragraphLines.join("\n");
  if (text.trim()) paragraphs.push(text);
  paragraphLines = [];
};

const flushSection = () => {
  addParagraph();
  sectionIndex += 1;
  let chunkIndex = 0;
  for (const paragraph of paragraphs) {
    for (const part of splitLongParagraph(paragraph)) {
      addRecord(part, chunkIndex++);
    }
  }
  paragraphs = [];
};

function addRecord(body, chunkIndex) {
  const key = `${String(sectionIndex).padStart(3, "0")}-${slug(heading)}`;
  const compactBody = body.toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "");
  const aliases = facts
    .filter((fact) => fact.source.includes("个人网站资料-我的个人经历.md"))
    .map((fact) => ({
      fact,
      // A paragraph mentioning Figma must not inherit every query and keyword
      // from a broad "hybrid product maker" fact. Keep only anchors it contains.
      matchedTerms: [fact.title, ...(fact.keywords ?? []), ...(fact.tags ?? [])].filter((term) => {
        const compactTerm = term.toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "");
        return compactTerm.length >= 4 && compactBody.includes(compactTerm);
      }),
    }))
    .filter(({ matchedTerms }) => matchedTerms.length > 0);
  // Only passages that name the fact's subject inherit its question aliases.
  // Generated queries are never copied into keywords and scored a second time.
  const namedSubjects = aliases.filter(({ fact, matchedTerms }) => {
    const subject = fact.title.split(/[：:（(]/u)[0].split(/\s+/u)[0]
      .toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "");
    return (subject.length >= 4 && compactBody.includes(subject))
      || matchedTerms.some((term) => {
        const anchor = term.toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "");
        return /^[a-z][a-z0-9._; -]{3,}$/iu.test(term) && anchorFrequency.get(anchor) === 1;
      });
  });
  const sensitive = /我老婆|老婆|婚礼|我家的猫|奶奶/u.test(body);
  const personalKeywords = [...new Set([
    ...(/我老婆|老婆|婚礼/u.test(body) ? ["妻子", "婚礼"] : []),
    ...(/我家的猫/u.test(body) ? ["猫", "宠物"] : []),
    ...(/奶奶/u.test(body) ? ["奶奶", "祖母"] : []),
  ])];
  records.push({
    id: `oral-history-${key}-${String(chunkIndex + 1).padStart(2, "0")}`,
    groupId: `oral-history-${key}-${String(chunkIndex + 1).padStart(2, "0")}`,
    recordType: "oral_history",
    title: heading,
    section: heading,
    body,
    tags: ["口述经历原文", ...(sensitive ? ["个人经历"] : [])],
    keywords: [...new Set([heading, ...personalKeywords, ...aliases.flatMap(({ matchedTerms }) => matchedTerms)])],
    queries: [...new Set(namedSubjects.flatMap(({ fact }) => fact.queries ?? []))],
    source: `${relative(root, sourcePath)}#${slug(heading)}`,
    visibility: "public",
    ...(sensitive ? { sensitivity: "personal" } : {}),
  });
}

for (const line of raw.replace(/^\uFEFF/u, "").split(/\r?\n/u)) {
  const headingMatch = line.match(/^#{1,6}\s+(.+?)\s*#*\s*$/u);
  if (headingMatch) {
    if (paragraphs.length || paragraphLines.length) flushSection();
    heading = headingMatch[1].trim();
    continue;
  }
  if (!line.trim()) {
    addParagraph();
    continue;
  }
  paragraphLines.push(line);
}
flushSection();

await writeFile(outputPath, `${JSON.stringify(records, null, 2)}\n`, "utf8");
console.log(`Imported original oral-history text into ${records.length} source passages.`);
