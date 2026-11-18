import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

test("chat obtains structured search sources before asking Hydrogen and exposes them in SSE", { timeout: 20_000 }, async () => {
  const requests: Array<{ path: string; body: any }> = [];
  let searchHasResults = true;
  const gateway = createServer(async (req, res) => {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    requests.push({ path: req.url || "", body });
    if (req.url === "/v1/tools/search") {
      res.setHeader("Content-Type", "application/json");
      return res.end(JSON.stringify({ results: searchHasResults ? [{
        title: "可核对的产品发布", url: "https://example.com/release", date: "2026-11-18T00:00:00Z",
        summary: "Search 返回的独有事实：示例产品发布了功能 X。", snippet: "功能 X 已发布。", rerank_score: 2.5,
      }] : [] }));
    }
    if (req.url?.startsWith("/v1beta/models/gemini-4-hydrogen:streamGenerateContent")) {
      res.setHeader("Content-Type", "text/event-stream");
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
    const chat = async () => {
      const response = await fetch(`${apiUrl}/v1/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "今天有什么 AI 新闻吗？你怎么看？", provider: "gptproto", model: "gemini-4-hydrogen" }),
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
  } finally {
    child.kill("SIGTERM");
    gateway.closeAllConnections();
    await new Promise<void>((resolve) => gateway.close(() => resolve()));
  }
});
