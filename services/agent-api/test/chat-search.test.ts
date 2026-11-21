import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

test("chat preserves the source and type of live and research evidence in SSE", { timeout: 20_000 }, async () => {
  const requests: Array<{ path: string; body: any }> = [];
  let searchHasResults = true;
  let vercelFails = false;
  const gateway = createServer(async (req, res) => {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    requests.push({ path: req.url || "", body });
    if (req.url === "/v1/tools/fetch") {
      res.setHeader("Content-Type", "application/json");
      return res.end(JSON.stringify({ title: "读取的网页", content: "# PAGEONLYFACT\n网页正文与当前问题有关。" }));
    }
    if (req.url === "/v1/chat/completions") {
      if (vercelFails) { res.statusCode = 429; return res.end("overloaded"); }
      res.setHeader("Content-Type", "text/event-stream");
      const frames = [
        { id: "gen_gateway_diagnostic", choices: [{ delta: { reasoning: "不可下发的内部思考" } }] },
        { id: "gen_gateway_diagnostic", choices: [{ delta: { content: "来自 Vercel 的正文。" }, finish_reason: "stop" }] },
        { id: "gen_gateway_diagnostic", choices: [], usage: { prompt_tokens: 100, completion_tokens: 28, total_tokens: 128, completion_tokens_details: { reasoning_tokens: 20 } } },
      ];
      return res.end(frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("") + "data: [DONE]\n\n");
    }
    if (req.url === "/v1/tools/search") {
      res.setHeader("Content-Type", "application/json");
      return res.end(JSON.stringify({ results: searchHasResults ? [{
        title: "可核对的产品发布", url: "https://example.com/release", date: "2026-11-18T00:00:00Z",
        summary: "Search 返回的独有事实：示例产品发布了功能 X。", snippet: "功能 X 已发布。", rerank_score: 2.5,
      }] : [] }));
    }
    if (req.url?.startsWith("/v1beta/models/gemini-4-hydrogen:streamGenerateContent")) {
      res.setHeader("Content-Type", "text/event-stream");
      if (body.systemInstruction.parts[0].text.includes("JanitorAI 的托管入口")) {
        const frames = ["它支持平台提供的后端。[[", "R1", "]] [[R999]]"];
        return res.end(frames.map((text, i) => `data: ${JSON.stringify({ candidates: [{
          content: { parts: [{ text }] }, ...(i === frames.length - 1 ? { finishReason: "STOP" } : {}),
        }] })}\n\n`).join(""));
      }
      return res.end(`data: ${JSON.stringify({ candidates: [{
        content: { parts: [{ text: searchHasResults ? "示例产品发布了功能 X。来源：https://example.com/release" : "暂时没有可核验的实时信息。" }] }, finishReason: "STOP",
      }] })}\n\n`);
    }
    res.statusCode = 404;
    res.end();
  });
  await new Promise<void>((resolve) => gateway.listen(0, "127.0.0.1", resolve));
  const gatewayAddress = gateway.address();
  assert.ok(gatewayAddress && typeof gatewayAddress === "object");
  const baseUrl = `http://127.0.0.1:${gatewayAddress.port}/v1`;

  const child = spawn(process.execPath, [
    "--import", fileURLToPath(new URL("../node_modules/tsx/dist/loader.mjs", import.meta.url)),
    fileURLToPath(new URL("../src/server.ts", import.meta.url)),
  ], { env: {
    ...process.env, PORT: "0", DEFAULT_PROVIDER: "gptproto", GPTPROTO_MODEL: "gemini-4-hydrogen",
    GPTPROTO_API_KEY: "test-key", GPTPROTO_BASE_URL: baseUrl,
    VERCEL_AI_API_KEY: "test-vercel-key", VERCEL_AI_BASE_URL: baseUrl, AGENT_PROVIDER_ORDER: "vercel,gptproto",
    DEEPSEEK_API_KEY: "test-key", DEEPSEEK_BASE_URL: baseUrl,
    AGENT_EMBEDDING_LEXICAL_CONFIDENCE_THRESHOLD: "0", DATABASE_URL: "", ADMIN_PASSWORD: "", ADMIN_SESSION_SECRET: "",
  }, stdio: ["ignore", "pipe", "pipe"] });
  let logs = "";
  child.stderr.on("data", (data) => { logs += String(data); });
  try {
    const apiUrl = await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`API did not start: ${logs}`)), 10_000);
      child.once("exit", () => { clearTimeout(timer); reject(new Error(`API exited: ${logs}`)); });
      child.stdout.on("data", (data) => {
        logs += String(data);
        const match = logs.match(/Agent API listening on http:\/\/0\.0\.0\.0:(\d+)/u);
        if (match && match[1] !== "0") { clearTimeout(timer); resolve(`http://127.0.0.1:${match[1]}`); }
      });
    });
    const chat = async (provider = "gptproto", message = "今天有什么 AI 新闻吗？你怎么看？") => {
      const response = await fetch(`${apiUrl}/v1/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, provider, model: "gemini-4-hydrogen" }),
      });
      assert.equal(response.status, 200);
      return (await response.text()).split("\n").filter((line) => line.startsWith("data:"))
        .map((line) => JSON.parse(line.slice(5)));
    };
    const events = await chat();
    assert.ok(events.some((event) => event.type === "citation" && event.url === "https://example.com/release"));
    assert.ok(events.some((event) => event.type === "delta" && event.text.includes("功能 X")));
    assert.ok(!events.some((event) => event.type === "tool_error" || event.type === "error"));
    assert.equal(requests[0].path, "/v1/tools/search");
    assert.match(requests[0].body.query, /^\d{4}-\d{2}-\d{2}/u);
    const firstModel = requests.find((item) => item.path.startsWith("/v1beta/models/"));
    assert.ok(firstModel);
    assert.match(firstModel.body.systemInstruction.parts[0].text, /Search 返回的独有事实/u);
    assert.match(firstModel.body.systemInstruction.parts[0].text, /https:\/\/example.com\/release/u);
    assert.ok(!firstModel.body.tools?.some((tool: any) => tool.google_search || tool.googleSearch));

    searchHasResults = false;
    const emptyEvents = await chat();
    assert.ok(emptyEvents.some((event) => event.type === "tool_error" && event.code === "search_evidence_unavailable"));
    assert.ok(!emptyEvents.some((event) => event.type === "citation"));
    const secondModel = requests.filter((item) => item.path.startsWith("/v1beta/models/")).at(-1);
    assert.ok(secondModel.body.tools.some((tool: any) => tool.google_search || tool.googleSearch));

    searchHasResults = true;
    const gatewayEvents = await chat("auto");
    assert.ok(gatewayEvents.some((event) => event.type === "status" && event.provider === "vercel"));
    assert.ok(!gatewayEvents.some((event) => event.type === "provider_diagnostics"));
    assert.ok(!JSON.stringify(gatewayEvents).includes("gen_gateway_diagnostic"));
    assert.ok(!JSON.stringify(gatewayEvents).includes("不可下发的内部思考"));
    assert.equal(gatewayEvents.find((event) => event.type === "done").usage.reasoningTokens, 20);
    const gatewayModel = requests.filter((item) => item.path === "/v1/chat/completions").at(-1);
    assert.equal(gatewayModel.body.model, "google/gemini-4-hydrogen");
    assert.match(gatewayModel.body.messages[0].content, /Search 返回的独有事实/u);

    vercelFails = true;
    const before = requests.length;
    const fallbackEvents = await chat("auto");
    const attempts = requests.slice(before);
    assert.equal(attempts.filter((item) => item.path === "/v1/tools/search").length, 1);
    assert.ok(attempts.some((item) => item.path === "/v1/chat/completions"));
    assert.ok(attempts.some((item) => item.path.startsWith("/v1beta/models/")));
    assert.equal(fallbackEvents.filter((event) => event.type === "citation").length, 1);
    assert.equal(fallbackEvents.filter((event) => event.type === "done").length, 1);
    assert.equal(fallbackEvents.filter((event) => event.type === "delta").map((event) => event.text).join(""), "示例产品发布了功能 X。来源：https://example.com/release");
    assert.equal(fallbackEvents.filter((event) => event.type === "status").at(-1).provider, "gptproto");
    assert.ok(!fallbackEvents.some((event) => event.type === "error"));

    vercelFails = false;
    const beforeRead = requests.length;
    const pageEvents = await chat("auto", "概括 https://example.com/page");
    const pageRequests = requests.slice(beforeRead);
    assert.equal(pageRequests.filter((item) => item.path === "/v1/tools/fetch").length, 1);
    assert.equal(pageRequests.filter((item) => item.path === "/v1/tools/search").length, 0);
    assert.match(pageRequests.find((item) => item.path === "/v1/chat/completions")!.body.messages[0].content, /PAGEONLYFACT/u);
    assert.ok(pageEvents.some((event) => event.type === "citation" && event.url === "https://example.com/page"));
    assert.ok(!pageEvents.some((event) => event.type === "error"));
    const research = await chat("gptproto", "JanitorAI 的 Janitor Router 怎么用？");
    const researchSources = research.find((event) => event.type === "fact_sources")?.sources;
    assert.ok(researchSources?.some((source: any) => source.kind === "research"));
    assert.ok(researchSources?.every((source: any) => source.kind === "research"));
    const citation = research.find((event) => event.type === "citation");
    assert.equal(citation?.origin, "research");
    assert.equal(new URL(citation.url).hostname, "help.janitorai.com");
    const rendered = research.filter((event) => event.type === "delta").map((event) => event.text).join("");
    assert.match(rendered, /\[出处 1\]\(<https:\/\/help.janitorai.com\//u);
    assert.doesNotMatch(rendered, /\[\[R/u);
    assert.match(logs, /index loaded: 1\d{3} records/u);
    assert.match(logs, /retrieval selected \[\{"id":/u);
    assert.match(logs, /"responseId":"gen_gateway_diagnostic"/u);
    assert.match(logs, /"reasoningTokens":20/u);
  } finally {
    child.kill("SIGTERM");
    gateway.closeAllConnections();
    await new Promise<void>((resolve) => gateway.close(() => resolve()));
  }
});
