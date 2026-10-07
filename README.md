# MouT.me

个人网站。当前完成「此刻」（咖啡馆靠窗座位，默认首页）和「创作」（工作室）两个场景：同一个角色、同一个座位和镜头，导航切换时只有房间换掉（像素块转场）。
Blender/Cycles 把房间的光照烘焙进贴图和顶点色，浏览器用 three.js 实时渲染，可以小范围拖动视角；物件悬停高亮、浮尘和麦克风波形在后期合成里完成，场景里的物件打开真实的 HTML 内容层。
不支持 WebGL2（或带 `?flat`）时回退到 2.5D 预渲染图。

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
| `tools/scene/` | Blender 场景脚本：`scene_<id>.py` 是每个场景的入口（热点、调色、反射平面、窗外背景），`stage.py` 是共用的座位和镜头，`room.py`/`props*.py` 是创作，`cafe.py`/`street.py` 是此刻；`textures*.py` 生成场景里的图片贴图 |
| `tools/content/` | 把 `ref/` 里的素材转换成网页资源 |
| `tools/qa/` | 截图与交互回归脚本（Playwright + 本机 Chromium） |
| `public/` | 构建脚本生成的静态资源，以及旧首页 `public/legacy/` |

## 资源管线

### 实时 3D 场景

所有命令都用 `Blender -b --factory-startup --python tools/scene/bake.py -- --scene <now|create> --stage <stage> ...`，产物在 `.cache/bake/<scene>/`：

1. `--stage bake --atlas 4096 --samples 256 --vsamples 512`（创作约 40 分钟，此刻约 2.6 小时）：
   把模型实体化、按 0.5 m 网格切分大面，剔除任何拖动角度都看不到的面；小而密的几何烘焙成顶点色，其余（含焊接体素和带图片贴图的面）展开进光照贴图集，
   烘焙时去掉高光/清漆层只保留漫反射，OIDN 降噪后编码成 `sqrt(x / (x + K))` 存 8 位。输出 `room.glb`、`atlas.png`、`room.json`（相机、热点包围盒）。
   物件（或它的父级）上的自定义属性 `texel` 是贴图密度倍数，此刻的街道用 0.3–0.9 省贴图。`--stage plan` 只做前面的几何处理并打印贴图预算。
2. `--stage backdrop [--res 2560 --samples 256]`：单独渲染窗外 `exterior` 集合（有自己的灯光），贴在场景 `BACKDROP.dist` 远的平面上（创作 40 m，此刻 80 m）。
   此刻窗外近处的街道（`street` 集合，到对面店铺为止）和房间一起烘焙，拖动时视差才对；更远的街区、天际线和云在背景图里。
3. `--stage lut`：把曝光、白平衡、AgX 和 look 做成 48³ LUT；改了色彩设置才需要重跑。
4. `pnpm assets scene3d [scene]`：gltfpack 压缩模型，贴图集/窗外图转 avif + webp 两档，写 `public/scene/<scene>/3d/scene.json`。
   gltfpack 只用 `-c` 和浮点坐标：`-cc` 会弄坏笔记本这类贴得很近的薄层，16 位坐标在街道的尺度下精度只有约 1 mm。
   网页端的 meshopt 解码器来自 `meshoptimizer` 包，版本要和 gltfpack 一致。

此刻笔记本屏幕、杯垫、菜单板等贴图由 `python3 tools/scene/textures_now.py` 生成到 `tools/scene/build/tex/`（屏幕截的是 `.cache/qa3d/desktop_default.jpg`）。

诊断：`tools/scene/nospec.py` 渲染去掉高光的 Cycles 参考图，`tools/scene/bakecheck.py` 在 Blender 里直接显示烘焙结果；
`node tools/qa/view-encoded.mjs <in.png> <out.jpg>` 把编码图过 LUT 预览；网页加 `?debugView=1` 看反射遮罩，`?debugView=2` 看反射图。

### 2.5D 回退

1. **渲染场景**：`tools/scene/render_all.sh [scene] [桌面采样] [移动采样]`
   需要 Blender 5.x（默认 `/Applications/Blender.app`，可用 `BLENDER=` 覆盖）。原始 PNG 写到 `.cache/scene-src/<scene>/`，脚本最后自动执行第 2 步。
   - `beauty_*`：美术图，桌面 16:9 与移动 9:16 两个机位
   - `mask_*`：物件 ID 遮罩，R 通道 = (热点序号 + 1) × 16，序号对应 `HOTSPOTS` 的顺序
   - `depth_*`：深度，近黑远白，用于视差
2. **编码场景图**：`pnpm assets scene [scene]` → `public/scene/<scene>/`（avif + webp 多尺寸、低清占位、遮罩、压缩深度）
3. **照片 / 音频 / 旧首页**：`pnpm assets photos|audio|legacy`
4. **Newsletter**：`pnpm content` 把 `ref/社思现场-全部内容-Markdown` 转成 `public/content/newsletter/*.json`

改动 Blender 场景里物件的位置后，只要重跑第 1 步；网页端的热点位置、悬停范围都直接从遮罩里算，不需要手动维护坐标。麦克风旁波形的位置写在 `src/scene/sceneData.ts` 的 `SCENE.wave`。

## 路由

`/` 进入 `/now`。
- 此刻：`/now`、`/now/project`、`/now/thought`、`/now/me`、`/now/cats/xiaoba`、`/now/cats/shaojiu`、`/now/window`、`/now/index`
- 创作：`/create`、`/create/writing`、`/create/writing/vol-24`、`/create/podcast`、`/create/products/find-muse`、`/create/legacy`、`/create/cats/shaojiu`、`/create/me`、`/create/books`、`/create/window`、`/create/index`
- `/chat` 在当前场景上打开和我聊聊。

未完成的状态（游戏、工作、出发）会回到当前场景并给出施工提示。

部署时需要把所有未命中静态文件的路径回退到 `index.html`（单页应用回退）。

## QA

```bash
pnpm dev &
node tools/qa/shots.mjs     # 桌面 / 笔记本 / 手机截图 + 每个热点的悬停态 → .cache/qa/
node tools/qa/flows.mjs     # 播放、Esc、键盘、施工提示、深链、场景切换、无 WebGL 降级
node tools/qa/room3d.mjs    # 3D 场景默认/拖动极限/悬停截图 → .cache/qa3d/（SCENE=now、VIEWS、DRAGS、HOVER、QUERY 可调）
```
