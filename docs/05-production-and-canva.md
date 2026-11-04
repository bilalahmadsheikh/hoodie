# 05 · Production files and the Canva tech pack

## Printer files

```bash
python tools/make_print_files.py
```

Writes to `production/` (transparent PNG, 300 DPI, actual print size; sizes also in
`print_sizes.json`):

| File | Size |
|---|---|
| `print_back_GIK_map_58x48cm_300dpi.png` | 58 × 47.5 cm |
| `print_front_text_30cm_300dpi.png` | 29.8 × 4.1 cm |
| `print_sleeve_33_4.4cm_300dpi.png` | 6.7 × 4.4 cm |

The map source is only 1448 px wide, so at 58 cm it is enlarged (fine text slightly
soft). Use a higher-resolution or vector original when one exists.

## Tech-pack PDF

`production/tech_pack.html` is a 6-page A4-landscape document: cover, garment
components & colours, front print, back print, sleeve print, construction &
measurements. Render it to PDF:

```bash
NODE_PATH=$PWD/tools/node_modules node tools/make_tech_pack.js
```

Edit the HTML directly for wording, sizes or new pages. Page images come from
`renders/` and `production/`.

## Canva tech pack (for the hoodie maker)

The maker works in Canva, so we built the tech pack there through Claude's Canva
connector. What worked:

1. **Connect Canva** in claude.ai (Settings → Connectors).
2. **Allow `www.canva.com` in the cloud environment's network settings** (environment
   menu → Edit → Network access → Allowed domains). Without it, file uploads fail with
   `CONNECT tunnel failed, response 403`.
3. **Create the design** from an outline (`create-design`, presentation format): one
   section per page with the exact specs as text.
4. **Upload the real files** (`create-upload-url`, then a raw-bytes POST of each PNG).
   Each returns a media ID.
5. **Replace Canva's generated images with ours** (`edit-design`: `update_fill` on the
   existing image frames, `insert_fill` for new ones), delete generated text overlays,
   fix typos, then `commit` after the owner approves the preview.

**Always check what Canva generated.** Its first draft invented its own campus map
(not ours), wrote the wrong date ("(1/06/17"), and had typos ("hammered",
"topsitching"). A maker could have printed the invented map. Read every page before
sharing.

The current design: https://www.canva.com/d/xtTl-yeRoKJjowQ, with the full-size
print files in the owner's Canva Uploads. Share it with the maker from Canva's Share
button.

## What to send a maker

- The Canva link (or `production/GIK_hoodie_tech_pack.pdf`)
- The three `production/print_*_300dpi.png` files
- `production/Fredoka-Bold.woff` + licence (if they re-typeset text)
- For the front text and "33": the look is **engraved** (debossed ~1.4 mm with ink fill); confirm the maker can deboss fleece, otherwise flat screen print
- Ask for a **fabric lab-dip and an ink strike-off** before production. Hex colours
  are screen colours.
