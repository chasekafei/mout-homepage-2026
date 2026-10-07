# MouT.me

个人网站。当前完成的是「创作」场景：Blender/Cycles 把房间的光照烘焙进贴图和顶点色，浏览器用 three.js 实时渲染，可以小范围拖动视角；物件悬停高亮、浮尘和麦克风波形在后期合成里完成，桌上的物件打开真实的 HTML 内容层。不支持 WebGL2（或带 `?flat`）时回退到旧的 2.5D 预渲染图。

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
| `src/scene3d/` | `Room3D.ts` 实时渲染（烘焙辐射度解码、地板/桌面平面反射、泛光、AgX LUT、悬停描边）；`Stage3D.tsx` 拖动、拾取、信标 |
| `src/scene/` | `SceneStage.tsx` 选择 3D 或 2.5D；`Stage2D.tsx`、`compositor.ts`、`sceneData.ts` 是 2.5D 回退 |
| `src/panels/` | 各物件打开后的内容层 |
| `tools/scene/` | Blender 场景脚本（程序化建模、灯光、相机、渲染通道） |
| `tools/content/` | 把 `ref/` 里的素材转换成网页资源 |
| `tools/qa/` | 截图与交互回归脚本（Playwright + 本机 Chromium） |
| `public/` | 构建脚本生成的静态资源，以及旧首页 `public/legacy/` |

## 资源管线

### 实时 3D 场景

所有命令都用 `Blender -b --factory-startup --python tools/scene/bake.py -- --stage <stage> ...`，产物在 `.cache/bake/`：

1. `--stage bake --atlas 4096 --samples 256 --vsamples 512`（约 40 分钟）：
   把模型实体化、按 0.5 m 网格切分大面，剔除任何拖动角度都看不到的面；小而密的几何烘焙成顶点色，其余（含焊接体素和带图片贴图的面）展开进光照贴图集，
   烘焙时去掉高光/清漆层只保留漫反射，OIDN 降噪后编码成 `sqrt(x / (x + K))` 存 8 位。输出 `room.glb`、`atlas.png`、`room.json`（相机、热点包围盒）。
   `--stage plan` 只做前面的几何处理并打印贴图预算。
2. `--stage backdrop [--res 2560 --samples 256]`：单独渲染窗外（`tools/scene/exterior.py`，有自己的太阳角度），贴在 40 m 外的平面上。
3. `--stage lut`：把曝光、白平衡、AgX 和 look 做成 48³ LUT；改了色彩设置才需要重跑。
4. `pnpm assets scene3d`：gltfpack 压缩模型，贴图集/窗外图转 avif + webp 两档，写 `public/scene/create/3d/scene.json`。

诊断：`tools/scene/nospec.py` 渲染去掉高光的 Cycles 参考图，`tools/scene/bakecheck.py` 在 Blender 里直接显示烘焙结果；
`node tools/qa/view-encoded.mjs <in.png> <out.jpg>` 把编码图过 LUT 预览；网页加 `?debugView=1` 看反射遮罩，`?debugView=2` 看反射图。

### 2.5D 回退

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
node tools/qa/room3d.mjs    # 3D 场景默认/拖动极限/悬停截图 → .cache/qa3d/（VIEWS、DRAGS、HOVER、QUERY 可调）
```
