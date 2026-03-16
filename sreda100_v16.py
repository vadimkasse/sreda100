#!/usr/bin/env python3
"""
SREDA100 v16
- twist removed from primary
- chaos bimodal: t in 0.35-0.45 OR 0.83-0.95
- shatter primary: t max 0.65
- font_size min 90 (min 120 if ls > 40)
- noise_flow weight lowered
- earthquake / gravity high weight
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

# Duotone palette — high contrast colors on black
PALETTE = [
    ((255, 255, 255), "white"),
    ((255, 255, 255), "white"),   # white weighted higher
    ((255, 255, 255), "white"),
    ((255, 220, 0),   "yellow"),
    ((255, 80,  0),   "orange"),
    ((220, 0,   0),   "red"),
    ((0,   200, 255), "cyan"),
    ((0,   255, 120), "green"),
    ((180, 0,   255), "violet"),
    ((255, 0,   140), "magenta"),
]

AVAILABLE_FONTS = [(p, i, l) for p, i, l in BOLD_FONTS if os.path.exists(p)]

# Primary: no twist
PRIMARY_EFFECTS = ["chaos", "earthquake", "shatter", "noise_flow", "gravity"]
PRIMARY_WEIGHTS = [3,       6,            4,          1,            6]

# Secondary: twist allowed here as subtle finisher
SECONDARY_EFFECTS = ["chaos", "twist", "shatter"]
SECONDARY_WEIGHTS = [4,       3,       3]


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


def make_word_tile(word, font_path, font_index, font_size, letter_spacing=0, color=(255,255,255)):
    font = get_font(font_path, font_size, font_index)
    chars = list(word)
    tmp = Image.new("RGBA", (1, 1))
    cw = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w = max(sum(cw) + letter_spacing*(len(chars)-1) + font_size, 10)
    tile = Image.new("RGBA", (int(total_w), font_size*3), (0,0,0,0))
    draw = ImageDraw.Draw(tile)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=(*color, 255))
        x += cw[i] + letter_spacing
    bb = draw.textbbox((font_size//4, font_size//3), word, font=font)
    return tile.crop((0, 0, max(int(x+font_size//4),10), max(bb[3]-bb[1]+font_size//2,10)))


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
            mask = (yi >= y0) & (yi < y1)
            dx += mask * shift
            if rng.random() < 0.3:
                dy += mask * rng.uniform(-amp*0.3, amp*0.3)

    elif mode == "twist":
        cx, cy = w/2, h/2
        dist = np.sqrt((xi-cx)**2 + (yi-cy)**2) + 1
        angle = t * 2.5 * (dist / (min(w,h)*0.5))
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
            mask = owner == i
            dx += mask * sox[i]
            dy += mask * soy[i]

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


def warp_grid(grid, pad, dx, dy):
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


def pick_chaos_t(rng):
    """Bimodal: low zone 0.35-0.45 or high zone 0.83-0.95"""
    if rng.random() < 0.5:
        return rng.uniform(0.35, 0.45)
    else:
        return rng.uniform(0.83, 0.95)


def generate(day, seed=None, glitch=False):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    if not AVAILABLE_FONTS:
        raise RuntimeError("No fonts found — run on macOS.")

    font_path, font_index, font_label = rng.choice(AVAILABLE_FONTS)

    # Color
    color_rgb, color_name = rng.choice(PALETTE)

    # Font size: min 90, min 120 if ls will be > 40
    letter_spacing = rng.randint(-10, 80)
    min_fs = 120 if letter_spacing > 40 else 90
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, font_index, target_fraction, WIDTH, min_size=min_fs)

    col_gap = rng.randint(0, max(font_size//3, 1))
    row_gap = rng.randint(0, max(font_size//4, 1))

    # Pass 1
    e1 = rng.choices(PRIMARY_EFFECTS, weights=PRIMARY_WEIGHTS)[0]
    if e1 == "chaos":
        t1 = pick_chaos_t(rng)
    elif e1 == "shatter":
        t1 = rng.uniform(0.40, 0.65)
    elif e1 == "noise_flow":
        t1 = rng.uniform(0.03, 0.10)
    else:
        t1 = rng.uniform(0.40, 0.95)

    # Pass 2 — subtle, different from pass 1
    e2_pool = [e for e in SECONDARY_EFFECTS if e != e1]
    e2 = rng.choices(e2_pool, weights=[SECONDARY_WEIGHTS[SECONDARY_EFFECTS.index(e)] for e in e2_pool])[0]
    t2 = rng.uniform(0.10, 0.25)

    tile = make_word_tile(day, font_path, font_index, font_size, letter_spacing, color_rgb)
    grid, pad = make_grid(tile, col_gap, row_gap)

    dx1, dy1 = displacement(t1, seed, e1)
    pass1 = warp_grid(grid, pad, dx1, dy1)
    bg = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
    bg.paste(pass1.convert("RGB"), mask=pass1.split()[3])

    dx2, dy2 = displacement(t2, seed+1, e2)
    bg = warp_rgb(bg, dx2, dy2)

    if glitch:
        ga = rng.uniform(0.2, 0.8)
        shift = int(ga * 18)
        if shift > 0:
            r, g, b = bg.split()
            r = r.transform(bg.size, Image.AFFINE, (1,0,shift,0,1,0))
            b = b.transform(bg.size, Image.AFFINE, (1,0,-shift,0,1,0))
            bg = Image.merge("RGB", (r,g,b))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{e1}{int(t1*100)}_{e2}{int(t2*100)}"
             f"_{font_label}_fs{font_size}_ls{letter_spacing}"
             f"_{color_name}"
             f"_{day}_{date_str}"
             f"{'_glitch' if glitch else ''}"
             f"_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {e1:12s}{int(t1*100):2d} + {e2:8s}{int(t2*100):2d} | {font_label:28s} fs={font_size:3d} ls={letter_spacing:3d}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--glitch", action="store_true")
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day} (v15)...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None, args.glitch)
    print(f"\nDone → {OUTPUT_DIR}")
