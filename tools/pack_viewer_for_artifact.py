"""Package viewer/index.html + the .glb for hosting as a Claude artifact.

The artifact host has rules a normal web server doesn't:
  * the page is wrapped in its own <html>/<head>/<body>, so ours are stripped;
  * it will not serve .glb files, so the model is gzipped and base64-encoded
    into a .txt file that the viewer unpacks in the browser;
  * fixed UI needs safe-area padding on phones.

Run:  python tools/pack_viewer_for_artifact.py
Out:  dist/artifact/gik_hoodie_viewer.html
      dist/artifact/hoodie_model.glb.gz.b64.txt
"""
import base64
import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "viewer" / "index.html"
GLB = ROOT / "model" / "oatmeal_hoodie_realistic.glb"
OUT = ROOT / "dist" / "artifact"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v = SRC.read_text()
    v = re.sub(r"<!doctype html>\s*", "", v, flags=re.I)
    v = re.sub(r"</?html[^>]*>\s*", "", v)
    v = re.sub(r"</?head>\s*", "", v)
    v = re.sub(r"</?body>\s*", "", v)
    v = re.sub(r"<meta charset[^>]*>\s*", "", v)
    v = re.sub(r'<meta name="viewport"[^>]*>\s*', "", v)
    v = re.sub(r"(<title>[^<]*</title>)",
               r'\1\n<meta name="claude:viewport-fit-sides" content="cover">', v, count=1)
    v = v.replace(
        "header { position:fixed; left:16px; top:14px; pointer-events:none; }",
        "header { position:fixed; left:max(16px, env(safe-area-inset-left, 0px)); "
        "right:max(16px, env(safe-area-inset-right, 0px)); "
        "top:calc(14px + env(safe-area-inset-top, 0px)); pointer-events:none; }")
    v = v.replace("nav { position:fixed; left:50%; bottom:16px;",
                  "nav { position:fixed; left:50%; bottom:calc(16px + env(safe-area-inset-bottom, 0px));")
    old = "  'oatmeal_hoodie_realistic.glb', '../model/oatmeal_hoodie_realistic.glb'].filter(Boolean);"
    if old not in v:
        raise SystemExit("viewer/index.html model list changed; update this script")
    v = v.replace(old, "  'hoodie_model.glb.gz.b64.txt'].filter(Boolean);")
    (OUT / "gik_hoodie_viewer.html").write_text(v)

    packed = base64.b64encode(gzip.compress(GLB.read_bytes(), 9, mtime=0))
    (OUT / "hoodie_model.glb.gz.b64.txt").write_bytes(packed)
    mb = len(packed) / 1e6
    print(f"wrote {OUT}/gik_hoodie_viewer.html and hoodie_model.glb.gz.b64.txt ({mb:.1f} MB)")
    if mb > 15.5:
        print("WARNING: over the ~16 MB per-file artifact limit; reduce triangles or textures")


if __name__ == "__main__":
    main()
