#!/usr/bin/env bash
# Render every pass the 2.5D fallback needs, then encode them into public/scene/<scene>/.
# Usage: tools/scene/render_all.sh [scene] [samples_desktop] [samples_mobile]
set -euo pipefail
cd "$(dirname "$0")/../.."
BL=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
SCENE=${1:-create}
SRC=.cache/scene-src/$SCENE
mkdir -p "$SRC"
SD=${2:-192}
SM=${3:-160}
run() { "$BL" -b --factory-startup --python tools/scene/build.py -- --scene "$SCENE" "$@" 2>&1 | grep -E "BUILD|RENDER_DONE|ANCHORS|Error|Traceback" || true; }
for cam in desktop mobile; do
  run --mode mask --cam $cam --res 1920 --out $SRC/mask_$cam.png
  run --mode depth --cam $cam --res 1280 --out $SRC/depth_$cam.png
done
run --mode final --cam desktop --res 2560 --samples "$SD" --out $SRC/beauty_desktop.png
run --mode final --cam mobile --res 2560 --samples "$SM" --out $SRC/beauty_mobile.png
node tools/content/build-assets.mjs scene "$SCENE"
echo ALL_DONE
