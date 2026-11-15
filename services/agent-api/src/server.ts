import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  buildSystemPrompt,
  estimateTextTokens,
  factContext,
  retrieveFacts,
  selectHistoryWithinBudget,
  shouldSearch,
  buildRuntimeContext,
  type FactSource,
  type AgentRequest,
  type ChatMessage,
} from "@mout/agent-core";
import { config, type ProviderName } from "./config.js";
import { providerModel, sseEvent, streamProvider } from "./provider.js";
import {
  archiveEnabled,
  beginArchiveTurn,
  completeArchiveTurn,
  getAdminConversation,
  listAdminConversations,
  updateAdminConversation,
  warmArchive,
} from "./archive.js";
import { adminConfigured, allowAdminLogin, clearAdminCookie, isAdminRequest, setAdminCookie, verifyAdminPassword } from "./admin-auth.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../");
let facts: Awaited<ReturnType<typeof loadFacts>> = [];
const hits = new Map<string, { count: number; resetAt: number }>();

async function loadFacts() {
  const raw = await readFile(resolve(root, "content/agent-public/facts.json"), "utf8");
  return JSON.parse(raw) as import("@mout/agent-core").PersonalFact[];
}

function originAllowed(origin: string | undefined): boolean {
  return !origin || config.allowedOrigins.includes(origin);
}

