import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { warmAgentBackend } from "./api";
import "./admin.css";

type ReviewLabel = "none" | "job" | "collaboration" | "other";
type ReviewStatus = "unreviewed" | "reviewing" | "reviewed";
type AnswerQuality = "unrated" | "good" | "needs_improvement";
type ConversationSummary = {
  id: string;
  title: string;
  source: "im" | "homepage";
  createdAt: string | number;
  lastActivityAt: string | number;
  messageCount: number;
  preview: string;
  label: ReviewLabel;
  reviewStatus: ReviewStatus;
  quality: AnswerQuality;
  potentialContact: boolean;
};
type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string | number;
  provider?: string;
  model?: string;
  status?: string;
  citations?: Array<{ title: string; url: string }>;
};
type ConversationDetail = ConversationSummary & { notes: string; messages: ConversationMessage[] };
type ApiError = Error & { status?: number };

const API_URL = (import.meta.env.VITE_AGENT_API_URL as string | undefined)?.replace(/\/$/, "");
const PAGE_SIZE = 40;

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) throw new Error("没有配置 Agent API 地址");
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  const body = await response.json().catch(() => ({})) as { error?: string };
  if (!response.ok) {
    const error = new Error(body.error || `请求失败 (${response.status})`) as ApiError;
    error.status = response.status;
    throw error;
  }
  return body as T;
}

function dateTime(value: string | number) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

