import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  buildSystemPrompt,
  clampHistory,
  factContext,
  retrieveFacts,
  shouldSearch,
  buildRuntimeContext,
  type AgentRequest,
  type ChatMessage,
} from "@mout/agent-core";
import { config, type ProviderName } from "./config.js";
import { providerModel, sseEvent, streamProvider } from "./provider.js";

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
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
}

function sendJson(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage, maxBytes = 128_000): Promise<unknown> {
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
  const search = shouldSearch(input.message);
  const selectedFacts = retrieveFacts(input.message, facts, config.maxContextFacts);
  const runtimeContext = buildRuntimeContext(new Date(), config.timeZone, input.timezone);
  const messages: ChatMessage[] = [
    { role: "system", content: buildSystemPrompt(input.mode, factContext(selectedFacts), runtimeContext) },
    ...clampHistory(input.history, config.maxHistoryMessages),
    { role: "user", content: input.message },
  ];

  res.statusCode = 200;
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
  for await (const event of streamProvider(provider, { messages, model: providerModel(provider, input.model), stream: true, useWebSearch: search })) {
    res.write(sseEvent(event));
    await new Promise<void>((resolve) => setImmediate(resolve));
  }
  res.end();
}

const server = createServer(async (req, res) => {
  setCors(req, res);
  if (req.method === "OPTIONS") return res.end();
  if (!originAllowed(req.headers.origin)) return sendJson(res, 403, { error: "origin 不被允许" });
  if (req.method === "GET" && req.url === "/health") return sendJson(res, 200, { ok: true, provider: config.defaultProvider, model: config.defaultProvider === "deepseek" ? config.deepseek.model : config.gptproto.model, corpusFacts: facts.length });
  if (req.method === "POST" && req.url === "/v1/chat") return handleChat(req, res);
  return sendJson(res, 404, { error: "not_found" });
});

facts = await loadFacts();
server.listen(config.port, "0.0.0.0", () => console.log(`Agent API listening on http://0.0.0.0:${config.port}`));
