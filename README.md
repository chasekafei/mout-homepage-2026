# MouT.me

个人网站。当前完成「此刻」（咖啡馆靠窗座位，默认首页）、「创作」（工作室）、「工作」（深夜的家里书房）、「游戏」（傍晚的游戏房）和「出发」（Model Y 驾驶座）五个场景：同一个角色、同一个座位和镜头，导航切换时只有房间换掉（像素块转场）。
角色永远看着正前方，每个场景把最重要的东西放在他视线里（此刻是笔记本、创作是日记本、工作是 AI Agent 核心、游戏是显像管电视、出发是前方的路）；只有手臂按场景换姿势（`models_char.ARMS`：托腮、打字、握手柄、握方向盘）。
「出发」的车内只有一套，车窗外按目的地切换（名古屋、第比利斯、巴统、赛里木湖、多哈、北海道、福冈、大连、长沙），切换复用同一个像素块转场。
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
| `tools/scene/` | Blender 场景脚本：`scene_<id>.py` 是每个场景的入口（热点、调色、反射平面、窗外背景），`stage.py` 是共用的座位和镜头（`SEAT`/`YAW`：座位整体朝镜头右侧转 36°，正前方的东西才不会被头挡住；桌面坐标系 `DESK_ROOT` 里 +Y 就是他看的方向），`room.py`/`props*.py` 是创作，`cafe.py`/`street.py` 是此刻，`study.py`/`nightcity.py` 是工作，`gameroom.py` 是游戏（窗外复用 `nightcity.py` 的 `dusk` 风格），`car.py` 是出发的车内、`roads.py` 是窗外的通用街景零件（道路、楼、树、山、海，以及保证地标不被挡住的 `Sightline`）、`dests.py` 是每个目的地；`textures*.py` 生成场景里的图片贴图 |
| `tools/content/` | 把 `ref/` 里的素材转换成网页资源 |
| `tools/qa/` | 截图与交互回归脚本（Playwright + 本机 Chromium） |
| `public/` | 构建脚本生成的静态资源，以及旧首页 `public/legacy/` |

## 资源管线

### 实时 3D 场景

所有命令都用 `Blender -b --factory-startup --python tools/scene/bake.py -- --scene <now|create|work|play> --stage <stage> ...`，产物在 `.cache/bake/<scene>/`：

1. `--stage bake --atlas 4096 --samples 256 --vsamples 512`（创作约 16 分钟，此刻约 20 分钟，工作约 15 分钟，游戏约 15 分钟）：
   把模型实体化、按 0.5 m 网格切分大面，剔除任何拖动角度都看不到的面；小而密的几何烘焙成顶点色，其余（含焊接体素和带图片贴图的面）展开进光照贴图集，
   烘焙时去掉高光/清漆层只保留漫反射，OIDN 降噪后编码成 `sqrt(x / (x + K))` 存 8 位。输出 `room.glb`、`atlas.png`、`room.json`（相机、热点包围盒）。
   物件（或它的父级）上的自定义属性 `texel` 是贴图密度倍数，此刻的街道用 0.3–0.9 省贴图。`--stage plan` 只做前面的几何处理并打印贴图预算。
2. `--stage backdrop [--res 2560 --samples 256]`：单独渲染窗外 `exterior` 集合（有自己的灯光），贴在场景 `BACKDROP.dist` 远的平面上（创作 40 m，此刻 80 m）。
   此刻窗外近处的街道（`street` 集合，到对面店铺为止）和房间一起烘焙，拖动时视差才对；更远的街区、天际线和云在背景图里。
3. `--stage lut`：把曝光、白平衡、AgX 和 look 做成 48³ LUT；改了色彩设置才需要重跑。
4. `pnpm assets scene3d [scene]`：gltfpack 压缩模型，贴图集/窗外图转 avif + webp 两档，写 `public/scene/<scene>/3d/scene.json`。
   gltfpack 只用 `-c` 和浮点坐标：`-cc` 会弄坏笔记本这类贴得很近的薄层，16 位坐标在街道的尺度下精度只有约 1 mm。
   网页端的 meshopt 解码器来自 `meshoptimizer` 包，版本要和 gltfpack 一致。

