# Agent 公开知识库

API 会把 `facts.json`、`blog.json`、`resume-source.json` 和 `oral-history.json` 加载成同一个可检索语料。`facts.json` 是关键词索引和主题摘要；其余文件保存博客、简历和口述经历的原文片段。

只把适合访客了解的内容放进语料。不要加入私人联系方式、公司机密或未经审核的内部笔记。检索只会返回 `visibility: "public"` 的记录。标记为 `sensitivity: "personal"` 的博客或口述片段，只有当前问题明确匹配其标题或关键词时才会召回。

## 添加经历或观点

一条记录只写一个主题。`title` 写主题名称，`body` 补足背景、本人负责的工作、取舍和结果；`tags` 写较宽泛的概念，`keywords` 加入项目别名和常见叫法，`queries` 写访客可能直接提出的问题。`source` 保留资料来源和版本；明确表达过的判断使用 `recordType: "opinion"`，经历事实使用 `recordType: "fact"`。

```json
{
  "id": "project-example",
  "title": "项目名称与关键判断",
  "body": "说明用户场景、遇到的问题、我采取的做法、原因，以及结果或限制。",
  "recordType": "fact",
  "tags": ["项目类型", "行业", "角色"],
  "keywords": ["项目别名", "产品类别", "核心能力"],
  "queries": ["这个项目是什么", "你负责了什么", "当时为什么这样设计"],
  "project": { "name": "项目展示名", "href": "/work/project-example", "eyebrow": "产品经历" },
  "source": "docs/public-source.md#project",
  "visibility": "public"
}
```

`project` 可选，仅用于在回答后展示站内项目卡片。`href` 和可选的 `image` 必须是确实存在的站内路径。

`facts.json` 的 `body` 是索引摘要，不是简历原文。涉及履历、职责或业绩时，模型优先参考 `resume-source.json` 的原文并用自然的第一人称回答；只有访客明确要求原句或出处时，才引用相关原文。2026 版在内部优先于旧版，聊天时不要主动解释版本来源。

向量索引只使用博客、简历和口述经历原文记录，不嵌入 `facts.json` 的摘要正文；摘要中的关键词和问法仍供关键词检索使用。

## 更新简历原文

生成器从 `ref/AI产品负责人_设计版简历_v6-打印修复.html` 按可见 DOM 区块抽取 2026 版内容；将来更新 HTML 时，替换该文件后重跑生成器。2024/2021 历史版仍从 PDF 抽取，本地需要 Poppler 的 `pdftotext`。更新后运行：

```sh
node tools/content/build-agent-resume-corpus.mjs
```

若 `pdftotext` 不在 `PATH`，通过 `PDFTOTEXT_BIN` 指定它的完整路径。生成器保留各来源的正文措辞和页码，仅规范历史 PDF 文本层中的汉字兼容字形、拆分长段落并移除电话、邮箱、QQ/WeChat 账号及链接。HTML 抽取忽略 CSS、注释、打印按钮和链接属性，只读可见的简历区块。原始简历、HTML、Prompt 和博客源文件保存在本地，不需要提交；更新源文件后提交生成的语料 JSON 即可。

## 更新口述经历原文

口述经历以段落为单位原样切分，不做摘要。更新 `docs/个人网站资料-我的个人经历.md` 后运行：

```sh
node tools/content/build-agent-oral-history-corpus.mjs
```

少数包含家庭成员或婚礼细节的片段会标记为个人内容，只在问题明确提到对应主题时召回。

## 添加或更新博客

把自己的 Markdown 或 UTF-8 文本文章放在 `ref/Blog` 下，然后运行：

```sh
node tools/content/build-agent-blog-corpus.mjs
```

导入器只读取 `.md` 和 `.txt`，不导入图片、HTML 和链接资源；会移除邮箱和手机号文本，跳过编码损坏的文件，并按标题和段落拆成约 1,500 字符的片段。日期从文章元信息和路径谨慎推断；如果日期相互冲突，只保留目录年份并标记为不确定。博客片段带有历史标签，Agent 会把它们作为当时的记录或观点，而不是当前事实。部署运行时只需要生成后的 `blog.json`，不需要 `ref/Blog` 下的原始媒体文件。依赖已安装时也可以运行 `pnpm agent:blogs`。

## 检索验证

检索将中文 n-gram 关键词排名与 GPT Proto embedding 的语义排名用加权 RRF 合并；关键词结果权重较高，项目名、原文短语和别名仍有优先级。语义索引只嵌入博客、简历和口述经历的原文片段标题/章节/正文，不嵌入 `facts.json` 的摘要正文、标签或摘要生成的别名。索引是本地生成的压缩 Float32 文件，不使用 Neon/pgvector。单篇长博客最多召回两个片段、口述经历最多三个片段、简历最多 3 段；简历原文版本优先级和敏感资料门槛仍然生效。没有索引、模型版本与语料 hash 不匹配、或 embedding API 临时失败时，会自动退回关键词检索。

在设置好 `GPTPROTO_API_KEY` 和 embedding 配置的本地环境中生成索引：

```sh
node tools/content/build-agent-embedding-index.mjs
```

先运行 `node tools/content/build-agent-blog-corpus.mjs`、`node tools/content/build-agent-resume-corpus.mjs` 和 `node tools/content/build-agent-oral-history-corpus.mjs` 更新原文语料，再运行索引构建。生成 `embedding-index.json` 和 `embedding-index.f32.gz` 后，将它们与语料改动一起提交/部署。修改任何已索引原文后，需要重建向量文件。API 默认最多注入 8 条资料，可通过 `MAX_CONTEXT_FACTS` 调整；每轮 embedding API 请求至少向量化当前问题，只有短追问才会批量加入最近两条用户问题（各截取前 300 字符）。

生成索引前可以先查看关键词基线；索引生成后评测器会请求测试查询向量，并比较混合检索的 MRR、Hit@3 和 Hit@5：

```sh
pnpm agent:retrieval-eval
```

评测用例保存在 `packages/agent-core/test/semantic-retrieval-eval.json`。增加资料时继续加入有代表性的语义改写，并确保简历原文引用相关用例仍然通过。

修改资料后运行：

```sh
bun test packages/agent-core/test/retrieval.test.ts
```

加入新主题时，同时补充代表性问法和预期记录 ID。测试覆盖项目资料召回、简历原文召回、版本优先级、博客日期和敏感记录门槛。
