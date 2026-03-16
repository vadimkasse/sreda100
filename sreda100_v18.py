#!/usr/bin/env python3
"""
SREDA100 v18
RGB split displacement:
- Each channel rendered separately
- Each channel gets its own displacement pass
- R: earthquake / gravity (structural splits)
- G: no warp OR subtle chaos (anchor)
- B: chaos / shatter (maximum distortion)
- Composited back to RGB on black
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

# R channel: structural effects
R_EFFECTS = ["earthquake", "gravity", "shatter"]
R_WEIGHTS  = [4, 4, 2]

# G channel: anchor — subtle or none
G_EFFECTS = ["none", "chaos_low", "shatter_low"]
G_WEIGHTS  = [4, 3, 3]

# B channel: maximum distortion
B_EFFECTS = ["chaos", "shatter", "earthquake"]
B_WEIGHTS  = [5, 3, 2]


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


def make_word_tile(word, font_path, font_index, font_size, letter_spacing=0):
    """Returns grayscale tile — will be used as mask per channel."""
    font = get_font(font_path, font_size, font_index)
    chars = list(word)
    tmp = Image.new("L", (1, 1))
    cw = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w = max(sum(cw) + letter_spacing*(len(chars)-1) + font_size, 10)
    tile = Image.new("L", (int(total_w), font_size*3), 0)
    draw = ImageDraw.Draw(tile)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=255)
        x += cw[i] + letter_spacing
    bb = draw.textbbox((font_size//4, font_size//3), word, font=font)
    return tile.crop((0, 0, max(int(x+font_size//4),10), max(bb[3]-bb[1]+font_size//2,10)))


def make_grid_mono(tile, col_gap=0, row_gap=0):
    """Build tiled grid as grayscale (L mode)."""
    pad = max(WIDTH, HEIGHT)
    gw, gh = WIDTH+pad*2, HEIGHT+pad*2
    grid = Image.new("L", (gw, gh), 0)
    sx, sy = max(tile.width+col_gap,1), max(tile.height+row_gap,1)
    for gy in range(-pad, gh, sy):
        for gx in range(-pad, gw, sx):
            grid.paste(tile, (gx, gy))
    return grid, pad


def displacement(t, seed, mode):
    rng = np.random.RandomState(seed)
    w, h = WIDTH, HEIGHT
    xi = np.tile(np.arange(w), (h,1)).astype(np.float32)
    yi = np.tile(np.arange(h).reshape(-1,1), (1,w)).astype(np.float32)
    amp = t * 200

    if mode in ("none",):
        return np.zeros((h,w), np.float32), np.zeros((h,w), np.float32)

    elif mode in ("chaos", "chaos_low"):
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
            mask = (yi >= y0) & (yi < y1)
            dx += mask * shift
            if rng.random() < 0.3:
                dy += mask * rng.uniform(-amp*0.3, amp*0.3)

    elif mode in ("shatter", "shatter_low"):
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
            mask_v = owner == i
            dx += mask_v * sox[i]
            dy += mask_v * soy[i]

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


def warp_mono(grid_l, pad, dx, dy):
    """Warp a grayscale grid, crop to output size."""
    gn = np.array(grid_l, dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi+pad+dy, 0, gn.shape[0]-1).astype(np.int32)
    sx = np.clip(oj+pad+dx, 0, gn.shape[1]-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "L")


def pick_t(rng, mode):
    if mode == "chaos":
        return rng.uniform(0.35, 0.45) if rng.random() < 0.5 else rng.uniform(0.83, 0.95)
    elif mode in ("chaos_low", "shatter_low"):
        return rng.uniform(0.10, 0.25)
    elif mode == "none":
        return 0.0
    elif mode == "shatter":
        return rng.uniform(0.40, 0.65)
    else:
        return rng.uniform(0.40, 0.90)


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

    # Pick effects per channel
    r_mode = rng.choices(R_EFFECTS, weights=R_WEIGHTS)[0]
    g_mode = rng.choices(G_EFFECTS, weights=G_WEIGHTS)[0]
    b_mode = rng.choices(B_EFFECTS, weights=B_WEIGHTS)[0]

    r_t = pick_t(rng, r_mode)
    g_t = pick_t(rng, g_mode)
    b_t = pick_t(rng, b_mode)

    # Build grayscale tile + grid (same base for all channels)
    tile = make_word_tile(day, font_path, font_index, font_size, letter_spacing)
    grid, pad = make_grid_mono(tile, col_gap, row_gap)

    # Warp each channel independently with different seed offsets
    dx_r, dy_r = displacement(r_t, seed,     r_mode)
    dx_g, dy_g = displacement(g_t, seed+1,   g_mode)
    dx_b, dy_b = displacement(b_t, seed+2,   b_mode)

    r_ch = warp_mono(grid, pad, dx_r, dy_r)
    g_ch = warp_mono(grid, pad, dx_g, dy_g)
    b_ch = warp_mono(grid, pad, dx_b, dy_b)

    # Merge channels on black background
    bg = Image.merge("RGB", (r_ch, g_ch, b_ch))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"R{r_mode[:3]}{int(r_t*100)}"
             f"_G{g_mode[:3]}{int(g_t*100)}"
             f"_B{b_mode[:3]}{int(b_t*100)}"
             f"_{font_label}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ R:{r_mode:12s}{int(r_t*100):2d} G:{g_mode:12s}{int(g_t*100):2d} B:{b_mode:12s}{int(b_t*100):2d} | {font_label:28s} fs={font_size:3d}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day} (v18, RGB split)...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None)
    print(f"\nDone → {OUTPUT_DIR}")
