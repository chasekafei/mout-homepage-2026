# Agent 公开知识库

API 会把 `facts.json`、`blog.json` 和 `resume-source.json` 加载成同一个可检索语料。`facts.json` 是主题索引和摘要；`blog.json` 是博客清理拆分后的原文片段；`resume-source.json` 保存三版简历的原文片段、版本、页码和 PDF 来源。

只把适合访客了解的内容放进语料。不要加入私人联系方式、公司机密或未经审核的内部笔记。检索只会返回 `visibility: "public"` 的记录。标记为 `sensitivity: "personal"` 的博客片段，只有当前问题明确匹配其标题或关键词时才会召回。

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

`facts.json` 的 `body` 是索引摘要，不是简历原文。涉及履历、职责或业绩的回答必须引用 `resume-source.json` 中的原句；2026 版优先，引用早期版本时注明年份。不要从不同版本拼接一条引文。

## 更新简历原文

本地需要 Poppler 的 `pdftotext`。将更新后的简历 PDF 放到 `ref` 对应路径后运行：

```sh
node tools/content/build-agent-resume-corpus.mjs
```

若 `pdftotext` 不在 `PATH`，通过 `PDFTOTEXT_BIN` 指定它的完整路径。生成器保留简历正文措辞和页码，仅规范 PDF 文本层中的汉字兼容字形、拆分长段落并移除电话、邮箱、QQ/WeChat 账号及链接。简历原文进入回答前会校验引文是否逐字存在于检索片段；若校验失败，API 会改为返回该片段原文。为完成校验，简历来源回答会在检查通过后再开始输出。运行服务时只需要生成后的 `resume-source.json`，不依赖 Poppler。原始简历、Prompt 和博客源文件保存在本地，不需要提交；更新源文件后提交生成的语料 JSON 即可。

## 添加或更新博客

把自己的 Markdown 或 UTF-8 文本文章放在 `ref/Blog` 下，然后运行：

```sh
node tools/content/build-agent-blog-corpus.mjs
```

导入器只读取 `.md` 和 `.txt`，不导入图片、HTML 和链接资源；会移除邮箱和手机号文本，跳过编码损坏的文件，并按标题和段落拆成约 1,500 字符的片段。日期从文章元信息和路径谨慎推断；如果日期相互冲突，只保留目录年份并标记为不确定。博客片段带有历史标签，Agent 会把它们作为当时的记录或观点，而不是当前事实。部署运行时只需要生成后的 `blog.json`，不需要 `ref/Blog` 下的原始媒体文件。依赖已安装时也可以运行 `pnpm agent:blogs`。

## 检索验证

检索使用中文 n-gram，并分别加权标题、关键词、标签和正文；`queries` 是高信号的自然问法。单篇长博客最多召回两个片段，避免占满本轮上下文。API 默认最多注入 8 条资料，可通过 `MAX_CONTEXT_FACTS` 调整。追问时会结合当前问题和最近的用户问题检索。

修改资料后运行：

```sh
bun test packages/agent-core/test/retrieval.test.ts
```

加入新主题时，同时补充代表性问法和预期记录 ID。测试覆盖项目资料召回、简历原文召回、版本优先级、博客日期和敏感记录门槛。