function setCors(req: IncomingMessage, res: ServerResponse) {
  const origin = req.headers.origin;
  if (originAllowed(origin)) {
    if (origin) res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, PATCH, OPTIONS");
  res.setHeader("Access-Control-Allow-Credentials", "true");
}

function sendJson(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage, maxBytes = 1_500_000): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const value = Buffer.from(chunk);
    size += value.length;
    if (size > maxBytes) throw new Error("请求体过大");
    chunks.push(value);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function clientKey(req: IncomingMessage): string {
  return String(req.headers["x-forwarded-for"] || req.socket.remoteAddress || "unknown").split(",")[0].trim();
}

function allowedRequest(req: IncomingMessage): boolean {
  const key = clientKey(req);
  const now = Date.now();
  const current = hits.get(key);
  if (!current || current.resetAt <= now) {
    hits.set(key, { count: 1, resetAt: now + 60_000 });
    return true;
  }
  current.count += 1;
  return current.count <= 20;
}

function originAllowedForAdmin(req: IncomingMessage): boolean {
  const origin = req.headers.origin;
  return !!origin && config.allowedOrigins.includes(origin);
}

function adminDenied(req: IncomingMessage, res: ServerResponse): boolean {
  if (!adminConfigured()) {
    sendJson(res, 503, { error: "管理员登录尚未配置" });
    return true;
  }
  if (!originAllowedForAdmin(req)) {
    sendJson(res, 403, { error: "origin 不被允许" });
    return true;
  }
  if (!isAdminRequest(req)) {
    sendJson(res, 401, { error: "需要管理员登录" });
    return true;
  }
  return false;
}

const CONTACT_INTENT = /(求职|找工作|应聘|招聘|岗位|职位|面试|内推|简历|猎头|职业机会|工作机会|合作|联名|商务|项目合作|咨询合作|想联系|联系你|联系MouT|联系Mout|与你聊聊|聊合作|一起做|work together|job opportunity|collaborat|partnership|hiring|recruiting)/iu;

function potentialContact(message: string): boolean {
  return CONTACT_INTENT.test(message);
}

function asRequest(value: unknown): AgentRequest {
  const input = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const message = typeof input.message === "string" ? input.message.trim() : "";
  if (!message || message.length > 8_000) throw new Error("message 必须是 1 到 8000 个字符");
  const conversationId = typeof input.conversationId === "string" ? input.conversationId.trim() : undefined;
  if (conversationId && !/^[a-zA-Z0-9_-]{8,128}$/.test(conversationId)) throw new Error("conversationId 格式不正确");
  const provider = input.provider === "deepseek" ? "deepseek" : input.provider === "gptproto" ? "gptproto" : undefined;
  const mode = input.mode === "about" || input.mode === "work" || input.mode === "opinion" || input.mode === "casual" ? input.mode : "casual";
  return { message, conversationId, timezone: typeof input.timezone === "string" ? input.timezone : undefined, history: Array.isArray(input.history) ? input.history as ChatMessage[] : [], provider, mode, model: typeof input.model === "string" ? input.model : undefined, source: input.source === "homepage" ? "homepage" : "im" };
}

async function handleChat(req: IncomingMessage, res: ServerResponse) {
  if (!allowedRequest(req)) return sendJson(res, 429, { error: "请求太频繁，请稍后再试" });
  let input: AgentRequest;
  try { input = asRequest(await readJson(req)); } catch (error) { return sendJson(res, 400, { error: error instanceof Error ? error.message : "请求格式不正确" }); }

  const provider = input.provider || config.defaultProvider;
  const model = providerModel(provider, input.model);
  const conversationId = input.conversationId || randomUUID();
  const search = shouldSearch(input.message);
  const retrievalQueries = [
    input.message,
    ...(input.history ?? []).filter((message) => message.role === "user").slice(-2).map((message) => message.content),
  ];
  const selectedFacts = retrieveFacts(retrievalQueries, facts, config.maxContextFacts);
  const runtimeContext = buildRuntimeContext(new Date(), config.timeZone, input.timezone);
  const systemPrompt = buildSystemPrompt(input.mode, factContext(selectedFacts), runtimeContext);
  const currentMessageTokens = estimateTextTokens(input.message) + 8;
  const historyBudget = Math.max(0,
    config.maxContextTokens
      - config.contextOutputReserveTokens
      - config.contextSafetyMarginTokens
      - estimateTextTokens(systemPrompt)
      - currentMessageTokens,
  );
  const history = selectHistoryWithinBudget(input.history, historyBudget, config.maxHistoryMessages);
  const factSources: FactSource[] = selectedFacts.map((fact) => {
    const project = fact.project;
    const projectPresentation = project
      && typeof project.name === "string"
      && typeof project.href === "string"
      && project.href.startsWith("/")
      && !project.href.startsWith("//")
      ? {
        name: project.name.slice(0, 100),
        href: project.href.slice(0, 240),
        ...(typeof project.eyebrow === "string" ? { eyebrow: project.eyebrow.slice(0, 80) } : {}),
        ...(typeof project.image === "string" && project.image.startsWith("/") && !project.image.startsWith("//") ? { image: project.image.slice(0, 240) } : {}),
      }
      : undefined;
    return {
      id: fact.id,
      title: fact.title,
      source: fact.source,
      kind: projectPresentation ? "project" : "profile",
      ...(projectPresentation ? { project: projectPresentation } : {}),
    };
  });
  const messages: ChatMessage[] = [
    { role: "system", content: systemPrompt },
    ...history,
    { role: "user", content: input.message },
  ];

  res.statusCode = 200;
  res.setHeader("X-Conversation-Id", conversationId);
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Content-Encoding", "identity");
  res.socket?.setNoDelay(true);
  res.flushHeaders?.();
  // A short SSE comment makes small early events pass through buffering proxies.
  res.write(`: stream-open${" ".repeat(2048)}\n\n`);
  res.write(sseEvent({ type: "status", value: search ? "searching" : "answering" }));
  if (factSources.length) res.write(sseEvent({ type: "fact_sources", sources: factSources }));
  if (potentialContact(input.message)) res.write(sseEvent({ type: "contact_prompt" }));

  // Start the archive write alongside generation; a sleeping database never delays the first token.
  const archiveTurnPromise = archiveEnabled() ? beginArchiveTurn({
    conversationId,
    source: input.source || "im",
    userMessage: input.message,
    title: input.message,
    potentialContact: potentialContact(input.message),
  }).catch((error) => {
    console.error("Unable to archive chat turn", error instanceof Error ? error.name : "DatabaseError");
    if (!res.destroyed && !res.writableEnded) {
      res.write(sseEvent({ type: "archive_warning", message: "这次对话暂时无法写入后台归档，但仍可继续聊天。" }));
    }
    return null;
  }) : Promise.resolve(null);

  let answer = "";
  let citations: Array<{ title: string; url: string }> = [];
  let answerStatus: "complete" | "error" = "complete";
  try {
    for await (const event of streamProvider(provider, { messages, model, stream: true, useWebSearch: search })) {
      if (event.type === "delta") answer += event.text;
      if (event.type === "citation") citations = [...citations, { title: event.title, url: event.url }];
      if (event.type === "error") answerStatus = "error";
      if (!res.destroyed && !res.writableEnded) res.write(sseEvent(event));
      await new Promise<void>((resolve) => setImmediate(resolve));
    }
  } catch (error) {
    answerStatus = "error";
    const message = error instanceof Error ? error.message : "上游请求失败";
    if (!res.destroyed && !res.writableEnded) res.write(sseEvent({ type: "error", message }));
  }
  if (!answer.trim()) answerStatus = "error";

  const archiveTurn = await archiveTurnPromise;
  if (archiveTurn) {
    try {
      await completeArchiveTurn({
        assistantMessageId: archiveTurn.assistantMessageId,
        conversationId: archiveTurn.conversationId,
        content: answer,
        status: answerStatus,
        model,
        provider,
        citations,
        factSources,
      });
    } catch (error) {
      console.error("Unable to finalize archived chat turn", error);
      if (!res.destroyed && !res.writableEnded) {
        res.write(sseEvent({ type: "archive_warning", message: "回复已生成，但这次对话暂未完成后台归档。" }));
      }
    }
  }
  res.end();
}

async function handleAdminLogin(req: IncomingMessage, res: ServerResponse) {
  if (!originAllowedForAdmin(req)) return sendJson(res, 403, { error: "origin 不被允许" });
  if (!adminConfigured()) return sendJson(res, 503, { error: "管理员登录尚未配置" });
  if (!allowAdminLogin(clientKey(req))) return sendJson(res, 429, { error: "登录尝试过多，请稍后再试" });
  let input: unknown;
  try { input = await readJson(req, 4_096); } catch { return sendJson(res, 400, { error: "请求格式不正确" }); }
  const password = input && typeof input === "object" ? (input as Record<string, unknown>).password : undefined;
  if (!verifyAdminPassword(password)) return sendJson(res, 401, { error: "密码不正确" });
  setAdminCookie(req, res);
  return sendJson(res, 200, { ok: true });
}

function handleAdminLogout(req: IncomingMessage, res: ServerResponse) {
  if (!originAllowedForAdmin(req)) return sendJson(res, 403, { error: "origin 不被允许" });
  clearAdminCookie(req, res);
  return sendJson(res, 200, { ok: true });
}

async function handleAdminRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (adminDenied(req, res)) return;
  if (req.method === "GET" && /^\/v1\/admin\/conversations(?:\?.*)?$/.test(req.url || "")) {
    const url = new URL(req.url || "/v1/admin/conversations", "http://localhost");
    const labelValue = url.searchParams.get("label") || "";
    if (labelValue && !["none", "job", "collaboration", "other"].includes(labelValue)) {
      return sendJson(res, 400, { error: "label 不正确" });
    }
    const contactValue = url.searchParams.get("potentialContact");
    if (contactValue && contactValue !== "true" && contactValue !== "false") {
      return sendJson(res, 400, { error: "potentialContact 不正确" });
    }
    try {
      const result = await listAdminConversations({
        limit: Math.min(100, Math.max(1, Number(url.searchParams.get("limit")) || 50)),
        offset: Math.min(100_000, Math.max(0, Number(url.searchParams.get("offset")) || 0)),
        query: (url.searchParams.get("q") || "").slice(0, 200),
        label: labelValue as "none" | "job" | "collaboration" | "other" | "",
        potentialContact: contactValue ? contactValue === "true" : undefined,
      });
      return sendJson(res, 200, result);
    } catch (error) {
      console.error("Unable to list archived conversations", error);
      return sendJson(res, 503, { error: "对话归档暂时不可用" });
    }
  }

  const detailMatch = req.url?.match(/^\/v1\/admin\/conversations\/([a-zA-Z0-9_-]{8,128})(?:\?.*)?$/);
  if (detailMatch && req.method === "GET") {
    try {
      const result = await getAdminConversation(detailMatch[1]);
      return result ? sendJson(res, 200, result) : sendJson(res, 404, { error: "conversation_not_found" });
    } catch (error) {
      console.error("Unable to read archived conversation", error);
      return sendJson(res, 503, { error: "对话归档暂时不可用" });
    }
  }

  if (detailMatch && req.method === "PATCH") {
    let input: unknown;
    try { input = await readJson(req, 8_192); } catch { return sendJson(res, 400, { error: "请求格式不正确" }); }
    const body = (input && typeof input === "object" ? input : {}) as Record<string, unknown>;
    const labels = ["none", "job", "collaboration", "other"];
    const statuses = ["unreviewed", "reviewing", "reviewed"];
    const qualities = ["unrated", "good", "needs_improvement"];
    const validLabel = body.label === undefined || labels.includes(String(body.label));
    const validStatus = body.reviewStatus === undefined || statuses.includes(String(body.reviewStatus));
    const validQuality = body.quality === undefined || qualities.includes(String(body.quality));
    const validNotes = body.notes === undefined || (typeof body.notes === "string" && body.notes.length <= 4_000);
    if (!validLabel || !validStatus || !validQuality || !validNotes || (body.label === undefined && body.reviewStatus === undefined && body.quality === undefined && body.notes === undefined)) {
      return sendJson(res, 400, { error: "label、reviewStatus 或 notes 不正确" });
    }
    try {
      const conversation = await updateAdminConversation(detailMatch[1], {
        label: body.label as "none" | "job" | "collaboration" | "other" | undefined,
        reviewStatus: body.reviewStatus as "unreviewed" | "reviewing" | "reviewed" | undefined,
        quality: body.quality as "unrated" | "good" | "needs_improvement" | undefined,
        notes: body.notes as string | undefined,
      });
      return conversation ? sendJson(res, 200, { conversation }) : sendJson(res, 404, { error: "conversation_not_found" });
    } catch (error) {
      console.error("Unable to update archived conversation", error);
      return sendJson(res, 503, { error: "对话归档暂时不可用" });
    }
  }

  sendJson(res, 404, { error: "not_found" });
}

