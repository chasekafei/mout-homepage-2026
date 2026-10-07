"""Diagnostic: render the desktop view with specular and metal removed (what the diffuse bake can reproduce).

Usage: Blender -b --factory-startup --python tools/scene/nospec.py [-- <scene>]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import build  # noqa: E402

SCENE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv[:-1] else "create"
sys.argv = [sys.argv[0], "--", "--scene", SCENE, "--mode", "preview", "--cam", "desktop", "--res", "1440",
            "--samples", "96", "--out", str(build.ROOT / f".cache/qa3d/nospec_{SCENE}.png")]
args = build.parse()
build.build(args)
build.setup_render(args)
for m in bpy.data.materials:
    if m.name.startswith("ext_") or not m.use_nodes:
        continue
    p = m.node_tree.nodes.get("Principled BSDF")
    if p is not None:
        p.inputs["Specular IOR Level"].default_value = 0.0
        p.inputs["Metallic"].default_value = 0.0
        p.inputs["Coat Weight"].default_value = 0.0
build.setup_compositor()
s = bpy.context.scene
s.render.filepath = args.out
bpy.ops.render.render(write_still=True)
print("NOSPEC_DONE", args.out)
