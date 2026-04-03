#!/usr/bin/env python3
"""
SREDA100 v20
Pipeline:
  1. Gradient applied to word tile (v17 logic)
  2. Tile → grid → displacement pass 1
  3. Optional displacement pass 2 (subtle)
  4. Monochrome halo split (v19 logic) as final color pass
"""

import argparse
import random
import math
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os

WIDTH, HEIGHT = 1080, 1920
OUTPUT_DIR = os.path.expanduser("~/sreda100_output")

BOLD_FONTS = [
    ("/System/Library/Fonts/Helvetica.ttc",                       1, "helvetica_bold"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                   1, "helvetica_neue_bold"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                   4, "helvetica_neue_cond_bold"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                   9, "helvetica_neue_black"),
    ("/System/Library/Fonts/Supplemental/Futura.ttc",             2, "futura_bold"),
    ("/System/Library/Fonts/Supplemental/Futura.ttc",             4, "futura_cond_extrabold"),
    ("/System/Library/Fonts/Supplemental/Didot.ttc",              2, "didot_bold"),
    ("/System/Library/Fonts/Supplemental/GillSans.ttc",           1, "gill_sans_bold"),
    ("/System/Library/Fonts/Supplemental/GillSans.ttc",           6, "gill_sans_ultrabold"),
    ("/System/Library/Fonts/Supplemental/Impact.ttf",             0, "impact"),
    ("/System/Library/Fonts/Supplemental/Rockwell.ttc",           2, "rockwell_bold"),
]

AVAILABLE_FONTS = [(p, i, l) for p, i, l in BOLD_FONTS if os.path.exists(p)]

# Palette ordered by hue — pick base then neighbor(s)
# No white, no dark colors, all vivid
PALETTE_WHEEL = [
    ("red",     (255,  50,  50)),
    ("orange",  (255, 120,   0)),
    ("yellow",  (255, 220,   0)),
    ("lime",    (180, 255,   0)),
    ("green",   (  0, 255, 100)),
    ("teal",    (  0, 220, 160)),
    ("cyan",    (  0, 210, 255)),
    ("ice",     (120, 200, 255)),
    ("violet",  (140,  80, 255)),
    ("magenta", (255,   0, 200)),
    ("pink",    (255, 100, 180)),
]

HALO_PALETTE = [
    ((  0, 200, 255), "cyan"),
    ((  0, 200, 255), "cyan"),
    ((255, 220,   0), "yellow"),
    ((255, 220,   0), "yellow"),
    ((120, 200, 255), "ice"),
    ((  0, 220, 160), "teal"),
    ((180, 255,   0), "lime"),
    ((  0, 255, 100), "green"),
    ((255, 120,   0), "orange"),
    ((255, 100, 180), "pink"),
    ((255,  50,  50), "red"),
    ((140,  80, 255), "violet"),
]

PRIMARY_EFFECTS = ["chaos", "earthquake", "shatter", "noise_flow", "gravity"]
PRIMARY_WEIGHTS = [3, 6, 4, 1, 6]

SECONDARY_EFFECTS = ["chaos", "twist", "shatter"]
SECONDARY_WEIGHTS = [4, 3, 3]

INCOMPATIBLE = {"chaos": ["twist"], "twist": ["chaos"]}


def get_font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.load_default()


def fit_font_to_width(word, font_path, font_index, target_fraction, canvas_w, min_size=90):
    lo, hi = min_size, 200
    for _ in range(20):
        mid = (lo + hi) // 2
        font = get_font(font_path, mid, font_index)
        tmp = Image.new("RGB", (1, 1))
        bb = ImageDraw.Draw(tmp).textbbox((0, 0), word, font=font)
        lo, hi = (mid, hi) if bb[2]-bb[0] < target_fraction*canvas_w else (lo, mid)
    return min(lo, 200)


