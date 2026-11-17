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

默认通过 DeepSeek 官方 API 调用 `deepseek-v4-pro`，使用 OpenAI 兼容的 Chat Completions 和流式响应。遇到需要实时搜索、用户提供网页链接，或继续追问已读网页时，该轮使用支持官方托管工具的 `deepseek-flash`，同时声明 `deepseek_web_search` 和 `deepseek_read_url`，具体是否搜索或阅读由模型判断。两种模型都携带相同的分身人格、个人资料和对话历史，并显式设置 `thinking: { type: "disabled" }`。embedding 仍使用 GPT Proto 的 `text-embedding-3-large`，因此需要保留 `GPTPROTO_API_KEY`。

Railway 已有环境变量会覆盖代码默认值，切换时请设置：

```text
DEFAULT_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=<DeepSeek 官方 API Key>
```

如果希望所有轮次均使用官方 Chatbot 工具链，将 `DEEPSEEK_MODEL` 改为 `deepseek-flash` 即可，不需要新增环境变量。官方工具说明：[构建 Chatbot](https://api-docs.deepseek.com/zh-cn/guides/build_a_chatbot/)、[联网工具](https://api-docs.deepseek.com/zh-cn/guides/web_tools/)；当前文档要求托管工具使用 `deepseek-flash`，因此不会向 Pro 发送不支持的工具声明。

客户端会展示搜索、阅读网页的进度、网页来源和工具失败提示。DeepSeek 返回的 `server_tool_calls`（包括 `kind` 和网页 `signature`）以内部字段随消息保存到本地历史，并在后续请求中原样回传，供 DeepSeek 恢复已读网页；不会作为回答正文展示。工具回传字段也计入本地和服务端的历史预算，切换回 GPT Proto 时不会向它发送 DeepSeek 专用字段。

GPT Proto 的 `gemini-3.8-flash` 仍可通过 `DEFAULT_PROVIDER=gptproto` 或请求级 provider 选择。检测到实时意图时，该路由使用 Responses API 并启用 `web_search_preview`。浏览器永远不接触任意 provider 的 API key。

每次请求还会注入服务端当前时间、`AGENT_TIMEZONE` 指定的 MouT 默认时区、访客浏览器时区、星期、可推导的农历日期和常见节日。中国法定节假日的调休安排不会由模型猜测，只有在联网搜索得到可信来源时才使用。

## 语义检索

知识检索默认将现有中文关键词检索与 GPT Proto embeddings 混合排序，不使用 Neon 向量扩展。向量索引只由博客、简历和口述经历原文片段的标题/章节/正文生成；不会嵌入 `facts.json` 的摘要、标签或摘要派生别名，它们只参与关键词匹配。2026 年简历 HTML、历史简历 PDF 和口述经历由本地原始来源生成片段。关键词命中不足时，请求一个查询向量；短追问会把上一条访客问题（最多 300 字符）与当前问题合成一个输入。单次最多等待 5 秒，瞬时错误重试一次，之后回退关键词检索。服务端没有加载到与语料 hash、模型版本和维数一致的索引时，也会继续使用关键词检索。

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
