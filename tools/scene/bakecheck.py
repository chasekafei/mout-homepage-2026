"""Diagnostic: render the baked room (decoded radiance as emission) through the beauty camera and compositor.

Usage: Blender -b --factory-startup --python tools/scene/bakecheck.py [-- <scene>]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import build  # noqa: E402

SCENE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv[:-1] else "create"
BAKE = build.ROOT / ".cache/bake" / SCENE
K = 0.6

sys.argv = [sys.argv[0], "--", "--scene", SCENE, "--mode", "preview", "--cam", "desktop", "--res", "1440",
            "--samples", "16", "--out", str(build.ROOT / f".cache/qa3d/bakecheck_{SCENE}.png")]
args = build.parse()
build.build(args)
build.setup_render(args)
for o in bpy.data.objects:
    if o.type == "MESH" and not o.name.startswith("ext_"):
        o.hide_render = True

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(BAKE / "room.glb"))
imported = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]

atlas = bpy.data.images.load(str(BAKE / "atlas.png"))
atlas.colorspace_settings.name = "Non-Color"


def decode_mat(name, use_uv, layer=""):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    if use_uv:
        src = t.nodes.new("ShaderNodeTexImage")
        src.image = atlas
        src.interpolation = "Linear"
        sock = src.outputs["Color"]
    else:
        src = t.nodes.new("ShaderNodeVertexColor")
        src.layer_name = layer
        sock = src.outputs["Color"]
    sep = t.nodes.new("ShaderNodeSeparateColor")
    t.links.new(sock, sep.inputs[0])
    comb = t.nodes.new("ShaderNodeCombineColor")
    for i, ch in enumerate("RGB"):
        sq = t.nodes.new("ShaderNodeMath")
        sq.operation = "MULTIPLY"
        t.links.new(sep.outputs[i], sq.inputs[0])
        t.links.new(sep.outputs[i], sq.inputs[1])
        cl = t.nodes.new("ShaderNodeMath")
        cl.operation = "MINIMUM"
        t.links.new(sq.outputs[0], cl.inputs[0])
        cl.inputs[1].default_value = 0.9995
        den = t.nodes.new("ShaderNodeMath")
        den.operation = "SUBTRACT"
        den.inputs[0].default_value = 1.0
        t.links.new(cl.outputs[0], den.inputs[1])
        num = t.nodes.new("ShaderNodeMath")
        num.operation = "MULTIPLY"
        num.inputs[1].default_value = K
        t.links.new(cl.outputs[0], num.inputs[0])
        div = t.nodes.new("ShaderNodeMath")
        div.operation = "DIVIDE"
        t.links.new(num.outputs[0], div.inputs[0])
        t.links.new(den.outputs[0], div.inputs[1])
        t.links.new(div.outputs[0], comb.inputs[i])
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    t.links.new(comb.outputs[0], em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return m


for o in imported:
    uv = len(o.data.uv_layers) > 0
    cols = [a.name for a in o.data.color_attributes]
    print("BAKECHECK", o.name, "uv" if uv else "vertex", cols, [a.data_type for a in o.data.color_attributes])
    o.data.materials.clear()
    o.data.materials.append(decode_mat(o.name + "_dec", uv, cols[0] if cols else ""))
    o.visible_shadow = False

build.setup_compositor()
s = bpy.context.scene
s.render.filepath = args.out
bpy.ops.render.render(write_still=True)
print("BAKECHECK_DONE", args.out)
