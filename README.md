# Realistic Oatmeal / Warm-Taupe Hoodie (3D)

![comparison](renders/comparison_sheet.png)

A rebuilt, more realistic version of the *Oatmeal Taupe Hoodie 3D Editable Kit* (the original is kept in `original_kit/`).
The proportions and colour were matched to the reference product photo.

## Files

| Path | What |
|---|---|
| `model/oatmeal_hoodie_realistic.glb` | **Main model** (glTF 2.0, PBR + fleece sheen, textures embedded) |
| `model/oatmeal_hoodie_realistic_obj.zip` | OBJ + MTL + textures, for tools without glTF |
| `model/textures/` | Tiling jersey-fleece / rib-knit normal maps and grain colour maps |
| `viewer/index.html` | three.js studio viewer (put the `.glb` next to it, serve over http) |
| `renders/` | Front, 3/4, side, back and pocket close-up renders |
| `build_hoodie.py` | Generator: run it to rebuild everything |
| `tools/render.js` | Headless render script (Playwright) |

## What changed vs. the original kit

| Original | Realistic version |
|---|---|
| Separate tubes intersecting, puffy "balloon" sleeves | One continuous fabric shell (SDF + marching cubes), natural armpit blend |
| Helmet-like round hood | Upright hood with a rolled front edge, V crossover at the neck and a centre-back seam |
| Short, boxy body | Oversized drop-shoulder fit, proportions measured off the photo |
| No folds | Drape folds, elbow creases, stacked folds above the cuffs, blousing over the rib hem |
| Flat colours | Jersey-fleece and 1x1 rib normal maps, fabric grain, `KHR_materials_sheen` brushed-fleece sheen, baked ambient occlusion and heather mottle |
| Solid stitch tubes | Dashed tonal topstitching on the pocket, hem, cuffs, armholes, shoulders, side seams and hood |
| Thin cords | Draw-cords that hang over the chest, with gunmetal aglets and eyelets |

**Colour:** fabric albedo `#CCB8A6` (rib `#C7B3A2`). Under the studio lighting it renders at RGB ≈ 199/180/165, against ≈ 201/183/168 for the lit fabric in the reference photo.

## Editing in Blender

`File → Import → glTF 2.0` and pick `oatmeal_hoodie_realistic.glb`. The pieces are separate objects:
`Front_Body`, `Back_Body`, `Kangaroo_Pocket`, `Sleeve_Left/Right`, `Hood`, `Rib_Hem`,
`Rib_Cuff_Left/Right`, `Topstitching`, `Drawcords`, `Drawcord_Eyelets`, `Aglets`.

- **Recolour:** change *Base Color* on `Fleece_Oatmeal` / `Rib_Knit_Oatmeal`, or edit `FABRIC_HEX` in `build_hoodie.py`.
- **Baked shading:** ambient occlusion lives in the `Color` attribute (COLOR_0), which multiplies the base colour.
- **UVs:** tiled at 1 UV unit = 5 cm, so the fabric texture repeats. For a print or logo, add a decal or a second UV map on `Front_Body` / `Back_Body`.
- **Units:** metres. Y is up and +Z is the front.

## Rebuild

```bash
pip install numpy scipy scikit-image trimesh fast-simplification pygltflib pillow
```

```bash
python build_hoodie.py
```

`QUICK=1 python build_hoodie.py` does a fast low-resolution preview build.
The model is about 337k triangles. It is a static garment, not rigged or set up for cloth simulation.
