# MouT 个人 Agent

个人 Agent 由两个前端入口和一个服务端组成：

- `apps/im`：部署到 `im.mout.me` 的独立聊天页；
- 当前根应用：个人网站里的 `/chat` 对话层，使用同一套 API；
- `services/agent-api`：部署到 Railway、Vercel Function 或其他 Node/Edge 运行时的服务端；
- `packages/agent-core`：人格规则、公开资料检索和请求类型；
- `content/agent-public`：允许公开回答的个人资料小段落。

## Neon 对话归档

创建 Neon Postgres 项目后，建议选择离 Railway API 较近的 region，并从 Neon 控制台复制 pooled connection string，作为 Railway 的 `DATABASE_URL`。Neon URL 常带 `sslmode=require`；API 会将驱动旧别名显式规范为等效的 `sslmode=verify-full`，保留 `channel_binding` 等其他参数。

API 在收到 `/v1/warmup` 或聊天请求时惰性建表；页面首次打开只做一次带 4 秒超时的预热，不会定时 ping。Neon 空闲后会暂停 compute；归档使用低连接数池，闲置连接 30 秒释放。

在 Railway 设置：

```text
DATABASE_URL=<Neon pooled connection string>
ADMIN_PASSWORD=<你的后台密码>
ADMIN_SESSION_SECRET=<至少 32 字符的随机密钥>
ALLOWED_ORIGINS=https://mout.me,https://www.mout.me,https://im.mout.me,http://localhost:5173,http://localhost:5174
```

可用 `openssl rand -hex 32` 生成 `ADMIN_SESSION_SECRET`。Neon 连接串和两个管理凭据只放在 Railway Variables，不要放进 Vercel 或提交到 Git。

把 Railway API 服务绑定到 `api.mout.me`，并确保 Vercel 主站和 `apps/im` 都将 `VITE_AGENT_API_URL` 设为 `https://api.mout.me`。管理 cookie 使用 `HttpOnly; SameSite=Strict`，因此 `im.mout.me` 与 API 必须是 `mout.me` 下的同站子域；不要在生产环境使用 `*.up.railway.app` 作为前端 API 地址。

管理员收件箱在 `https://im.mout.me/admin`。API 不配置 `ADMIN_PASSWORD` 或 `ADMIN_SESSION_SECRET` 时，管理接口会保持关闭。归档数据库暂时不可用时聊天仍会继续，前端会提示本轮没有成功归档。

首次部署可在 Neon 建一个空数据库，然后将 pooled connection string 填入 Railway；第一次打开聊天页的 warmup 会惰性创建 `services/agent-api/sql/001_archive.sql` 定义的表和索引。数据库没有自动清理保留期。Neon Free 的存储、计算和恢复能力有额度限制，定期从 Neon 导出 SQL 备份有助于保留重要的求职/合作对话。

## Provider

独立聊天页在输入框上方提供模型选择器，默认 Gemini 4 Hydrogen。选择保存在当前浏览器；切换模型保留对话，每条回复显示实际模型并随历史保存。已明确保存的模型偏好会继续沿用；新的默认值只作用于尚未选择模型的浏览器。想比较不同模型的独立回答时，可先新建对话再问同一个问题。模型目录在 `packages/agent-core/src/models.ts`，前端与 API 使用同一份 ID 和 provider 对应表。

| 模型 | 前端 / GPTProto ID | Vercel Gateway ID | 路由 |
| --- | --- | --- | --- |
| Gemini 3.8 Flash | `gemini-3.8-flash` | `google/gemini-3.8-flash` | 自动主备 |
| Gemini 4 Hydrogen | `gemini-4-hydrogen` | `google/gemini-4-hydrogen` | 自动主备 |
| Gemini 4 Argon | `gemini-4-argon` | `google/gemini-4-argon` | 自动主备 |
| GPT 6.1 Sol | `gpt-6.1-sol` | `openai/gpt-6.1-sol` | 自动主备 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | `anthropic/claude-sonnet-5.5` | 自动主备 |
| Claude Fable 5.2 | `claude-fable-5-2` | `anthropic/claude-fable-5.2` | 自动主备 |
| DeepSeek V4 Pro | `deepseek-v4-pro` | 不使用 Gateway | 仅 DeepSeek 官方 |

选择器对六个聚合模型发送 `provider=auto`，DeepSeek 仍发送 `provider=deepseek`。默认顺序为 Vercel → GPTProto，只尝试已配置 key 的供应商；首段有效正文前遇到网络错误、超时、408/425/429/5xx 或空回复时，切换另一个供应商，保持同一模型、人设、资料和历史。400/401/403 等请求或权限错误直接返回，不用备用掩盖配置错误。已经开始输出正文后不重发请求，避免重复或拼接两份回答；失败尝试的引用、工具上下文与结束事件不会混入成功回答。

