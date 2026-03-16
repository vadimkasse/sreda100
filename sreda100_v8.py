#!/usr/bin/env python3
"""
SREDA100 v8
Var 1: random font
Var 2: random size (word fills 20–95% canvas width)
Var 2b: random letter spacing (-10 to +80px)
Var 3: random effect (8 options)
Var 4: glitch — chromatic aberration + scanlines (optional)

Effects: none / wave / turbulence / radial / chaos / twist / shear / pinch
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

EFFECTS = ["none", "wave", "turbulence", "radial", "chaos", "twist", "shear", "pinch"]


# ── FONT ────────────────────────────────────────────────────────────────────

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
        draw = ImageDraw.Draw(tmp)
        bb = draw.textbbox((0, 0), word, font=font)
        if bb[2] - bb[0] < target_fraction * canvas_w:
            lo = mid
        else:
            hi = mid
    return lo


# ── TILE ────────────────────────────────────────────────────────────────────

def make_word_tile(word, font_path, font_size, letter_spacing=0):
    """Render word tile with optional letter spacing (can be negative)."""
    font = get_font(font_path, font_size)
    chars = list(word)

    # Measure each char
    tmp = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(tmp)
    char_widths = []
    for ch in chars:
        bb = draw.textbbox((0, 0), ch, font=font)
        char_widths.append(bb[2] - bb[0])

    total_w = sum(char_widths) + letter_spacing * (len(chars) - 1) + font_size
    total_w = max(total_w, 10)
    total_h = font_size * 3

    tile = Image.new("RGBA", (int(total_w), int(total_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)

    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size // 3), ch, font=font, fill=(255, 255, 255, 255))
        x += char_widths[i] + letter_spacing

    # Tight crop height
    bb = draw.textbbox((font_size // 4, font_size // 3), word, font=font)
    tile_h = max(bb[3] - bb[1] + font_size // 2, 10)
    tile_w = max(int(x + font_size // 4), 10)
    return tile.crop((0, 0, tile_w, tile_h))


# ── GRID ────────────────────────────────────────────────────────────────────

def make_grid(tile, col_gap=0, row_gap=0):
    pad = max(WIDTH, HEIGHT)
    gw = WIDTH + pad * 2
    gh = HEIGHT + pad * 2
    grid = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    sx = max(tile.width + col_gap, 1)
    sy = max(tile.height + row_gap, 1)
    for gy in range(-pad, gh, sy):
        for gx in range(-pad, gw, sx):
            grid.paste(tile, (gx, gy), tile)
    return grid, pad


# ── DISPLACEMENT ─────────────────────────────────────────────────────────────

def make_displacement(t, seed, mode):
    rng = np.random.RandomState(seed)
    w, h = WIDTH, HEIGHT
    xi = np.tile(np.arange(w), (h, 1)).astype(np.float32)
    yi = np.tile(np.arange(h).reshape(-1, 1), (1, w)).astype(np.float32)
    amp = t * 200

    if mode == "none":
        return np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)

    elif mode == "wave":
        fx = rng.uniform(0.003, 0.012)
        fy = rng.uniform(0.003, 0.012)
        dx = amp * np.sin(yi * fx + rng.uniform(0, 6.28))
        dy = amp * np.sin(xi * fy + rng.uniform(0, 6.28))

    elif mode == "turbulence":
        dx = np.zeros((h, w), np.float32)
        dy = np.zeros((h, w), np.float32)
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
        dx = np.zeros((h, w), np.float32)
        dy = np.zeros((h, w), np.float32)
        for _ in range(7):
            f = rng.uniform(0.002, 0.018)
            a = amp * rng.uniform(0.2, 1.0)
            ax, ay = rng.uniform(-1, 1), rng.uniform(-1, 1)
            dx += a * np.sin(yi * f * ax + xi * f * ay + rng.uniform(0, 6.28))
            dy += a * np.cos(xi * f * ay + yi * f * ax + rng.uniform(0, 6.28))

    elif mode == "twist":
        cx, cy = w / 2, h / 2
        dist = np.sqrt((xi - cx)**2 + (yi - cy)**2) + 1
        angle = t * 2.5 * (dist / (min(w, h) * 0.5))
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)
        rx = xi - cx
        ry = yi - cy
        dx = rx * cos_a - ry * sin_a + cx - xi
        dy = rx * sin_a + ry * cos_a + cy - yi

    elif mode == "shear":
        freq = rng.uniform(0.002, 0.008)
        dx = amp * 1.8 * np.sin(yi * freq + rng.uniform(0, 6.28))
        dy = amp * 0.4 * np.sin(xi * freq * 0.5 + rng.uniform(0, 6.28))

    elif mode == "pinch":
        n_pts = rng.randint(2, 5)
        dx = np.zeros((h, w), np.float32)
        dy = np.zeros((h, w), np.float32)
        for _ in range(n_pts):
            px = rng.uniform(w * 0.2, w * 0.8)
            py = rng.uniform(h * 0.2, h * 0.8)
            dist = np.sqrt((xi - px)**2 + (yi - py)**2) + 1
            s = np.clip(amp * 80 / dist, 0, amp)
            dx += s * (px - xi) / dist
            dy += s * (py - yi) / dist

    return dx.astype(np.float32), dy.astype(np.float32)


# ── WARP ────────────────────────────────────────────────────────────────────

def apply_displacement(grid, pad, dx, dy):
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1, 1), (1, WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT, 1))
    sy = np.clip(oi + pad + dy, 0, gn.shape[0] - 1).astype(np.int32)
    sx = np.clip(oj + pad + dx, 0, gn.shape[1] - 1).astype(np.int32)
    return Image.fromarray(gn[sy, sx].astype(np.uint8), "RGBA")


# ── GLITCH ──────────────────────────────────────────────────────────────────

def apply_glitch(img, amount, seed):
    rng = random.Random(seed + 99999)
    shift = int(amount * 18)
    if shift > 0:
        r, g, b = img.split()
        r = r.transform(img.size, Image.AFFINE, (1, 0, shift, 0, 1, 0))
        b = b.transform(img.size, Image.AFFINE, (1, 0, -shift, 0, 1, 0))
        img = Image.merge("RGB", (r, g, b))
    # Scanlines
    draw = ImageDraw.Draw(img)
    for y in range(0, HEIGHT, rng.randint(3, 10)):
        if rng.random() < amount * 0.3:
            draw.line([(0, y), (WIDTH, y)],
                      fill=(255, 255, 255, rng.randint(5, 35)), width=1)
    return img


# ── GENERATE ────────────────────────────────────────────────────────────────

def generate(day, seed=None, glitch=False):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    available = {k: v for k, v in FONTS.items() if os.path.exists(v)}
    if not available:
        raise RuntimeError("No fonts found. Run on macOS.")

    # Var 1: font
    font_name = rng.choice(list(available.keys()))
    font_path = available[font_name]

    # Var 2: size
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, target_fraction, WIDTH)

    # Var 2b: letter spacing
    letter_spacing = rng.randint(-10, 80)

    # Grid gaps
    col_gap = rng.randint(0, max(font_size // 3, 1))
    row_gap = rng.randint(0, max(font_size // 4, 1))

    # Var 3: effect
    effect = rng.choice(EFFECTS)
    t = rng.uniform(0.3, 0.95)

    # Build
    tile = make_word_tile(day, font_path, font_size, letter_spacing)
    grid, pad = make_grid(tile, col_gap, row_gap)
    dx, dy = make_displacement(t, seed, effect)
    warped = apply_displacement(grid, pad, dx, dy)

    bg = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    bg.paste(warped.convert("RGB"), mask=warped.split()[3])

    # Var 4: glitch
    glitch_amount = 0
    if glitch:
        glitch_amount = rng.uniform(0.2, 0.8)
        bg = apply_glitch(bg, glitch_amount, seed)

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{date_str}_{day}"
             f"_{font_name}_fs{font_size}_ls{letter_spacing}"
             f"_{effect}_t{int(t*100)}"
             f"{'_glitch' if glitch else ''}"
             f"_seed{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {os.path.basename(fname)}")
    print(f"   font={font_name} size={font_size}px spacing={letter_spacing}"
          f" effect={effect} t={t:.2f}"
          + (f" glitch={glitch_amount:.2f}" if glitch else ""))
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--glitch", action="store_true",
                        help="Add chromatic aberration and scanlines")
    args = parser.parse_args()

    for _ in range(args.batch):
        generate(args.day,
                 args.seed if args.batch == 1 else None,
                 args.glitch)