def make_gradient_map(width, height, color_a, color_b, angle_deg):
    angle_rad = math.radians(angle_deg)
    xi = np.tile(np.arange(width),  (height, 1)).astype(np.float32)
    yi = np.tile(np.arange(height).reshape(-1, 1), (1, width)).astype(np.float32)
    proj = xi * math.cos(angle_rad) + yi * math.sin(angle_rad)
    proj -= proj.min()
    proj /= (proj.max() + 1e-8)
    # Boost contrast — S-curve so endpoints are more saturated
    proj = proj ** 0.7   # gamma < 1 pushes values toward ends
    r = (color_a[0] * (1-proj) + color_b[0] * proj).astype(np.uint8)
    g = (color_a[1] * (1-proj) + color_b[1] * proj).astype(np.uint8)
    b = (color_a[2] * (1-proj) + color_b[2] * proj).astype(np.uint8)
    return Image.fromarray(np.stack([r, g, b], axis=2), "RGB")


def make_word_tile_gradient(word, font_path, font_index, font_size,
                             letter_spacing=0, gradient_img=None):
    font = get_font(font_path, font_size, font_index)
    chars = list(word)
    tmp = Image.new("L", (1, 1))
    cw = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w = max(sum(cw) + letter_spacing*(len(chars)-1) + font_size, 10)
    total_h = font_size * 3
    mask = Image.new("L", (int(total_w), total_h), 0)
    draw = ImageDraw.Draw(mask)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=255)
        x += cw[i] + letter_spacing
    bb = draw.textbbox((font_size//4, font_size//3), word, font=font)
    tile_h = max(bb[3]-bb[1]+font_size//2, 10)
    tile_w = max(int(x+font_size//4), 10)
    mask = mask.crop((0, 0, tile_w, tile_h))
    grad_tile = gradient_img.resize((tile_w, tile_h), Image.LANCZOS) if gradient_img else \
                Image.new("RGB", (tile_w, tile_h), (255, 255, 255))
    tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    tile.paste(grad_tile.convert("RGBA"), mask=mask)
    return tile


def make_grid(tile, col_gap=0, row_gap=0):
    pad = max(WIDTH, HEIGHT)
    gw, gh = WIDTH+pad*2, HEIGHT+pad*2
    grid = Image.new("RGBA", (gw, gh), (0,0,0,0))
    sx, sy = max(tile.width+col_gap,1), max(tile.height+row_gap,1)
    for gy in range(-pad, gh, sy):
        for gx in range(-pad, gw, sx):
            grid.paste(tile, (gx, gy), tile)
    return grid, pad


def displacement(t, seed, mode):
    rng = np.random.RandomState(seed)
    w, h = WIDTH, HEIGHT
    xi = np.tile(np.arange(w), (h,1)).astype(np.float32)
    yi = np.tile(np.arange(h).reshape(-1,1), (1,w)).astype(np.float32)
    amp = t * 200

    if mode == "chaos":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        for _ in range(7):
            f = rng.uniform(0.002, 0.018)
            a = amp * rng.uniform(0.2, 1.0)
            ax, ay = rng.uniform(-1,1), rng.uniform(-1,1)
            dx += a * np.sin(yi*f*ax + xi*f*ay + rng.uniform(0,6.28))
            dy += a * np.cos(xi*f*ay + yi*f*ax + rng.uniform(0,6.28))
    elif mode == "earthquake":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_bands = rng.randint(8, 25)
        bh = h // n_bands
        for i in range(n_bands):
            y0, y1 = i*bh, (i+1)*bh
            shift = rng.uniform(-amp, amp) * rng.choice([-1,1])
            mask_b = (yi >= y0) & (yi < y1)
            dx += mask_b * shift
            if rng.random() < 0.3:
                dy += mask_b * rng.uniform(-amp*0.3, amp*0.3)
    elif mode == "twist":
        cx = w/2 + rng.uniform(-w*0.15, w*0.15)
        cy = h/2 + rng.uniform(-h*0.15, h*0.15)
        direction = rng.choice([-1, 1])
        dist = np.sqrt((xi-cx)**2 + (yi-cy)**2) + 1
        angle = direction * t * 2.5 * (dist / (min(w,h)*0.5))
        rx, ry = xi-cx, yi-cy
        dx = rx*np.cos(angle) - ry*np.sin(angle) + cx - xi
        dy = rx*np.sin(angle) + ry*np.cos(angle) + cy - yi
    elif mode == "shatter":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n = rng.randint(12, 40)
        px = rng.uniform(0, w, n)
        py = rng.uniform(0, h, n)
        sox = rng.uniform(-amp, amp, n)
        soy = rng.uniform(-amp*0.6, amp*0.6, n)
        owner = np.zeros((h,w), dtype=np.int32)
        min_dist = None
        for i in range(n):
            d = (xi-px[i])**2 + (yi-py[i])**2
            if min_dist is None:
                min_dist = d.copy()
            else:
                closer = d < min_dist
                min_dist = np.where(closer, d, min_dist)
                owner = np.where(closer, i, owner)
        for i in range(n):
            mv = owner == i
            dx += mv * sox[i]
            dy += mv * soy[i]
    elif mode == "noise_flow":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        for _ in range(6):
            scale = rng.uniform(0.003, 0.015)
            af = (np.sin(xi*scale + rng.uniform(0,6.28)) *
                  np.cos(yi*scale*0.7 + rng.uniform(0,6.28)) * math.pi * 2)
            la = amp * rng.uniform(0.3, 0.8)
            dx += la * np.cos(af)
            dy += la * np.sin(af)
    elif mode == "gravity":
        gy = rng.uniform(h*0.2, h*0.8)
        freq = rng.uniform(0.004, 0.012)
        dist_to_line = yi - gy
        dx = amp * 0.5 * np.sin(xi*freq + dist_to_line*0.008)
        dy = -np.sign(dist_to_line) * np.clip(np.abs(dist_to_line)*t*0.8, 0, amp*1.5)
    else:
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)

    return dx.astype(np.float32), dy.astype(np.float32)


def warp_rgba(grid, pad, dx, dy):
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi+pad+dy, 0, gn.shape[0]-1).astype(np.int32)
    sx = np.clip(oj+pad+dx, 0, gn.shape[1]-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "RGBA")


def warp_rgb(img, dx, dy):
    gn = np.array(img, dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi+dy, 0, img.height-1).astype(np.int32)
    sx = np.clip(oj+dx, 0, img.width-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "RGB")


def spatial_shift_rgb(img_np, dx_px, dy_px):
    """Shift RGB numpy array by integer pixels."""
    result = np.zeros_like(img_np)
    h, w = img_np.shape[:2]
    sx, sy = int(dx_px), int(dy_px)
    src_x0 = max(0, -sx);  src_x1 = min(w, w-sx)
    dst_x0 = max(0,  sx);  dst_x1 = min(w, w+sx)
    src_y0 = max(0, -sy);  src_y1 = min(h, h-sy)
    dst_y0 = max(0,  sy);  dst_y1 = min(h, h+sy)
    result[dst_y0:dst_y1, dst_x0:dst_x1] = img_np[src_y0:src_y1, src_x0:src_x1]
    return result


def apply_halo(img_rgb, halo_color, halo_r, halo_angle_deg):
    """
    Subtle chromatic fringe — additive tint on shifted copy.
    No channel replacement, so no red/green artifacts.
    """
    arr = np.array(img_rgb, dtype=np.float32)
    hr, hg, hb = [c / 255.0 for c in halo_color]
    max_ch = max(hr, hg, hb, 0.01)
    hr, hg, hb = hr/max_ch, hg/max_ch, hb/max_ch

    dx_px = halo_r * math.cos(math.radians(halo_angle_deg))
    dy_px = halo_r * math.sin(math.radians(halo_angle_deg))

    arr_plus  = spatial_shift_rgb(arr,  dx_px,  dy_px)
    arr_minus = spatial_shift_rgb(arr, -dx_px, -dy_px)

    # Additive blend — shifted copies add tinted glow, original stays bright
    strength = 0.25
    out = arr.copy()
    out[:,:,0] = np.clip(arr[:,:,0] + arr_plus [:,:,0] * hr  * strength, 0, 255)
    out[:,:,1] = np.clip(arr[:,:,1] + arr_plus [:,:,1] * hg  * strength, 0, 255)
    out[:,:,2] = np.clip(arr[:,:,2] + arr_minus[:,:,2] * hb  * strength, 0, 255)

    return Image.fromarray(out.astype(np.uint8), "RGB")


def pick_chaos_t(rng):
    return rng.uniform(0.35, 0.45) if rng.random() < 0.5 else rng.uniform(0.83, 0.95)


def generate(day, seed=None):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    if not AVAILABLE_FONTS:
        raise RuntimeError("No fonts found — run on macOS.")

    font_path, font_index, font_label = rng.choice(AVAILABLE_FONTS)
    letter_spacing = rng.randint(-10, 80)
    min_fs = 120 if letter_spacing > 40 else 90
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, font_index, target_fraction, WIDTH, min_size=min_fs)
    col_gap = rng.randint(0, max(font_size//3, 1))
    row_gap = rng.randint(0, max(font_size//4, 1))

    # Gradient — base color + adjacent neighbor on color wheel
    n = len(PALETTE_WHEEL)
    base_idx = rng.randint(0, n - 1)
    # Step 1 or 2 positions along wheel (both directions)
    step = rng.choice([-2, -1, 1, 2])
    neighbor_idx = (base_idx + step) % n
    grad_name_a, color_a = PALETTE_WHEEL[base_idx]
    grad_name_b, color_b = PALETTE_WHEEL[neighbor_idx]
    grad_angle = rng.uniform(0, 360)
    grad_label = f"{grad_name_a}-{grad_name_b}"

    # Primary effect
    e1 = rng.choices(PRIMARY_EFFECTS, weights=PRIMARY_WEIGHTS)[0]
    if e1 == "chaos":
        t1 = pick_chaos_t(rng)
    elif e1 == "shatter":
        t1 = rng.uniform(0.40, 0.65)
    elif e1 == "noise_flow":
        t1 = rng.uniform(0.03, 0.10)
    else:
        t1 = rng.uniform(0.40, 0.95)

    # Secondary effect (subtle)
    excluded = [e1] + INCOMPATIBLE.get(e1, [])
    e2_pool = [e for e in SECONDARY_EFFECTS if e not in excluded]
    e2 = rng.choices(e2_pool, weights=[SECONDARY_WEIGHTS[SECONDARY_EFFECTS.index(e)] for e in e2_pool])[0]
    t2 = rng.uniform(0.10, 0.25)

    # Halo (v19)
    halo_color, halo_name = rng.choice(HALO_PALETTE)
    halo_r = rng.uniform(3, 10)
    halo_angle = rng.uniform(0, 360)

    # Build
    grad_img = make_gradient_map(WIDTH, HEIGHT, color_a, color_b, grad_angle)
    tile = make_word_tile_gradient(day, font_path, font_index, font_size,
                                    letter_spacing, grad_img)
    grid, pad = make_grid(tile, col_gap, row_gap)

    dx1, dy1 = displacement(t1, seed, e1)
    pass1 = warp_rgba(grid, pad, dx1, dy1)
    bg = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
    bg.paste(pass1.convert("RGB"), mask=pass1.split()[3])

    dx2, dy2 = displacement(t2, seed+1, e2)
    bg = warp_rgb(bg, dx2, dy2)

    # Halo split as final pass
    bg = apply_halo(bg, halo_color, halo_r, halo_angle)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{e1}{int(t1*100)}_{e2}{int(t2*100)}"
             f"_{grad_label}_halo{halo_name}{int(halo_r)}"
             f"_{font_label}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {e1:12s}{int(t1*100):2d} | grad={grad_label:20s} | halo={halo_name:6s}{int(halo_r):2d}px | {font_label}")
    return out_path, {
        "effect1": e1,
        "effect2": e2,
        "intensity1": int(t1 * 100),
        "intensity2": int(t2 * 100),
        "font": font_label,
        "gradient": grad_label,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day} (v20, gradient + halo)...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None)
    print(f"\nDone → {OUTPUT_DIR}")
