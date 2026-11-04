# GIK 13 14 Hoodie — 3D model, prints and production kit

A realistic 3D model of a cream-beige fleece pullover hoodie with three prints,
plus everything needed to manufacture it, and a reusable pipeline for the next one.

- **3D viewer:** https://claude.ai/artifact/3hkLLwRwZE3gaSFJWwWvRm
- **Canva tech pack (for the maker):** https://www.canva.com/d/xtTl-yeRoKJjowQ (owner's Canva account)
- **How it was built / how to make the next hoodie:** [`docs/`](docs/README.md)

![front print](renders/front_print_comparison.png)

![back print](renders/back_print_comparison.png)

## The hoodie

| | |
|---|---|
| Fabric | Brushed cotton fleece, cream beige `#F2DCC0`; rib hem & cuffs `#ECD5B8` |
| Trims | Self-colour draw-cords `#E8D1B4`, gunmetal aglets, embroidered eyelets, tonal topstitching |
| Fit | Oversized, drop shoulder, kangaroo pocket, 2-panel hood with crossover V |
| Front print | "Chai Phir Uzair kay kamray ma... !" / "01/06/27", Comic Neue Bold, ink `#43220A`, 29.8 × 4.1 cm, under the cord tips |
| Sleeve print | "33", bold Comic Neue, ink `#43220A`, 6.3 × 4.7 cm, **wearer's right** outer upper arm |
| Back print | "13 14 Guide to the GIK Institute" campus map, ink `#4E2E14`, 58 × 47.5 cm, under the hood |

## Quick start

```bash
pip install -r requirements.txt
```

```bash
cd tools && npm install && npx playwright install chromium && cd ..
```

```bash
tools/build_all.sh
```

That rebuilds the model, the printer files, all renders, the tech-pack PDF and the
shareable viewer package. To iterate quickly on the model only:

```bash
QUICK=1 python build_hoodie.py
```

## What's where

| Path | What |
|---|---|
| `build_hoodie.py` | **The generator.** All settings (colours, sizes, prints, placements) are constants at the top. |
| `model/oatmeal_hoodie_realistic.glb` | Main 3D model (glTF 2.0, PBR + fleece sheen, each part and print a separate object) |
| `model/oatmeal_hoodie_realistic_obj.zip` | OBJ + MTL + textures |
| `production/print_*_300dpi.png` | **Print-ready files** for the printer (transparent, 300 DPI, actual size) |
| `production/GIK_hoodie_tech_pack.pdf` | 6-page tech pack (specs, colours, placements, construction) |
| `viewer/index.html` | three.js 3D viewer with camera presets |
| `renders/` | Every view, plus comparison sheets against the mock-ups |
| `artwork/` | Source artwork, mock-up references, font (Comic Neue, SIL OFL) |
| `tools/` | Render, print export, tech-pack PDF, viewer packaging, `build_all.sh` |
| `docs/` | Full write-up of the process, how to change things, lessons learned |
| `original_kit/` | The basic kit this started from |

## Docs

1. [Workflow and setup](docs/01-workflow.md)
2. [The 3D model](docs/02-3d-model.md)
3. [Prints](docs/03-prints.md)
4. [Viewer and sharing](docs/04-viewer-and-sharing.md)
5. [Production files and Canva](docs/05-production-and-canva.md)
6. [New hoodie checklist](docs/06-new-hoodie-checklist.md)
7. [Lessons learned](docs/07-lessons-learned.md)

## Editing in Blender

`File → Import → glTF 2.0` → `model/oatmeal_hoodie_realistic.glb`. Objects:
`Front_Body`, `Back_Body`, `Kangaroo_Pocket`, `Sleeve_Left/Right`, `Hood`, `Rib_Hem`,
`Rib_Cuff_Left/Right`, `Topstitching`, `Drawcords`, `Drawcord_Eyelets`, `Aglets`,
`Front_Print`, `Sleeve_Print`, `Back_Print`. Units are metres, Y up, +Z front, and
+X is the wearer's left. Baked shading is in the `Color` attribute.

The model is about 360k triangles. It is a static garment, not rigged or set up for
cloth simulation. Garment measurements are the model's oversized proportions; grade
to your own size chart.
