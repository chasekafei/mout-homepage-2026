# MouT 个人 Agent

个人 Agent 由两个前端入口和一个服务端组成：

- `apps/im`：部署到 `im.mout.me` 的独立聊天页；
- 当前根应用：个人网站里的 `/chat` 对话层，使用同一套 API；
- `services/agent-api`：部署到 Railway、Vercel Function 或其他 Node/Edge 运行时的服务端；
- `packages/agent-core`：人格规则、公开资料检索和请求类型；
- `content/agent-public`：允许公开回答的个人资料小段落。

## Provider

默认 provider 是 GPT Proto，默认模型为 `gemini-3.8-flash`。服务端通过 OpenAI 兼容的 Chat Completions 请求普通对话；检测到“今天、最新、现在”等实时意图时，改用 GPT Proto Responses API 并启用 `web_search_preview`。

DeepSeek 官方 API 作为第二个 provider，通过 `DEFAULT_PROVIDER=deepseek` 或请求级 provider 选择。浏览器永远不接触任意 provider 的 API key。

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

独立聊天页会在当前浏览器的 `localStorage` 中保存多个匿名 conversation。刷新页面会恢复当前对话，顶部的“历史”可以切换旧对话，“新对话”会生成新的随机 conversation ID。API 请求会携带这个 ID，但服务端不把匿名访客的聊天记录写入共享内存或数据库，因此不同浏览器之间不会串线，Railway 重启也不会影响本地历史。

每次请求仍然按消息顺序发送上下文，服务端默认只取最近 16 条消息，约 8 轮问答。长时间讨论不同主题时建议新建对话；跨设备同步和更长的服务端摘要记忆需要以后增加登录和数据库。
