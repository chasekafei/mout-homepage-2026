import { useEffect, useRef, useState } from "react";
import { MarkdownContent } from "@mout/chat-ui";
import type { DeepSeekToolStep, ProviderEvent } from "@mout/agent-core";
import { ABOUT, BOOKS, CATS, PRODUCTS, SCENES, type SceneId } from "../content/site";

type Go = (path: string) => void;

export function LegacyPanel() {
  return (
    <div className="legacy">
      <p className="lede">
        大学学 CSS3 时写的个人首页。没有一张切图，鼠标移到不同的 tab 上，方块会像魔方一样翻到对应的那一面。
        从那之后，它就一直没更新过，直到这个网站。
      </p>
      <ScaledFrame src="/legacy/index.html" title="旧个人首页：叫我小T" w={1000} h={720} />
      <p className="meta">当年的名字叫“叫我小T”，副标题是“给生活打个草稿……”。外链已经失效，页面原样保留。</p>
      <a className="cta" href="/legacy/index.html" target="_blank" rel="noreferrer">在新窗口打开 ↗</a>
    </div>
  );
}

function ScaledFrame({ src, title, w, h }: { src: string; title: string; w: number; h: number }) {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(0.5);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setK(e.contentRect.width / w));
    ro.observe(box.current!);
    return () => ro.disconnect();
  }, [w]);
  return (
    <div className="crt">
      <div ref={box} className="crt-screen" style={{ aspectRatio: `${w} / ${h}` }}>
        <iframe src={src} title={title} loading="lazy" style={{ width: w, height: h, transform: `scale(${k})` }} />
      </div>
    </div>
  );
}

type Photo = { cat: string; src: string; thumb: string; w: number; h: number };

