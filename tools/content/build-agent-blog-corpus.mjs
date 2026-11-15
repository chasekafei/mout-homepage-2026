import { readdir, readFile, writeFile } from "node:fs/promises";
import { basename, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)));
const blogRoot = join(root, "ref/Blog");
const outputPath = join(root, "content/agent-public/blog.json");
const MAX_CHARS = 1_500;

async function collectTextFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await collectTextFiles(path));
    else if ([".md", ".txt"].includes(extname(entry.name).toLowerCase())) files.push(path);
  }
  return files.sort((a, b) => relative(blogRoot, a).localeCompare(relative(blogRoot, b), "zh-CN"));
}

function parseFrontmatter(text) {
  if (!text.startsWith("---")) return { text };
  const end = text.indexOf("\n---", 3);
  if (end < 0) return { text };
  const header = text.slice(3, end);
  const fields = Object.fromEntries(
    header.split(/\r?\n/u)
      .map((line) => line.match(/^([\w-]+):\s*["']?(.*?)["']?\s*$/u))
      .filter(Boolean)
      .map((match) => [match[1].toLowerCase(), match[2]]),
  );
  return { text: text.slice(end + 4), title: fields.title, date: fields.date };
}

function inferDate(path, text, frontmatterDate) {
  const relativePath = relative(blogRoot, path).split("\\").join("/");
  const folderYear = relativePath.split("/")[0];
  const pathDates = [...relativePath.matchAll(/((?:19|20)\d{2})(?:[-/.年](0[1-9]|1[0-2]|[1-9])(?:[-/.月](0[1-9]|[12]\d|3[01]|[1-9])日?)?)?(?!\d)/gu)]
    .map((match) => parseDate(match[0]))
    .filter(Boolean);
  const frontmatter = parseDate(frontmatterDate);
  const openingLines = text.split(/\r?\n/u).slice(0, 12);
  const metadataLine = openingLines.find((line) => /^\s*>?\s*(?:19|20)\d{2}[-/.年]/u.test(line));
  const bodyMetadata = parseDate(metadataLine);
  const explicitDates = [frontmatter, ...pathDates, bodyMetadata].filter(Boolean);
  const hasFolderYear = /^(?:19|20)\d{2}$/u.test(folderYear);
  const conflicts = new Set(explicitDates.map((date) => date.slice(0, 4))).size > 1
    || (hasFolderYear && explicitDates.some((date) => date.slice(0, 4) !== folderYear));

  if (conflicts && hasFolderYear) return { publishedAt: folderYear, dateConfidence: "uncertain" };
  if (explicitDates.length) return { publishedAt: explicitDates[0] };
  if (hasFolderYear) return { publishedAt: folderYear };
  return {};
}

function parseDate(value) {
  const match = value?.match(/(?:^|[^\d])((?:19|20)\d{2})(?:[-/.年](0[1-9]|1[0-2]|[1-9])(?:[-/.月](0[1-9]|[12]\d|3[01]|[1-9])日?)?)?(?!\d)/u);
  if (!match) return undefined;
  if (match[2] && match[3]) return match[1] + "-" + match[2].padStart(2, "0") + "-" + match[3].padStart(2, "0");
  if (match[2]) return match[1] + "-" + match[2].padStart(2, "0");
  return match[1];
}

function cleanMarkdown(text) {
  return text
    .replace(/<!--[^]*?-->/gu, " ")
    .replace(/^\s*!\[[^\]]*\]\([^)]*\)\s*$/gmu, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/gu, "")
    .replace(/^\s*<img\b[^>]*>\s*$/gimu, "")
    .replace(/<[^>]+>/gu, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/gu, "$1")
    .replace(/^\s*\[[^\]]+\]:\s*\S+\s*$/gmu, "")
    .replace(/\bhttps?:\/\/[^\s)]+/giu, "")
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/gu, " ")
    .replace(/(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)/gu, " ")
    .replace(/^\s*(?:Area|Pin):\s*.*$/gimu, "")
    .replace(/^\s*---+\s*$/gmu, "")
    .replace(/[ \t]+$/gmu, "")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function titleFrom(text, path, frontmatterTitle) {
  if (frontmatterTitle?.trim()) return frontmatterTitle.trim();
  const heading = text.match(/^#\s+(.+?)\s*#*\s*$/mu)?.[1];
  if (heading) return heading.trim();
  return basename(path, extname(path)).replace(/^\[\d{4}-\d{2}-\d{2}\]\s*/u, "").trim();
}

function splitLongText(text, limit) {
  if (text.length <= limit) return [text];
  const pieces = [];
  let remaining = text;
  while (remaining.length > limit) {
    let splitAt = remaining.lastIndexOf("。", limit);
    if (splitAt < limit * 0.45) splitAt = remaining.lastIndexOf("\n", limit);
    if (splitAt < limit * 0.45) splitAt = limit;
    else splitAt += 1;
    pieces.push(remaining.slice(0, splitAt).trim());
    remaining = remaining.slice(splitAt).trim();
  }
  if (remaining) pieces.push(remaining);
  return pieces;
}

function splitArticle(text, articleTitle) {
  const sections = [];
  let currentHeading = articleTitle;
  let currentParagraphs = [];
  const flush = () => {
    const body = currentParagraphs.join("\n\n").trim();
    if (body) sections.push({ heading: currentHeading, body });
    currentParagraphs = [];
  };

  for (const line of text.split(/\r?\n/u)) {
    const heading = line.match(/^#{1,6}\s+(.+?)\s*#*\s*$/u)?.[1];
    if (heading) {
      flush();
      currentHeading = heading.trim();
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }
    currentParagraphs.push(line.trim());
  }
  flush();

  const chunks = [];
  for (const section of sections) {
    const paragraphs = section.body.split(/\n\n/u);
    let current = "";
    for (const paragraph of paragraphs) {
      for (const part of splitLongText(paragraph, MAX_CHARS)) {
        const candidate = current ? `${current}\n\n${part}` : part;
        if (candidate.length > MAX_CHARS && current) {
          chunks.push({ heading: section.heading, body: current });
          current = part;
        } else current = candidate;
      }
    }
    if (current) chunks.push({ heading: section.heading, body: current });
  }
  return chunks;
}

function slug(value) {
  return value.toLocaleLowerCase("zh-CN")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/gu, "")
    .slice(0, 90) || "untitled";
}

function makeRecord(path, chunk, index, date, articleTitle) {
  const relativePath = relative(root, path).split("\\").join("/");
  const groupId = `blog-${slug(relative(blogRoot, path).replace(/\.[^.]+$/u, ""))}`;
  const year = date.publishedAt?.slice(0, 4);
  const contextTitle = chunk.heading && chunk.heading !== articleTitle
    ? `${articleTitle} / ${chunk.heading}`
    : articleTitle;
  const tags = ["个人博客", ...(year ? [year] : [])];
  if (/产品|用户|增长|设计|体验|运营/u.test(`${articleTitle} ${chunk.heading} ${chunk.body}`)) tags.push("产品思考");
  if (/AI|人工智能|模型|Agent|大模型/iu.test(`${articleTitle} ${chunk.heading} ${chunk.body}`)) tags.push("AI");
  if (/游戏/u.test(`${articleTitle} ${chunk.heading} ${chunk.body}`)) tags.push("游戏");
  if (/生活|人生|奶奶|家庭|记忆/u.test(`${articleTitle} ${chunk.heading} ${chunk.body}`)) tags.push("个人随笔");
  const searchableText = `${articleTitle} ${chunk.heading} ${chunk.body}`;
  const aliases = [
    [/C\.ai|Character\.AI/iu, ["Character.AI", "C.ai", "AI 陪伴", "AI 角色聊天"]],
    [/接龙/u, ["微信群接龙", "群聊接龙", "微信群报名"]],
  ].flatMap(([pattern, values]) => pattern.test(searchableText) ? values : []);
  return {
    id: `${groupId}-${String(index + 1).padStart(3, "0")}`,
    groupId,
    recordType: "blog",
    title: contextTitle,
    body: chunk.body,
    tags: [...new Set(tags)],
    keywords: [...new Set([articleTitle, chunk.heading, ...aliases].filter(Boolean))],
    queries: [`${articleTitle} 主要说什么`, `关于${articleTitle}的看法`],
    source: relativePath,
    visibility: "public",
    ...(date.publishedAt ? { publishedAt: date.publishedAt } : {}),
    ...(date.dateConfidence ? { dateConfidence: date.dateConfidence } : {}),
    ...(relativePath.includes("/关于奶奶的记忆/") ? { sensitivity: "personal" } : {}),
  };
}

const files = await collectTextFiles(blogRoot);
const records = [];
const skipped = [];
let includedArticles = 0;

for (const path of files) {
  const raw = await readFile(path, "utf8");
  const replacementCount = (raw.match(/\uFFFD/gu) ?? []).length;
  if (replacementCount > Math.max(2, raw.length * 0.001)) {
    skipped.push({ source: relative(root, path), reason: "包含较多不可解码字符" });
    continue;
  }
  const parsed = parseFrontmatter(raw.replace(/^\uFEFF/u, ""));
  const cleaned = cleanMarkdown(parsed.text);
  const articleTitle = titleFrom(cleaned, path, parsed.title);
  if (!cleaned || !articleTitle) {
    skipped.push({ source: relative(root, path), reason: "没有可用正文或标题" });
    continue;
  }
  const chunks = splitArticle(cleaned, articleTitle);
  if (!chunks.length) {
    skipped.push({ source: relative(root, path), reason: "没有可用正文段落" });
    continue;
  }
  const date = inferDate(path, parsed.text, parsed.date);
  chunks.forEach((chunk, index) => records.push(makeRecord(path, chunk, index, date, articleTitle)));
  includedArticles += 1;
}

await writeFile(outputPath, `${JSON.stringify(records, null, 2)}\n`, "utf8");
const bytes = Buffer.byteLength(JSON.stringify(records));
console.log(`Imported ${includedArticles} articles into ${records.length} chunks (${bytes.toLocaleString()} JSON bytes).`);
if (skipped.length) {
  console.warn(`Skipped ${skipped.length} files:`);
  for (const item of skipped) console.warn(`- ${item.source}: ${item.reason}`);
}