Railway 中新增 `VERCEL_AI_API_KEY`（沿用本地同名变量），将 `DEFAULT_PROVIDER` 设为 `auto`，并保留 `GPTPROTO_API_KEY` 和 `DEEPSEEK_API_KEY`。新变量只放服务端，不要添加 `VITE_` 前缀。`VERCEL_AI_BASE_URL` 默认 `https://ai-gateway.vercel.sh/v1`，`AGENT_PROVIDER_ORDER` 默认 `vercel,gptproto`，这两项无需填写。若想优先 GPTProto，可将顺序改为 `gptproto,vercel`；请求级显式偏好 `gptproto` 或 `vercel` 也会先尝试该供应商，再使用已配置备用。

未显式选择模型的入口（例如首页）沿用 `DEFAULT_PROVIDER=auto`、`GPTPROTO_MODEL=gemini-4-hydrogen`。`GPTPROTO_MODEL` 继续表示不带模型参数时的逻辑模型，Gateway 的带厂商前缀 ID 由服务端映射，不用手工填入环境变量。回复标签、日志和归档记录实际使用的供应商；Gateway 的 namespace ID 不会传给 GPTProto。embedding 仍使用 GPTProto 的 `text-embedding-3-large`，无需重建索引。

每次供应商尝试的首正文等待默认最多 120 秒，可通过可选 `UPSTREAM_FIRST_TOKEN_TIMEOUT_MS` 调整。首段正文到达后停止该计时，继续使用原来的长流式预算；前端总截止时间为 10 分钟，为两次尝试及流式输出预留空间。客户端取消后不会再请求备用。日志中的 `provider attempt`、`provider fallback` 和 `provider complete provider=...` 可定位每一次切换。

