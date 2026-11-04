# 02 · The 3D model

## How the geometry is made

The garment is a **signed distance field (SDF)**: a function that returns, for any
point in space, how far it is from the fabric surface (negative inside). Shapes are
combined with smooth-min/smooth-max, which gives natural blends (armpits, hood onto
shoulders) instead of intersecting tubes.

| Part | SDF building block (in `build_hoodie.py`) |
|---|---|
| Torso | rounded box, width/depth interpolated per height (`torso_raw`) |
| Sleeves | chain of round cones along `SLEEVE` points with radii `SLEEVE_R` |
| Cuffs | round cone `CUFF_A → CUFF_B`, with a hole carved in |
| Hood | ellipsoid shell (`HOOD_C`, `HOOD_R`) with the face opening cut away and a thickened rolled edge |
| Pocket | the torso surface pushed out inside the pocket outline (`pocket_sdf2d`) |
| Folds | small displacements added to the SDF: blousing over the hem, elbow creases, stacked folds above the cuffs, drag lines |

The SDF is sampled on a 3.2 mm voxel grid → marching cubes (scikit-image) → Taubin
smoothing → decimated to ~230k triangles (fast-simplification). Faces are then
labelled into editable pieces (`Front_Body`, `Back_Body`, `Hood`, `Sleeve_Left/Right`,
`Kangaroo_Pocket`, `Rib_Hem`, `Rib_Cuff_*`).

Extras built on top of the surface:
- **Topstitching:** dashed thread tubes projected onto the surface (`build_stitching`).
- **Draw-cords:** hang as a taut string over the chest (`build_drawstrings`), metal aglets.
- **Baked shading:** ambient occlusion computed from the SDF + subtle heather mottle,
  stored as vertex colours (COLOR_0).
- **Fabric textures:** procedural jersey-fleece and 1×1 rib normal maps (`make_textures`),
  tiled at 5 cm.
- **Materials:** glTF PBR with `KHR_materials_sheen` for the brushed-fleece look.

Units are metres, Y up, +Z is the front. **+X is the wearer's left** (it is on your
right when you look at the front).

## Settings you'll most often change

All at the top of `build_hoodie.py`:

| Setting | What it does |
|---|---|
| `FABRIC_HEX`, `RIB_HEX`, `CORD_HEX`, `THREAD_HEX`, `AGLET_HEX` | Garment colours |
| `HEM_TOP`, `SHOULDER_Y` | Rib height, body length |
| `torso_raw()` → `A`/`B` arrays | Body width/depth at each height |
| `SLEEVE`, `SLEEVE_R`, `CUFF_*` | Sleeve path, thickness, cuff position |
| `HOOD_C`, `HOOD_R`, and `zplane`/`yv` in `hood_parts()` | Hood size and face-opening shape |
| `POCKET_*` | Kangaroo pocket outline |

## Colour matching

The render colour depends on fabric colour **and** viewer lighting
(`toneMappingExposure` in `viewer/index.html`, currently 0.58). To match a photo:

```bash
python3 -c "
from PIL import Image; import numpy as np
im=np.asarray(Image.open('renders/front.png').convert('RGB')).astype(float)
print(np.median(im[300:700,250:650].reshape(-1,3),0))"
```

Compare with the same measurement on the reference photo's lit fabric and adjust.
Current result: render ≈ 234/211/184 against the mock-ups' ≈ 239/215/184.

## Editing in Blender

`File → Import → glTF 2.0` → `model/oatmeal_hoodie_realistic.glb`. Each piece and
each print is its own object. The baked shading is in the `Color` attribute.
For geometry changes that should survive a rebuild, change `build_hoodie.py` instead.