此刻笔记本屏幕、杯垫、菜单板等贴图由 `python3 tools/scene/textures_now.py` 生成到 `tools/scene/build/tex/`（屏幕截的是 `.cache/qa3d/desktop_default.jpg`）；
工作场景的六个工具图标和行业铭牌由 `python3 tools/scene/textures_work.py` 生成，游戏场景的电视画面、街机屏、GBA 屏幕和地毯由 `python3 tools/scene/textures_game.py` 生成。

工作场景的布局：AI Agent 核心（体素方块 + 指令环 + 六个工具卡片，搜索是激活的红色连接点）立在正前方的矮台上；
电子政务、品牌营销、游戏三个模块按时间顺序挂在前墙的一段弧线上，社交站在矮台右端，一根发光的线从最早的政务一路串到社交，再沿矮台接进核心。
窗外的夜景城市（`nightcity.py`，`exterior` 集合）只进背景图。

游戏场景的布局：正前方是电视柜上的显像管电视（柜里 FC、MD、PS4、Switch，烧酒趴在电视顶上），电视上方一排掌机；左前角是按平台排好的存档架，盒子往上变成发光的像素块一直到天花板；右前角是街机；茶几上是 GBA、第二个手柄和卡带，小八躺在旁边。存档架默认随机生成约六百个盒子；如果有 `tools/scene/data/game_library.json`（`[{"platform": "ps|switch|dvd|gb|big", "color": "#rrggbb"}]`），就按真实游戏库一盒一盒摆。
婚礼请柬小游戏：把 Cocos 导出的网页版放进 `public/games/wedding/`，再把 `src/content/site.ts` 里 `WEDDING_GAME.src` 设成 `/games/wedding/index.html`，`/play/gba` 就能直接玩。

出发场景：车内（方向盘、中控屏导航、球拍和亚运会门票、出风口上的电影票、护照和登机牌、两只猫）只在名古屋的天光下烘焙一次；每个目的地是 `dests.DESTS` 里的一项（建造函数、太阳方向和颜色、`nightcity.SKIES` 里的天空），
渲染成 `backdrop_<地点>` 和 `public/scene/depart/<地点>/` 下的 2.5D 美术图。地标都放在视线左偏约 30°、仰角 10° 以内，桌面和手机两个机位都看得到。
`tools/scene/bake_depart.sh` 跑完整条管线（`DESTS="nagoya tbilisi ..."` 选目的地，`SKIP_CABIN=1` 跳过车内烘焙只重渲窗外，约 6 分钟一个地点），单独预览某个地点用 `DEST=<地点>` 加 `build.py --mode preview`。
新加目的地：在 `dests.py` 写建造函数并登记进 `DESTS`，在 `site.ts` 的 `TRIPS` 和 `SCENES.depart.views` 里加上同一个 id。旅行照片、时间、文字和攻略链接都写在 `TRIPS`，观赛记录写在 `MATCHES`，空着的字段界面会自动隐藏。

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
- 工作：`/work`、`/work/agent`、`/work/social`、`/work/games`、`/work/brand`、`/work/gov`、`/work/me`、`/work/cats/xiaoba`、`/work/cats/shaojiu`、`/work/window`、`/work/index`
- 游戏：`/play`、`/play/tv`、`/play/gba`、`/play/archive`、`/play/handhelds`、`/play/arcade`、`/play/me`、`/play/cats/shaojiu`、`/play/cats/xiaoba`、`/play/window`、`/play/index`
- 出发：`/depart`、`/depart/nav`、`/depart/nav/<地点>`（开到那里，车窗外随之切换）、`/depart/window`（当前这一站）、`/depart/pingpong`、`/depart/cinema`、`/depart/passport`、`/depart/me`、`/depart/cats/shaojiu`、`/depart/cats/xiaoba`、`/depart/index`
- `/chat` 在当前场景上打开和我聊聊。

部署时需要把所有未命中静态文件的路径回退到 `index.html`（单页应用回退）。

## QA

```bash
pnpm dev &
node tools/qa/shots.mjs     # 桌面 / 笔记本 / 手机截图 + 每个热点的悬停态 → .cache/qa/
node tools/qa/flows.mjs     # 播放、Esc、键盘、深链、场景切换、出发换目的地、无 WebGL 降级
node tools/qa/room3d.mjs    # 3D 场景默认/拖动极限/悬停截图 → .cache/qa3d/（SCENE=now|work|play|depart、VIEWS、DRAGS、HOVER、QUERY 可调）
```
