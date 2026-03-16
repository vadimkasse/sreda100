#!/usr/bin/env python3
"""
SREDA100 v7
Var 1: random font
Var 2: random size (word fills 20–95% of canvas width)
Var 3: random effect (wave / turbulence / radial / chaos / none)
Var 4: glitch — not yet
"""

import argparse
import random
import math
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

WIDTH, HEIGHT = 1080, 1920
OUTPUT_DIR = os.path.expanduser("~/sreda100_output")

FONTS = {
    "helvetica":   "/System/Library/Fonts/Helvetica.ttc",
    "helvetica_neue": "/System/Library/Fonts/HelveticaNeue.ttc",
    "arial":       "/System/Library/Fonts/Arial.ttf",
    "times":       "/System/Library/Fonts/Times New Roman.ttf",
    "georgia":     "/System/Library/Fonts/Georgia.ttf",
    "courier":     "/System/Library/Fonts/Courier New.ttf",
    "impact":      "/System/Library/Fonts/Supplemental/Impact.ttf",
    "futura":      "/System/Library/Fonts/Supplemental/Futura.ttc",
    "didot":       "/System/Library/Fonts/Supplemental/Didot.ttc",
    "baskerville": "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "gill_sans":   "/System/Library/Fonts/Supplemental/GillSans.ttc",
    "optima":      "/System/Library/Fonts/Supplemental/Optima.ttc",
    "palatino":    "/System/Library/Fonts/Supplemental/Palatino.ttc",
}


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def fit_font_to_width(word, font_path, target_fraction, canvas_w):
    """Find font size so word width = target_fraction * canvas_w."""
    lo, hi = 10, 2000
    for _ in range(20):
        mid = (lo + hi) // 2
        font = get_font(font_path, mid)
        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)
        bb = draw.textbbox((0, 0), word, font=font)
        w = bb[2] - bb[0]
        if w < target_fraction * canvas_w:
            lo = mid
        else:
            hi = mid
    return lo


def make_word_tile(word, font_path, font_size):
    font = get_font(font_path, font_size)
    tmp = Image.new("RGBA", (font_size * (len(word) + 2), font_size * 3), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tmp)
    draw.text((0, 0), word, font=font, fill=(255, 255, 255, 255))
    bb = draw.textbbox((0, 0), word, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    return tmp.crop((0, 0, tw + 4, th + font_size // 3))


def make_grid(tile, col_gap=0, row_gap=0):
    pad = max(WIDTH, HEIGHT)
    gw = WIDTH + pad * 2
    gh = HEIGHT + pad * 2
    grid = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    sx = tile.width + col_gap
    sy = tile.height + row_gap
    for gy in range(-pad, gh, sy):
        for gx in range(-pad, gw, sx):
            grid.paste(tile, (gx, gy), tile)
    return grid, pad


def make_displacement(t, seed, mode):
    rng = np.random.RandomState(seed)
    w, h = WIDTH, HEIGHT
    xi = np.tile(np.arange(w), (h, 1))
    yi = np.tile(np.arange(h).reshape(-1, 1), (1, w))
    amp = t * 200

    if mode == "none":
        return np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)

    elif mode == "wave":
        fx = rng.uniform(0.003, 0.01)
        fy = rng.uniform(0.003, 0.01)
        dx = amp * np.sin(yi * fx + rng.uniform(0, 6.28))
        dy = amp * np.sin(xi * fy + rng.uniform(0, 6.28))

    elif mode == "turbulence":
        dx = np.zeros((h, w))
        dy = np.zeros((h, w))
        for o in range(5):
            f = 0.004 * (2 ** o)
            a = amp / (1.5 ** o)
            dx += a * np.sin(yi * f + rng.uniform(0, 6.28) + xi * f * 0.4)
            dy += a * np.sin(xi * f + rng.uniform(0, 6.28) + yi * f * 0.4)

    elif mode == "radial":
        cx, cy = w / 2, h / 2
        dist = np.sqrt((xi - cx)**2 + (yi - cy)**2) + 1
        nx = (xi - cx) / dist
        ny = (yi - cy) / dist
        strength = amp * (1 - np.clip(dist / (min(w, h) * 0.6), 0, 1))
        wave = np.sin(dist * 0.035 + rng.uniform(0, 6.28))
        dx = nx * strength * wave
        dy = ny * strength * wave

    elif mode == "chaos":
        dx = np.zeros((h, w))
        dy = np.zeros((h, w))
        for _ in range(7):
            f = rng.uniform(0.002, 0.018)
            a = amp * rng.uniform(0.2, 1.0)
            ax, ay = rng.uniform(-1, 1), rng.uniform(-1, 1)
            dx += a * np.sin(yi * f * ax + xi * f * ay + rng.uniform(0, 6.28))
            dy += a * np.cos(xi * f * ay + yi * f * ax + rng.uniform(0, 6.28))

    return dx.astype(np.float32), dy.astype(np.float32)


def apply_displacement(grid, pad, dx, dy):
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1, 1), (1, WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT, 1))
    sy = np.clip(oi + pad + dy, 0, gn.shape[0] - 1).astype(np.int32)
    sx = np.clip(oj + pad + dx, 0, gn.shape[1] - 1).astype(np.int32)
    return Image.fromarray(gn[sy, sx].astype(np.uint8), "RGBA")


EFFECTS = ["none", "wave", "turbulence", "radial", "chaos"]


def generate(day, seed=None):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()

    # ── VAR 1: random font ──────────────────────────────────────────────────
    available = {k: v for k, v in FONTS.items() if os.path.exists(v)}
    font_name = rng.choice(list(available.keys()))
    font_path = available[font_name]

    # ── VAR 2: random size (word fills 20–95% canvas width) ────────────────
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, target_fraction, WIDTH)

    # Grid gaps: smaller word = tighter grid, bigger = more breathing room
    col_gap = rng.randint(0, int(font_size * 0.4))
    row_gap = rng.randint(0, int(font_size * 0.3))

    # ── VAR 3: random effect ────────────────────────────────────────────────
    effect = rng.choice(EFFECTS)
    t = rng.uniform(0.3, 0.95)   # how far into the process

    # Build
    tile = make_word_tile(day, font_path, font_size)
    grid, pad = make_grid(tile, col_gap, row_gap)
    dx, dy = make_displacement(t, seed, effect)
    warped = apply_displacement(grid, pad, dx, dy)

    bg = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    bg.paste(warped.convert("RGB"), mask=warped.split()[3])

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{date_str}_{day}"
             f"_{font_name}_s{font_size}"
             f"_{effect}_t{int(t*100)}"
             f"_seed{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {os.path.basename(fname)}")
    print(f"   font={font_name} size={font_size}px ({int(target_fraction*100)}% width)"
          f" effect={effect} t={t:.2f}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=1)
    args = parser.parse_args()

    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch == 1 else None)
