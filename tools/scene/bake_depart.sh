#!/usr/bin/env bash
# Bake + publish 出发. The cabin is baked once (under the 名古屋 sky); every destination adds a 3D backdrop
# (backdrop_<dest>) and a 2.5D beauty set (public/scene/depart/<dest>/). A painted destination
# (tools/scene/paint.py) ships its painting as the backdrop and has it laid under the beauty renders.
# Usage: DESTS="nagoya tbilisi" tools/scene/bake_depart.sh            # cabin + those destinations
#        SKIP_CABIN=1 DESTS="batumi" tools/scene/bake_depart.sh       # add a destination to an existing bake
set -euo pipefail
cd "$(dirname "$0")/../.."
BL=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
DESTS=${DESTS:-nagoya}
SRC=.cache/scene-src/depart
t0=$(date +%s)
bake() { "$BL" -b --factory-startup --python tools/scene/bake.py -- --scene depart "$@"; }
pass() { "$BL" -b --factory-startup --python tools/scene/build.py -- --scene depart "$@" 2>&1 | grep -E "BUILD|RENDER_DONE|Error|Traceback" || true; }
mkdir -p "$SRC"
if [ -z "${SKIP_CABIN:-}" ]; then
  echo "== cabin bake $(date)"; DEST=nagoya bake --stage bake --atlas 4096 --samples 256 --vsamples 512
  echo "== lut $(date)"; DEST=nagoya bake --stage lut
  for cam in desktop mobile; do
    DEST=nagoya pass --mode mask --cam $cam --res 1920 --out $SRC/mask_$cam.png
    DEST=nagoya pass --mode depth --cam $cam --res 1280 --out $SRC/depth_$cam.png
    DEST=nagoya bake --stage guide --cam $cam --res 2560
  done
fi
for d in $DESTS; do
  echo "== $d backdrop $(date)"; DEST=$d bake --stage backdrop --res 2560 --samples 256
done
node tools/content/build-assets.mjs scene3d depart
echo "== 3d done $(( ($(date +%s) - t0) / 60 )) min"
for d in $DESTS; do
  mkdir -p $SRC/$d
  echo "== $d beauty $(date)"
  DEST=$d pass --mode final --cam desktop --res 2560 --samples 192 --out $SRC/$d/beauty_desktop_cabin.png
  DEST=$d pass --mode final --cam mobile --res 2560 --samples 160 --out $SRC/$d/beauty_mobile_cabin.png
  for cam in desktop mobile; do
    python3 tools/scene/paint_beauty.py $d $cam $SRC/$d/beauty_${cam}_cabin.png $SRC/$d/beauty_$cam.png
  done
done
node tools/content/build-assets.mjs scene depart
echo "== DEPART_DONE $(( ($(date +%s) - t0) / 60 )) min"
