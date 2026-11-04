# 03 · Prints

Every print is two things:

1. **A decal on the 3D model.** A copy of the garment faces under the print, lifted
   0.8 mm along the surface normal, with planar UVs and a transparent texture
   (`build_print_decal`, `build_sleeve_print`). It follows the folds, keeps the knit
   texture (second UV set), and is its own object in the `.glb`.
2. **A print-ready file for the printer.** A transparent PNG at 300 DPI and actual
   size (`tools/make_print_files.py` → `production/`).

Both come from the same settings, so the 3D preview and the printer file always match.

## Current prints

### Back: GIK campus map
| Setting | Value |
|---|---|
| `PRINT_SRC` | `artwork/gik_map_artwork.webp` |
| `PRINT_CROP` | `(16, 30, 1430, 1038)`, the crop inside the artwork's decorative frame |
| `PRINT_W` | `0.58` → 58 cm wide |
| `PRINT_STRETCH` | `1.15`, a vertical stretch to fill the back like the mock-up (set `1.0` for no stretch) |
| `PRINT_TOP` | `0.662` → top edge 18 cm below the shoulder point |
| `INK_HEX` | `#4E2E14` |

**Background removal:** the artwork is a brown drawing on parchment. We turn
luminance into alpha (paper → transparent, darkest ink → opaque) and print a single
ink colour. This works for any one-colour drawing on a light background. Multi-colour
art needs a different approach: keep its RGB and use its own alpha.

### Front: chest text
| Setting | Value |
|---|---|
| `FRONT_LINES` | `["Chai Phir Uzair kay kamray ma... !", "01/06/27"]` |
| `FRONT_FONT` | `artwork/fonts/ComicNeue-Bold.woff` (SIL OFL, free for commercial use) |
| `FRONT_TEXT_W` | `0.30`, the first line's width (30 cm) |
| `FRONT_TEXT_CY` | `0.418`, the block's centre height, just under the cord tips |
| `FRONT_INK_HEX` | `#43220A` |

Text is rendered from the font file, so it is crisp at any size.

### Sleeve: "33"
| Setting | Value |
|---|---|
| `SLEEVE_TEXT` | `"33"` |
| `SLEEVE_TEXT_H` | `0.044`, digit height (4.4 cm) |
| `SLEEVE_BOLD` | `0.026`, extra outline stroke as a fraction of the font size (heavier look) |
| `SLEEVE_SIDE` | `-1` = **wearer's right** sleeve; `+1` = wearer's left |
| `SLEEVE_ANCHOR` | point on the sleeve centre-line; its Y sets the height |
| `SLEEVE_FACING` | which way the print faces (outer arm, slightly forward) |

The sleeve decal is projected along the local surface normal and kept upright.
Keep it clear of the armhole seam: at `y ≈ 0.47+` the seam's stitching runs through it.

## Adding a new print

1. Put the artwork (or font) in `artwork/`.
2. Make its texture: copy `make_front_text_texture` (for text) or `make_print_texture`
   (for art).
3. Make its decal: call `build_print_decal(..., piece, width, height, y_top, facing, name)`
   for front/back panels, or adapt `build_sleeve_print` for curved areas.
4. Register it in `main()` (`parts[...]`, `EXTRA_UV1[...]`), give it an ink material
   in `write_glb` (`ink("Name_Ink", tex)`), and add it to the OBJ material table.
5. Add a print-ready export to `tools/make_print_files.py`.
6. Add a camera preset in `viewer/index.html` → `VIEWS` and a nav button.

## Placement measurements for the tech pack

Measure on the model, then describe placements from points a maker can find on any
size (shoulder point, armhole seam, hem), not from absolute model coordinates.
`project_to_surface()` and `garment_grad()` give exact surface points.