const server = createServer(async (req, res) => {
  setCors(req, res);
  if (req.method === "OPTIONS") return res.end();
  if (!originAllowed(req.headers.origin)) return sendJson(res, 403, { error: "origin 不被允许" });
  if (req.method === "GET" && req.url === "/health") return sendJson(res, 200, { ok: true, provider: config.defaultProvider, model: config.defaultProvider === "deepseek" ? config.deepseek.model : config.gptproto.model, corpusFacts: facts.length, archiveEnabled: archiveEnabled() });
  if (req.method === "GET" && req.url === "/v1/warmup") {
    try { return sendJson(res, 200, await warmArchive()); }
    catch (error) {
      console.error("Archive warmup failed", error);
      return sendJson(res, 503, { ok: false, archived: true });
    }
  }
  if (req.method === "POST" && req.url === "/v1/chat") return handleChat(req, res);
  if (req.method === "POST" && req.url === "/v1/admin/login") return handleAdminLogin(req, res);
  if (req.method === "POST" && req.url === "/v1/admin/logout") return handleAdminLogout(req, res);
  if (req.url?.startsWith("/v1/admin/conversations")) return handleAdminRequest(req, res);
  return sendJson(res, 404, { error: "not_found" });
});

facts = await loadFacts();
server.listen(config.port, "0.0.0.0", () => console.log(`Agent API listening on http://0.0.0.0:${config.port}`));
