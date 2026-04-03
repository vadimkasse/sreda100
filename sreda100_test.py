#!/usr/bin/env python3
"""
SREDA100 TEST
12 new displacement effects for testing:
  drift, scatter, fold, melt, wave, ripple, glitch, crumple, tilt, pull, shear, explode
Single pass (no secondary displacement).
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

TEST_EFFECTS = ["drift", "scatter", "fold", "melt", "wave", "ripple", "glitch", "crumple", "tilt", "pull", "shear", "explode"]


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
    proj = proj ** 0.7
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
    """Displacement field computation with 12 new test effects."""
    rng = np.random.RandomState(seed)
    w, h = WIDTH, HEIGHT
    xi = np.tile(np.arange(w), (h,1)).astype(np.float32)
    yi = np.tile(np.arange(h).reshape(-1,1), (1,w)).astype(np.float32)
    amp = t * 200

    if mode == "drift":
        # Smooth varying shifts per band
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_bands = rng.randint(6, 15)
        bh = h // n_bands
        prev_shift = 0
        for i in range(n_bands):
            y0, y1 = i*bh, (i+1)*bh
            target_shift = rng.uniform(-amp, amp)
            shift = prev_shift + (target_shift - prev_shift) * 0.6
            mask_b = (yi >= y0) & (yi < y1)
            dx += mask_b * shift
            prev_shift = shift

    elif mode == "scatter":
        # Random blocks with independent displacement
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        block_size = rng.randint(30, 80)
        for by in range(0, h, block_size):
            for bx in range(0, w, block_size):
                bdx = rng.uniform(-amp, amp) * 0.5
                bdy = rng.uniform(-amp, amp) * 0.5
                by_end = min(by + block_size, h)
                bx_end = min(bx + block_size, w)
                dx[by:by_end, bx:bx_end] = bdx
                dy[by:by_end, bx:bx_end] = bdy

    elif mode == "fold":
        # Mirror along random axis
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        fold_axis = rng.choice(["vertical", "horizontal"])
        if fold_axis == "vertical":
            fold_x = rng.uniform(w*0.2, w*0.8)
            dist_from_fold = np.abs(xi - fold_x)
            dx = amp * 0.8 * np.sign(xi - fold_x) * (1.0 - np.exp(-dist_from_fold/100))
        else:
            fold_y = rng.uniform(h*0.2, h*0.8)
            dist_from_fold = np.abs(yi - fold_y)
            dy = amp * 0.8 * np.sign(yi - fold_y) * (1.0 - np.exp(-dist_from_fold/100))

    elif mode == "melt":
        # Vertical displacement increases top to bottom
        dx = np.zeros((h,w), np.float32)
        melt_factor = yi / h
        dy = amp * melt_factor * 0.7 + amp * 0.3 * np.sin(xi*0.01 + rng.uniform(0, 6.28))

    elif mode == "wave":
        # Horizontal sine waves, uniform amplitude
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_waves = rng.randint(3, 8)
        for i in range(n_waves):
            freq = rng.uniform(0.003, 0.015)
            phase = rng.uniform(0, 6.28)
            dx += amp * 0.3 * np.sin(yi*freq + phase) / n_waves

    elif mode == "ripple":
        # Concentric circles from random point, subtle
        cx = rng.uniform(0, w)
        cy = rng.uniform(0, h)
        dist = np.sqrt((xi-cx)**2 + (yi-cy)**2)
        freq = rng.uniform(0.005, 0.020)
        phase = rng.uniform(0, 6.28)
        wave = np.sin(dist*freq + phase)
        dx = amp * 0.3 * wave * (xi-cx) / (dist + 1)
        dy = amp * 0.3 * wave * (yi-cy) / (dist + 1)

    elif mode == "glitch":
        # Sharp asymmetric shifts, VHS artifact
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_glitches = rng.randint(4, 12)
        for _ in range(n_glitches):
            y0 = rng.randint(0, h)
            h_glitch = rng.randint(20, 80)
            y1 = min(y0 + h_glitch, h)
            shift = rng.uniform(-amp, amp) * rng.choice([-1, 1])
            mask_g = (yi >= y0) & (yi < y1)
            dx += mask_g * shift * (1 + rng.uniform(-0.5, 0.5))

    elif mode == "crumple":
        # Local random deformations, crumpled paper look
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_crumples = rng.randint(8, 20)
        for _ in range(n_crumples):
            cx = rng.uniform(0, w)
            cy = rng.uniform(0, h)
            radius = rng.uniform(50, 200)
            strength = rng.uniform(-amp*0.5, amp*0.5)
            dist = np.sqrt((xi-cx)**2 + (yi-cy)**2)
            influence = np.exp(-(dist**2) / (radius**2 + 1))
            angle = np.arctan2(yi-cy, xi-cx)
            dx += influence * strength * np.cos(angle)
            dy += influence * strength * np.sin(angle)

    elif mode == "tilt":
        # Perspective distortion, canvas on tilted plane
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        tilt_x = rng.uniform(-0.3, 0.3)
        tilt_y = rng.uniform(-0.3, 0.3)
        dx = amp * tilt_x * (yi / h - 0.5)
        dy = amp * tilt_y * (xi / w - 0.5)

    elif mode == "pull":
        # Attraction toward 2-3 random points
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_pulls = rng.randint(2, 4)
        for _ in range(n_pulls):
            px = rng.uniform(0, w)
            py = rng.uniform(0, h)
            strength = amp * rng.uniform(0.3, 0.8)
            dist = np.sqrt((xi-px)**2 + (yi-py)**2) + 1
            dx += strength * (px - xi) / dist
            dy += strength * (py - yi) / dist

    elif mode == "shear":
        # Diagonal shift across whole frame
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        shear_amount = rng.uniform(-0.5, 0.5)
        dx = amp * shear_amount * (yi / h - 0.5)
        dy = amp * shear_amount * (xi / w - 0.5)

    elif mode == "explode":
        # Radial outward displacement
        cx = w / 2 + rng.uniform(-w*0.2, w*0.2)
        cy = h / 2 + rng.uniform(-h*0.2, h*0.2)
        dist = np.sqrt((xi-cx)**2 + (yi-cy)**2) + 1
        angle = np.arctan2(yi-cy, xi-cx)
        radial = amp * 0.7 * np.exp(-dist / (min(w,h)*0.3))
        dx = radial * np.cos(angle)
        dy = radial * np.sin(angle)

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
    """Subtle chromatic fringe."""
    arr = np.array(img_rgb, dtype=np.float32)
    hr, hg, hb = [c / 255.0 for c in halo_color]
    max_ch = max(hr, hg, hb, 0.01)
    hr, hg, hb = hr/max_ch, hg/max_ch, hb/max_ch

    dx_px = halo_r * math.cos(math.radians(halo_angle_deg))
    dy_px = halo_r * math.sin(math.radians(halo_angle_deg))

    arr_plus  = spatial_shift_rgb(arr,  dx_px,  dy_px)
    arr_minus = spatial_shift_rgb(arr, -dx_px, -dy_px)

    strength = 0.25
    out = arr.copy()
    out[:,:,0] = np.clip(arr[:,:,0] + arr_plus [:,:,0] * hr  * strength, 0, 255)
    out[:,:,1] = np.clip(arr[:,:,1] + arr_plus [:,:,1] * hg  * strength, 0, 255)
    out[:,:,2] = np.clip(arr[:,:,2] + arr_minus[:,:,2] * hb  * strength, 0, 255)

    return Image.fromarray(out.astype(np.uint8), "RGB")


def generate(day, seed=None, effect_override=None, t_min=0.40, t_max=0.95):
    """Generate single image. If effect_override, use only that effect."""
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

    # Gradient
    n = len(PALETTE_WHEEL)
    base_idx = rng.randint(0, n - 1)
    step = rng.choice([-2, -1, 1, 2])
    neighbor_idx = (base_idx + step) % n
    grad_name_a, color_a = PALETTE_WHEEL[base_idx]
    grad_name_b, color_b = PALETTE_WHEEL[neighbor_idx]
    grad_angle = rng.uniform(0, 360)
    grad_label = f"{grad_name_a}-{grad_name_b}"

    # Primary effect (use override if provided)
    if effect_override:
        e1 = effect_override
    else:
        e1 = rng.choice(TEST_EFFECTS)
    t1 = rng.uniform(t_min, t_max)

    # Halo
    halo_color, halo_name = rng.choice(HALO_PALETTE)
    halo_r = rng.uniform(3, 10)
    halo_angle = rng.uniform(0, 360)

    # Build (single pass only — no secondary effect)
    grad_img = make_gradient_map(WIDTH, HEIGHT, color_a, color_b, grad_angle)
    tile = make_word_tile_gradient(day, font_path, font_index, font_size,
                                    letter_spacing, grad_img)
    grid, pad = make_grid(tile, col_gap, row_gap)

    dx1, dy1 = displacement(t1, seed, e1)
    pass1 = warp_rgba(grid, pad, dx1, dy1)
    bg = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
    bg.paste(pass1.convert("RGB"), mask=pass1.split()[3])

    # Halo as final pass
    bg = apply_halo(bg, halo_color, halo_r, halo_angle)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{e1}{int(t1*100)}"
             f"_{grad_label}_halo{halo_name}{int(halo_r)}"
             f"_{font_label}_fs{font_size}_ls{letter_spacing}"
             f"_{day}_{date_str}_s{seed}.png")
    out_path = os.path.join(OUTPUT_DIR, fname)
    bg.save(out_path, "PNG")
    print(f"✅ {e1:12s}{int(t1*100):2d} | grad={grad_label:20s} | halo={halo_name:6s}{int(halo_r):2d}px | {font_label}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default="WEDNESDAY")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--effect", type=str, default=None, help="Use only this effect")
    parser.add_argument("--test-all", action="store_true", help="Test all 12 effects × 10 iterations each (120 files)")
    args = parser.parse_args()

    if args.test_all:
        print(f"Testing all {len(TEST_EFFECTS)} effects × 10 iterations (120 total)...")
        for effect_name in TEST_EFFECTS:
            effect_dir = os.path.join(OUTPUT_DIR, f"test_{effect_name}")
            os.makedirs(effect_dir, exist_ok=True)
            print(f"\n→ {effect_name} (10×)")
            for i in range(10):
                seed = random.randint(0, 2**32)
                out_path = generate("WEDNESDAY", seed=seed, effect_override=effect_name)
                fname = os.path.basename(out_path)
                new_path = os.path.join(effect_dir, fname)
                os.rename(out_path, new_path)
        print(f"\nDone → {OUTPUT_DIR}/test_*/")
    elif args.effect:
        if args.effect not in TEST_EFFECTS:
            print(f"❌ Effect '{args.effect}' not recognized. Available: {', '.join(TEST_EFFECTS)}")
        else:
            print(f"Generating {args.batch} × {args.day} with effect '{args.effect}'...")
            for _ in range(args.batch):
                generate(args.day, args.seed if args.batch==1 else None, effect_override=args.effect)
            print(f"\nDone → {OUTPUT_DIR}")
    else:
        print(f"Generating {args.batch} × {args.day} (test mode, random effect)...")
        for _ in range(args.batch):
            generate(args.day, args.seed if args.batch==1 else None)
        print(f"\nDone → {OUTPUT_DIR}")
