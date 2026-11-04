"""Export print-ready production files (transparent PNG, 300 DPI, actual print size)."""
import sys, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_hoodie as B  # noqa: E402

DPI = 300
OUT = ROOT / "production"
OUT.mkdir(exist_ok=True)
px = lambda m: int(round(m / 0.0254 * DPI))
ink = lambda hx: tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))


def save(img, name):
    img.save(OUT / name, dpi=(DPI, DPI), optimize=True)
    return name


def back_print():
    w_m = B.PRINT_W
    src = Image.open(B.PRINT_SRC).convert("RGB").crop(B.PRINT_CROP)
    h_m = w_m / (src.width / src.height) * B.PRINT_STRETCH
    W, H = px(w_m), px(h_m)
    im = src.resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    L = a @ np.array([0.30, 0.59, 0.11])
    bg, lo = np.median(L), np.percentile(L, 0.5)
    alpha = B.smoothstep(0.12, 0.72, (bg - L) / (bg - lo))
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = ink(B.INK_HEX)
    rgba[..., 3] = np.round(alpha * 255)
    e = 24  # clear what is left of the artwork's frame along the edges
    rgba[:e, :, 3] = rgba[-e:, :, 3] = 0
    rgba[:, :e, 3] = rgba[:, -e:, 3] = 0
    return save(Image.fromarray(rgba, "RGBA"), "print_back_GIK_map_58x48cm_300dpi.png"), w_m, h_m


def text_block(lines, sizes_px, gap_factor, stroke=0):
    fonts = [ImageFont.truetype(str(B.FRONT_FONT), s) for s in sizes_px]
    boxes = [f.getbbox(t, stroke_width=stroke) for f, t in zip(fonts, lines)]
    asc, desc = fonts[0].getmetrics()
    gap = int((asc + desc) * gap_factor)
    W = max(b[2] - b[0] for b in boxes) + 20
    H = gap * (len(lines) - 1) + (boxes[-1][3]) + 20
    top = min(b[1] for b in boxes[:1])
    mask = Image.new("L", (W, H - top), 0)
    d = ImageDraw.Draw(mask)
    for i, (t, f) in enumerate(zip(lines, fonts)):
        d.text((W / 2, 10 + i * gap - top), t, font=f, fill=255, anchor="ma", stroke_width=stroke, stroke_fill=255)
    bb = mask.getbbox()
    mask = mask.crop(bb)
    return mask


def to_rgba(mask, hx):
    rgba = Image.new("RGBA", mask.size, ink(hx) + (0,))
    rgba.putalpha(mask)
    return rgba


def front_print():
    target_w = px(B.FRONT_TEXT_W)
    probe = ImageFont.truetype(str(B.FRONT_FONT), 400)
    size = int(400 * target_w / probe.getlength(B.FRONT_LINES[0]))
    mask = text_block(B.FRONT_LINES, [size, int(size * 0.92)], 1.12)
    w_m, h_m = mask.width / DPI * 0.0254, mask.height / DPI * 0.0254
    return save(to_rgba(mask, B.FRONT_INK_HEX), "print_front_text_30cm_300dpi.png"), w_m, h_m


def sleeve_print():
    probe = ImageFont.truetype(str(B.FRONT_FONT), 400)
    l, t, r, b = probe.getbbox(B.SLEEVE_TEXT)
    size = int(400 * px(B.SLEEVE_TEXT_H) / (b - t))
    mask = text_block([B.SLEEVE_TEXT], [size], 1.0, stroke=round(size * B.SLEEVE_BOLD))
    w_m, h_m = mask.width / DPI * 0.0254, mask.height / DPI * 0.0254
    return save(to_rgba(mask, B.FRONT_INK_HEX), "print_sleeve_33_4.4cm_300dpi.png"), w_m, h_m


if __name__ == "__main__":
    info = {}
    for key, fn in (("back", back_print), ("front", front_print), ("sleeve", sleeve_print)):
        name, w, h = fn()
        info[key] = {"file": name, "width_cm": round(w * 100, 1), "height_cm": round(h * 100, 1)}
        print(key, info[key])
    (OUT / "print_sizes.json").write_text(json.dumps(info, indent=2))
