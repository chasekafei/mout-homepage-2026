import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { selectHistoryWithinBudget } from "@mout/agent-core";
import { AgentEvent, AgentMode, AgentSource, ChatMessage, isMockMode, streamChat, warmAgentBackend } from "./api";
import { MarkdownContent } from "@mout/chat-ui";
import "./styles.css";

type IconName = "arrow" | "back" | "book" | "chevron" | "close" | "external" | "globe" | "spark";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const props = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", xmlns: "http://www.w3.org/2000/svg", "aria-hidden": true };
  if (name === "arrow") return <svg {...props}><path d="M12 4v16M5 13l7 7 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "back") return <svg {...props}><path d="M19 12H5m6-6-6 6 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "book") return <svg {...props}><path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H20v17H7.5A2.5 2.5 0 0 0 5 21.5m0-17v17M5 4.5A2.5 2.5 0 0 1 7.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "chevron") return <svg {...props}><path d="m8 10 4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "close") return <svg {...props}><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
  if (name === "external") return <svg {...props}><path d="M14 5h5v5M19 5l-8 8M19 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "globe") return <svg {...props}><circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.5" /><path d="M3.8 12h16.4M12 3.5c2.2 2.4 3.2 5.2 3.2 8.5S14.2 18.1 12 20.5C9.8 18.1 8.8 15.3 8.8 12S9.8 5.9 12 3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>;
  return <svg {...props}><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Zm6.2 13.1.8 2.1 2.1.8-2.1.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8.8-2.1Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" /></svg>;
}

const QUICK_PROMPTS = [
  { label: "你做过哪些 AI 产品？", text: "你做过哪些 AI 产品？" },
  { label: "为什么一直做 Agent？", text: "你为什么一直在做 Agent？" },
  { label: "从哪里开始了解你？", text: "如果我想了解你，应该从哪里开始？" },
];

const makeId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const CONVERSATIONS_KEY = "mout.im.conversations.v1";
const MAX_STORED_MESSAGES = 256;
const MAX_CONVERSATIONS = 12;
const ACTIVE_STORAGE_BUDGET = 116_000;
const ARCHIVE_STORAGE_BUDGET = 12_000;

type StoredConversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  mode: AgentMode;
  messages: ChatMessage[];
};

type ConversationState = { activeId: string; conversations: StoredConversation[] };

function newConversation(): StoredConversation {
  return {
    id: window.crypto?.randomUUID?.() ?? makeId("conversation"),
    title: "新的对话",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    mode: "profile",
    messages: [],
  };
}

function loadConversationState(): ConversationState {
  const fallback = newConversation();
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    if (!raw) return { activeId: fallback.id, conversations: [fallback] };
    const parsed = JSON.parse(raw) as Partial<ConversationState>;
    const conversations = Array.isArray(parsed.conversations)
      ? parsed.conversations.map((item) => ({
        id: typeof item.id === "string" ? item.id : makeId("conversation"),
        title: typeof item.title === "string" ? item.title : "新的对话",
        createdAt: typeof item.createdAt === "number" ? item.createdAt : Date.now(),
        updatedAt: typeof item.updatedAt === "number" ? item.updatedAt : Date.now(),
        mode: item.mode === "current" ? "current" as const : "profile" as const,
        messages: Array.isArray(item.messages) ? item.messages.filter((message): message is ChatMessage => (
          !!message && (message.role === "user" || message.role === "assistant") && typeof message.content === "string"
        )).map((message) => ({ ...message, pending: false })).slice(-MAX_STORED_MESSAGES) : [],
      })).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_CONVERSATIONS)
      : [];
    if (!conversations.length) return { activeId: fallback.id, conversations: [fallback] };
    const activeId = typeof parsed.activeId === "string" && conversations.some((item) => item.id === parsed.activeId)
      ? parsed.activeId
      : conversations[0].id;
    return { activeId, conversations };
  } catch {
    return { activeId: fallback.id, conversations: [fallback] };
  }
}

function conversationDate(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(timestamp);
}

type MessageSetter = (value: ChatMessage[] | ((current: ChatMessage[]) => ChatMessage[])) => void;

