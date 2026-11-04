#!/usr/bin/env bash
# Rebuild everything from build_hoodie.py's settings, in order.
#   1. 3D model (.glb / .obj zip) + textures + print decals
#   2. 300 DPI print-ready PNGs for the printer
#   3. Renders of every viewer camera
#   4. Tech-pack PDF
#   5. Viewer package for artifact hosting
#   6. Production zip for the hoodie maker
# Usage: tools/build_all.sh            (full quality, ~5 min + renders)
#        QUICK=1 tools/build_all.sh    (low-res model for fast iteration)
set -euo pipefail
cd "$(dirname "$0")/.."

TOOLS_NODE="tools/node_modules"
if [ ! -d "$TOOLS_NODE/three" ]; then
  echo "Installing node tools (three, playwright) into tools/node_modules ..."
  (cd tools && npm install --no-audit --no-fund)
fi

echo "== 1/6 model"
python build_hoodie.py

echo "== 2/6 print files"
python tools/make_print_files.py

echo "== 3/6 renders"
THREE_DIR="$PWD/$TOOLS_NODE/three" NODE_PATH="$PWD/$TOOLS_NODE" \
  node tools/render.js model/oatmeal_hoodie_realistic.glb renders \
  front chest sleeve three side back print detail

echo "== 4/6 tech pack PDF"
NODE_PATH="$PWD/$TOOLS_NODE" node tools/make_tech_pack.js

echo "== 5/6 artifact package"
python tools/pack_viewer_for_artifact.py

echo "== 6/6 maker package"
python tools/make_package.py

echo "Done."