const labelText: Record<ReviewLabel, string> = { none: "未分类", job: "求职", collaboration: "合作", other: "其他" };
function Icon({ name }: { name: "search" | "close" | "back" | "logout" | "external" }) {
  const props = { width: 17, height: 17, viewBox: "0 0 24 24", fill: "none", xmlns: "http://www.w3.org/2000/svg", "aria-hidden": true };
  if (name === "search") return <svg {...props}><circle cx="10.8" cy="10.8" r="6.4" stroke="currentColor" strokeWidth="1.7" /><path d="m16 16 4.2 4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>;
  if (name === "close") return <svg {...props}><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>;
  if (name === "back") return <svg {...props}><path d="M19 12H5m6-6-6 6 6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (name === "logout") return <svg {...props}><path d="M10 5H5v14h5m4-3 4-4-4-4m4 4H9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  return <svg {...props}><path d="M14 5h5v5M19 5l-8 8M19 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function AdminApp() {
  const [authorized, setAuthorized] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [labelFilter, setLabelFilter] = useState<"all" | ReviewLabel>("all");
  const [contactOnly, setContactOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const listRequestId = useRef(0);
  const detailRequestId = useRef(0);
  const detailAbort = useRef<AbortController | null>(null);
  const patchRequestId = useRef(0);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const loadConversations = useCallback(async (nextOffset = 0, append = false) => {
    const requestId = ++listRequestId.current;
    setLoadingList(true);
    setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(nextOffset) });
    if (appliedQuery.trim()) params.set("q", appliedQuery.trim());
    if (labelFilter !== "all") params.set("label", labelFilter);
    if (contactOnly) params.set("potentialContact", "true");
    try {
      const result = await adminRequest<{ items: ConversationSummary[]; total: number }>(`/v1/admin/conversations?${params}`);
      if (requestId !== listRequestId.current) return;
      setItems((current) => append ? [...current, ...result.items] : result.items);
      setOffset(nextOffset);
      setTotal(result.total);
      if (!append && result.items.length === 0) {
        setSelectedId("");
        setDetail(null);
      } else if (!append && (!selectedId || !result.items.some((item) => item.id === selectedId))) {
        setSelectedId(result.items[0]?.id ?? "");
      }
    } catch (reason) {
      if (requestId !== listRequestId.current) return;
      const err = reason as ApiError;
      if (err.status === 401) setAuthorized(false);
      else setError(err.message || "无法加载对话");
    } finally {
      if (requestId === listRequestId.current) setLoadingList(false);
    }
  }, [appliedQuery, labelFilter, contactOnly, selectedId]);

  const loadDetail = useCallback(async (id: string) => {
    const requestId = ++detailRequestId.current;
    detailAbort.current?.abort();
    if (!id) {
      setDetail(null);
      setLoadingDetail(false);
      return;
    }
    const controller = new AbortController();
    detailAbort.current = controller;
    setLoadingDetail(true);
    setError("");
    try {
      const result = await adminRequest<{ conversation: Omit<ConversationDetail, "messages">; messages: ConversationMessage[] }>(`/v1/admin/conversations/${encodeURIComponent(id)}`, { signal: controller.signal });
      if (requestId !== detailRequestId.current) return;
      const next = { ...result.conversation, messages: result.messages };
      setDetail(next);
      setNotes(next.notes || "");
    } catch (reason) {
      if (requestId !== detailRequestId.current) return;
      const err = reason as ApiError;
      if (err.status === 401) setAuthorized(false);
      else setError(err.message || "无法加载对话内容");
    } finally {
      if (requestId === detailRequestId.current) setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    document.title = "对话收件箱 · MouT.me";
  }, []);

  useEffect(() => {
    void warmAgentBackend();
    adminRequest<{ items: ConversationSummary[]; total: number }>("/v1/admin/conversations?limit=1&offset=0")
      .then(() => setAuthorized(true))
      .catch((reason) => {
        const err = reason as ApiError;
        if (err.status !== 401) setError(err.message || "无法连接 Agent API");
      })
      .finally(() => {
        setCheckingAuth(false);
      });
  }, []);

  useEffect(() => {
    if (authorized) void loadConversations();
  }, [authorized, appliedQuery, labelFilter, contactOnly]);

  useEffect(() => {
    if (authorized && selectedId) void loadDetail(selectedId);
    else if (!selectedId) {
      detailAbort.current?.abort();
      setDetail(null);
      setLoadingDetail(false);
    }
    return () => {
      detailRequestId.current += 1;
      detailAbort.current?.abort();
    };
  }, [authorized, selectedId, loadDetail]);

  const counts = useMemo(() => ({
    unreviewed: items.filter((item) => item.reviewStatus === "unreviewed").length,
    potential: items.filter((item) => item.potentialContact || item.label === "job" || item.label === "collaboration").length,
  }), [items]);

  const login = async (event: FormEvent) => {
    event.preventDefault();
    setLoginError("");
    try {
      await adminRequest("/v1/admin/login", { method: "POST", body: JSON.stringify({ password }) });
      setPassword("");
      setAuthorized(true);
    } catch (reason) {
      setLoginError((reason as Error).message || "密码不正确");
    }
  };

  const logout = async () => {
    try { await adminRequest("/v1/admin/logout", { method: "POST", body: "{}" }); } catch { /* local view still exits */ }
    setAuthorized(false);
    setItems([]);
    setDetail(null);
    setSelectedId("");
  };

  const updateDetail = async (patch: { label?: ReviewLabel; reviewStatus?: ReviewStatus; quality?: AnswerQuality; notes?: string }) => {
    if (!detail) return;
    const targetId = detail.id;
    const requestId = ++patchRequestId.current;
    setSaving(true);
    setNotice("");
    try {
      await adminRequest<{ conversation: Omit<ConversationDetail, "messages"> }>(`/v1/admin/conversations/${encodeURIComponent(targetId)}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setItems((current) => current.map((item) => item.id === targetId ? { ...item, ...patch } : item));
      if (selectedIdRef.current === targetId) {
        setDetail((current) => current?.id === targetId ? { ...current, ...patch, messages: current.messages } : current);
        if (typeof patch.notes === "string") setNotice("备注已保存");
      }
    } catch (reason) {
      if (selectedIdRef.current === targetId) setError((reason as Error).message || "保存失败");
    } finally {
      if (requestId === patchRequestId.current) setSaving(false);
    }
  };

  const applySearch = (event: FormEvent) => {
    event.preventDefault();
    setSelectedId("");
    setAppliedQuery(query);
  };

  if (checkingAuth) return <div className="admin-screen admin-checking"><span className="admin-spinner" /><span>正在连接收件箱</span></div>;

  if (!authorized) return (
    <main className="admin-screen admin-login-screen">
      <header className="admin-login-brand"><a href="/">MouT<em>.me</em></a><span>PRIVATE INBOX</span></header>
      <section className="admin-login-form">
        <span className="admin-kicker">OWNER ACCESS</span>
        <h1>对话收件箱</h1>
        <p>输入管理密码查看访客对话。</p>
        <form onSubmit={(event) => void login(event)}>
          <label htmlFor="admin-password">管理密码</label>
          <input id="admin-password" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required />
          {error && <div className="admin-error">{error}</div>}
          {loginError && <div className="admin-error">{loginError}</div>}
          <button className="admin-primary" type="submit">进入收件箱</button>
        </form>
      </section>
      <footer className="admin-login-foot">MouT.me · Personal Agent</footer>
    </main>
  );

  return (
    <main className="admin-screen">
      <header className="admin-header">
        <a className="admin-brand" href="/"><span className="admin-brand-mark">M</span><span>MouT<em>.me</em></span><i>/</i><strong>对话收件箱</strong></a>
        <div className="admin-header-right"><span><i className="admin-live-dot" />已连接</span><button type="button" onClick={() => void logout()}><Icon name="logout" />退出</button></div>
      </header>

      <section className={`admin-workspace ${selectedId ? "has-selection" : ""}`}>
        <aside className="admin-list-pane">
          <div className="admin-list-title"><div><span className="admin-kicker">CONVERSATION ARCHIVE</span><h1>访客对话</h1></div><span className="admin-total">{total}</span></div>
          <div className="admin-summary"><div><strong>{counts.unreviewed}</strong><span>本页待复盘</span></div><div><strong>{counts.potential}</strong><span>本页可能联系</span></div></div>
          <form className="admin-search" onSubmit={applySearch}><Icon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索对话内容" aria-label="搜索对话内容" /><button type="submit">搜索</button></form>
          <div className="admin-filters" role="group" aria-label="按意向筛选">
            {(["all", "job", "collaboration", "other"] as const).map((label) => <button key={label} type="button" className={labelFilter === label ? "is-selected" : ""} onClick={() => { setSelectedId(""); setLabelFilter(label); }}>{label === "all" ? "全部" : labelText[label]}</button>)}
          </div>
          <button className={`admin-contact-filter ${contactOnly ? "is-selected" : ""}`} type="button" onClick={() => { setSelectedId(""); setContactOnly((value) => !value); }}>可能联系 <span>{counts.potential}</span></button>
          <div className="admin-list" aria-busy={loadingList}>
            {error && <p className="admin-inline-error">{error}</p>}
            {items.map((item) => <button key={item.id} type="button" className={`admin-conversation ${selectedId === item.id ? "is-active" : ""}`} onClick={() => setSelectedId(item.id)}>
              <span className={`admin-status-dot is-${item.reviewStatus}`} />
              <span className="admin-conversation-copy"><strong>{item.title || "新对话"}</strong><span>{item.preview || "暂无消息"}</span><small>{dateTime(item.lastActivityAt)} · {item.messageCount} 条消息</small></span>
              <span className="admin-row-badges">{item.potentialContact && <span className="admin-label-mark label-contact">可能联系</span>}{item.label !== "none" && <span className={`admin-label-mark label-${item.label}`}>{labelText[item.label]}</span>}{item.quality === "needs_improvement" && <span className="admin-label-mark label-quality">待改进</span>}</span>
            </button>)}
            {!loadingList && items.length === 0 && <div className="admin-empty-list"><strong>还没有对话</strong><span>访客开始聊天后会显示在这里。</span></div>}
            {items.length < total && <button className="admin-load-more" type="button" disabled={loadingList} onClick={() => void loadConversations(offset + PAGE_SIZE, true)}>{loadingList ? "加载中…" : "加载更多"}</button>}
          </div>
        </aside>

        <section className="admin-transcript-pane" aria-label="对话内容">
          {detail ? <>
            <div className="admin-transcript-head"><div><span className="admin-kicker">{detail.source === "homepage" ? "MOUT.ME" : "IM.MOUT.ME"} · {detail.id.slice(0, 8)}</span><h2>{detail.title || "新对话"}</h2><p>开始于 {dateTime(detail.createdAt)} · 最近活动 {dateTime(detail.lastActivityAt)}</p>{detail.potentialContact && <span className="admin-potential-note">可能包含求职或合作意向 · 请人工确认</span>}</div><button className="admin-icon-button mobile-back" type="button" onClick={() => setSelectedId("")} aria-label="返回对话列表"><Icon name="back" /></button></div>
            <div className="admin-transcript" aria-busy={loadingDetail}>
              {loadingDetail ? <div className="admin-transcript-loading"><span className="admin-spinner" />正在载入对话</div> : detail.messages.map((message) => <article key={message.id} className={`archive-message archive-${message.role}`}>
                <div className="archive-message-meta"><strong>{message.role === "user" ? "访客" : "MouT 的分身"}</strong><time>{dateTime(message.createdAt)}</time>{message.role === "assistant" && message.model && <span>{message.model}</span>}{message.status && message.status !== "complete" && <span className="archive-message-status">{message.status}</span>}</div>
                <p>{message.content || (message.status === "pending" ? "回答生成中…" : "（无文本内容）")}</p>
                {!!message.citations?.length && <div className="archive-citations">{message.citations.map((citation) => <a key={citation.url} href={citation.url} target="_blank" rel="noreferrer">{citation.title || citation.url}<Icon name="external" /></a>)}</div>}
              </article>)}
              {detail.messages.length === 0 && !loadingDetail && <div className="admin-empty-transcript">这个对话还没有消息。</div>}
            </div>
          </> : <div className="admin-empty-detail"><span className="admin-kicker">INBOX</span><h2>选择一段对话</h2><p>完整提问和 Agent 回答会显示在这里。</p></div>}
        </section>

        <aside className="admin-review-pane" aria-label="复盘信息">
          {detail ? <>
            <div className="admin-review-title"><span className="admin-kicker">REVIEW</span><h2>复盘信息</h2></div>
            <label className="admin-field"><span>意向分类</span><select disabled={saving} value={detail.label} onChange={(event) => void updateDetail({ label: event.target.value as ReviewLabel })}><option value="none">未分类</option><option value="job">求职</option><option value="collaboration">合作</option><option value="other">其他</option></select></label>
            <label className="admin-field"><span>复盘状态</span><select disabled={saving} value={detail.reviewStatus} onChange={(event) => void updateDetail({ reviewStatus: event.target.value as ReviewStatus })}><option value="unreviewed">未读</option><option value="reviewing">复盘中</option><option value="reviewed">已复盘</option></select></label>
            <label className="admin-field"><span>回答质量</span><select disabled={saving} value={detail.quality} onChange={(event) => void updateDetail({ quality: event.target.value as AnswerQuality })}><option value="unrated">未评价</option><option value="good">回答不错</option><option value="needs_improvement">需要改进</option></select></label>
            <label className="admin-field admin-notes-field"><span>我的备注</span><textarea rows={7} value={notes} onChange={(event) => { setNotes(event.target.value); setNotice(""); }} placeholder="记录事实错误、表达偏差或待跟进事项…" /></label>
            <button className="admin-primary admin-save-notes" type="button" disabled={saving || notes === (detail.notes || "")} onClick={() => void updateDetail({ notes })}>{saving ? "保存中…" : notice || "保存备注"}</button>
            <dl className="admin-metadata"><div><dt>入口</dt><dd>{detail.source === "homepage" ? "个人网站 3D 场景" : "im.mout.me"}</dd></div><div><dt>消息数</dt><dd>{detail.messageCount}</dd></div><div><dt>会话 ID</dt><dd>{detail.id}</dd></div></dl>
          </> : <div className="admin-empty-review">选择对话后可添加分类与复盘备注。</div>}
        </aside>
      </section>
    </main>
  );
}
