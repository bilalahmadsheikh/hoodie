"""Bundle everything a hoodie maker needs into one zip.

Run (after tools/build_all.sh):  python tools/make_package.py
Out: dist/GIK_hoodie_production_package.zip
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "GIK_hoodie_production_package.zip"
P = ROOT / "production"
R = ROOT / "renders"

FILES = {
    "01_Tech_Pack/GIK_hoodie_tech_pack.pdf": P / "GIK_hoodie_tech_pack.pdf",
    "02_Print_Files/print_front_text_30cm_300dpi.png": P / "print_front_text_30cm_300dpi.png",
    "02_Print_Files/print_sleeve_33_4.4cm_300dpi.png": P / "print_sleeve_33_4.4cm_300dpi.png",
    "02_Print_Files/print_back_GIK_map_58x48cm_300dpi.png": P / "print_back_GIK_map_58x48cm_300dpi.png",
    "02_Print_Files/print_sizes.json": P / "print_sizes.json",
    "03_Font/Fredoka-Bold.woff": P / "Fredoka-Bold.woff",
    "03_Font/Fredoka-OFL-LICENSE.txt": P / "Fredoka-OFL-LICENSE.txt",
    "04_Reference_Renders/front.png": R / "front.png",
    "04_Reference_Renders/back.png": R / "back.png",
    "04_Reference_Renders/three_quarter.png": R / "three.png",
    "04_Reference_Renders/side.png": R / "side.png",
    "04_Reference_Renders/front_print_closeup.png": R / "chest.png",
    "04_Reference_Renders/back_print_closeup.png": R / "print.png",
    "04_Reference_Renders/sleeve_33_closeup.png": R / "sleeve.png",
    "04_Reference_Renders/pocket_detail.png": R / "detail.png",
    "04_Reference_Renders/front_comparison_with_mockup.png": R / "front_print_comparison.png",
    "04_Reference_Renders/back_comparison_with_mockup.png": R / "back_print_comparison.png",
    "05_3D_Model/oatmeal_hoodie_realistic.glb": ROOT / "model" / "oatmeal_hoodie_realistic.glb",
}


def readme(sizes):
    s = {k: f'{v["width_cm"]} x {v["height_cm"]} cm' for k, v in sizes.items()}
    return f"""GIK 13 14 HOODIE - PRODUCTION PACKAGE
=====================================

Start with 01_Tech_Pack/GIK_hoodie_tech_pack.pdf (6 pages: overview, garment
components and colours, front print, back print, sleeve print, construction).

GARMENT
  Cream beige brushed cotton fleece #F2DCC0, rib hem and cuffs #ECD5B8,
  self-colour draw-cords #E8D1B4 with gunmetal metal aglets, tonal stitching.
  Oversized drop-shoulder pullover, kangaroo pocket, 2-panel hood.

PRINTS (files in 02_Print_Files: transparent PNG, 300 DPI, actual size)
  Front:  "Chai Phir Uzair kay kamray ma... !" / "01/06/27"
          {s['front']}, ink #43220A, Fredoka Bold.
          Engraved look: letters debossed about 1.4 mm into the fleece with ink
          fill. Flat screen print from the same file if debossing isn't possible.
          Centred, just under the draw-cord tips, about 5 cm above the pocket top.
  Sleeve: "33", {s['sleeve']}, ink #43220A, Fredoka Bold, same engraved look.
          WEARER'S RIGHT sleeve (on the left when you look at the front),
          outer upper arm, level with the bottom of the armhole seam.
  Back:   "13 14 Guide to the GIK Institute" campus map, {s['back']},
          ink #4E2E14 (one colour). Centred, top edge about 18 cm below the
          high point of the shoulder.

NOTES
  - Colours are screen (hex) values: please send a fabric lab-dip and an ink
    strike-off for approval before production.
  - Garment measurements in the tech pack are reference proportions; grade to
    your own size chart. Print sizes stay fixed.
  - The map artwork was enlarged from a 1448 px original, so very small text
    is slightly soft. A higher-resolution original will print sharper.
  - Font: Fredoka Bold, SIL Open Font License (free for commercial use), in 03_Font.
  - 04_Reference_Renders: how the finished hoodie should look.
  - 05_3D_Model: the 3D model (.glb, opens in Blender or any glTF viewer).
    Interactive viewer: https://claude.ai/artifact/3hkLLwRwZE3gaSFJWwWvRm
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sizes = json.loads((P / "print_sizes.json").read_text())
    missing = [str(src) for src in FILES.values() if not src.exists()]
    if missing:
        raise SystemExit("missing: " + ", ".join(missing))
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("README.txt", readme(sizes))
        for arc, src in FILES.items():
            z.write(src, arc)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(FILES) + 1} files)")


if __name__ == "__main__":
    main()
