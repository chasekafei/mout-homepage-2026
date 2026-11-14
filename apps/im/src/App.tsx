import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { AgentEvent, AgentMode, AgentSource, ChatMessage, isMockMode, streamChat } from "./api";
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

function timeLabel(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(timestamp);
}

function SourceRow({ source }: { source: AgentSource }) {
  const external = source.kind === "web" && source.url;
  const content = (
    <>
      <span className={`source-mark source-${source.kind}`} aria-hidden><Icon name={source.kind === "web" ? "globe" : "book"} size={15} /></span>
      <span className="source-copy"><strong>{source.title}</strong><small>{source.detail ?? (source.kind === "web" ? "实时来源" : "公开资料")}</small></span>
      {external && <Icon name="external" size={14} />}
    </>
  );
  return external ? <a className="source-row" href={source.url} target="_blank" rel="noreferrer">{content}</a> : <div className="source-row">{content}</div>;
}

function AssistantMark({ small = false }: { small?: boolean }) {
  return <span className={`assistant-mark ${small ? "assistant-mark-small" : ""}`}><img src="/avatar-pixel.png" alt="" className="pixel" />{!small && <i />}</span>;
}

export function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const cameFromHomepage = params.get("source") === "homepage";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<AgentMode>("profile");
  const [isStreaming, setIsStreaming] = useState(false);
  const [searching, setSearching] = useState(false);
  const [sources, setSources] = useState<AgentSource[]>([]);
  const [error, setError] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [sessionId] = useState(() => window.crypto?.randomUUID?.() ?? makeId("session"));
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = conversationRef.current;
    if (!node || messages.length === 0) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages, searching]);

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
    setShowContext(false);
    setSearching(false);
    setIsStreaming(true);
    try {
      const requestMessages = next.filter((message) => !message.pending).map(({ role, content: text }) => ({ role, content: text }));
      await streamChat({ sessionId, messages: requestMessages, mode, source: cameFromHomepage ? "homepage" : "im" }, (event: AgentEvent) => {
        if (event.type === "meta") setSearching(Boolean(event.searching));
        if (event.type === "source") {
          setSources((current) => current.some((item) => item.id === event.source.id) ? current : [...current, event.source]);
          setShowContext(true);
        }
        if (event.type === "delta") {
          setMessages((current) => current.map((message) => message.id === assistant.id ? { ...message, content: message.content + event.text, pending: true } : message));
        }
        if (event.type === "done") {
          setMessages((current) => current.map((message) => message.id === assistant.id ? { ...message, pending: false } : message));
          setSearching(false);
        }
        if (event.type === "error") {
          setError(event.message);
          setMessages((current) => current.map((message) => message.id === assistant.id ? { ...message, pending: false } : message));
        }
      });
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
          {messages.length > 0 && <button className="clear-button" type="button" onClick={clear}>清空对话</button>}
        </div>
      </header>

      <div className="im-layout">
        <aside className="identity-rail" aria-label="分身介绍">
          <div className="portrait-frame"><img src="/photo.webp" alt="MouT" /><span className="portrait-pixel"><img src="/avatar-pixel.png" alt="" className="pixel" /></span></div>
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
                    <div className="message-body"><div className="message-head"><strong>{message.role === "assistant" ? "MouT 的分身" : "你"}</strong><time>{timeLabel(message.createdAt)}</time></div>{message.role === "assistant" && searching && !message.content ? <div className="searching-state"><span className="searching-pulse" /><span>正在查找公开来源</span></div> : <p>{message.content}{message.pending && <span className="stream-caret" />}</p>}{message.role === "assistant" && message.content && !message.pending && sources.length > 0 && message.id === messages.at(-1)?.id && <button className="inline-sources" type="button" onClick={() => setShowContext(true)}><Icon name="book" size={14} />基于 {sources.length} 个来源</button>}</div>
                  </article>
                ))}
                {error && <div className="error-note"><span>连接中断</span>{error}<button type="button" onClick={() => void send(messages.at(-2)?.content ?? "")}>重试</button></div>}
              </div>
            )}
          </div>

          <div className="composer-wrap">
            <div className="composer-mode"><span className="mode-pulse" /><span>{mode === "profile" ? "公开资料模式" : "实时信息模式"}</span><button type="button" onClick={() => setMode(mode === "profile" ? "current" : "profile")} aria-label="切换回答模式"><Icon name="chevron" size={15} /></button></div>
            <form className={`composer ${isStreaming ? "is-streaming" : ""}`} onSubmit={handleSubmit}>
              <textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleKeyDown} rows={1} placeholder={mode === "profile" ? "问我做过什么，或者为什么这样想…" : "想查什么最新信息？"} aria-label="输入问题" disabled={isStreaming} />
              <div className="composer-bottom"><span className="composer-hint"><kbd>Enter</kbd> 发送 <span>·</span> <kbd>Shift</kbd><span>+</span><kbd>Enter</kbd> 换行</span><button className="send-button" type="submit" disabled={!input.trim() || isStreaming} aria-label="发送问题"><Icon name="arrow" size={19} /></button></div>
            </form>
            <p className="composer-footnote">这是 MouT 的 AI 分身，回答来自他的公开资料。答案可能会有偏差。</p>
          </div>
        </main>

        <aside className={`context-rail ${showContext ? "is-open" : ""}`} aria-label="回答来源">
          <div className="context-header"><div><span className="eyebrow">CONTEXT</span><h2>这次回答</h2></div><button type="button" onClick={() => setShowContext(false)} aria-label="关闭来源面板"><Icon name="close" size={18} /></button></div>
          {searching ? <div className="context-searching"><span className="search-ring" /><strong>正在查找最新信息</strong><p>只在问题需要时连接公开网络。</p></div> : sources.length > 0 ? <><p className="context-lede">回答优先使用 MouT 的公开资料；外部来源会单独标记。</p><div className="source-list">{sources.map((source) => <SourceRow key={source.id} source={source} />)}</div></> : <div className="context-empty"><Icon name="book" size={22} /><p>当回答引用资料时，来源会出现在这里。</p></div>}
          <div className="context-bottom"><span className="context-signal" /><span>{mode === "profile" ? "个人资料已启用" : "实时搜索已启用"}</span></div>
        </aside>
      </div>

      {showContext && <button className="context-scrim" type="button" onClick={() => setShowContext(false)} aria-label="关闭来源面板" />}
      <footer className="im-footer"><span>一个个人网站里的小小 Agent</span><span className="footer-rule" /><a href="mailto:hello@mout.me">联系 MouT</a></footer>
    </div>
  );
}