/** Smooths provider-sized chunks into a readable stream without hiding the real network latency. */
function createTextReveal(setMessages: MessageSetter, messageId: string) {
  let queue = "";
  let timer = 0;
  let finished = false;
  let resolveDone: (() => void) | null = null;
  const done = new Promise<void>((resolve) => { resolveDone = resolve; });

  const finalize = () => {
    setMessages((current) => current.map((message) => message.id === messageId ? { ...message, pending: false } : message));
    resolveDone?.();
    resolveDone = null;
  };

  const drain = () => {
    if (!queue) {
      timer = 0;
      if (finished) finalize();
      return;
    }
    const chars = Array.from(queue);
    const take = chars.length > 80 ? 4 : chars.length > 24 ? 2 : 1;
    const text = chars.slice(0, take).join("");
    queue = chars.slice(take).join("");
    setMessages((current) => current.map((message) => message.id === messageId ? { ...message, content: message.content + text, pending: true } : message));
    timer = window.setTimeout(drain, 18);
  };

  return {
    push(text: string) {
      queue += text;
      if (!timer) drain();
    },
    finish() {
      finished = true;
      if (!timer) drain();
      return done;
    },
  };
}

function timeLabel(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(timestamp);
}

function SourceRow({ source }: { source: AgentSource }) {
  let externalUrl: string | null = null;
  if (source.kind === "web" && source.url) {
    try {
      const candidate = new URL(source.url);
      if (candidate.protocol === "http:" || candidate.protocol === "https:") externalUrl = candidate.href;
    } catch {
      externalUrl = null;
    }
  }
  const content = (
    <>
      <span className={`source-mark source-${source.kind}`} aria-hidden><Icon name={source.kind === "web" ? "globe" : "book"} size={15} /></span>
      <span className="source-copy"><strong>{source.title}</strong><small>{source.detail ?? source.source ?? (source.kind === "web" ? "实时来源" : "公开资料")}</small></span>
      {externalUrl && <Icon name="external" size={14} />}
    </>
  );
  return externalUrl ? <a className="source-row" href={externalUrl} target="_blank" rel="noopener noreferrer nofollow">{content}</a> : <div className="source-row">{content}</div>;
}

function AssistantMark({ small = false }: { small?: boolean }) {
  return <span className={`assistant-mark ${small ? "assistant-mark-small" : ""}`}><img src="/avatar-pixel.png" alt="" className="pixel" />{!small && <i />}</span>;
}

function safeLocalPath(value: string | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin ? `${url.pathname}${url.search}${url.hash}` : null;
  } catch { return null; }
}

function ProjectSource({ source }: { source: AgentSource }) {
  const href = safeLocalPath(source.project?.href);
  if (!href || !source.project) return null;
  const image = safeLocalPath(source.project.image);
  return (
    <a className="project-source" href={`https://mout.me${href}`} target="_blank" rel="noreferrer">
      {image ? <img src={`https://mout.me${image}`} alt="" loading="lazy" /> : <span className="project-source-mark"><Icon name="spark" size={17} /></span>}
      <span className="project-source-copy">{source.project.eyebrow && <small>{source.project.eyebrow}</small>}<strong>{source.project.name}</strong><span>{source.title}</span></span>
      <Icon name="external" size={15} />
    </a>
  );
}