export function CatsPanel({ who, scene, go }: { who: "shaojiu" | "xiaoba"; scene: SceneId; go: Go }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [big, setBig] = useState<Photo | null>(null);
  useEffect(() => { fetch("/media/cats/index.json").then((r) => r.json()).then(setPhotos).catch(() => {}); }, []);
  const cat = CATS[who];
  const other = who === "shaojiu" ? "xiaoba" : "shaojiu";
  const list = photos.filter((p) => p.cat === who || p.cat === "both");

  return (
    <div className="cats">
      <div className="cat-card">
        <div>
          <span className="meta">{cat.breed} · {cat.spot[scene]}</span>
          {cat.lines.map((l) => <p key={l}>{l}</p>)}
        </div>
        <button type="button" className="chip" onClick={() => go(`/${scene}/cats/${other}`)}>看看{CATS[other].name} →</button>
      </div>
      {big ? (
        <figure className="cat-big">
          <img src={big.src} width={big.w} height={big.h} alt={`${cat.name}的照片`} />
          <button type="button" className="chip" onClick={() => setBig(null)}>← 返回相册</button>
        </figure>
      ) : (
        <div className="cat-grid">
          {list.map((p, i) => (
            <button type="button" key={p.src} className="cat-thumb" onClick={() => setBig(p)} aria-label={`放大第 ${i + 1} 张`}>
              <img src={p.thumb} width={480} height={480} loading="lazy" alt="" />
              {p.cat === "both" && <span className="tag">合照</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AboutPanel({ go }: { go: Go }) {
  return (
    <div className="about">
      <div className="about-id">
        <img src="/media/me/avatar-pixel.png" width={96} height={96} alt="MouT.me 的像素头像" className="pixel" />
        <div>
          <p className="about-lead">{ABOUT.lead}</p>
          <div className="words">{ABOUT.words.map((w) => <span key={w}>{w}</span>)}</div>
        </div>
      </div>
      <p>{ABOUT.chain}</p>
      <section className="block">
        <div className="block-head"><h3>一些时间点</h3></div>
        <ol className="timeline">
          {ABOUT.timeline.map((x) => <li key={x.t}><span>{x.t}</span><p>{x.d}</p></li>)}
        </ol>
      </section>
      <section className="block">
        <div className="block-head"><h3>场外</h3></div>
        <p>{ABOUT.life}</p>
      </section>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/chat")}>和我的分身聊聊</button>
        {ABOUT.contact.map((c) => <a key={c.href} className="chip" href={c.href} target="_blank" rel="noreferrer">{c.label}</a>)}
      </div>
    </div>
  );
}

export function BooksPanel({ go }: { go: Go }) {
  const target = ["/create/writing", "/create/podcast", "/create/products", "/create/me"];
  return (
    <div className="books">
      <p className="lede">桌上立着的四本书，是我做东西时的四个动作。</p>
      <ol className="book-list">
        {BOOKS.map((b, i) => (
          <li key={b.spine} className={`book book-${i}`}>
            <button type="button" onClick={() => go(target[i])}>
              <span className="spine">{b.spine}</span>
              <span className="book-main"><strong>{b.zh}</strong><span>{b.d}</span></span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function WindowPanel({ go }: { go: Go }) {
  const places = ["新疆 · 北疆大环线", "格鲁吉亚 · 巴统", "日本 · 福冈 / 北海道 / 名古屋", "卡塔尔 · 多哈", "香港 · 澳门", "成都 · 重庆 · 大连 · 长沙"];
  return (
    <div className="window">
      <p className="lede">
        远程工作的那几年，我大部分时间在家办公，也常常带着电脑出发。很多次出门，是为了去现场看王楚钦和孙颖莎的比赛。
      </p>
      <ul className="places">{places.map((p) => <li key={p}>{p}</li>)}</ul>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/depart")}>去「出发」：坐进驾驶座</button>
      </div>
    </div>
  );
}

const FAQ = [
  { q: "你现在在做什么？", a: `离职后在休息，同时用 AI web coding 做自己的产品：CrossPod 串台、${PRODUCTS.map((p) => p.name).join("、")}，还有这个网站。` },
  { q: "你是做什么的？", a: "产品经理出身，做过电子政务、品牌营销小游戏、游戏创业、熟人社交，最近几年专注 AI 和 AI Agent。也会设计，会写代码。" },
  { q: "为什么做 CrossPod？", a: "因为看到一篇文章时，我更想听听身边某个人的看法。串台让你用朋友的分身开一期节目，它不一定最好，但一定最像你们。" },
  { q: "那两只猫叫什么？", a: "烧酒是狸花猫，小八是英短蓝白。在这个房间里，一个在桌角卷成一团，一个摊在麦克风旁边。" },
];

type LiveMessage = {
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  sources?: Array<{ id: string; title: string; source?: string; detail?: string; kind: "profile" | "project" | "web"; url?: string; project?: { name: string; href: string; eyebrow?: string } }>;
  contactPrompt?: boolean;
  deepseekToolCalls?: DeepSeekToolStep[];
};

const AGENT_API_URL = (import.meta.env.VITE_AGENT_API_URL as string | undefined)?.replace(/\/$/, "");
const IM_URL = (import.meta.env.VITE_IM_URL as string | undefined) || "https://im.mout.me/?source=homepage";

async function streamHomepageAgent(
  conversationId: string,
  message: string,
  history: LiveMessage[],
  onDelta: (text: string) => void,
  onStatus: (status: "searching" | "reading" | "answering") => void,
  onArchiveWarning: (message: string) => void,
  onSources: (sources: NonNullable<LiveMessage["sources"]>) => void,
  onContactPrompt: () => void,
  onProviderContext: (deepseekToolCalls: DeepSeekToolStep[]) => void,
  onToolWarning: (message: string) => void,
) {
  if (!AGENT_API_URL) {
    const lower = message.toLowerCase();
    const answer = lower.includes("猫")
      ? "烧酒是狸花猫，小八是英短蓝白。在网站的不同房间里，它们会出现在不同的位置。"
      : lower.includes("crosspod")
        ? "因为看到一篇文章时，我更想听听身边某个人的看法。CrossPod 让你用朋友的分身开一期播客，它不一定最专业，但希望最像真实朋友。"
        : lower.includes("agent") || lower.includes("分身")
      ? "我一直觉得，Agent 最重要的不是工具数量，而是它能不能进入真实的 context。做 Super Intern 的时候，我更在意 Agent 能不能待在用户已经在用的 Discord、Telegram 和工作流里。"
      : lower.includes("产品") || lower.includes("经历") || lower.includes("什么") || lower.includes("工作")
        ? "我做过 AI 拍照社交、AI VTuber、AI 信息社区和 Super Intern。它们看起来跨度很大，但我一直在追同一个问题：AI 怎么进入人已经在用的场景。"
        : "可以问我做过什么、为什么一直做 AI Agent，或者我怎么看待产品和设计。如果资料里没有，我会明确说不知道。";
    for (const part of answer.split(/(?<=[，。！？；：])/u)) {
      onDelta(part);
      await new Promise((resolve) => window.setTimeout(resolve, 24));
    }
    return;
  }

  const response = await fetch(`${AGENT_API_URL}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ conversationId, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, message, history, mode: "casual", source: "homepage" }),
  });
  if (!response.ok || !response.body) throw new Error(`分身暂时无法连接（${response.status}）`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === "[DONE]") continue;
      try {
        const event = JSON.parse(raw) as ProviderEvent;
        if (event.type === "status" && (event.value === "searching" || event.value === "reading" || event.value === "answering")) onStatus(event.value);
        if (event.type === "delta" && event.text) {
          onStatus("answering");
          onDelta(event.text);
        }
        if (event.type === "provider_context" && Array.isArray(event.deepseekToolCalls)) {
          onProviderContext(event.deepseekToolCalls);
        }
        if (event.type === "tool_error") {
          onToolWarning(event.tool === "deepseek_read_url"
            ? "网页暂时无法读取，这次回答可能缺少该网页的信息。"
            : "搜索暂时不可用，最新信息可能不完整。");
        }
        if (event.type === "archive_warning") onArchiveWarning(event.message || "本轮对话暂时没有归档");
        if (event.type === "contact_prompt") onContactPrompt();
        if (event.type === "citation" && typeof (event as { title?: unknown }).title === "string" && typeof (event as { url?: unknown }).url === "string") {
          const citation = event as { title: string; url: string };
          onSources([{ id: citation.url, title: citation.title, kind: "web", source: "实时来源", url: citation.url }]);
        }
        if (event.type === "fact_sources" && Array.isArray((event as { sources?: unknown }).sources)) {
          const sources = (event as { sources: unknown[] }).sources.filter((source): source is NonNullable<LiveMessage["sources"]>[number] => (
            !!source && typeof source === "object"
            && typeof (source as { id?: unknown }).id === "string"
            && typeof (source as { title?: unknown }).title === "string"
            && ["profile", "project"].includes(String((source as { kind?: unknown }).kind))
          ));
          onSources(sources);
        }
        if (event.type === "error") throw new Error(event.message || "分身暂时无法回答");
      } catch (error) {
        if (error instanceof SyntaxError) continue;
        throw error;
      }
    }
    if (done) break;
  }
}

function safeHomePath(value: string | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin ? `${url.pathname}${url.search}${url.hash}` : null;
  } catch { return null; }
}

export function ChatPanel() {
  const [conversationId] = useState(() => window.crypto?.randomUUID?.() ?? `homepage-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"searching" | "reading" | "answering" | "idle">("idle");
  const [error, setError] = useState("");
  const [archiveWarning, setArchiveWarning] = useState("");
  const [toolWarning, setToolWarning] = useState("");

  useEffect(() => {
    if (!AGENT_API_URL) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 8_000);
    fetch(`${AGENT_API_URL}/v1/warmup`, { signal: controller.signal }).catch(() => {}).finally(() => window.clearTimeout(timer));
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, []);

  const ask = async (value: string) => {
    const content = value.trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    setArchiveWarning("");
    setToolWarning("");
    const assistant: LiveMessage = { role: "assistant", content: "", pending: true };
    const next = [...messages, { role: "user" as const, content }, assistant];
    setMessages(next);
    setBusy(true);
    setStatus("answering");
    try {
      await streamHomepageAgent(conversationId, content, next.slice(0, -2), (text) => {
        assistant.content += text;
        setMessages([...next.slice(0, -1), { ...assistant }]);
      }, setStatus, setArchiveWarning, (sources) => {
        assistant.sources = [...(assistant.sources ?? []).filter((source) => !sources.some((item) => item.id === source.id)), ...sources];
        setMessages([...next.slice(0, -1), { ...assistant }]);
      }, () => {
        assistant.contactPrompt = true;
        setMessages([...next.slice(0, -1), { ...assistant }]);
      }, (deepseekToolCalls) => {
        assistant.deepseekToolCalls = deepseekToolCalls;
        setMessages([...next.slice(0, -1), { ...assistant }]);
      }, setToolWarning);
      assistant.pending = false;
      setMessages([...next.slice(0, -1), { ...assistant }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "分身暂时无法连接");
      setMessages(next.slice(0, -1));
    } finally {
      setBusy(false);
      setStatus("idle");
    }
  };

  return (
    <div className="chat chat-live">
      <p className="lede">几年前我用 Dify 做过一个“个人 AI 分身”。现在它住进了这个网站：你可以问我的经历、做过的产品和一些公开表达过的观点。</p>
      <div className="chat-log" aria-live="polite">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`qa qa-${message.role}`}>
            <div className={`bubble bubble-${message.role === "user" ? "q" : "a"}`}>
              <MarkdownContent content={message.content} className="home-chat-markdown" />{message.pending && <span className="chat-caret" />}
            </div>
            {!!message.sources?.length && <div className="home-chat-sources"><span>本轮检索资料</span>{message.sources.map((source) => <div className={`home-chat-source home-chat-source-${source.kind}`} key={source.id}><small>{source.source || source.detail || (source.kind === "web" ? "实时来源" : "公开资料")}</small><strong>{source.title}</strong>{source.kind === "project" && source.project && safeHomePath(source.project.href) && <a href={safeHomePath(source.project.href)!}>{source.project.name} · 查看项目</a>}{source.kind === "web" && source.url && /^https?:\/\//i.test(source.url) && <a href={source.url} target="_blank" rel="noopener noreferrer nofollow">打开来源 ↗</a>}</div>)}</div>}
            {message.contactPrompt && <div className="home-contact-prompt"><span>想继续聊工作或合作？</span><a href="mailto:hello@mout.me?subject=%E6%9D%A5%E8%87%AA%20MouT.me%20AI%20%E5%88%86%E8%BA%AB">联系 MouT</a></div>}
          </div>
        ))}
        {status === "searching" && <p className="chat-status">正在查找公开来源…</p>}
        {status === "reading" && <p className="chat-status">正在阅读网页…</p>}
        {error && <p className="chat-error">{error}</p>}
        {archiveWarning && <p className="chat-status">{archiveWarning}</p>}
        {toolWarning && <p className="chat-status" role="status">{toolWarning}</p>}
      </div>
      <form className="chat-form" onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="问我做过什么，或者为什么这样想…" aria-label="输入问题" disabled={busy} />
        <button type="submit" className="chip" disabled={busy || !input.trim()}>{busy ? "回答中" : "发送"}</button>
      </form>
      <div className="chat-chips">
        {FAQ.map((f) => <button type="button" key={f.q} className="chip" onClick={() => void ask(f.q)} disabled={busy}>{f.q}</button>)}
      </div>
      <a className="chat-open" href={IM_URL} target="_blank" rel="noreferrer">打开完整的分身页面 ↗</a>
    </div>
  );
}

export function IndexPanel({ scene, go }: { scene: SceneId; go: Go }) {
  return (
    <div className="index">
      <p className="lede">不想在场景里找东西的话，这里是{SCENES[scene].label}场景里全部的内容。</p>
      <ul className="index-list">
        {SCENES[scene].hotspots.map((h) => (
          <li key={h.id}>
            <a href={`/${scene}/${h.route}`} onClick={(e) => { e.preventDefault(); go(`/${scene}/${h.route}`); }}>
              <span className="hover-kind">{h.kind}</span>
              <strong>{h.label}</strong>
              <span>{h.hint}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
