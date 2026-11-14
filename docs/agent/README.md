# MouT 个人 Agent

个人 Agent 由两个前端入口和一个服务端组成：

- `apps/im`：部署到 `im.mout.me` 的独立聊天页；
- 当前根应用：个人网站里的 `/chat` 对话层，使用同一套 API；
- `services/agent-api`：部署到 Railway、Vercel Function 或其他 Node/Edge 运行时的服务端；
- `packages/agent-core`：人格规则、公开资料检索和请求类型；
- `content/agent-public`：允许公开回答的个人资料小段落。

## Neon 对话归档

创建 Neon Postgres 项目后，建议选择离 Railway API 较近的 region，并从 Neon 控制台复制 pooled connection string，作为 Railway 的 `DATABASE_URL`。API 在收到 `/v1/warmup` 或聊天请求时惰性建表；页面首次打开只做一次带 4 秒超时的预热，不会定时 ping。Neon 空闲后会暂停 compute；归档使用低连接数池，闲置连接 30 秒释放。

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

默认 provider 是 GPT Proto，默认模型为 `gemini-3.8-flash`。服务端通过 OpenAI 兼容的 Chat Completions 请求普通对话；检测到“今天、最新、现在”等实时意图时，改用 GPT Proto Responses API 并启用 `web_search_preview`。

DeepSeek 官方 API 作为第二个 provider，通过 `DEFAULT_PROVIDER=deepseek` 或请求级 provider 选择。浏览器永远不接触任意 provider 的 API key。

每次请求还会注入服务端当前时间、`AGENT_TIMEZONE` 指定的 MouT 默认时区、访客浏览器时区、星期、可推导的农历日期和常见节日。中国法定节假日的调休安排不会由模型猜测，只有在联网搜索得到可信来源时才使用。

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
