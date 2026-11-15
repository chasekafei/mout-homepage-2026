import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)));
const outputPath = join(root, "content/agent-public/resume-source.json");
const factsPath = join(root, "content/agent-public/facts.json");
const pdfToText = process.env.PDFTOTEXT_BIN || "pdftotext";
const maxChars = 1_800;
const searchAliases = [
  [/AI\s*VTuber/iu, ["AI 主播", "AI 虚拟主播", "虚拟主播"]],
];
const resumes = [
  { version: "2024", path: "ref/闫宇琨-AI产品经理-2024.09.17.pdf" },
  { version: "2021", path: "ref/闫宇琨的个人简历-产品经理方向-2021.pdf" },
];
const currentResumeHtml = "ref/AI产品负责人_设计版简历_v6-打印修复.html";
const htmlExtractor = join(root, "tools/content/extract-agent-resume-html.py");
const htmlRecords = JSON.parse(execFileSync("python3", [htmlExtractor, join(root, currentResumeHtml)], {
  encoding: "utf8",
  maxBuffer: 8 * 1024 * 1024,
}));

const normalizePdfGlyphs = (text) => text.replace(/\p{Script=Han}/gu, (character) => character.normalize("NFKC"));
const compact = (text) => normalizePdfGlyphs(text).toLocaleLowerCase("zh-CN").replace(/[^\p{L}\p{N}]+/gu, "");

const removeContactDetails = (text) => text
  .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/gu, "")
  .replace(/(?:\+?86\s*[-]?\s*)?1[3-9](?:[\s-]?\d){9}/gu, "")
  .replace(/\bQQ\s*\/\s*WeChat\s*[:：]\s*[\w-]+/giu, "")
  .replace(/https?:\/\/[^\s)]+/giu, "");

function cleanPage(text) {
  return removeContactDetails(normalizePdfGlyphs(text))
    .replace(/\r/gu, "")
    .split("\n")
    .filter((line) => !/^\s*(?:●\s*)?MOUT\.ME\s*\/\s*(?:RESUME|AI PRODUCT LEAD)\b/iu.test(line))
    .filter((line) => !/^\s*\d{2}\s*\/\s*\d{2}\s*$/u.test(line))
    .map((line) => line.replace(/[ \t]+$/gu, ""))
    .join("\n")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function splitLongBlock(block) {
  const pieces = [];
  let remaining = block;
  while (remaining.length > maxChars) {
    let splitAt = remaining.lastIndexOf("\n", maxChars);
    if (splitAt < maxChars * 0.5) splitAt = maxChars;
    pieces.push(remaining.slice(0, splitAt).trim());
    remaining = remaining.slice(splitAt).trim();
  }
  if (remaining) pieces.push(remaining);
  return pieces;
}

function makeChunks(pageText) {
  const chunks = [];
  let current = "";
  for (const block of pageText.split(/\n\s*\n/gu).map((part) => part.trim()).filter(Boolean)) {
    for (const piece of splitLongBlock(block)) {
      const candidate = current ? `${current}\n\n${piece}` : piece;
      if (candidate.length > maxChars && current) {
        chunks.push(current);
        current = piece;
      } else current = candidate;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

const records = [];
const facts = JSON.parse(await readFile(factsPath, "utf8"));
for (const record of htmlRecords) {
  const compactBody = compact(`${record.title} ${record.body}`);
  const aliases = facts
    .filter((fact) => fact.source.includes("2026"))
    .filter((fact) => [fact.title, ...(fact.keywords ?? [])]
      .some((term) => compact(term).length >= 4 && compactBody.includes(compact(term))))
    .flatMap((fact) => [fact.title, ...(fact.keywords ?? [])])
    .filter(Boolean);
  const lexicalAliases = searchAliases.flatMap(([pattern, values]) => pattern.test(normalizePdfGlyphs(`${record.title} ${record.body}`)) ? values : []);
  records.push({ ...record, keywords: [...new Set([...record.keywords, ...aliases, ...lexicalAliases])] });
}
for (const resume of resumes) {
  const pdfPath = join(root, resume.path);
  await readFile(pdfPath);
  const extracted = execFileSync(pdfToText, ["-layout", "-enc", "UTF-8", pdfPath, "-"], {
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const pages = extracted.split("\f").map(cleanPage).filter(Boolean);
  pages.forEach((pageText, pageIndex) => {
    const page = pageIndex + 1;
    for (const [chunkIndex, body] of makeChunks(pageText).entries()) {
      const compactBody = compact(body);
      const aliases = facts
        .filter((fact) => fact.source.includes(resume.version))
        .filter((fact) => [fact.title, ...(fact.keywords ?? [])]
          .some((term) => compact(term).length >= 4 && compactBody.includes(compact(term))))
        .flatMap((fact) => [fact.title, ...(fact.keywords ?? [])])
        .filter(Boolean);
      const normalizedBody = normalizePdfGlyphs(body);
      const lexicalAliases = searchAliases.flatMap(([pattern, values]) => pattern.test(normalizedBody) ? values : []);
      records.push({
        id: `resume-${resume.version}-p${page}-${String(chunkIndex + 1).padStart(2, "0")}`,
        groupId: `resume-${resume.version}-p${page}`,
        recordType: "resume_source",
        sourceVersion: resume.version,
        page,
        title: `${resume.version}版简历 · PDF 第 ${page} 页`,
        body,
        sourceFormat: "pdf",
        tags: ["简历原文", resume.version, "工作与项目经历"],
        keywords: [...new Set([basename(resume.path, ".pdf"), `简历 ${resume.version}`, ...aliases, ...lexicalAliases])],
        source: `${resume.path}#page=${page}`,
        visibility: "public",
      });
    }
  });
}

await writeFile(outputPath, `${JSON.stringify(records, null, 2)}\n`, "utf8");
console.log(`Extracted ${records.length} verbatim resume passages into ${outputPath}`);
