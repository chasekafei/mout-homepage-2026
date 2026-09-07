# 创作场景 v2 资产

v2 是一份独立的 Blender 资产，保留 v1 文件不变。它把创作场景重建为一个有明确前后层次的图形化体素舞台：后墙、地台、固定坐姿角色、桌面内容簇、前景猫和语义锚点。

## 文件

- 源文件：`public/assets/create-scene-v2.blend`
- 网页资产：`public/assets/create-scene-v2.glb`
- 建模脚本：`tools/blender/build_create_scene_v2.py`

## 导出命令

由于 Blender 5.2 在当前 macOS 图形环境中需要 GUI 初始化，使用独立实例运行：

```sh
open -na /Applications/Blender.app --args --factory-startup --python /Users/mout/Project/mout-homepage/tools/blender/build_create_scene_v2.py --python-expr "import bpy; bpy.ops.wm.quit_blender()"
```

脚本会覆盖 v2 的 `.blend` 和 `.glb`，不会触碰 v1 资产。

## 场景结构

- `avatar_root`：固定坐姿角色的父节点，网页状态切换时保持其位置和姿态。
- `rubik_root`：三阶魔方 27 个 cubelet 的父节点，网页端可以对整个根节点做自动旋转。
- `anchor_create_newspaper`：写作和长期内容入口。
- `anchor_create_podcast`：CrossPod 和播客入口。
- `anchor_create_products`：Find Muse、Dimensional Inn、stpHQ 等独立产品入口。
- `anchor_create_rubik`：旧个人网站和 CSS 实验入口。
- `anchor_create_cats`：烧酒与小八的生活层入口。

## 网页接入注意

Three.js 读取 GLB 后坐标已经转换为 glTF 的 Y-up 坐标。当前包围盒约为：

```text
min [-5.4, -0.39, -3.25]
max [ 5.4,  5.65,  3.25]
center [0, 2.63, 0]
```

正交相机应显式 lookAt `[0, 2.63, 0]`，并按包围盒设置 frustum。默认 `zoom: 64` 会只显示很小的一块区域；在默认 `[-1, 1]` frustum 下可先从 `zoom: 0.25` 附近调试。

Blender 默认字体不保证中文字形。场景标题和可访问文本应由网页 HTML 层提供，GLB 内的文字只作为英文品牌装饰。
