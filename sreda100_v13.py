#!/usr/bin/env python3
"""
SREDA100 v13
Two displacement passes:
  Pass 1 (primary):   chaos / earthquake / twist / shatter / noise_flow(t<0.1)
  Pass 2 (secondary): any different from pass 1, including drift / gravity
Filename: {effect1}+{effect2}_{t1}+{t2}_{font}_{size}_{day}_{date}_s{seed}.png
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
    "impact":         "/System/Library/Fonts/Supplemental/Impact.ttf",
    "helvetica_neue": "/System/Library/Fonts/HelveticaNeue.ttc",
    "helvetica":      "/System/Library/Fonts/Helvetica.ttc",
    "futura":         "/System/Library/Fonts/Supplemental/Futura.ttc",
    "gill_sans":      "/System/Library/Fonts/Supplemental/GillSans.ttc",
    "baskerville":    "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "didot":          "/System/Library/Fonts/Supplemental/Didot.ttc",
}

# Pass 1: primary effects (build the main structure)
PRIMARY_EFFECTS   = ["chaos", "earthquake", "twist", "shatter", "noise_flow"]
PRIMARY_WEIGHTS   = [5, 4, 3, 4, 2]

# Pass 2: secondary effects — no drift
SECONDARY_EFFECTS = ["chaos", "earthquake", "twist", "shatter", "gravity"]
SECONDARY_WEIGHTS = [3, 3, 2, 2, 3]

T_RANGES = {
    "chaos":      (0.4, 0.95),
    "earthquake": (0.4, 0.95),
    "twist":      (0.45, 0.75),
    "shatter":    (0.4, 0.95),
    "noise_flow": (0.03, 0.10),   # very subtle as primary
    "drift":      (0.4, 0.90),    # secondary only
    "gravity":    (0.4, 0.85),    # secondary only
}


# ── HELPERS ──────────────────────────────────────────────────────────────────

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
        lo, hi = (mid, hi) if bb[2]-bb[0] < target_fraction*canvas_w else (lo, mid)
    return lo


def make_word_tile(word, font_path, font_size, letter_spacing=0):
    font = get_font(font_path, font_size)
    chars = list(word)
    tmp = Image.new("RGBA", (1, 1))
    cw = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w = max(sum(cw) + letter_spacing*(len(chars)-1) + font_size, 10)
    tile = Image.new("RGBA", (int(total_w), font_size*3), (0,0,0,0))
    draw = ImageDraw.Draw(tile)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=(255,255,255,255))
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


# ── DISPLACEMENT MODES ───────────────────────────────────────────────────────

def displacement(t, seed, mode, w=WIDTH, h=HEIGHT):
    rng = np.random.RandomState(seed)
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

    elif mode == "drift":
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_strips = rng.randint(15, 50)
        sh = h / n_strips
        for i in range(n_strips):
            y0, y1 = i*sh, (i+1)*sh
            sx_val = rng.uniform(-amp*1.2, amp*1.2)
            sy_val = rng.uniform(-amp*0.1, amp*0.1)
            mask = (yi >= y0) & (yi < y1)
            blend = (np.clip((yi-y0)/max(sh*0.1,1),0,1) *
                     np.clip((y1-yi)/max(sh*0.1,1),0,1))
            dx += mask * sx_val * blend
            dy += mask * sy_val

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


def warp_image(img_rgba, dx, dy, pad=0):
    """Apply displacement to an RGBA image (with optional pad offset)."""
    gn = np.array(img_rgba.convert("RGBA"), dtype=np.float32)
    h, w = img_rgba.height, img_rgba.width
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi + pad + dy, 0, gn.shape[0]-1).astype(np.int32)
    sx = np.clip(oj + pad + dx, 0, gn.shape[1]-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "RGBA")


def warp_rgb(img_rgb, dx, dy):
    """Apply displacement to an RGB image (no grid padding needed)."""
    gn = np.array(img_rgb, dtype=np.float32)
    h_img, w_img = img_rgb.height, img_rgb.width
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH))
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1))
    sy = np.clip(oi + dy, 0, h_img-1).astype(np.int32)
    sx = np.clip(oj + dx, 0, w_img-1).astype(np.int32)
    return Image.fromarray(gn[sy,sx].astype(np.uint8), "RGB")


# ── MAIN ─────────────────────────────────────────────────────────────────────

def generate(day, seed=None, glitch=False):
    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    available = {k:v for k,v in FONTS.items() if os.path.exists(v)}
    if not available:
        raise RuntimeError("No fonts found — run on macOS.")

    # Var 1: font
    font_name = rng.choice(list(available.keys()))
    font_path = available[font_name]

    # Var 2: size + spacing
    target_fraction = rng.uniform(0.20, 0.95)
    font_size = fit_font_to_width(day, font_path, target_fraction, WIDTH)
    letter_spacing = rng.randint(-10, 80)
    col_gap = rng.randint(0, max(font_size//3, 1))
    row_gap = rng.randint(0, max(font_size//4, 1))

    # Var 3: pass 1 effect
    e1 = rng.choices(PRIMARY_EFFECTS, weights=PRIMARY_WEIGHTS)[0]
    t1_min, t1_max = T_RANGES[e1]
    t1 = rng.uniform(t1_min, t1_max)

    # Var 4: pass 2 effect — must differ from pass 1
    e2_pool = [e for e in SECONDARY_EFFECTS if e != e1]
    e2_w = [SECONDARY_WEIGHTS[SECONDARY_EFFECTS.index(e)] for e in e2_pool]
    e2 = rng.choices(e2_pool, weights=e2_w)[0]
    t2 = rng.uniform(0.10, 0.25)   # pass 2 always subtle

    # Build grid
    tile = make_word_tile(day, font_path, font_size, letter_spacing)
    grid, pad = make_grid(tile, col_gap, row_gap)

    # Pass 1: warp grid
    dx1, dy1 = displacement(t1, seed, e1)
    pass1 = warp_image(grid, dx1, dy1, pad)
    bg = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
    bg.paste(pass1.convert("RGB"), mask=pass1.split()[3])

    # Pass 2: warp the result of pass 1 — subtle (t2=0.10–0.25)
    dx2, dy2 = displacement(t2, seed + 1, e2)
    bg = warp_rgb(bg, dx2, dy2)

    # Optional glitch
    if glitch:
        ga = rng.uniform(0.2, 0.8)
        shift = int(ga * 18)
        if shift > 0:
            r, g, b = bg.split()
            r = r.transform(bg.size, Image.AFFINE, (1,0,shift,0,1,0))
            b = b.transform(bg.size, Image.AFFINE, (1,0,-shift,0,1,0))
            bg = Image.merge("RGB", (r,g,b))

    # Save — effect combo first
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{e1}{int(t1*100)}_{e2}{int(t2*100)}"
             f"_{font_name}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}"
             f"{'_glitch' if glitch else ''}"
             f"_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {e1}+{e2:10s} t={t1:.2f}+{t2:.2f} | {font_name:16s} fs={font_size:3d} ls={letter_spacing:3d}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--glitch", action="store_true")
    args = parser.parse_args()

    print(f"Generating {args.batch} × {args.day} (2-pass displacement)...")
    for _ in range(args.batch):
        generate(args.day, args.seed if args.batch==1 else None, args.glitch)
    print(f"\nDone → {OUTPUT_DIR}")
