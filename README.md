# MouT.me

个人网站。当前完成的是「创作」场景：一张 Blender/Cycles 预渲染的房间图，由网页端 WebGL 合成器叠加物件高亮、深度视差、浮尘和麦克风波形；桌上的物件打开真实的 HTML 内容层。

## 本地运行

```bash
pnpm install
pnpm dev          # http://localhost:5173
pnpm build        # 类型检查 + 产物输出到 dist/
```

## 目录

| 路径 | 内容 |
|---|---|
| `src/content/site.ts` | 所有文案和结构化内容：导航状态、热点、产品、猫、关于我、播客、联系方式 |
| `src/scene/` | `compositor.ts` WebGL 着色器；`sceneData.ts` 遮罩/深度解码与热点区域；`SceneStage.tsx` 场景交互 |
| `src/panels/` | 各物件打开后的内容层 |
| `tools/scene/` | Blender 场景脚本（程序化建模、灯光、相机、渲染通道） |
| `tools/content/` | 把 `ref/` 里的素材转换成网页资源 |
| `tools/qa/` | 截图与交互回归脚本（Playwright + 本机 Chromium） |
| `public/` | 构建脚本生成的静态资源，以及旧首页 `public/legacy/` |

## 资源管线

1. **渲染场景**：`tools/scene/render_all.sh [桌面采样] [移动采样]`
   需要 Blender 5.x（默认 `/Applications/Blender.app`，可用 `BLENDER=` 覆盖）。原始 PNG 写到 `.cache/scene-src/`，脚本最后自动执行第 2 步。
   - `beauty_*`：美术图，桌面 16:9 与移动 9:16 两个机位
   - `mask_*`：物件 ID 遮罩，R 通道 = (热点序号 + 1) × 16，序号对应 `HOTSPOTS` 的顺序
   - `depth_*`：深度，近黑远白，用于视差
2. **编码场景图**：`pnpm assets scene` → `public/scene/create/`（avif + webp 多尺寸、低清占位、遮罩、压缩深度）
3. **照片 / 音频 / 旧首页**：`pnpm assets photos|audio|legacy`
4. **Newsletter**：`pnpm content` 把 `ref/社思现场-全部内容-Markdown` 转成 `public/content/newsletter/*.json`

改动 Blender 场景里物件的位置后，只要重跑第 1 步；网页端的热点位置、悬停范围都直接从遮罩里算，不需要手动维护坐标。麦克风旁波形的位置写在 `src/scene/sceneData.ts` 的 `SCENE.wave`。

## 路由

`/create`、`/create/writing`、`/create/writing/vol-24`、`/create/podcast`、`/create/products/find-muse`、`/create/legacy`、`/create/cats/shaojiu`、`/create/me`、`/create/books`、`/create/window`、`/create/index`、`/chat`。
未完成的状态（此刻、游戏、工作、出发）会回到 `/create` 并给出施工提示。

部署时需要把所有未命中静态文件的路径回退到 `index.html`（单页应用回退）。

## QA

```bash
pnpm dev &
node tools/qa/shots.mjs     # 桌面 / 笔记本 / 手机截图 + 每个热点的悬停态 → .cache/qa/
node tools/qa/flows.mjs     # 播放、Esc、键盘、施工提示、深链、无 WebGL 降级
```
