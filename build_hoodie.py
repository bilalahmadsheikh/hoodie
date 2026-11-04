"""
Realistic oatmeal / warm-taupe pullover hoodie generator.

The garment shell is modelled as a signed-distance field (torso, drop-shoulder
sleeves, rib cuffs, rib hem, kangaroo pocket and a standing hood with a rolled
front edge), polygonised with marching cubes, smoothed and decimated. That
gives one continuous, seamless fabric surface with natural armpit blends and
soft drape folds instead of separate intersecting tubes.

On top of the shell it adds:
  * dashed topstitching projected onto the surface (pocket, hem, cuffs,
    armholes, hood edge, hood centre seam, shoulders, side seams)
  * draw-cords that hang over the chest as a taut string, with metal aglets
    and embroidered eyelets
  * baked ambient occlusion + subtle heather mottling as vertex colours
  * procedural tiling textures: jersey-fleece and 1x1 rib-knit normal maps,
    fabric grain colour map
  * glTF PBR materials with KHR_materials_sheen for the brushed-fleece look

Run:   python build_hoodie.py
Needs: numpy, scipy, scikit-image, trimesh, fast-simplification, pygltflib, Pillow
Units: metres (Blender: 1 unit = 1 m). Y up, +Z is the front of the hoodie.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from skimage.measure import marching_cubes

OUT = Path(__file__).resolve().parent
MODEL_DIR = OUT / "model"
TEX_DIR = MODEL_DIR / "textures"
MODEL_DIR.mkdir(exist_ok=True)
TEX_DIR.mkdir(exist_ok=True)

RNG = np.random.default_rng(7)

# --------------------------------------------------------------------------
# Colour — sampled from the reference photo (lit fabric ~#CDBBAC, shadow
# ~#A69485). This is the albedo that reproduces it under neutral studio light.
# --------------------------------------------------------------------------
FABRIC_HEX = "#F2DCC0"   # creamy beige, matched to the print mock-ups
RIB_HEX = "#ECD5B8"      # rib knit reads a touch deeper
THREAD_HEX = "#CDB496"   # tonal stitching thread
CORD_HEX = "#E8D1B4"     # self-colour draw-cord
AGLET_HEX = "#8E8A86"    # brushed gunmetal tips
INK_HEX = "#4E2E14"      # dark sepia-brown screen-print ink (as on the mock-up)

# Back print: "13 14 Guide to the GIK Institute" map artwork, screen printed on the
# back panel. Placement follows the mock-up: centred, just under the hood, ~56 cm wide.
ART_DIR = OUT / "artwork"
PRINT_SRC = ART_DIR / "gik_map_artwork.webp"
PRINT_PNG = ART_DIR / "gik_map_back_print.png"
PRINT_CROP = (16, 30, 1430, 1038)   # inside the decorative border of the artwork
PRINT_W = 0.58
PRINT_TOP = 0.662
PRINT_STRETCH = 1.15                # mock-up layout is taller than the flat art
EXTRA_UV1 = {}                      # part name -> second UV set (fabric tiling)

# Front print: two centred lines of rounded handwriting, just below the cord tips.
FRONT_LINES = ["Chai Phir Uzair kay kamray ma... !", "01/06/27"]
FRONT_FONT = ART_DIR / "fonts" / "ComicNeue-Bold.woff"   # SIL Open Font License
FRONT_PNG = ART_DIR / "front_text_print.png"
FRONT_INK_HEX = "#43220A"           # dark chocolate brown, sampled from the mock-up
FRONT_TEXT_W = 0.30                 # metres across the first line
FRONT_TEXT_CY = 0.418               # centre height of the two-line block

# Sleeve print: a small "33" on the outer upper arm (bicep/tricep height) of the
# wearer's right sleeve (x < 0, the one on the left in the front view).
SLEEVE_TEXT = "33"
SLEEVE_PNG = ART_DIR / "sleeve_33_print.png"
SLEEVE_TEXT_H = 0.044               # cap height of the digits, metres
SLEEVE_BOLD = 0.026                 # extra stroke weight, as a fraction of the font size
SLEEVE_SIDE = -1                    # -1: wearer's right sleeve; +1: wearer's left
SLEEVE_ANCHOR = np.array([0.332, 0.461, 0.000])  # upper-arm point on the sleeve centre-line
SLEEVE_FACING = np.array([0.92, 0.0, 0.38])       # outer side of the arm, turned slightly forward


def srgb_to_linear(hexcode):
    c = np.array([int(hexcode.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# --------------------------------------------------------------------------
# SDF helpers (vectorised, p is (N,3))
# --------------------------------------------------------------------------
def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sd_round_cone(p, a, b, r1, r2):
    """Inigo Quilez' exact round-cone SDF."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    x2 = np.sum((pa * l2 - y[:, None] * ba) ** 2, axis=1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=1)
    k1 = np.linalg.norm(q / r, axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def seg_param(p, a, b):
    """Parameter t in [0,1] of the closest point on segment ab, and radial vectors."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    t = np.clip(((p - a) @ ba) / (ba @ ba), 0, 1)
    rad = p - (a + t[:, None] * ba)
    return t, rad


# Value noise (3D), used for organic fold variation and heather mottle.
_PERM = RNG.permutation(256)
_PERM = np.concatenate([_PERM, _PERM])
_GRAD = RNG.uniform(-1, 1, 256)


def vnoise3(p):
    p = np.asarray(p, float)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = f * f * (3 - 2 * f)
    i &= 255

    def h(dx, dy, dz):
        return _GRAD[_PERM[_PERM[_PERM[(i[:, 0] + dx) & 255] + ((i[:, 1] + dy) & 255)] + ((i[:, 2] + dz) & 255)]]

    x00 = h(0, 0, 0) * (1 - u[:, 0]) + h(1, 0, 0) * u[:, 0]
    x10 = h(0, 1, 0) * (1 - u[:, 0]) + h(1, 1, 0) * u[:, 0]
    x01 = h(0, 0, 1) * (1 - u[:, 0]) + h(1, 0, 1) * u[:, 0]
    x11 = h(0, 1, 1) * (1 - u[:, 0]) + h(1, 1, 1) * u[:, 0]
    y0 = x00 * (1 - u[:, 1]) + x10 * u[:, 1]
    y1 = x01 * (1 - u[:, 1]) + x11 * u[:, 1]
    return y0 * (1 - u[:, 2]) + y1 * u[:, 2]


def fbm(p, octaves=3):
    s, a, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + a * vnoise3(p * (2 ** o) + 17.3 * o)
        tot += a
        a *= 0.5
    return s / tot


# --------------------------------------------------------------------------
# Garment dimensions (metres) — proportions measured off the reference photo
# --------------------------------------------------------------------------
HEM_TOP = 0.085            # top of the rib waistband
SHOULDER_Y = 0.842         # neck-side shoulder height
NECK_R = 0.070

# Sleeve centre-line from inside the drop shoulder to the wrist, then the cuff.
SLEEVE = np.array([
    [0.262, 0.640, -0.006],
    [0.322, 0.470, -0.002],
    [0.378, 0.305, 0.006],
    [0.416, 0.180, 0.012],
    [0.440, 0.082, 0.018],
])
SLEEVE_R = np.array([0.080, 0.074, 0.068, 0.064, 0.061])
CUFF_A = np.array([0.441, 0.080, 0.018])
CUFF_B = np.array([0.462, -0.016, 0.024])
CUFF_R = (0.0465, 0.0445)

HOOD_C = np.array([0.0, 0.850, -0.050])
HOOD_R = np.array([0.214, 0.152, 0.190])

# Kangaroo pocket outline (y -> half width) and slanted hand openings.
POCKET_Y0, POCKET_Y1 = 0.099, 0.347
POCKET_TOP_HW = 0.144
POCKET_BOT_HW = 0.212
POCKET_OPEN_Y = 0.176      # opening runs from the top corner down to here


def pocket_halfwidth(y):
    # straight slanted opening from the top corner out to the side, then vertical
    t = np.clip((POCKET_Y1 - y) / (POCKET_Y1 - POCKET_OPEN_Y), 0, 1)
    side = POCKET_TOP_HW + (POCKET_BOT_HW + 0.006 - POCKET_TOP_HW) * (t ** 0.92)
    # very slight inward taper at the bottom
    side = side - 0.006 * smoothstep(POCKET_OPEN_Y, POCKET_Y0, y)
    return side


def pocket_sdf2d(x, y):
    """Approximate 2D signed distance to the pocket outline in the XY plane."""
    hw = pocket_halfwidth(y)
    dx = np.abs(x) - hw
    # slanted edge: convert horizontal distance to perpendicular distance
    slope = (POCKET_BOT_HW - POCKET_TOP_HW) / (POCKET_Y1 - POCKET_OPEN_Y)
    on_slant = (y > POCKET_OPEN_Y) & (y < POCKET_Y1)
    dx = np.where(on_slant, dx / np.sqrt(1 + slope * slope), dx)
    dy = np.maximum(POCKET_Y0 - y, y - POCKET_Y1)
    out = np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2)
    return out + np.minimum(np.maximum(dx, dy), 0)


# --------------------------------------------------------------------------
# Component SDFs
# --------------------------------------------------------------------------
def torso_raw(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ax = np.abs(x)
    ys = [-0.01, 0.010, 0.075, 0.092, 0.125, 0.250, 0.450, 0.600, 0.690, 0.780, 0.86]
    A = np.interp(y, ys, [0.278, 0.279, 0.281, 0.292, 0.297, 0.294, 0.298, 0.312, 0.326, 0.318, 0.300])
    B = np.interp(y, ys, [0.104, 0.106, 0.110, 0.121, 0.128, 0.129, 0.128, 0.124, 0.118, 0.106, 0.092])
    # front belly is fuller than the back
    B = B + np.where(z > 0, 0.008 * smoothstep(0.85, 0.3, y), -0.004)
    r = 0.080
    qx = ax - (A - r)
    qz = np.abs(z) - (B - r)
    d2 = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - r
    ytop = SHOULDER_Y - 0.030 * (np.clip(ax - 0.05, 0, None) / 0.22) ** 1.6 - 0.016 * (z / 0.12) ** 2
    d = smax(d2, (y - ytop) * 0.9, 0.065)
    d = smax(d, -y, 0.004)
    return d


def torso(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    d = torso_raw(p)
    ax = np.abs(x)
    sgn = np.sign(x)

    # --- drape folds -----------------------------------------------------
    # blousing ripples just above the rib hem
    blouse = smoothstep(0.21, 0.098, y) * smoothstep(0.078, 0.098, y)
    d -= 0.0045 * blouse * (0.6 + 0.4 * np.sin(x * 38 + 1.3 * np.sin(x * 9)))
    # soft vertical drag lines from under the arms down the sides
    side = smoothstep(0.16, 0.29, ax) * smoothstep(0.66, 0.30, y) * smoothstep(0.10, 0.25, y)
    d -= 0.0030 * side * np.sin(z * 55 + y * 9 + sgn * 0.8)
    # gentle diagonal folds from shoulder towards chest centre (front+back)
    diag = smoothstep(0.78, 0.55, y) * smoothstep(0.05, 0.20, ax) * smoothstep(0.32, 0.20, ax)
    d -= 0.0030 * diag * np.sin((ax * 1.0 + (0.78 - y) * 0.75) * 48 + 0.6 * sgn)
    # low-frequency organic variation everywhere
    d -= 0.0022 * fbm(p * np.array([6.0, 4.0, 6.0]) + 3.1, 2)

    # --- kangaroo pocket (raised double layer on the front) ---------------
    pd = pocket_sdf2d(x, y)
    front = smoothstep(0.0, 0.06, z)
    inside = smoothstep(0.004, -0.007, pd)
    # pocket bags out a little in the middle
    bag = 0.0038 + 0.0035 * np.clip(1 - (x / 0.17) ** 2, 0, 1) * np.clip(np.sin(np.pi * (y - POCKET_Y0) / (POCKET_Y1 - POCKET_Y0)), 0, 1)
    # the hand openings lift away from the body
    slope = (POCKET_BOT_HW - POCKET_TOP_HW) / (POCKET_Y1 - POCKET_OPEN_Y)
    open_zone = ((y > POCKET_OPEN_Y - 0.01) & (y < POCKET_Y1)).astype(float)
    lift = 0.0045 * open_zone * smoothstep(-0.03, 0.0, pd) * smoothstep(POCKET_OPEN_Y - 0.01, POCKET_OPEN_Y + 0.05, y)
    d -= front * inside * (bag + lift)
    # small groove right outside the pocket outline (shadow line)
    d += front * 0.0010 * np.exp(-((pd - 0.005) / 0.0035) ** 2)

    # --- rib hem: slightly gathered + groove at the join -------------------
    d += 0.0018 * np.exp(-((y - HEM_TOP) / 0.004) ** 2)

    # neck opening going into the body (seen through the hood)
    neck = np.maximum(np.sqrt(x ** 2 + ((z - 0.005) / 1.12) ** 2) - NECK_R, 0.64 - y)
    d = smax(d, -neck, 0.012)
    return d


def sleeve_one(p, phase):
    """Sleeve on the +X side; p already mirrored."""
    d = np.full(len(p), 1e3)
    s_glob = np.zeros(len(p))
    best = np.full(len(p), 1e3)
    rad_best = np.zeros((len(p), 3))
    seglen = np.linalg.norm(np.diff(SLEEVE, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seglen)])
    # flatten the sleeve a little front-to-back
    q = p.copy()
    q[:, 2] = (q[:, 2] - 0.0) / 0.88
    for i in range(len(SLEEVE) - 1):
        di = sd_round_cone(q, SLEEVE[i], SLEEVE[i + 1], SLEEVE_R[i], SLEEVE_R[i + 1])
        d = smin(d, di, 0.02)
        t, rad = seg_param(p, SLEEVE[i], SLEEVE[i + 1])
        dist = np.linalg.norm(rad, axis=1)
        m = dist < best
        best = np.where(m, dist, best)
        s_glob = np.where(m, cum[i] + t * seglen[i], s_glob)
        rad_best[m] = rad[m]
    d = d * 0.88
    L = cum[-1]
    s = s_glob / L                          # 0 at shoulder, 1 at wrist
    theta = np.arctan2(rad_best[:, 2], rad_best[:, 0] - rad_best[:, 1] * 0.0)

    # --- folds -------------------------------------------------------------
    # stacked compression folds above the cuff (sleeve is longer than the arm)
    stack = smoothstep(0.62, 0.97, s)
    d -= 0.0060 * stack * np.sin(s * L * 95 + 1.8 * np.sin(theta * 2 + phase) + 1.2 * fbm(p * 14 + phase, 2) + phase)
    # crease rings around the elbow, partial around the sleeve
    elbow = np.exp(-((s - 0.50) / 0.13) ** 2)
    d -= 0.0032 * elbow * np.sin(s * L * 60 + 2.2 * np.cos(theta + phase)) * (0.45 + 0.55 * np.cos(theta - 0.6))
    # long twisting folds running down the upper arm
    upper = smoothstep(0.05, 0.25, s) * smoothstep(0.75, 0.45, s)
    d -= 0.0028 * upper * np.sin(theta * 3 + s * 7 + phase)
    d -= 0.0022 * fbm(p * 9 + phase * 5, 2)
    return d, s


def sleeves(p):
    q = p.copy()
    right = q[:, 0] >= 0
    q[:, 0] = np.abs(q[:, 0])
    d_r, s_r = sleeve_one(q, 0.0)
    d_l, s_l = sleeve_one(q, 1.7)
    d = np.where(right, d_r, d_l)
    s = np.where(right, s_r, s_l)
    # drop-shoulder armhole seam: a faint crease where sleeve meets body
    return d, s


def cuffs(p):
    q = p.copy()
    q[:, 0] = np.abs(q[:, 0])
    q[:, 2] = CUFF_A[2] + (q[:, 2] - CUFF_A[2]) / 0.86
    d = sd_round_cone(q, CUFF_A, CUFF_B, CUFF_R[0], CUFF_R[1]) * 0.86
    t, rad = seg_param(q, CUFF_A, CUFF_B)
    # opening into the sleeve
    hole = sd_round_cone(q, CUFF_A + (CUFF_B - CUFF_A) * 0.45, CUFF_B + (CUFF_B - CUFF_A) * 0.4, 0.028, 0.036)
    d = smax(d, -hole, 0.004)
    return d, t


def hood_parts(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ax = np.abs(x)
    q = p.copy()
    # fuller at the back/top, slightly narrower at the face
    q[:, 0] *= 1.0 + 0.10 * smoothstep(-0.05, 0.10, z - HOOD_C[2])
    E = sd_ellipsoid(q, HOOD_C, HOOD_R)
    # a flattened crown and a fold where the hood collapses on the shoulders
    E -= 0.0040 * fbm(p * 8 + 11.0, 2)
    E -= 0.0045 * smoothstep(0.86, 0.78, y) * np.sin(ax * 70 + z * 30)
    # face opening: forward plane + V-shaped crossover at the neck
    zplane = 0.015 + 0.26 * (0.985 - y) + 0.11 * (ax / 0.15) ** 2
    yv = 0.770 + 0.62 * ax
    open_sdf = np.maximum((zplane - z) * 0.85, (yv - y) * 0.75)
    t = 0.0042 + 0.0060 * np.exp(-(open_sdf / 0.010) ** 2)
    shell = np.abs(E) - t
    shell = smax(shell, -open_sdf, 0.005)
    return shell, E, open_sdf


def garment(p, return_parts=False):
    dt = torso(p)
    ds, s_sl = sleeves(p)
    dc, t_cf = cuffs(p)
    dh, E, open_sdf = hood_parts(p)
    # armhole seam groove (drop shoulder): crease where body and sleeve meet
    y = p[:, 1]
    d = smin(dt, ds, 0.003 + 0.030 * smoothstep(0.36, 0.55, y))
    seam = np.exp(-((dt - ds) / 0.006) ** 2) * (np.minimum(dt, ds) < 0.02)
    d += 0.0016 * seam
    # cuff: small step + groove where the sleeve is gathered into it
    d = smin(d, dc, 0.010)
    d = smin(d, dh, 0.014)
    if return_parts:
        return d, dict(torso=dt, sleeve=ds, cuff=dc, hood=dh, s_sleeve=s_sl, t_cuff=t_cf, open=open_sdf, E=E)
    return d


def garment_grad(p, eps=0.0008):
    g = np.zeros_like(p)
    for k in range(3):
        e = np.zeros(3)
        e[k] = eps
        g[:, k] = (garment(p + e) - garment(p - e)) / (2 * eps)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-9)


def project_to_surface(p, offset=0.0, iters=6):
    p = p.copy()
    for _ in range(iters):
        d = garment(p) - offset
        g = garment_grad(p)
        p -= d[:, None] * g
    return p


# --------------------------------------------------------------------------
# 1) Polygonise the shell
# --------------------------------------------------------------------------
def build_shell(voxel=None):
    import os
    quick = os.environ.get("QUICK")
    voxel = voxel or (0.007 if quick else 0.0032)
    lo = np.array([-0.545, -0.045, -0.255])
    hi = np.array([0.545, 1.015, 0.185])
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    xs = lo[0] + np.arange(n[0]) * voxel
    ys = lo[1] + np.arange(n[1]) * voxel
    zs = lo[2] + np.arange(n[2]) * voxel
    vol = np.empty((n[0], n[1], n[2]), dtype=np.float32)
    Y, Z = np.meshgrid(ys, zs, indexing="ij")
    for i, x in enumerate(xs):
        pts = np.stack([np.full(Y.size, x), Y.ravel(), Z.ravel()], axis=1)
        vol[i] = garment(pts).reshape(Y.shape)
    print("volume", vol.shape)
    verts, faces, _, _ = marching_cubes(vol, 0.0, spacing=(voxel, voxel, voxel))
    verts += lo
    mesh = trimesh.Trimesh(verts, faces, process=True)
    print("marching cubes:", len(mesh.vertices), "verts", len(mesh.faces), "faces")
    # keep the main connected piece (drops tiny floaters)
    parts = mesh.split(only_watertight=False)
    mesh = max(parts, key=lambda m: len(m.faces))
    trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=12)
    if quick:
        return mesh
    import fast_simplification
    v, f = fast_simplification.simplify(mesh.vertices.astype(np.float32), mesh.faces.astype(np.int32),
                                         target_count=230_000)
    mesh = trimesh.Trimesh(v, f, process=True)
    trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=4)
    print("decimated:", len(mesh.vertices), "verts", len(mesh.faces), "faces")
    return mesh


# --------------------------------------------------------------------------
# 2) Baked lighting helpers: SDF ambient occlusion + heather mottle
# --------------------------------------------------------------------------
def sdf_ao(p, n):
    occ = np.zeros(len(p))
    w = 1.0
    for h in (0.006, 0.014, 0.028, 0.050, 0.085, 0.13):
        d = garment(p + n * h)
        occ += w * np.clip(h - d, 0, None) / h
        w *= 0.72
    return np.clip(1.0 - 0.42 * occ, 0.30, 1.0)


def heather(p):
    m = 1.0 + 0.030 * fbm(p * 14.0, 3) + 0.018 * vnoise3(p * 55.0)
    return np.clip(m, 0.9, 1.06)


# --------------------------------------------------------------------------
# 3) Topstitching, cords
# --------------------------------------------------------------------------
def resample(pts, step):
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1]
    s = np.arange(0, L, step)
    return np.stack([np.interp(s, cum, pts[:, k]) for k in range(3)], axis=1)


def tube(pts, radius, sides=8, rz=None, closed_ends=True):
    """Tube mesh along a polyline. radius can be scalar or per-point."""
    pts = np.asarray(pts, float)
    n = len(pts)
    radius = np.broadcast_to(np.asarray(radius, float), (n,))
    rz = radius if rz is None else np.broadcast_to(np.asarray(rz, float), (n,))
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0])
    u = np.cross(tang, ref)
    bad = np.linalg.norm(u, axis=1) < 1e-3
    u[bad] = np.cross(tang[bad], [1.0, 0, 0])
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    w = np.cross(tang, u)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    V = (pts[:, None, :] + radius[:, None, None] * np.cos(ang)[None, :, None] * u[:, None, :]
         + rz[:, None, None] * np.sin(ang)[None, :, None] * w[:, None, :]).reshape(-1, 3)
    F = []
    for i in range(n - 1):
        for j in range(sides):
            k = (j + 1) % sides
            a, b, c, d = i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k, i * sides + k
            F += [[a, b, c], [a, c, d]]
    if closed_ends:
        V = np.vstack([V, pts[0], pts[-1]])
        c0, c1 = len(V) - 2, len(V) - 1
        last = (n - 1) * sides
        for j in range(sides):
            k = (j + 1) % sides
            F += [[c0, k, j], [c1, last + j, last + k]]
    # wind faces so normals point outwards
    return trimesh.Trimesh(V, np.array(F)[:, ::-1], process=False)


def stitch_line(guess, offset=0.0004, dash=0.0030, gap=0.0016, r=0.00052):
    """Project a guide polyline onto the fabric and emit dashed thread."""
    pts = resample(guess, 0.002)
    pts = project_to_surface(pts, offset=0.0)
    pts = resample(pts, 0.0008)
    n = garment_grad(pts)
    pts = pts + n * offset
    out = []
    period = dash + gap
    per = int(round(period / 0.0008))
    dl = max(2, int(round(dash / 0.0008)))
    for i0 in range(0, len(pts) - dl, per):
        seg = pts[i0:i0 + dl + 1]
        # bow each stitch slightly outwards so it sits on top of the knit
        bow = np.sin(np.linspace(0, np.pi, len(seg)))[:, None] * n[i0:i0 + dl + 1] * 0.00035
        out.append(tube(seg + bow, r, sides=5))
    return out


def ring_guess(center, axis, radius_u, radius_w, n=240, start=0.0, end=2 * np.pi, axis_u_hint=None):
    axis = np.asarray(axis, float)
    axis /= np.linalg.norm(axis)
    hint = np.array([0, 0, 1.0]) if axis_u_hint is None else np.asarray(axis_u_hint, float)
    w = hint - axis * (hint @ axis)
    w /= np.linalg.norm(w)
    u = np.cross(w, axis)
    a = np.linspace(start, end, n)
    return center + radius_u * np.cos(a)[:, None] * u + radius_w * np.sin(a)[:, None] * w


def build_stitching():
    pieces = []
    # --- kangaroo pocket ----------------------------------------------------
    def pocket_outline(inset, n=400):
        ys = np.linspace(POCKET_Y0 + inset, POCKET_Y1 - inset, n)
        right = np.stack([pocket_halfwidth(ys) - inset * 1.2, ys, np.full(n, 0.3)], axis=1)
        left = right[::-1].copy()
        left[:, 0] *= -1
        top = np.stack([np.linspace(-1, 1, 200) * (POCKET_TOP_HW - inset * 1.4), np.full(200, POCKET_Y1 - inset), np.full(200, 0.3)], axis=1)
        bot = np.stack([np.linspace(1, -1, 200) * (POCKET_BOT_HW - inset * 1.2), np.full(200, POCKET_Y0 + inset), np.full(200, 0.3)], axis=1)
        return right, top, left, bot

    def to_front(guess):
        g = guess.copy()
        g[:, 2] = 0.16
        return g

    # perimeter stitch 3 mm in, plus a second row on the slanted openings
    r, t, l, b = pocket_outline(0.0045)
    for g in (r, l, b):
        pieces += stitch_line(to_front(g))
    # pocket top hem: two rows
    for yy in (POCKET_Y1 - 0.0045, POCKET_Y1 - 0.014):
        xs = np.linspace(-POCKET_TOP_HW + 0.006, POCKET_TOP_HW - 0.006, 200)
        pieces += stitch_line(to_front(np.stack([xs, np.full(200, yy), np.zeros(200)], 1)))
    # opening double row (cover stitch along the slanted edge)
    for side in (-1, 1):
        ys = np.linspace(POCKET_OPEN_Y + 0.004, POCKET_Y1 - 0.016, 160)
        xs = side * (pocket_halfwidth(ys) - 0.0135)
        pieces += stitch_line(to_front(np.stack([xs, ys, np.zeros(160)], 1)))

    # --- rib hem join + cuff joins ------------------------------------------
    for yy in (HEM_TOP + 0.0045,):
        a = np.linspace(0, 2 * np.pi, 900)
        g = np.stack([0.32 * np.cos(a), np.full_like(a, yy), 0.16 * np.sin(a)], 1)
        pieces += stitch_line(g)
    for side in (-1, 1):
        ax = CUFF_B - CUFF_A
        c = CUFF_A + ax * 0.03
        g = ring_guess(c, ax, 0.075, 0.075, n=400)
        g[:, 0] *= side
        pieces += stitch_line(g)

    # --- drop-shoulder armhole seams (stitch beside the seam on the body) -----
    for side in (-1, 1):
        pts = []
        # points on the seam: where torso and sleeve distances are equal
        for ang in np.linspace(-np.pi * 0.98, np.pi * 0.98, 260):
            c = np.array([0.318, 0.610, -0.002])
            v = np.array([np.sin(ang) * 0.02, np.cos(ang), np.sin(ang)])
            v[1] *= 0.14
            v[2] *= 0.13
            pts.append(c + v - np.array([0.012 * np.cos(ang), 0, 0]))
        g = np.array(pts)
        g[:, 0] *= side
        pieces += stitch_line(g)

    # --- side seams -----------------------------------------------------------
    for side in (-1, 1):
        ys = np.linspace(HEM_TOP + 0.01, 0.45, 200)
        g = np.stack([np.full(200, side * 0.40), ys, np.full(200, -0.006)], 1)
        pieces += stitch_line(g)

    # --- hood: front edge topstitch and centre-back seam ---------------------
    pieces += stitch_line(hood_edge_curve(0.014))
    for xoff in (-0.0045, 0.0045):
        a = np.linspace(0.30 * np.pi, 1.36 * np.pi, 300)
        g = np.stack([np.full_like(a, xoff), HOOD_C[1] + 0.20 * np.sin(a) * 0.95, HOOD_C[2] + 0.20 * np.cos(a)], 1)
        g = g[(g[:, 1] > 0.86)]
        pieces += stitch_line(g)

    # --- shoulder seams --------------------------------------------------------
    for side in (-1, 1):
        xs = np.linspace(0.19, 0.29, 80)
        g = np.stack([side * xs, np.full(80, 0.93), np.full(80, -0.012)], 1)
        pieces += stitch_line(g)
    return trimesh.util.concatenate(pieces)


def hood_edge_curve(inset, n=420):
    """Points on the outer hood surface, `inset` metres back from the face opening."""
    c = np.array([0.0, 0.875, 0.09])
    pts = []
    for ang in np.linspace(-0.40 * np.pi, 1.40 * np.pi, n):
        dirv = np.array([np.cos(ang), np.sin(ang), 0.0])
        lo, hi = 0.0, 0.30
        for _ in range(40):  # bisect along the ray for open_sdf == inset
            mid = 0.5 * (lo + hi)
            q = c + dirv * mid
            # slide q onto the ellipsoid surface along z
            zs = np.linspace(0.17, -0.06, 120)
            P = np.stack([np.full(120, q[0]), np.full(120, q[1]), zs], 1)
            _, E, o = hood_parts(P)
            k = np.argmax(E < 0) if np.any(E < 0) else 0
            if o[k] < inset:
                lo = mid
            else:
                hi = mid
        pts.append(P[k])
    pts = np.array(pts)
    _, E, _ = hood_parts(pts)
    pts = pts[(pts[:, 1] > 0.80)]
    # nudge outwards along the ellipsoid normal so projection lands on the outside
    nrm = (pts - HOOD_C) / HOOD_R ** 2
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    return pts + nrm * 0.01


def surface_front_z(x, y, r):
    """z of the front fabric surface (+offset r) at (x, y), by marching from the front."""
    z = np.full(len(x), 0.30)
    for _ in range(120):
        p = np.stack([x, y, z], 1)
        d = garment(p) - r
        z -= np.clip(d, -0.004, 0.02) * 0.9
        if np.all(np.abs(d) < 0.0002):
            break
    return z


def build_drawstrings():
    cords, tips, eyelets = [], [], []
    for side, (dx_end, length) in ((-1, (-0.006, 0.312)), (1, (-0.004, 0.300))):
        x0 = side * 0.056
        y0 = 0.812
        # eyelet sits on the hood's front band
        z0 = surface_front_z(np.array([x0]), np.array([y0]), 0.0)[0]
        n0 = garment_grad(np.array([[x0, y0, z0]]))[0]
        ring = np.array([[x0 + 0.0055 * np.cos(a), y0 + 0.0055 * np.sin(a), z0] for a in np.linspace(0, 2 * np.pi, 40)])
        ring = project_to_surface(ring, offset=0.0009)
        eyelets.append(tube(ring, 0.0016, sides=6, closed_ends=False))
        # hanging cord: taut string over the chest, free end hangs vertically
        N = 160
        u = np.linspace(0, 1, N)
        ys = y0 - length * u
        xs = x0 + side * (dx_end * u ** 1.4 + 0.003 * np.sin(np.pi * u))
        rc = 0.0042
        surf = surface_front_z(xs, ys, rc + 0.0006)
        zs = np.maximum(surf, z0 + 0.004)
        zs[0] = z0 + 0.002
        for _ in range(400):
            zs[1:-1] = np.maximum(surf[1:-1], 0.5 * (zs[:-2] + zs[2:]))
            zs[-1] = max(surf[-1], zs[-2])
        path = np.stack([xs, ys, zs], 1)
        # a small kink where the cord exits the eyelet
        path[:6, 2] = np.linspace(z0 - 0.002, zs[6], 6)
        cords.append(tube(path, rc, sides=14, rz=rc * 0.78, closed_ends=True))
        # metal aglet
        tdir = path[-1] - path[-4]
        tdir /= np.linalg.norm(tdir)
        tip = np.array([path[-1] + tdir * s for s in np.linspace(-0.004, 0.026, 14)])
        prof = np.full(14, 0.0037)
        prof[-2:] = [0.0033, 0.0026]
        tips.append(tube(tip, prof, sides=20))
    return trimesh.util.concatenate(cords), trimesh.util.concatenate(tips), trimesh.util.concatenate(eyelets)


# --------------------------------------------------------------------------
# 4) Procedural textures (tileable)
# --------------------------------------------------------------------------
TILE_M = 0.05  # one texture tile covers 5 x 5 cm of fabric


def _height_to_normal(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    n = np.stack([-gx * strength, gy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def _tile_noise(size, cells, rng):
    g = rng.normal(size=(cells, cells))
    F = np.fft.fft2(g)
    big = np.zeros((size, size), complex)
    c = cells // 2
    big[:c, :c] = F[:c, :c]
    big[:c, -c:] = F[:c, -c:]
    big[-c:, :c] = F[-c:, :c]
    big[-c:, -c:] = F[-c:, -c:]
    out = np.real(np.fft.ifft2(big))
    return (out - out.mean()) / (out.std() + 1e-9)


def make_textures(size=1024):
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:size, 0:size] / size
    # single-jersey face: columns of V-shaped loops (~0.65 mm wales at 5 cm/tile)
    wales = 76
    courses = 98
    u = xx * wales
    v = yy * courses
    fu = (u % 1.0) - 0.5
    fv = (v % 1.0)
    leg = np.abs(fu) - 0.25 - (fv - 0.5) * 0.18 * np.sign(fu)
    loop = np.exp(-(leg / 0.13) ** 2)
    jitter = _tile_noise(size, 64, rng) * 0.25
    fuzz = _tile_noise(size, 512, rng)
    h_jersey = loop + 0.30 * jitter + 0.22 * fuzz
    Image.fromarray(_height_to_normal(h_jersey, 1.6)).save(TEX_DIR / "fleece_jersey_normal.jpg", quality=92)

    # 1x1 rib: strong vertical ridges (~3.2 mm period) plus the jersey face
    ribs = 16
    r = np.cos(2 * np.pi * xx * ribs)
    h_rib = 1.2 * np.sign(r) * np.abs(r) ** 0.6 + 0.35 * loop + 0.20 * fuzz
    Image.fromarray(_height_to_normal(h_rib, 3.2)).save(TEX_DIR / "rib_knit_normal.jpg", quality=92)

    # colour grain: near-white multiplier, slightly brighter loop tops
    grain = 0.93 + 0.035 * loop + 0.02 * jitter + 0.015 * fuzz
    grain = np.clip(grain, 0, 1)
    g8 = (np.stack([grain] * 3, -1) * 255).astype(np.uint8)
    Image.fromarray(g8).save(TEX_DIR / "fabric_grain_color.jpg", quality=90)
    grain_r = 0.93 + 0.05 * (r > 0) + 0.02 * fuzz
    Image.fromarray((np.stack([np.clip(grain_r, 0, 1)] * 3, -1) * 255).astype(np.uint8)).save(TEX_DIR / "rib_grain_color.jpg", quality=90)
    print("textures written")


# --------------------------------------------------------------------------
# 5) UVs (box projection in metres / TILE_M, split per projection axis)
# --------------------------------------------------------------------------
def box_uv_split(mesh, colors, rib_axis=None):
    V = np.asarray(mesh.vertices)
    F = np.asarray(mesh.faces)
    N = np.asarray(mesh.vertex_normals)
    fn = np.asarray(mesh.face_normals)
    if rib_axis is not None:
        # cylindrical projection around a local axis, ribs run along the axis
        c, a = rib_axis
        a = np.asarray(a, float) / np.linalg.norm(a)
        rel = V - c
        h = rel @ a
        radial = rel - h[:, None] * a
        ref = np.array([0, 0, 1.0]) - a * a[2]
        ref /= np.linalg.norm(ref)
        ang = np.arctan2(np.cross(ref, radial) @ a, radial @ ref)
        rad = np.linalg.norm(radial, axis=1).mean()
        uv = np.stack([ang * rad, h], 1) / TILE_M
        # split the seam where the angle wraps
        fa = ang[F]
        wrap = (fa.max(1) - fa.min(1)) > np.pi
        newV, newN, newC, newUV, newF = [V], [N], [colors], [uv], F.copy()
        extra = {}
        cnt = len(V)
        for fi in np.where(wrap)[0]:
            for k in range(3):
                vi = F[fi, k]
                if ang[vi] < 0:
                    if vi not in extra:
                        extra[vi] = cnt
                        cnt += 1
                        newV.append(V[vi:vi + 1])
                        newN.append(N[vi:vi + 1])
                        newC.append(colors[vi:vi + 1])
                        newUV.append(np.array([[(ang[vi] + 2 * np.pi) * rad / TILE_M, uv[vi, 1]]]))
                    newF[fi, k] = extra[vi]
        return np.vstack(newV), np.vstack(newN), np.vstack(newC), np.vstack(newUV), newF
    axis = np.argmax(np.abs(fn), axis=1)
    sign = np.sign(fn[np.arange(len(F)), axis])
    key = axis * 2 + (sign > 0)
    outV, outN, outC, outUV, outF = [], [], [], [], np.zeros_like(F)
    base = 0
    for k in np.unique(key):
        fidx = np.where(key == k)[0]
        sub = F[fidx]
        uniq, inv = np.unique(sub.ravel(), return_inverse=True)
        P = V[uniq]
        ax = k // 2
        s = 1 if k % 2 else -1
        if ax == 0:
            uv = np.stack([-s * P[:, 2], P[:, 1]], 1)
        elif ax == 1:
            uv = np.stack([P[:, 0], -s * P[:, 2]], 1)
        else:
            uv = np.stack([s * P[:, 0], P[:, 1]], 1)
        outV.append(P)
        outN.append(N[uniq])
        outC.append(colors[uniq])
        outUV.append(uv / TILE_M)
        outF[fidx] = inv.reshape(-1, 3) + base
        base += len(uniq)
    return np.vstack(outV), np.vstack(outN), np.vstack(outC), np.vstack(outUV), outF


# --------------------------------------------------------------------------
# 6) glTF writer (pygltflib) with KHR_materials_sheen
# --------------------------------------------------------------------------
def write_glb(parts, path):
    import pygltflib as G

    blob = bytearray()
    bufferViews, accessors, meshes, nodes, images, textures, samplers = [], [], [], [], [], [], []

    def add_view(data, target=None):
        nonlocal blob
        while len(blob) % 4:
            blob += b"\0"
        off = len(blob)
        blob += data
        bufferViews.append(G.BufferView(buffer=0, byteOffset=off, byteLength=len(data), target=target))
        return len(bufferViews) - 1

    def add_acc(arr, ctype, typ, target, normalized=False, minmax=False):
        arr = np.ascontiguousarray(arr)
        bv = add_view(arr.tobytes(), target)
        kw = {}
        if minmax:
            kw = dict(min=arr.min(0).tolist(), max=arr.max(0).tolist())
        accessors.append(G.Accessor(bufferView=bv, componentType=ctype, count=len(arr), type=typ, normalized=normalized, **kw))
        return len(accessors) - 1

    samplers.append(G.Sampler(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497))
    samplers.append(G.Sampler(magFilter=9729, minFilter=9987, wrapS=33071, wrapT=33071))

    def add_tex(file, sampler=0):
        data = Path(file).read_bytes()
        bv = add_view(data)
        mime = "image/png" if str(file).endswith(".png") else "image/jpeg"
        images.append(G.Image(bufferView=bv, mimeType=mime, name=Path(file).stem))
        textures.append(G.Texture(sampler=sampler, source=len(images) - 1))
        return len(textures) - 1

    t_jn = add_tex(TEX_DIR / "fleece_jersey_normal.jpg")
    t_rn = add_tex(TEX_DIR / "rib_knit_normal.jpg")
    t_jc = add_tex(TEX_DIR / "fabric_grain_color.jpg")
    t_rc = add_tex(TEX_DIR / "rib_grain_color.jpg")
    t_pr = add_tex(PRINT_PNG, sampler=1)
    t_fp = add_tex(FRONT_PNG, sampler=1)
    t_sp = add_tex(SLEEVE_PNG, sampler=1)

    def fabric(name, hexcode, color_tex, normal_tex, nscale, rough, sheen=1.0):
        c = srgb_to_linear(hexcode)
        ext = {}
        if sheen:
            sc = np.clip((0.6 * c + 0.4 * c.mean() + 0.06) * sheen, 0, 1)
            ext["KHR_materials_sheen"] = {"sheenColorFactor": sc.tolist(), "sheenRoughnessFactor": 0.55}
        pbr = G.PbrMetallicRoughness(baseColorFactor=[*c.tolist(), 1.0], metallicFactor=0.0, roughnessFactor=rough)
        if color_tex is not None:
            pbr.baseColorTexture = G.TextureInfo(index=color_tex)
        m = G.Material(name=name, pbrMetallicRoughness=pbr, doubleSided=True, extensions=ext)
        if normal_tex is not None:
            m.normalTexture = G.NormalMaterialTexture(index=normal_tex, scale=nscale)
        return m

    def ink(name, tex):
        return G.Material(name=name, alphaMode="BLEND", doubleSided=False,
                          pbrMetallicRoughness=G.PbrMetallicRoughness(
                              baseColorFactor=[1.0, 1.0, 1.0, 1.0], baseColorTexture=G.TextureInfo(index=tex),
                              metallicFactor=0.0, roughnessFactor=0.88),
                          normalTexture=G.NormalMaterialTexture(index=t_jn, texCoord=1, scale=0.55),
                          extensions={"KHR_materials_sheen": {"sheenColorFactor": [0.12, 0.09, 0.07], "sheenRoughnessFactor": 0.6}})

    materials = [
        fabric("Fleece_Oatmeal", FABRIC_HEX, t_jc, t_jn, 0.55, 0.93),
        fabric("Rib_Knit_Oatmeal", RIB_HEX, t_rc, t_rn, 0.9, 0.95),
        fabric("Stitch_Thread", THREAD_HEX, None, None, 1.0, 0.8, sheen=0),
        fabric("Drawcord", CORD_HEX, t_jc, t_jn, 0.8, 0.9, sheen=0.5),
        G.Material(name="Aglet_Gunmetal", pbrMetallicRoughness=G.PbrMetallicRoughness(
            baseColorFactor=[*srgb_to_linear(AGLET_HEX).tolist(), 1.0], metallicFactor=1.0, roughnessFactor=0.32)),
        # water-based screen-print ink: sits in the fleece, keeps the knit texture
        ink("Back_Print_Ink", t_pr),
        ink("Front_Print_Ink", t_fp),
        ink("Sleeve_Print_Ink", t_sp),
    ]
    mat_index = {m.name: i for i, m in enumerate(materials)}

    for name, (V, Nn, C, UV, F, mat) in parts.items():
        attrs = G.Attributes(
            POSITION=add_acc(V.astype(np.float32), 5126, "VEC3", 34962, minmax=True),
            NORMAL=add_acc(Nn.astype(np.float32), 5126, "VEC3", 34962),
        )
        if UV is not None:
            attrs.TEXCOORD_0 = add_acc(UV.astype(np.float32), 5126, "VEC2", 34962)
        if name in EXTRA_UV1:
            attrs.TEXCOORD_1 = add_acc(EXTRA_UV1[name].astype(np.float32), 5126, "VEC2", 34962)
        if C is not None:
            c4 = np.concatenate([C, np.ones((len(C), 1))], 1)
            attrs.COLOR_0 = add_acc(np.clip(np.round(c4 * 65535), 0, 65535).astype(np.uint16), 5123, "VEC4", 34962, normalized=True)
        idx = add_acc(F.astype(np.uint32).ravel(), 5125, "SCALAR", 34963)
        meshes.append(G.Mesh(name=name, primitives=[G.Primitive(attributes=attrs, indices=idx, material=mat_index[mat])]))
        nodes.append(G.Node(name=name, mesh=len(meshes) - 1))

    gltf = G.GLTF2(
        asset=G.Asset(generator="build_hoodie.py", version="2.0"),
        extensionsUsed=["KHR_materials_sheen"],
        scene=0,
        scenes=[G.Scene(name="Hoodie", nodes=list(range(len(nodes))))],
        nodes=nodes, meshes=meshes, materials=materials, accessors=accessors,
        bufferViews=bufferViews, buffers=[G.Buffer(byteLength=len(blob))],
        images=images, textures=textures, samplers=samplers,
    )
    gltf.set_binary_blob(bytes(blob))
    gltf.save_binary(str(path))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def make_print_texture(width=2048):
    """Turn the parchment artwork into ink-only RGBA (paper becomes transparent)."""
    im = Image.open(PRINT_SRC).convert("RGB").crop(PRINT_CROP)
    h = round(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    L = a @ np.array([0.30, 0.59, 0.11])
    bg = np.median(L)                      # parchment
    ink = np.percentile(L, 0.5)
    raw = (bg - L) / (bg - ink)
    alpha = smoothstep(0.12, 0.72, raw) * 0.96
    rgba = np.zeros((h, width, 4), np.uint8)
    rgba[..., :3] = [int(INK_HEX[i:i + 2], 16) for i in (1, 3, 5)]
    rgba[..., 3] = np.round(alpha * 255)
    rgba[:4, :, 3] = rgba[-4:, :, 3] = 0
    rgba[:, :4, 3] = rgba[:, -4:, 3] = 0
    Image.fromarray(rgba, "RGBA").save(PRINT_PNG, optimize=True)
    return width / h


def make_front_text_texture(width=2400, pad=40):
    """Render the front slogan as ink-only RGBA; returns the image aspect (w/h)."""
    from PIL import ImageDraw, ImageFont
    probe = ImageFont.truetype(str(FRONT_FONT), 200)
    w0 = probe.getlength(FRONT_LINES[0])
    size = int(200 * (width - 2 * pad) / w0)
    sizes = [size, int(size * 0.92)]           # the date is set a touch smaller
    fonts = [ImageFont.truetype(str(FRONT_FONT), s) for s in sizes]
    asc, desc = fonts[0].getmetrics()
    line_gap = int((asc + desc) * 1.12)
    h = pad * 2 + line_gap + sum(f.getmetrics()[0] + f.getmetrics()[1] for f in fonts[1:])
    mask = Image.new("L", (width, h), 0)
    d = ImageDraw.Draw(mask)
    y = pad
    for line, f in zip(FRONT_LINES, fonts):
        d.text((width / 2, y), line, font=f, fill=255, anchor="ma")
        y += line_gap
    rgba = np.zeros((h, width, 4), np.uint8)
    rgba[..., :3] = [int(FRONT_INK_HEX[i:i + 2], 16) for i in (1, 3, 5)]
    rgba[..., 3] = np.asarray(mask)
    Image.fromarray(rgba, "RGBA").save(FRONT_PNG, optimize=True)
    return width / h, (width - 2 * pad) / width


def build_print_decal(shell, lab, N, colors, piece, width, height, y_top, facing, name):
    """Decal mesh over `piece` faces under the print, lifted 0.8 mm, planar UVs.
    facing=+1 projects from the front, -1 from the back."""
    y0 = y_top - height
    V = np.asarray(shell.vertices)
    uv = np.stack([0.5 + facing * V[:, 0] / width, 1.0 - (V[:, 1] - y0) / height], 1)
    fidx = np.where(lab == piece)[0]
    F = np.asarray(shell.faces)[fidx]
    fu = uv[F]
    inside = (fu.max(1) > -0.005).all(1) & (fu.min(1) < 1.005).all(1)
    keep = inside & (facing * np.asarray(shell.face_normals)[fidx, 2] > 0.15)
    F = F[keep]
    uniq, inv = np.unique(F.ravel(), return_inverse=True)
    n = N[uniq]
    Vd = V[uniq] + n * 0.0008
    uv1 = np.stack([facing * V[uniq, 0], V[uniq, 1]], 1) / TILE_M
    print(f"  {name:16s} {len(F):7d} faces  ({width * 100:.0f} x {height * 100:.0f} cm)")
    return Vd, n, colors[uniq], uv[uniq], inv.reshape(-1, 3), uv1


def make_sleeve_text_texture(size=320, pad=24):
    """Render the sleeve number as ink-only RGBA; returns (aspect, cap height fraction)."""
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype(str(FRONT_FONT), size)
    sw = round(size * SLEEVE_BOLD)          # thicken the strokes for a bolder look
    l, t, r, b = font.getbbox(SLEEVE_TEXT, stroke_width=sw)
    w, h = (r - l) + 2 * pad, (b - t) + 2 * pad
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), SLEEVE_TEXT, font=font, fill=255, stroke_width=sw, stroke_fill=255)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = [int(FRONT_INK_HEX[i:i + 2], 16) for i in (1, 3, 5)]
    rgba[..., 3] = np.asarray(mask)
    Image.fromarray(rgba, "RGBA").save(SLEEVE_PNG, optimize=True)
    return w / h, (b - t) / h


def build_sleeve_print(shell, lab, N, colors, aspect, cap_frac):
    """Decal on the sleeve, projected along the local surface normal, text kept upright."""
    side = SLEEVE_SIDE
    piece = "Sleeve_Right" if side > 0 else "Sleeve_Left"
    flip = np.array([side, 1.0, 1.0])
    anchor = SLEEVE_ANCHOR * flip
    facing = SLEEVE_FACING * flip
    facing = facing / np.linalg.norm(facing)
    c = project_to_surface((anchor + facing * 0.09)[None], iters=10)[0]
    n = garment_grad(c[None])[0]
    up = np.array([0.0, 1.0, 0.0]) - n * n[1]
    up /= np.linalg.norm(up)
    right = np.cross(up, n)
    h = SLEEVE_TEXT_H / cap_frac
    w = h * aspect
    V = np.asarray(shell.vertices)
    rel = V - c
    uv = np.stack([0.5 + (rel @ right) / w, 0.5 - (rel @ up) / h], 1)
    near = np.abs(rel @ n) < 0.04
    fidx = np.where(lab == piece)[0]
    F = np.asarray(shell.faces)[fidx]
    fu = uv[F]
    inside = (fu.max(1) > -0.02).all(1) & (fu.min(1) < 1.02).all(1) & near[F].all(1)
    keep = inside & (np.asarray(shell.face_normals)[fidx] @ n > 0.3)
    F = F[keep]
    uniq, inv = np.unique(F.ravel(), return_inverse=True)
    nn = N[uniq]
    Vd = V[uniq] + nn * 0.0008
    uv1 = np.stack([rel[uniq] @ right, rel[uniq] @ up], 1) / TILE_M
    print(f"  {'Sleeve_Print':16s} {len(F):7d} faces  ({w * 100:.1f} x {h * 100:.1f} cm)")
    return Vd, nn, colors[uniq], uv[uniq], inv.reshape(-1, 3), uv1


def build_back_print(shell, lab, N, colors, aspect):
    ph = PRINT_W / aspect * PRINT_STRETCH
    return build_print_decal(shell, lab, N, colors, "Back_Body", PRINT_W, ph, PRINT_TOP, -1, "Back_Print")


def build_front_print(shell, lab, N, colors, aspect, line_frac):
    w = FRONT_TEXT_W / line_frac          # texture width incl. padding
    h = w / aspect
    return build_print_decal(shell, lab, N, colors, "Front_Body", w, h, FRONT_TEXT_CY + h / 2, +1, "Front_Print")


def main():
    make_textures()
    aspect = make_print_texture()
    f_aspect, f_frac = make_front_text_texture()
    s_aspect, s_cap = make_sleeve_text_texture()
    shell = build_shell()

    V = np.asarray(shell.vertices)
    N = np.asarray(shell.vertex_normals)
    print("baking AO / mottle ...")
    ao = np.concatenate([sdf_ao(V[i:i + 50000], N[i:i + 50000]) for i in range(0, len(V), 50000)])
    mott = heather(V)
    shade = np.clip(ao * mott, 0, 1)
    # dark gap inside the pocket hand openings
    pd = pocket_sdf2d(V[:, 0], V[:, 1])
    slant = (V[:, 1] > POCKET_OPEN_Y) & (V[:, 1] < POCKET_Y1 - 0.005) & (V[:, 2] > 0.05)
    shade *= 1 - 0.30 * slant * np.exp(-((pd - 0.0015) / 0.0028) ** 2)
    colors = np.stack([shade] * 3, 1)

    # ---- label faces into named, editable garment pieces -------------------
    cent = shell.triangles_center
    _, P = garment(cent, return_parts=True)
    dmin = np.minimum.reduce([P["torso"], P["sleeve"], P["cuff"], P["hood"]])
    lab = np.full(len(cent), "Front_Body", dtype=object)
    is_hood = (P["hood"] <= dmin + 1e-6) & (cent[:, 1] > 0.6)
    is_cuff = P["cuff"] <= dmin + 1e-6
    is_sleeve = (P["sleeve"] <= dmin + 1e-6) & ~is_cuff
    is_torso = ~(is_hood | is_cuff | is_sleeve)
    lab[is_torso & (cent[:, 2] < 0)] = "Back_Body"
    lab[is_torso & (cent[:, 1] < HEM_TOP)] = "Rib_Hem"
    pocket_mask = (pocket_sdf2d(cent[:, 0], cent[:, 1]) < 0.0) & (cent[:, 2] > 0.05) & is_torso & (cent[:, 1] >= HEM_TOP)
    lab[pocket_mask] = "Kangaroo_Pocket"
    lab[is_sleeve & (cent[:, 0] >= 0)] = "Sleeve_Right"
    lab[is_sleeve & (cent[:, 0] < 0)] = "Sleeve_Left"
    lab[is_cuff & (cent[:, 0] >= 0)] = "Rib_Cuff_Right"
    lab[is_cuff & (cent[:, 0] < 0)] = "Rib_Cuff_Left"
    lab[is_hood] = "Hood"

    parts = {}
    order = ["Front_Body", "Back_Body", "Kangaroo_Pocket", "Sleeve_Right", "Sleeve_Left", "Hood",
             "Rib_Hem", "Rib_Cuff_Right", "Rib_Cuff_Left"]
    for name in order:
        fidx = np.where(lab == name)[0]
        if len(fidx) == 0:
            continue
        sub = shell.submesh([fidx], append=True, repair=False)
        # keep the shell's smooth normals (avoid seams between pieces)
        _, vid = shell.kdtree.query(sub.vertices)
        sub_normals = N[vid]
        sub_colors = colors[vid]
        sub = trimesh.Trimesh(sub.vertices, sub.faces, vertex_normals=sub_normals, process=False)
        if name == "Rib_Hem":
            Vx, Nx, Cx, UVx, Fx = box_uv_split(sub, sub_colors, rib_axis=(np.zeros(3), np.array([0, 1.0, 0])))
            mat = "Rib_Knit_Oatmeal"
        elif name.startswith("Rib_Cuff"):
            s = 1 if name.endswith("Right") else -1
            c = CUFF_A * np.array([s, 1, 1])
            a = (CUFF_A - CUFF_B) * np.array([s, 1, 1])
            Vx, Nx, Cx, UVx, Fx = box_uv_split(sub, sub_colors, rib_axis=(c, a))
            mat = "Rib_Knit_Oatmeal"
        else:
            Vx, Nx, Cx, UVx, Fx = box_uv_split(sub, sub_colors)
            mat = "Fleece_Oatmeal"
        Nx = sub_normals_fix(Nx)
        parts[name] = (Vx, Nx, Cx, UVx, Fx, mat)
        print(f"  {name:16s} {len(Fx):7d} faces")

    Vp, Np_, Cp, UVp, Fp, UV1p = build_back_print(shell, lab, N, colors, aspect)
    parts["Back_Print"] = (Vp, Np_, Cp, UVp, Fp, "Back_Print_Ink")
    EXTRA_UV1["Back_Print"] = UV1p
    Vp, Np_, Cp, UVp, Fp, UV1p = build_front_print(shell, lab, N, colors, f_aspect, f_frac)
    parts["Front_Print"] = (Vp, Np_, Cp, UVp, Fp, "Front_Print_Ink")
    EXTRA_UV1["Front_Print"] = UV1p
    Vp, Np_, Cp, UVp, Fp, UV1p = build_sleeve_print(shell, lab, N, colors, s_aspect, s_cap)
    parts["Sleeve_Print"] = (Vp, Np_, Cp, UVp, Fp, "Sleeve_Print_Ink")
    EXTRA_UV1["Sleeve_Print"] = UV1p

    print("stitching ...")
    st = build_stitching()

    def trim_ao(m, floor=0.55):
        V_ = np.asarray(m.vertices)
        N_ = np.asarray(m.vertex_normals)
        a = np.clip(sdf_ao(V_ + N_ * 0.001, N_), floor, 1.0)
        return np.stack([a] * 3, 1)

    parts["Topstitching"] = (np.asarray(st.vertices), np.asarray(st.vertex_normals), trim_ao(st, 0.7), None, np.asarray(st.faces), "Stitch_Thread")
    print("drawstrings ...")
    cords, tips, eyes = build_drawstrings()
    cuv = np.stack([np.arange(len(cords.vertices)) % 14 / 14 * 0.02, np.asarray(cords.vertices)[:, 1]], 1) / TILE_M
    parts["Drawcords"] = (np.asarray(cords.vertices), np.asarray(cords.vertex_normals), trim_ao(cords) * heather(np.asarray(cords.vertices))[:, None], cuv, np.asarray(cords.faces), "Drawcord")
    parts["Drawcord_Eyelets"] = (np.asarray(eyes.vertices), np.asarray(eyes.vertex_normals), trim_ao(eyes), None, np.asarray(eyes.faces), "Stitch_Thread")
    parts["Aglets"] = (np.asarray(tips.vertices), np.asarray(tips.vertex_normals), None, None, np.asarray(tips.faces), "Aglet_Gunmetal")

    glb = MODEL_DIR / "oatmeal_hoodie_realistic.glb"
    write_glb(parts, glb)
    print("wrote", glb, round(glb.stat().st_size / 1e6, 2), "MB")

    # OBJ/MTL for tools without glTF (vertex colours/AO not carried by OBJ)
    obj = MODEL_DIR / "oatmeal_hoodie_realistic.obj"
    write_obj(parts, obj)
    import zipfile
    with zipfile.ZipFile(MODEL_DIR / "oatmeal_hoodie_realistic_obj.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in (obj, obj.with_suffix(".mtl"), *sorted(TEX_DIR.glob("*.jpg"))):
            z.write(f, f.relative_to(MODEL_DIR))
        z.write(PRINT_PNG, "textures/" + PRINT_PNG.name)
        z.write(FRONT_PNG, "textures/" + FRONT_PNG.name)
        z.write(SLEEVE_PNG, "textures/" + SLEEVE_PNG.name)
    obj.unlink()
    obj.with_suffix(".mtl").unlink()

    info = {
        "model": "Pullover hoodie — oatmeal / warm taupe (realistic)",
        "fabric_color_hex": FABRIC_HEX,
        "rib_color_hex": RIB_HEX,
        "units": "metres, Y up, +Z front",
        "texture_tile": f"{TILE_M * 100:.0f} cm per UV unit (textures repeat)",
        "parts": {k: int(len(v[4])) for k, v in parts.items()},
        "total_triangles": int(sum(len(v[4]) for v in parts.values())),
    }
    (MODEL_DIR / "hoodie_model_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


def sub_normals_fix(n):
    n = np.asarray(n, float)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)


def write_obj(parts, path):
    mtl = path.with_suffix(".mtl")
    lines = [f"mtllib {mtl.name}"]
    off = 1
    toff = 1
    for name, (V, Nn, C, UV, F, mat) in parts.items():
        lines.append(f"o {name}")
        lines += [f"v {a:.5f} {b:.5f} {c:.5f}" for a, b, c in V]
        lines += [f"vn {a:.4f} {b:.4f} {c:.4f}" for a, b, c in Nn]
        if UV is not None:
            lines += [f"vt {a:.4f} {b:.4f}" for a, b in UV]
        lines.append(f"usemtl {mat}")
        if UV is not None:
            lines += [f"f {a + off}/{a + toff}/{a + off} {b + off}/{b + toff}/{b + off} {c + off}/{c + toff}/{c + off}" for a, b, c in F]
            toff += len(UV)
        else:
            lines += [f"f {a + off}//{a + off} {b + off}//{b + off} {c + off}//{c + off}" for a, b, c in F]
        off += len(V)
    path.write_text("\n".join(lines) + "\n")
    defs = {
        "Fleece_Oatmeal": (FABRIC_HEX, "fabric_grain_color.jpg", "fleece_jersey_normal.jpg"),
        "Rib_Knit_Oatmeal": (RIB_HEX, "rib_grain_color.jpg", "rib_knit_normal.jpg"),
        "Stitch_Thread": (THREAD_HEX, None, None),
        "Drawcord": (CORD_HEX, "fabric_grain_color.jpg", "fleece_jersey_normal.jpg"),
        "Aglet_Gunmetal": (AGLET_HEX, None, None),
        "Back_Print_Ink": (INK_HEX, "gik_map_back_print.png", None),
        "Front_Print_Ink": (FRONT_INK_HEX, "front_text_print.png", None),
        "Sleeve_Print_Ink": (FRONT_INK_HEX, "sleeve_33_print.png", None),
    }
    out = []
    for m, (hx, kd, nm) in defs.items():
        c = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        out += [f"newmtl {m}", f"Kd {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}", "Ks 0.03 0.03 0.03", "Ns 8"]
        if kd:
            out.append(f"map_Kd textures/{kd}")
            if kd.endswith(".png"):
                out.append(f"map_d textures/{kd}")
        if nm:
            out.append(f"norm textures/{nm}")
        out.append("")
    mtl.write_text("\n".join(out))


if __name__ == "__main__":
    main()
