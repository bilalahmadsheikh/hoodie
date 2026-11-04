# 01 · Workflow and setup

## The pipeline

```
reference photos / mock-ups ─┐
artwork files (map, fonts) ──┤
                             ▼
                    build_hoodie.py  ──►  model/*.glb, model/*_obj.zip, model/textures/
                             │            artwork/*_print.png (decal textures)
                             ▼
              tools/make_print_files.py ─► production/print_*_300dpi.png  (for the printer)
                             ▼
                    tools/render.js  ──►  renders/*.png  (one per viewer camera)
                             ▼
               tools/make_tech_pack.js ─► production/GIK_hoodie_tech_pack.pdf
                             ▼
       tools/pack_viewer_for_artifact.py ─► dist/artifact/  (shareable 3D viewer)
                             ▼
                 Canva (via Claude's Canva connector) ─► editable tech pack for the maker
```

`tools/build_all.sh` runs steps 1–5 in order. Canva is a separate step; see
[05-production-and-canva.md](05-production-and-canva.md).

## How we worked (what the steps looked like in practice)

1. **Start from a reference.** We had a rough editable kit plus a product photo.
   We measured the photo on a pixel grid (shoulder height, sleeve angle, hood size,
   pocket corners) and converted pixels to metres using the chest width (60 cm).
2. **Iterate fast at low resolution.** `QUICK=1 python build_hoodie.py` builds a
   7 mm-voxel model in ~25 s. Render, compare side by side with the reference, adjust
   the numbers, repeat.
3. **Match colour by measurement, not by eye.** Sample the median RGB of the lit
   fabric in the reference and in our render (same crop), then adjust `FABRIC_HEX` /
   viewer exposure until they agree within a few units.
4. **Add prints as decals.** Each print is a separate mesh lifted 0.8 mm off the
   fabric with its own transparent texture, so it follows the folds.
5. **Full build, render all views, publish.** Full build ~2.5 min; renders ~1 min each
   with software WebGL.
6. **Production.** Export print-ready 300 DPI PNGs, a tech-pack PDF, and build the
   Canva version for the maker.

## Setup

Python 3.10+ and Node 18+.

```bash
pip install -r requirements.txt
```

```bash
cd tools && npm install && npx playwright install chromium
```

Then, from the repo root:

```bash
tools/build_all.sh
```

For quick iteration on the model only:

```bash
QUICK=1 python build_hoodie.py
```

```bash
THREE_DIR=$PWD/tools/node_modules/three NODE_PATH=$PWD/tools/node_modules node tools/render.js model/oatmeal_hoodie_realistic.glb /tmp/r front three back
```

`render.js` serves the viewer from a fake origin and intercepts the three.js CDN
requests with your local `tools/node_modules/three` (`THREE_DIR`), so it works
offline and behind proxies. Views: `front chest sleeve three side back print detail`
(defined in `viewer/index.html` → `VIEWS`).

## Repo map

| Path | Contents |
|---|---|
| `build_hoodie.py` | The generator. All settings are constants at the top. |
| `artwork/` | Source artwork, mock-up references, fonts, and the generated decal textures |
| `model/` | Output: `.glb` (main), OBJ zip, fabric textures, part list JSON |
| `viewer/index.html` | three.js viewer (orbit controls, camera presets, studio lighting) |
| `renders/` | Images of every camera view + comparison sheets |
| `production/` | Printer files (300 DPI PNGs), tech-pack HTML/PDF, font + licence |
| `tools/` | Render, print-file, tech-pack and packaging scripts; `build_all.sh` |
| `original_kit/` | The kit we started from, kept for comparison |
| `docs/` | You are here |