Gateway 的 Gemini 和 GPTProto 原生 Gemini 4 显式使用 `low` 思考强度，避免继承供应商默认值。可选 `AGENT_GEMINI_THINKING_LEVEL=medium` 或 `high` 可提高思考强度，无需配置时默认 `low`；这是思考深度设置，不是关闭思考或隐藏思考正文。两条 Gemini 4 路径保持同一强度，其他模型沿用各自设置。官方说明：[Gateway Google reasoning](https://vercel.com/docs/ai-gateway/models-and-providers/reasoning/google)、[Hydrogen 开发指南](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-hydrogen)。实际首字时间仍受上游排队和网络影响。

诊断日志按每次供应商尝试记录响应头耗时、首个流数据、首次收到推理片段的耗时、上游响应 ID 和实际返回的 token 用量（含 `reasoningTokens`）。`provider complete` 中 `headersMs`、`firstTokenMs` 从整条供应商链开始累计，`attemptHeadersMs`、`attemptFirstByteMs`、`attemptFirstReasoningMs` 从最终尝试开始计时；`upstreamId` 是该次尝试的响应 ID。没有返回的字段标记为未提供，不把它当成零；不记录推理正文，内部诊断事件不发给浏览器。Gateway 的 `gen_...` ID 可在其控制台或 [Generation Lookup](https://vercel.com/docs/ai-gateway/observability-and-spend/usage) 继续检查上游供应商和时延。首字前的等待仍可能同时包含网络、路由、排队和思考，日志不能单独证明每项所占时间。

Gemini 4 Hydrogen 与 Argon 在 GPTProto 路由使用原生 Gemini 流式接口 `/v1beta/models/{model}:streamGenerateContent?alt=sse`，将人格和个人资料传入 `systemInstruction`，将完整对话转换成 `contents`（`user` / `model`）。这是针对 Chat Completions 路由实测返回 `GenerateContentRequest.contents: contents is not specified` 的协议适配；模型 ID 和 API Key 沿用选择器配置，不切换模型。正文、来源和结束事件转换回现有 SSE 契约，思考片段不会显示为回答。需要搜索或阅读链接时，分别使用原生 `google_search`、`url_context` 工具。其他 GPTProto 模型继续使用现有 OpenAI 兼容协议。

非 DeepSeek 模型的实时问题优先调用 DeepSeek 官方独立 [Search API](https://api-docs.deepseek.com/zh-cn/api/search/)，与 embedding 并行执行，再把实际返回的网页标题、原始发布时间、摘要和链接作为外部资料传给所选模型。回答模型不会因此切换成 DeepSeek。搜索来源通过 SSE 展示并归档；外部资料不覆盖个人履历，也不作为网页里的指令执行。检索条件中的日期不代表每条结果都发生在当天，未注明日期的资料不会被视为当天新闻。

此路径复用现有 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`，无需新增变量。未配置 key、搜索失败或结果为空时，GPTProto 路由仍可尝试原生搜索；Gateway 不会收到不兼容的 GPTProto 工具声明。对于这条回退路径，启用工具和 `status=searching` 仅表示请求意图；日志另记 `search evidence` 中的 grounding 元数据、查询和网页来源数。如果上游没有提供可核验的搜索来源，页面会标注实时信息尚未核实，而不会宣称已完成搜索。Search API 单次最多等待 5 秒，瞬时错误重试一次；鉴权和余额错误不重试。

非 DeepSeek 模型收到网页链接时，先用同一官方凭据调用 DeepSeek Fetch API 抓取最多两页正文；页面内容和来源 URL 只取一次，再同时供主、备供应商使用。读取失败不会伪造网页内容。Gateway 统一使用 OpenAI Chat Completions 的 `messages`，无需 GPTProto 原生 `contents` 或专属工具字段。

DeepSeek V4 Pro 保留原有官方工具路径：需要实时搜索、用户提供网页链接或继续追问已读网页时，该轮使用支持官方托管工具的 `deepseek-flash`，同时声明 `deepseek_web_search` 和 `deepseek_read_url`。具体是否搜索或阅读由模型判断；回复上的模型标签和日志会标明实际模型。两种模型都携带相同的分身人格、个人资料和对话历史，并显式设置 `thinking: { type: "disabled" }`。

如果希望未选择模型的入口也默认使用 DeepSeek，可在 Railway 设置：

```text
DEFAULT_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=<DeepSeek 官方 API Key>
```

如果希望所有轮次均使用官方 Chatbot 工具链，将 `DEEPSEEK_MODEL` 改为 `deepseek-flash` 即可，不需要新增环境变量。官方工具说明：[构建 Chatbot](https://api-docs.deepseek.com/zh-cn/guides/build_a_chatbot/)、[联网工具](https://api-docs.deepseek.com/zh-cn/guides/web_tools/)；当前文档要求托管工具使用 `deepseek-flash`，因此不会向 Pro 发送不支持的工具声明。

客户端会展示搜索、阅读网页的进度、网页来源和工具失败提示。DeepSeek 返回的 `server_tool_calls`（包括 `kind` 和网页 `signature`）以内部字段随消息保存到本地历史，并在后续请求中原样回传，供 DeepSeek 恢复已读网页；不会作为回答正文展示。工具回传字段也计入本地和服务端的历史预算，切换回 GPT Proto 时不会向它发送 DeepSeek 专用字段。

GPT Proto 的 `gemini-3.8-flash` 仍保留在选择器中，使用原有 OpenAI 兼容协议；检测到实时意图时，该模型使用 Responses API 并启用 `web_search_preview`。Gemini 4 Hydrogen 和 Argon 使用上文的原生 Gemini 协议。浏览器永远不接触任意 provider 的 API key。

每次请求还会注入服务端当前时间、`AGENT_TIMEZONE` 指定的 MouT 默认时区、访客浏览器时区、星期、可推导的农历日期和常见节日。中国法定节假日的调休安排不会由模型猜测，只有在联网搜索得到可信来源时才使用。

## 语义检索

知识检索默认将现有中文关键词检索与 GPT Proto embeddings 混合排序，不使用 Neon 向量扩展。向量索引只由博客、简历和口述经历原文片段的标题/章节/正文生成；不会嵌入 `facts.json` 的摘要、标签或摘要派生别名，它们只参与关键词匹配。2026 年简历 HTML、历史简历 PDF 和口述经历由本地原始来源生成片段。关键词命中不足时，请求一个查询向量；短追问会把上一条访客问题（最多 300 字符）与当前问题合成一个输入。单次最多等待 5 秒，瞬时错误重试一次，之后回退关键词检索。服务端没有加载到与语料 hash、模型版本和维数一致的索引时，也会继续使用关键词检索。

个人记忆是事实依据，第一人称是表达方式；不能把所有检索文本都视为本人经历。人设统一要求保留主体、项目、平台、阶段和成果的对应关系，明确区分本人参与、团队背景、第三方案例与推测。未证实的具体细节直接省略，不能用模型知识、行业惯例、访客猜测或历史 AI 回答补齐；这些规则适用于所有模式，不为单个错误编写关键词分支。原文与向量索引无需因此改写或重建。

每轮 `retrieval selected` 日志列出实际注入的资料 ID、类型、版本与正文字符数，不输出正文。数量和 ID 用于复盘该轮的召回覆盖，不能证明模型实际使用了每条资料。

在本地设置 `GPTPROTO_API_KEY` 后，先从博客、简历和口述经历源文件更新原文片段，再生成静态文档索引：

```bash
node tools/content/build-agent-blog-corpus.mjs
node tools/content/build-agent-resume-corpus.mjs
node tools/content/build-agent-oral-history-corpus.mjs
node tools/content/build-agent-embedding-index.mjs
```

默认 embedding 配置为 `text-embedding-3-large`、1024 维和 GPT Proto 兼容 endpoint。可以用 `ROLEPLAY_EMBEDDING_MODEL`、`ROLEPLAY_EMBEDDING_VERSION`、`ROLEPLAY_EMBEDDING_DIMENSIONS`、`ROLEPLAY_EMBEDDING_BASE_URL` 覆盖，或使用对应的 `GPTPROTO_EMBEDDING_*` 变量。生成的 `content/agent-public/embedding-index.json` 与 `embedding-index.f32.gz` 需要随语料部署；更新博客、口述经历或简历原文后重建。添加原文后，先运行 `node tools/content/build-agent-blog-corpus.mjs`、`node tools/content/build-agent-oral-history-corpus.mjs` 或 `node tools/content/build-agent-resume-corpus.mjs` 更新原文片段。

索引生成前可运行查询集查看关键词基线；索引生成后会额外请求测试查询的 embeddings 并比较混合召回：

```bash
pnpm agent:retrieval-eval
```

脚本报告 lexical 与 hybrid 的 MRR、Hit@3、Hit@5 和逐条命中排名。部署 Railway 后，`GET /health` 的 `semanticRetrievalEnabled` 和 `semanticRecords` 可用于确认静态索引是否加载并启用。

## 本地运行

先在 `services/agent-api/.env` 中填写至少一个 provider 的 key：

```bash
cp services/agent-api/.env.example services/agent-api/.env
```

启动服务端：

```bash
pnpm --filter @mout/agent-api dev
```

启动独立聊天页（没有配置 `VITE_AGENT_API_URL` 时会使用本地 mock）：

```bash
pnpm --filter @mout/im dev
```

如果希望首页 `/chat` 连接真实服务，在根目录的环境变量中设置：

```bash
VITE_AGENT_API_URL=http://localhost:8787
VITE_IM_URL=http://localhost:5174/?source=homepage
```

## 发布前检查

只把经过审核的公开资料放入 `content/agent-public`。简历原件、客户名称、内部项目细节和私人联系方式不要进入公开构建产物。发布前至少检查：人格事实、未知问题拒答、实时搜索来源、限流、CORS 和移动端输入区。

## 会话与上下文

独立聊天页会在当前浏览器的 `localStorage` 中保存最多 12 个匿名 conversation。刷新页面会恢复当前对话，顶部的“历史”可以切换旧对话，“新对话”会生成新的随机 conversation ID。当前对话本地最多保留约 116k 估算 tokens，旧对话各保留约 12k，超出时从最早的完整问答轮次开始裁剪。

配置 `DATABASE_URL` 后，服务端会按 conversation ID 归档每条新问题与完整回答（包括模型、状态和引用），供管理员复盘。客户端裁剪上下文或清空本地记录不会删除 Neon 归档。服务端不会将归档内容混入其他访客的模型上下文，也不提供公开的归档读取接口。启用归档之前的历史不会自动上传；只归档启用后产生的新问答。

每次请求按消息顺序发送上下文。默认上下文预算约 128k tokens，先预留 system prompt、个人资料、实时日期、当前问题、8k 输出空间和 2k 安全余量，再从最新的完整问答轮次向前加入；如果新一轮放不进预算，就停止向更早历史添加。每条历史消息最多 32,000 字符，最多检查 256 条。Token 数按中日韩文字和其他字符估算，不等于各家模型的精确 tokenizer，因此预留了安全余量。长时间讨论不同主题时建议新建对话；跨设备同步和服务端摘要记忆需要以后增加登录和数据库。

## 回答呈现

独立聊天页、管理收件箱和首页 `/chat` 共用 `packages/chat-ui` 的 Markdown AST 渲染器。它只把 Markdown token 映射成 React 节点，不插入原始 HTML；原始 HTML 和 Markdown 图片会忽略，链接只允许 `http`、`https`、`mailto`、`tel`。

资料卡片使用 `content/agent-public/facts.json` 中审核过的 `project` 元数据展示；当前还没有纳入图片生成。后端会标记本轮检索并注入上下文的 fact sources，但它们表示“可用资料”，不等于模型一定逐条引用。求职/合作关键词只触发联系入口提示，不代表对意图作了确认。
