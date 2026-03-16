#!/usr/bin/env python3
"""
SREDA100 v10
Effects: chaos / earthquake / twist / noise_flow(t<0.5) / shatter / drift / gravity / pulse
Filename: {effect}_{t}_{font}_{size}_{spacing}_{seed}.png
Default batch: 20
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

FONTS = {
    "helvetica":      "/System/Library/Fonts/Helvetica.ttc",
    "helvetica_neue": "/System/Library/Fonts/HelveticaNeue.ttc",
    "arial":          "/System/Library/Fonts/Arial.ttf",
    "times":          "/System/Library/Fonts/Times New Roman.ttf",
    "georgia":        "/System/Library/Fonts/Georgia.ttf",
    "courier":        "/System/Library/Fonts/Courier New.ttf",
    "impact":         "/System/Library/Fonts/Supplemental/Impact.ttf",
    "futura":         "/System/Library/Fonts/Supplemental/Futura.ttc",
    "didot":          "/System/Library/Fonts/Supplemental/Didot.ttc",
    "baskerville":    "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "gill_sans":      "/System/Library/Fonts/Supplemental/GillSans.ttc",
    "optima":         "/System/Library/Fonts/Supplemental/Optima.ttc",
    "palatino":       "/System/Library/Fonts/Supplemental/Palatino.ttc",
}

EFFECTS = ["chaos", "earthquake", "twist", "noise_flow", "shatter", "drift", "gravity", "pulse"]
EFFECT_WEIGHTS = [5, 4, 3, 2, 4, 4, 3, 3]

# t ranges per effect
T_RANGES = {
    "chaos":      (0.4, 0.95),
    "earthquake": (0.4, 0.95),
    "twist":      (0.45, 0.75),   # constrained — extreme twist gets messy
    "noise_flow": (0.25, 0.50),   # only gentle range
    "shatter":    (0.4, 0.95),
    "drift":      (0.4, 0.95),
    "gravity":    (0.4, 0.90),
    "pulse":      (0.4, 0.90),
}


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def fit_font_to_width(word, font_path, target_fraction, canvas_w):
    lo, hi = 10, 2000
    for _ in range(20):
        mid = (lo + hi) // 2
        font = get_font(font_path, mid)
        tmp = Image.new("RGB", (1, 1))
        bb = ImageDraw.Draw(tmp).textbbox((0, 0), word, font=font)
        if bb[2] - bb[0] < target_fraction * canvas_w:
            lo = mid
        else:
            hi = mid
    return lo


def make_word_tile(word, font_path, font_size, letter_spacing=0):
    font = get_font(font_path, font_size)
    chars = list(word)
    tmp = Image.new("RGBA", (1, 1))
    char_widths = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w = max(sum(char_widths) + letter_spacing*(len(chars)-1) + font_size, 10)
    tile = Image.new("RGBA", (int(total_w), font_size*3), (0,0,0,0))
    draw = ImageDraw.Draw(tile)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=(255,255,255,255))
        x += char_widths[i] + letter_spacing
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


def make_displacement(t, seed, mode):
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
        band_h = h // n_bands
        for i in range(n_bands):
            y0, y1 = i*band_h, (i+1)*band_h
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

    elif mode == "noise_flow":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        for _ in range(6):
            scale = rng.uniform(0.003, 0.015)
            angle_field = (np.sin(xi*scale + rng.uniform(0,6.28)) *
                           np.cos(yi*scale*0.7 + rng.uniform(0,6.28)) * math.pi * 2)
            la = amp * rng.uniform(0.3, 0.8)
            dx += la * np.cos(angle_field)
            dy += la * np.sin(angle_field)

    elif mode == "shatter":
        # Voronoi-like: random seed points, each region shifts independently
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_shards = rng.randint(12, 40)
        px = rng.uniform(0, w, n_shards)
        py = rng.uniform(0, h, n_shards)
        sx_offsets = rng.uniform(-amp, amp, n_shards)
        sy_offsets = rng.uniform(-amp*0.6, amp*0.6, n_shards)
        # Assign each pixel to nearest shard center
        for i in range(n_shards):
            dist_i = (xi - px[i])**2 + (yi - py[i])**2
            if i == 0:
                min_dist = dist_i.copy()
                owner = np.zeros((h,w), dtype=np.int32)
            else:
                closer = dist_i < min_dist
                min_dist = np.where(closer, dist_i, min_dist)
                owner = np.where(closer, i, owner)
        for i in range(n_shards):
            mask = owner == i
            dx += mask * sx_offsets[i]
            dy += mask * sy_offsets[i]

    elif mode == "drift":
        # Each horizontal strip drifts independently — VHS-like but geometric
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_strips = rng.randint(15, 50)
        strip_h = h / n_strips
        for i in range(n_strips):
            y0 = i * strip_h
            y1 = y0 + strip_h
            shift_x = rng.uniform(-amp*1.2, amp*1.2)
            shift_y = rng.uniform(-amp*0.1, amp*0.1)
            mask = (yi >= y0) & (yi < y1)
            # Smooth edge between strips
            blend = np.clip((yi - y0) / max(strip_h*0.1, 1), 0, 1) * np.clip((y1 - yi) / max(strip_h*0.1, 1), 0, 1)
            dx += mask * shift_x * blend
            dy += mask * shift_y

    elif mode == "gravity":
        # Pixels pulled toward a gravity line (horizontal or diagonal)
        gravity_y = rng.uniform(h*0.2, h*0.8)
        gravity_strength = amp * 1.5
        dist_to_line = yi - gravity_y
        dx = np.zeros((h,w), np.float32)
        # Horizontal drift based on distance from gravity line
        freq = rng.uniform(0.004, 0.012)
        dx = amp * 0.5 * np.sin(xi * freq + dist_to_line * 0.008)
        # Pull toward gravity line
        dy = -np.sign(dist_to_line) * np.clip(np.abs(dist_to_line) * t * 0.8, 0, gravity_strength)

    elif mode == "pulse":
        # Rectangular concentric waves from center
        cx, cy = w/2, h/2
        # Chebyshev distance = rectangular
        cheby = np.maximum(np.abs(xi-cx), np.abs(yi-cy))
        freq = rng.uniform(0.015, 0.04)
        phase = rng.uniform(0, 6.28)
        wave = np.sin(cheby * freq + phase)
        nx = np.sign(xi - cx) / (np.abs(xi-cx) + 1)
        ny = np.sign(yi - cy) / (np.abs(yi-cy) + 1)
        dx = amp * wave * nx * 0.8
        dy = amp * wave * ny * 0.8

    else:
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)

    return dx.astype(np.float32), dy.astype(np.float32)


def apply_displacement(grid, pad, dx, dy):
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi+pad+dy, 0, gn.shape[0]-1).astype(np.int32)
    sx = np.clip(oj+pad+dx, 0, gn.shape[1]-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "RGBA")


def generate(day, seed=None, glitch=False):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    available = {k:v for k,v in FONTS.items() if os.path.exists(v)}
    if not available:
        raise RuntimeError("No fonts found — run on macOS.")

    font_name = rng.choice(list(available.keys()))
    font_path = available[font_name]
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, target_fraction, WIDTH)
    letter_spacing = rng.randint(-10, 80)
    col_gap = rng.randint(0, max(font_size//3, 1))
    row_gap = rng.randint(0, max(font_size//4, 1))

    effect = rng.choices(EFFECTS, weights=EFFECT_WEIGHTS)[0]
    t_min, t_max = T_RANGES[effect]
    t = rng.uniform(t_min, t_max)

    tile = make_word_tile(day, font_path, font_size, letter_spacing)
    grid, pad = make_grid(tile, col_gap, row_gap)
    dx, dy = make_displacement(t, seed, effect)
    warped = apply_displacement(grid, pad, dx, dy)

    bg = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
    bg.paste(warped.convert("RGB"), mask=warped.split()[3])

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
    # Effect and t first in filename
    fname = (f"{effect}_t{int(t*100)}"
             f"_{font_name}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}"
             f"{'_glitch' if glitch else ''}"
             f"_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {effect:12s} t={t:.2f} | {font_name:16s} fs={font_size:3d} ls={letter_spacing:3d} | s={seed}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--glitch", action="store_true")
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day}...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None, args.glitch)
    print(f"\nDone → {OUTPUT_DIR}")
