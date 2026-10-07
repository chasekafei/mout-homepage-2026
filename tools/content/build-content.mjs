// Converts ref/社思现场 markdown into JSON consumed by the writing layer.
import { readdir, readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Marked } from "marked";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SRC = path.join(ROOT, "ref/社思现场-全部内容-Markdown");
const OUT = path.join(ROOT, "public/content/newsletter");

const marked = new Marked({
  gfm: true,
  renderer: {
    image({ href, text }) {
      return `<img src="${href}" alt="${text === "img" || text === "thumbnail" ? "" : text}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
    },
    link({ href, tokens }) {
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.parser.parseInline(tokens)}</a>`;
    },
  },
});

function parse(md, file) {
  const lines = md.replace(/\r/g, "").split("\n");
  const titleLine = lines.find((l) => l.startsWith("# ")) ?? file;
  const title = titleLine.replace(/^#\s+/, "").trim();
  const volMatch = title.match(/VOL\.(\d+)/i);
  const vol = volMatch ? Number(volMatch[1]) : 0;
  const subtitle = (title.match(/[:：\s]\s*\[?(试刊号)\]?/) || [])[1] ?? "";
  const dateLine = lines.find((l) => /^·\d{4}-\d{2}-\d{2}/.test(l));
  const date = dateLine ? dateLine.slice(1).trim() : "";

  let body = lines.slice(lines.indexOf(titleLine) + 1);
  body = body.filter((l, i) => {
    const t = l.trim();
    if (t === "图片加载中") return false;
    if (i < 8 && (t === "MouT.me" || /^·\d{4}/.test(t))) return false;
    if (i < 4 && /^!\[img\]\(https:\/\/imgs\.zhubai\.love\/a5f3110231f8/.test(t)) return false;
    return true;
  });
  const footer = body.findIndex((l) => l.trim() === "Thanks for reading.");
  if (footer >= 0) body = body.slice(0, footer);

  const items = [];
  let section = "";
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  body = body.flatMap((l) => {
    const h = l.match(/^#{1,3}\s+(.+)$/);
    if (!h) return [l];
    const raw = h[1].trim();
    const url = (raw.match(/\]\((https?:[^)]+)\)/) || [])[1];
    const plain = raw.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").trim();
    const num = plain.match(/^(\d{1,2})\.\s*(.+)$/);
    if (!num && !url && plain.length <= 8) {
      section = plain;
      return ["", `<h2 class="nl-section">${esc(plain)}</h2>`, ""];
    }
    const n = num ? num[1].padStart(2, "0") : "";
    const title = num ? num[2].trim() : plain;
    const id = `i${items.length + 1}`;
    items.push({ id, section, n, title });
    const label = url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>` : esc(title);
    return ["", `<h3 class="nl-item" id="${id}">${n ? `<span class="nl-num">${n}</span>` : ""}${label}</h3>`, ""];
  });

  const range = (body.find((l) => /^>\s*补发/.test(l)) || "").replace(/^>\s*/, "");
  const src = body.join("\n").replace(/\]\(\s*(https?:\/\/[^\s)]+)[^)]*\)/g, "]($1)");
  const html = marked.parse(src);
  const words = html.replace(/<[^>]+>/g, "").replace(/\s+/g, "").length;
  return { slug: `vol-${String(vol).padStart(2, "0")}`, vol, title: `社思现场 VOL.${String(vol).padStart(2, "0")}`, subtitle, date, range, items, words, html };
}

const files = (await readdir(SRC)).filter((f) => f.endsWith(".md")).sort();
await mkdir(OUT, { recursive: true });
const index = [];
for (const f of files) {
  const issue = parse(await readFile(path.join(SRC, f), "utf8"), f);
  await writeFile(path.join(OUT, `${issue.slug}.json`), JSON.stringify(issue));
  const { html: _html, ...meta } = issue;
  index.push(meta);
}
index.sort((a, b) => b.vol - a.vol);
await writeFile(path.join(OUT, "index.json"), JSON.stringify(index, null, 1));
console.log(`newsletter: ${index.length} issues -> ${path.relative(ROOT, OUT)}`);
