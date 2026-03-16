#!/usr/bin/env python3
"""
SREDA100 v19 (rewrite)
True monochrome + chromatic halo:
- One base displacement (primary effect)
- Three spatial offsets of the same warped result
- Each offset scaled by base color weights
- Result: monochrome image with colored fringe where offsets diverge
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

PALETTE = [
    ((  0, 200, 255), "cyan"),
    ((  0, 200, 255), "cyan"),    # weighted higher
    ((255, 220,   0), "yellow"),
    ((255, 220,   0), "yellow"),  # weighted higher
    ((255, 140,  80), "amber"),
    (( 80, 200, 255), "ice"),
    ((  0, 255, 200), "teal"),
    ((200, 255,   0), "lime"),
]

PRIMARY_EFFECTS = ["chaos", "earthquake", "shatter", "noise_flow", "gravity"]
PRIMARY_WEIGHTS = [3, 6, 4, 1, 6]


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


def warp_mono(grid_l, pad, dx, dy):
    gn = np.array(grid_l, dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi+pad+dy, 0, gn.shape[0]-1).astype(np.int32)
    sx = np.clip(oj+pad+dx, 0, gn.shape[1]-1).astype(np.int32)
    return gn[sy,sx]


def spatial_shift(arr, dx_px, dy_px):
    result = np.zeros_like(arr)
    h, w = arr.shape
    sx, sy = int(dx_px), int(dy_px)
    src_x0 = max(0, -sx);  src_x1 = min(w, w-sx)
    dst_x0 = max(0,  sx);  dst_x1 = min(w, w+sx)
    src_y0 = max(0, -sy);  src_y1 = min(h, h-sy)
    dst_y0 = max(0,  sy);  dst_y1 = min(h, h+sy)
    result[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]
    return result


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

    base_color, color_name = rng.choice(PALETTE)
    br, bg_c, bb_c = [c / 255.0 for c in base_color]

    e1 = rng.choices(PRIMARY_EFFECTS, weights=PRIMARY_WEIGHTS)[0]
    if e1 == "chaos":
        t1 = pick_chaos_t(rng)
    elif e1 == "shatter":
        t1 = rng.uniform(0.40, 0.65)
    elif e1 == "noise_flow":
        t1 = rng.uniform(0.03, 0.10)
    else:
        t1 = rng.uniform(0.40, 0.95)

    halo_r = rng.uniform(3, 10)
    halo_angle = rng.uniform(0, 360)
    halo_dx = halo_r * math.cos(math.radians(halo_angle))
    halo_dy = halo_r * math.sin(math.radians(halo_angle))

    tile = make_word_tile(day, font_path, font_index, font_size, letter_spacing)
    grid, pad = make_grid_mono(tile, col_gap, row_gap)
    dx1, dy1 = displacement(t1, seed, e1)
    warped = warp_mono(grid, pad, dx1, dy1)

    # Center = G (anchor), +offset = R, -offset = B
    ch_center = warped
    ch_plus   = spatial_shift(warped,  halo_dx,  halo_dy)
    ch_minus  = spatial_shift(warped, -halo_dx, -halo_dy)

    out_r = np.clip(ch_plus   * br,   0, 255).astype(np.uint8)
    out_g = np.clip(ch_center * bg_c, 0, 255).astype(np.uint8)
    out_b = np.clip(ch_minus  * bb_c, 0, 255).astype(np.uint8)

    bg = Image.merge("RGB", (
        Image.fromarray(out_r, "L"),
        Image.fromarray(out_g, "L"),
        Image.fromarray(out_b, "L"),
    ))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{color_name}_{e1}{int(t1*100)}"
             f"_halo{int(halo_r)}"
             f"_{font_label}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {color_name:8s} {e1:12s} t={t1:.2f} halo={int(halo_r):2d}px | {font_label} fs={font_size}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day} (v19, monochrome halo)...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None)
    print(f"\nDone → {OUTPUT_DIR}")