export function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const cameFromHomepage = params.get("source") === "homepage";
  const [conversationState, setConversationState] = useState<ConversationState>(loadConversationState);
  const [input, setInput] = useState("");
  const activeConversation = conversationState.conversations.find((item) => item.id === conversationState.activeId) ?? conversationState.conversations[0];
  const messages = activeConversation?.messages ?? [];
  const [mode, setMode] = useState<AgentMode>(() => activeConversation?.mode ?? "profile");
  const [isStreaming, setIsStreaming] = useState(false);
  const [searching, setSearching] = useState(false);
  const [sources, setSources] = useState<AgentSource[]>([]);
  const [archiveWarning, setArchiveWarning] = useState("");
  const [error, setError] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);

  useEffect(() => { void warmAgentBackend(); }, []);

  const setMessages: MessageSetter = (value) => {
    setConversationState((state) => ({
      ...state,
      conversations: state.conversations.map((conversation) => {
        if (conversation.id !== state.activeId) return conversation;
        const nextMessages = (typeof value === "function" ? value(conversation.messages) : value).slice(-MAX_STORED_MESSAGES);
        const firstUser = nextMessages.find((message) => message.role === "user");
        return {
          ...conversation,
          title: conversation.title === "新的对话" && firstUser ? firstUser.content.slice(0, 28) : conversation.title,
          updatedAt: Date.now(),
          messages: nextMessages,
        };
      }),
    }));
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const conversations = [...conversationState.conversations]
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, MAX_CONVERSATIONS)
        .map((conversation) => ({
          ...conversation,
          messages: selectHistoryWithinBudget(
            conversation.messages,
            conversation.id === conversationState.activeId ? ACTIVE_STORAGE_BUDGET : ARCHIVE_STORAGE_BUDGET,
            MAX_STORED_MESSAGES,
          ),
        }));
      try {
        localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify({ activeId: conversationState.activeId, conversations }));
      } catch {
        // Persistence must not interrupt the live conversation if browser storage is full or disabled.
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [conversationState]);

  useEffect(() => {
    if (activeConversation) setMode(activeConversation.mode);
  }, [activeConversation?.id]);

  useEffect(() => {
    const node = conversationRef.current;
    if (!node || messages.length === 0) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages, searching]);

  const changeMode = (nextMode: AgentMode) => {
    if (isStreaming) return;
    setMode(nextMode);
    setConversationState((state) => ({
      ...state,
      conversations: state.conversations.map((conversation) => conversation.id === state.activeId ? { ...conversation, mode: nextMode, updatedAt: Date.now() } : conversation),
    }));
  };

  const startNewConversation = () => {
    if (isStreaming) return;
    const conversation = newConversation();
    setConversationState((state) => ({ activeId: conversation.id, conversations: [conversation, ...state.conversations].slice(0, MAX_CONVERSATIONS) }));
    setMode("profile");
    setSources([]);
    setError("");
    setSearching(false);
    setShowContext(false);
    setShowHistory(false);
    inputRef.current?.focus();
  };

  const switchConversation = (id: string) => {
    if (isStreaming || id === conversationState.activeId) {
      setShowHistory(false);
      return;
    }
    const conversation = conversationState.conversations.find((item) => item.id === id);
    if (!conversation) return;
    setConversationState((state) => ({ ...state, activeId: id }));
    setMode(conversation.mode);
    setSources([]);
    setError("");
    setSearching(false);
    setShowContext(false);
    setShowHistory(false);
  };

  const send = async (value = input) => {
    const content = value.trim();
    if (!content || isStreaming) return;
    setInput("");
    setError("");
    const user: ChatMessage = { id: makeId("user"), role: "user", content, createdAt: Date.now() };
    const assistant: ChatMessage = { id: makeId("assistant"), role: "assistant", content: "", createdAt: Date.now(), pending: true };
    const next = [...messages, user, assistant];
    setMessages(next);
    setSources([]);
    setArchiveWarning("");
    setShowContext(false);
    setSearching(false);
    setIsStreaming(true);
    const reveal = createTextReveal(setMessages, assistant.id);
    try {
      const requestMessages = next.filter((message) => !message.pending).map(({ role, content: text }) => ({ role, content: text }));
      await streamChat({ conversationId: conversationState.activeId, messages: requestMessages, mode, source: cameFromHomepage ? "homepage" : "im" }, (event: AgentEvent) => {
        if (event.type === "meta") setSearching(Boolean(event.searching));
        if (event.type === "source") {
          setSources((current) => current.some((item) => item.id === event.source.id) ? current : [...current, event.source]);
          setMessages((current) => current.map((message) => message.id === assistant.id
            ? { ...message, sources: [...(message.sources ?? []).filter((source) => source.id !== event.source.id), event.source] }
            : message));
          setShowContext(true);
        }
        if (event.type === "fact_sources") {
          const factSources = event.sources.filter((source) => source.kind === "profile" || source.kind === "project");
          setSources((current) => [...current.filter((source) => source.kind === "web"), ...factSources]);
          setMessages((current) => current.map((message) => message.id === assistant.id ? { ...message, sources: factSources } : message));
          if (factSources.length) setShowContext(true);
        }
        if (event.type === "contact_prompt") {
          setMessages((current) => current.map((message) => message.id === assistant.id ? { ...message, contactPrompt: true } : message));
        }
        if (event.type === "archive_warning") setArchiveWarning(event.message);
        if (event.type === "delta") {
          reveal.push(event.text);
        }
        if (event.type === "done") {
          void reveal.finish();
          setSearching(false);
        }
        if (event.type === "error") {
          setError(event.message);
        }
      });
      await reveal.finish();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "暂时无法连接分身";
      setError(message);
      setMessages((current) => current.filter((item) => item.id !== assistant.id));
    } finally {
      setIsStreaming(false);
      setSearching(false);
    }
  };

  const handleSubmit = (event: FormEvent) => { event.preventDefault(); void send(); };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault(); void send();
    }
  };
  const clear = () => { if (isStreaming) return; setMessages([]); setSources([]); setShowContext(false); setError(""); inputRef.current?.focus(); };

  return (
    <div className="im-app">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <header className="im-topbar">
        <a className="back-home" href={cameFromHomepage ? "https://mout.me/" : "https://mout.me/"}><Icon name="back" size={17} /><span>回到 MouT.me</span></a>
        <div className="top-brand"><span className="top-brand-dot" /><span>MouT<em>.me</em></span><small>/ AI clone</small></div>
        <div className="top-actions">
          <span className="connection-state"><i />{isMockMode ? "预览模式" : "在线"}</span>
          <button className="history-button" type="button" onClick={() => setShowHistory(true)}>历史 {conversationState.conversations.length}</button>
          <button className="new-chat-button" type="button" onClick={startNewConversation}>新对话</button>
          {messages.length > 0 && <button className="clear-button" type="button" onClick={clear}>清空对话</button>}
        </div>
      </header>

      <div className="im-layout">
        <aside className="identity-rail" aria-label="分身介绍">
          <div className="portrait-frame"><img src="/avatar-pixel.png" alt="MouT 的完整像素头像" className="pixel" /></div>
          <div className="identity-copy"><span className="eyebrow">PERSONAL CLONE 01</span><h1>和我的分身聊聊</h1><p>不在的时候，你可以先从这里了解我。</p></div>
          <div className="identity-note"><span className="quote-mark">“</span><p>表面情绪稳定，脑子里一直在施工。</p><span className="quote-author">— MouT</span></div>
          <div className="identity-meta"><div><span>身份</span><strong>AI 产品经理</strong></div><div><span>在这里聊</span><strong>经历 · 产品 · 想法</strong></div></div>
          <a className="studio-link" href="https://mout.me/work" target="_blank" rel="noreferrer"><span>进入我的工作场景</span><Icon name="external" size={15} /></a>
        </aside>

        <main className="chat-column">
          <div className="conversation" ref={conversationRef} aria-live="polite">
            {messages.length === 0 ? (
              <section className="welcome-view">
                <div className="welcome-orbit"><div className="orbit-line orbit-line-a" /><div className="orbit-line orbit-line-b" /><AssistantMark /></div>
                <p className="welcome-kicker">MouT 的公开分身</p>
                <h2>从一个问题开始，<br /><span>了解我怎么想。</span></h2>
                <p className="welcome-intro">我会基于自己的经历和公开资料回答。你可以问我做过什么，也可以问我为什么这样做。</p>
                <div className="quick-prompts">{QUICK_PROMPTS.map((prompt) => <button key={prompt.text} type="button" onClick={() => void send(prompt.text)}>{prompt.label}<Icon name="arrow" size={15} /></button>)}</div>
              </section>
            ) : (
              <div className="message-list">
                <div className="conversation-intro"><span className="eyebrow">OPEN CONVERSATION</span><span>{messages.length / 2 >= 1 ? "继续聊下去" : "刚刚开始"}</span></div>
                {messages.map((message) => (
                  <article className={`message message-${message.role}`} key={message.id}>
                    {message.role === "assistant" ? <AssistantMark small /> : <span className="user-mark">你</span>}
                    <div className="message-body">
                      <div className="message-head"><strong>{message.role === "assistant" ? "MouT 的分身" : "你"}</strong><time>{timeLabel(message.createdAt)}</time></div>
                      {message.role === "assistant" && message.pending && !message.content
                        ? searching ? <div className="searching-state"><span className="searching-pulse" /><span>正在查找公开来源</span></div> : <div className="thinking-state">正在组织回答<span className="thinking-dots" aria-hidden>···</span></div>
                        : <MarkdownContent content={message.content} className={`message-markdown ${message.role === "user" ? "user-markdown" : ""}`} />}
                      {message.role === "assistant" && message.pending && message.content && <span className="stream-caret" />}
                      {message.role === "assistant" && !!message.sources?.length && <div className="message-sources">
                        <button className="inline-sources" type="button" onClick={() => { setSources(message.sources ?? []); setShowContext(true); }}><Icon name="book" size={14} />本轮检索资料 {message.sources.length}</button>
                        <div className="project-source-list">{message.sources.filter((source) => source.kind === "project" && source.project).map((source) => <ProjectSource key={source.id} source={source} />)}</div>
                      </div>}
                      {message.role === "assistant" && message.contactPrompt && <div className="contact-prompt"><span>想继续聊工作或合作？</span><a href="mailto:hello@mout.me?subject=%E6%9D%A5%E8%87%AA%20MouT.me%20AI%20%E5%88%86%E8%BA%AB">联系 MouT<Icon name="external" size={14} /></a></div>}
                    </div>
                  </article>
                ))}
                {archiveWarning && <p className="archive-warning" role="status">{archiveWarning}</p>}
                {error && <div className="error-note"><span>连接中断</span>{error}<button type="button" onClick={() => void send(messages.at(-2)?.content ?? "")}>重试</button></div>}
              </div>
            )}
          </div>

          <div className="composer-wrap">
            <div className="composer-mode"><span className="mode-pulse" /><span>{mode === "profile" ? "公开资料模式" : "实时信息模式"}</span><button type="button" onClick={() => changeMode(mode === "profile" ? "current" : "profile")} aria-label="切换回答模式"><Icon name="chevron" size={15} /></button></div>
            <form className={`composer ${isStreaming ? "is-streaming" : ""}`} onSubmit={handleSubmit}>
              <textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleKeyDown} rows={1} placeholder={mode === "profile" ? "问我做过什么，或者为什么这样想…" : "想查什么最新信息？"} aria-label="输入问题" disabled={isStreaming} />
              <div className="composer-bottom"><span className="composer-hint"><kbd>Enter</kbd> 发送 <span>·</span> <kbd>Shift</kbd><span>+</span><kbd>Enter</kbd> 换行</span><button className="send-button" type="submit" disabled={!input.trim() || isStreaming} aria-label="发送问题"><Icon name="arrow" size={19} /></button></div>
            </form>
            <p className="composer-footnote">这是 MouT 的 AI 分身，回答来自他的公开资料。答案可能会有偏差。</p>
          </div>
        </main>

        <aside className={`context-rail ${showContext ? "is-open" : ""}`} aria-label="回答来源">
          <div className="context-header"><div><span className="eyebrow">CONTEXT</span><h2>本轮检索资料</h2></div><button type="button" onClick={() => setShowContext(false)} aria-label="关闭来源面板"><Icon name="close" size={18} /></button></div>
          {searching ? <div className="context-searching"><span className="search-ring" /><strong>正在查找最新信息</strong><p>只在问题需要时连接公开网络。</p></div> : sources.length > 0 ? <><p className="context-lede">这些是本轮检索到并注入上下文的个人资料与外部来源，不代表模型一定逐条引用。</p><div className="source-list">{sources.map((source) => <SourceRow key={source.id} source={source} />)}</div></> : <div className="context-empty"><Icon name="book" size={22} /><p>本轮检索到的资料会显示在这里。</p></div>}
          <div className="context-bottom"><span className="context-signal" /><span>{mode === "profile" ? "个人资料已启用" : "实时搜索已启用"}</span></div>
        </aside>
      </div>

      {showContext && <button className="context-scrim" type="button" onClick={() => setShowContext(false)} aria-label="关闭来源面板" />}
      {showHistory && <>
        <button className="history-scrim" type="button" onClick={() => setShowHistory(false)} aria-label="关闭历史对话" />
        <aside className="history-panel" aria-label="历史对话">
          <div className="history-panel-head"><div><span className="eyebrow">CONVERSATIONS</span><h2>我的对话</h2></div><button type="button" onClick={() => setShowHistory(false)} aria-label="关闭历史对话"><Icon name="close" size={18} /></button></div>
          <button className="history-new" type="button" onClick={startNewConversation}><span>＋</span>开始新对话</button>
          <div className="history-list">
            {conversationState.conversations.map((conversation) => <button key={conversation.id} className={`history-item ${conversation.id === conversationState.activeId ? "is-active" : ""}`} type="button" onClick={() => switchConversation(conversation.id)}><strong>{conversation.title}</strong><small>{conversation.messages.length ? `${Math.ceil(conversation.messages.length / 2)} 条消息 · ` : "空对话 · "}{conversationDate(conversation.updatedAt)}</small></button>)}
          </div>
          <p className="history-note">对话保存在当前浏览器中。每次回答会按上下文预算带入最近的完整问答轮次。</p>
        </aside>
      </>}
      <footer className="im-footer"><span>一个个人网站里的小小 Agent</span><span className="footer-rule" /><a href="mailto:hello@mout.me">联系 MouT</a></footer>
    </div>
  );
}
