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

const oralHistoryCount = records.length;
const industrySource = "docs/agent/AI Roleplay 与 AI 情感陪伴的行业观察.md";
const industryNotes = await readFile(join(root, industrySource), "utf8");
// Only sections with curated retrieval metadata become passages. The source
// Markdown remains the single copy of the approved text.
const industryTopics = [
  {
    id: "companion-vs-roleplay",
    heading: "AI Roleplay 和情感陪伴的区别",
    keywords: ["AI 角色扮演", "情感陪伴", "AI 陪伴", "内容消费"],
    queries: ["AI Roleplay 和 AI 情感陪伴有什么区别"],
  },
  {
    id: "replika",
    heading: "Replika 把单个角色做成长期关系",
    keywords: ["Replika", "AI 男友", "AI 女友", "捏人", "换装"],
  },
  {
    id: "character-platforms",
    heading: "Character.AI 和 MiniMax 把角色变成可分发的内容",
    keywords: ["Character.AI", "C.ai", "MiniMax", "Glow", "Talkie", "星野", "抽卡", "多角色平台"],
  },
  {
    id: "tavern",
    heading: "酒馆丰富了玩法，云端平台降低了门槛",
    keywords: ["SillyTavern", "云酒馆", "角色卡", "预设", "世界书", "Chub", "CHAI", "CrushOn.AI", "猫箱", "冒泡鸭"],
    queries: ["AI Roleplay 行业是怎么发展起来的", "酒馆的角色卡、预设和世界书分别是什么"],
  },
  {
    id: "worlds",
    heading: "对话开始影响整个世界里的后续事件",
    keywords: ["zeta", "Tipsy Chat", "世界玩法", "世界观", "状态管理", "好感度", "多角色", "剧情分支", "玩家选择", "后续剧情", "早期决策"],
    queries: ["zeta 和 Tipsy 的世界玩法有什么不同", "玩家的选择如何影响后续剧情"],
  },
  {
    id: "audience",
    heading: "AI Roleplay 的用户画像",
    keywords: ["用户画像", "乙女游戏", "网文", "梦女", "年龄分布", "男女比例"],
  },
  {
    id: "research",
    heading: "我怎么做用户调研",
    keywords: ["用户调研", "4chan", "PTT", "豆瓣人机之恋", "小红书", "论坛观察", "角色扮演用户调研", "日本市场", "台湾市场"],
    queries: ["你怎么调研 AI Roleplay 用户", "你在哪些论坛看日本和台湾的角色扮演用户"],
  },
  {
    id: "real-world",
    heading: "情感陪伴怎么走进现实生活",
    keywords: ["AI 情感陪伴", "自然选择", "EVE", "视频通话", "秋天的第一杯奶茶", "现实连接"],
  },
  {
    id: "interactive-video",
    heading: "视觉小说和互动短剧",
    keywords: ["视觉小说", "互动短剧", "互动小说", "视频生成", "预生成剧情"],
  },
  {
    id: "memory",
    heading: "我做的酒馆兼容 Bot 和长对话记忆",
    keywords: ["Discord Bot", "Dimensional Inn", "次元旅馆", "长对话记忆", "记忆系统", "兼容酒馆"],
    queries: ["你做的酒馆 Bot 为什么要加记忆系统"],
  },
  {
    id: "authoring",
    heading: "角色卡生态和创作助手",
    keywords: ["角色卡创作助手", "角色卡作者", "卡片分发", "AI 写角色卡", "角色卡水印", "模型写作"],
  },
  {
    id: "monetization",
    heading: "AI Roleplay 怎么做商业化",
    keywords: ["AI 角色扮演商业化", "变现", "内容运营", "创作者经济", "擦边", "免费聊天"],
    queries: ["做 AI Roleplay 怎么赚钱"],
  },
  {
    id: "opportunities",
    heading: "音频、IP 和视频的切入机会",
    keywords: ["互动广播剧", "音频 Roleplay", "互动播客", "IP 运营", "行业机会"],
    queries: ["小团队做 AI Roleplay 有哪些切入点"],
  },
];
const sections = new Map(industryNotes.split(/\r?\n(?=#{2,3} )/u).slice(1).map((section) => {
  const [heading, ...body] = section.split(/\r?\n/u);
  return [heading.replace(/^#{2,3} /u, "").trim(), body.join("\n").trim()];
}));
for (const { id, heading, keywords, queries } of industryTopics) {
  const body = sections.get(heading);
  if (!body) throw new Error(`Missing industry notes section: ${heading}`);
  records.push({
    id: `roleplay-industry-${id}`,
    groupId: "roleplay-industry-2026-11",
    recordType: "industry_notes",
    publishedAt: "2026-11",
    title: heading,
    section: heading,
    body,
    tags: ["行业观察"],
    keywords,
    ...(queries ? { queries } : {}),
    source: industrySource,
    visibility: "public",
  });
}

await writeFile(outputPath, `${JSON.stringify(records, null, 2)}\n`, "utf8");
console.log(`Imported ${oralHistoryCount} original oral-history passages and ${industryTopics.length} reviewed industry notes passages.`);
