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

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

BOLD_FONTS = [
    (os.path.join(FONTS_DIR, "Anton-Regular.ttf"),                      0, "anton"),
    (os.path.join(FONTS_DIR, "BarlowCondensed-Bold.ttf"),               0, "barlow_cond_bold"),
    (os.path.join(FONTS_DIR, "BarlowCondensed-ExtraBold.ttf"),          0, "barlow_cond_xbold"),
    (os.path.join(FONTS_DIR, "DMSans-Bold.ttf"),                        0, "dm_sans_bold"),
    (os.path.join(FONTS_DIR, "Inter-Black.ttf"),                        0, "inter_black"),
    (os.path.join(FONTS_DIR, "Inter-Bold.ttf"),                         0, "inter_bold"),
    (os.path.join(FONTS_DIR, "Lato-Black.ttf"),                         0, "lato_black"),
    (os.path.join(FONTS_DIR, "Lato-Bold.ttf"),                          0, "lato_bold"),
    (os.path.join(FONTS_DIR, "NunitoSans-ExtraBold.ttf"),               0, "nunito_xbold"),
    (os.path.join(FONTS_DIR, "Outfit-Bold.ttf"),                        0, "outfit_bold"),
    (os.path.join(FONTS_DIR, "PlayfairDisplay-Bold.ttf"),               0, "playfair_bold"),
    (os.path.join(FONTS_DIR, "PlusJakartaSans-Bold.ttf"),               0, "plus_jakarta_bold"),
    (os.path.join(FONTS_DIR, "RobotoSlab-Bold.ttf"),                    0, "roboto_slab_bold"),
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

PRIMARY_EFFECTS = ["shatter", "earthquake", "columns", "prism", "slices", "blocks",
                   "glitch", "shear", "tilt", "drift", "scatter", "fold", "melt", "wave"]
PRIMARY_WEIGHTS = [4, 6, 4, 3, 3, 4, 2, 2, 2, 3, 2, 2, 2, 2]

SECONDARY_EFFECTS = ["columns", "prism", "slices", "blocks", "shatter"]
SECONDARY_WEIGHTS = [4, 3, 3, 4, 3]

INCOMPATIBLE = {}


def get_font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.load_default()


def fit_font_to_width(word, font_path, font_index, target_fraction, canvas_w, min_size=90):
    lo, hi = min_size, 400
    for _ in range(20):
        mid = (lo + hi) // 2
        font = get_font(font_path, mid, font_index)
        tmp = Image.new("RGB", (1, 1))
        bb = ImageDraw.Draw(tmp).textbbox((0, 0), word, font=font)
        lo, hi = (mid, hi) if bb[2]-bb[0] < target_fraction*canvas_w else (lo, mid)
    return min(lo, 400)


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
    
    # Place only one tile exactly in the center of the padded grid
    gx = pad + WIDTH // 2 - tile.width // 2
    gy = pad + HEIGHT // 2 - tile.height // 2
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
        n = rng.randint(6, 20)
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
    elif mode == "glitch":
        # Sharp asymmetric shifts, VHS artifact look
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
    elif mode == "shear":
        # Diagonal shift across whole frame
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        shear_amount = rng.uniform(-0.5, 0.5)
        dx = amp * shear_amount * (yi / h - 0.5)
        dy = amp * shear_amount * (xi / w - 0.5)
    elif mode == "tilt":
        # Perspective distortion, canvas on tilted plane
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        tilt_x = rng.uniform(-0.3, 0.3)
        tilt_y = rng.uniform(-0.3, 0.3)
        dx = amp * tilt_x * (yi / h - 0.5)
        dy = amp * tilt_y * (xi / w - 0.5)
    elif mode == "drift":
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
        # Random blocks with independent displacement + smooth blending of neighbors
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        block_size = rng.randint(200, 500)  # Larger blocks to avoid fine ripples
        blend_width = block_size // 4  # Smooth transition zone

        # Generate block displacements
        blocks_y = (h + block_size - 1) // block_size
        blocks_x = (w + block_size - 1) // block_size
        block_disp = np.zeros((blocks_y, blocks_x, 2), dtype=np.float32)
        for by in range(blocks_y):
            for bx in range(blocks_x):
                block_disp[by, bx, 0] = rng.uniform(-amp, amp) * 0.5
                block_disp[by, bx, 1] = rng.uniform(-amp, amp) * 0.5

        # Apply with smooth blending of neighboring blocks at boundaries
        for y in range(h):
            for x in range(w):
                by = y // block_size
                bx = x // block_size
                by = min(by, blocks_y - 1)
                bx = min(bx, blocks_x - 1)

                local_y = y % block_size
                local_x = x % block_size

                # Blend current block with neighbors
                weights = []
                disps_x = []
                disps_y = []

                # Current block always included
                weights.append(1.0)
                disps_x.append(block_disp[by, bx, 0])
                disps_y.append(block_disp[by, bx, 1])

                # Top neighbor
                if by > 0 and local_y < blend_width:
                    weight = 1.0 - (local_y / blend_width)
                    weights.append(weight)
                    disps_x.append(block_disp[by - 1, bx, 0])
                    disps_y.append(block_disp[by - 1, bx, 1])

                # Bottom neighbor
                if by < blocks_y - 1 and (block_size - local_y - 1) < blend_width:
                    weight = 1.0 - ((block_size - local_y - 1) / blend_width)
                    weights.append(weight)
                    disps_x.append(block_disp[by + 1, bx, 0])
                    disps_y.append(block_disp[by + 1, bx, 1])

                # Left neighbor
                if bx > 0 and local_x < blend_width:
                    weight = 1.0 - (local_x / blend_width)
                    weights.append(weight)
                    disps_x.append(block_disp[by, bx - 1, 0])
                    disps_y.append(block_disp[by, bx - 1, 1])

                # Right neighbor
                if bx < blocks_x - 1 and (block_size - local_x - 1) < blend_width:
                    weight = 1.0 - ((block_size - local_x - 1) / blend_width)
                    weights.append(weight)
                    disps_x.append(block_disp[by, bx + 1, 0])
                    disps_y.append(block_disp[by, bx + 1, 1])

                total_weight = sum(weights)
                dx[y, x] = sum(w * dx_val for w, dx_val in zip(weights, disps_x)) / total_weight
                dy[y, x] = sum(w * dy_val for w, dy_val in zip(weights, disps_y)) / total_weight
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
    elif mode == "staircase":
        # Blocky quantized shifts (digital glitch look)
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        for _ in range(5):
            f = rng.uniform(0.002, 0.008)
            a = amp * rng.uniform(0.5, 1.2)
            # Quantize sine wave to create steps
            dx += a * np.round(np.sin(yi*f + rng.uniform(0,6.28)) * 3) / 3
            dy += a * np.round(np.cos(xi*f + rng.uniform(0,6.28)) * 3) / 3
    elif mode == "columns":
        # Vertical bands (vertical earthquake)
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_cols = rng.randint(8, 20)
        bw = w // n_cols
        for i in range(n_cols):
            x0, x1 = i*bw, (i+1)*bw
            shift = rng.uniform(-amp, amp)
            mask_b = (xi >= x0) & (xi < x1)
            dy += mask_b * shift
    elif mode == "prism":
        # Large angular facets (crystal look) - improved distribution
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        n_facets = rng.randint(3, 6)
        for _ in range(n_facets):
            angle = rng.uniform(0, 2 * math.pi)
            nx, ny = math.cos(angle), math.sin(angle)
            proj = xi * nx + yi * ny
            # Pick mid between min and max projection to ensure the line cuts the canvas anywhere
            p_min, p_max = proj.min(), proj.max()
            mid = rng.uniform(p_min + (p_max-p_min)*0.15, p_max - (p_max-p_min)*0.15)
            shift = rng.uniform(-amp, amp)
            mask = proj > mid
            dx += mask * shift * nx
            dy += mask * shift * ny
    elif mode == "slices":
        # Diagonal parallel bands
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        angle = rng.uniform(0, math.pi)
        nx, ny = math.cos(angle), math.sin(angle)
        proj = xi * nx + yi * ny
        n_slices = rng.randint(6, 15)
        slice_w = (proj.max() - proj.min()) / n_slices
        for i in range(n_slices):
            p0 = proj.min() + i * slice_w
            p1 = p0 + slice_w
            mask = (proj >= p0) & (proj < p1)
            shift = rng.uniform(-amp, amp)
            dx += mask * shift * nx
            dy += mask * shift * ny
    elif mode == "blocks":
        # Discrete rectangular block shifts - improved distribution
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)
        for _ in range(rng.randint(10, 20)):
            bw = rng.uniform(w * 0.1, w * 0.6)
            bh = rng.uniform(h * 0.05, h * 0.25)
            # Allow starting off-screen to cover edges
            bx = rng.uniform(-bw * 0.5, w)
            by = rng.uniform(-bh * 0.5, h)
            mask = (xi >= bx) & (xi < bx+bw) & (yi >= by) & (yi < by+bh)
            dx += mask * rng.uniform(-amp, amp)
            dy += mask * rng.uniform(-amp * 0.5, amp * 0.5)
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
    else:
        dx = np.zeros((h,w), np.float32)
        dy = np.zeros((h,w), np.float32)

    return dx.astype(np.float32), dy.astype(np.float32)


def warp_rgba(grid, pad, dx, dy):
    """Warp RGBA grid with bilinear interpolation."""
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH)).astype(np.float32)
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1)).astype(np.float32)

    # Raw float coordinates
    sy_float = oi + pad + dy
    sx_float = oj + pad + dx

    # Integer and fractional parts
    sy_int = np.floor(sy_float).astype(np.int32)
    sx_int = np.floor(sx_float).astype(np.int32)
    fy = sy_float - sy_int
    fx = sx_float - sx_int

    # Clip integer indices to valid range
    sy0 = np.clip(sy_int, 0, gn.shape[0]-1)
    sy1 = np.clip(sy_int + 1, 0, gn.shape[0]-1)
    sx0 = np.clip(sx_int, 0, gn.shape[1]-1)
    sx1 = np.clip(sx_int + 1, 0, gn.shape[1]-1)

    # Sample 4 neighboring pixels
    v00 = gn[sy0, sx0]
    v01 = gn[sy0, sx1]
    v10 = gn[sy1, sx0]
    v11 = gn[sy1, sx1]

    # Bilinear interpolation
    fy = fy[:, :, np.newaxis]  # Broadcast for color channels
    fx = fx[:, :, np.newaxis]
    interpolated = (v00 * (1-fy) * (1-fx) +
                    v01 * (1-fy) * fx +
                    v10 * fy * (1-fx) +
                    v11 * fy * fx)

    return Image.fromarray(interpolated.astype(np.uint8), "RGBA")


def warp_rgb(img, dx, dy):
    """Warp RGB image with bilinear interpolation."""
    gn = np.array(img, dtype=np.float32)
    oi = np.tile(np.arange(HEIGHT).reshape(-1,1), (1,WIDTH)).astype(np.float32)
    oj = np.tile(np.arange(WIDTH), (HEIGHT,1)).astype(np.float32)

    # Raw float coordinates
    sy_float = oi + dy
    sx_float = oj + dx

    # Integer and fractional parts
    sy_int = np.floor(sy_float).astype(np.int32)
    sx_int = np.floor(sx_float).astype(np.int32)
    fy = sy_float - sy_int
    fx = sx_float - sx_int

    # Clip integer indices to valid range
    sy0 = np.clip(sy_int, 0, img.height-1)
    sy1 = np.clip(sy_int + 1, 0, img.height-1)
    sx0 = np.clip(sx_int, 0, img.width-1)
    sx1 = np.clip(sx_int + 1, 0, img.width-1)

    # Sample 4 neighboring pixels
    v00 = gn[sy0, sx0]
    v01 = gn[sy0, sx1]
    v10 = gn[sy1, sx0]
    v11 = gn[sy1, sx1]

    # Bilinear interpolation
    fy = fy[:, :, np.newaxis]  # Broadcast for color channels
    fx = fx[:, :, np.newaxis]
    interpolated = (v00 * (1-fy) * (1-fx) +
                    v01 * (1-fy) * fx +
                    v10 * fy * (1-fx) +
                    v11 * fy * fx)

    return Image.fromarray(interpolated.astype(np.uint8), "RGB")


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


def apply_chromatic_aberration(img_rgb, max_strength):
    """
    Asymmetric channel shift: R and B move independently with their own vectors.
    """
    if max_strength <= 0:
        return img_rgb
    
    arr = np.array(img_rgb)
    out = np.zeros_like(arr)
    
    # Green channel stays as the anchor
    out[:,:,1] = arr[:,:,1]
    
    # Red channel: independent random vector
    angle_r = random.uniform(0, 2 * math.pi)
    dist_r = random.uniform(max_strength * 0.4, max_strength)
    dx_r, dy_r = dist_r * math.cos(angle_r), dist_r * math.sin(angle_r)
    out[:,:,0] = spatial_shift_rgb(arr[:,:,0:1], dx_r, dy_r)[:,:,0]
    
    # Blue channel: another independent random vector
    angle_b = random.uniform(0, 2 * math.pi)
    dist_b = random.uniform(max_strength * 0.4, max_strength)
    dx_b, dy_b = dist_b * math.cos(angle_b), dist_b * math.sin(angle_b)
    out[:,:,2] = spatial_shift_rgb(arr[:,:,2:3], dx_b, dy_b)[:,:,0]
    
    return Image.fromarray(out, "RGB")


def pick_chaos_t(rng):
    return rng.uniform(0.15, 0.25)


def generate(day, seed=None):
    global WIDTH, HEIGHT

    if seed is None:
        seed = random.randint(0, 2**32)
    rng = random.Random(seed)

    day = day.upper()
    if not AVAILABLE_FONTS:
        raise RuntimeError("No fonts found — run on macOS.")

    # Save original dimensions for output
    ORIG_WIDTH, ORIG_HEIGHT = WIDTH, HEIGHT

    # Compute font_size at original resolution (for filename accuracy)
    font_path, font_index, font_label = rng.choice(AVAILABLE_FONTS)
    letter_spacing = rng.randint(-10, 80)
    min_fs = 120 if letter_spacing > 40 else 90
    target_fraction = rng.uniform(0.55, 0.95)
    font_size = fit_font_to_width(day, font_path, font_index, target_fraction, ORIG_WIDTH, min_size=min_fs)
    font_size_render = font_size * 2  # Scale for 2x supersampling

    # Enable supersampling: render at 2x resolution
    WIDTH, HEIGHT = ORIG_WIDTH * 2, ORIG_HEIGHT * 2

    col_gap = rng.randint(0, max(font_size_render//8, 1))
    row_gap = rng.randint(0, max(font_size_render//8, 1))

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
    if e1 == "shatter":
        t1 = rng.uniform(0.20, 0.40)
    elif e1 == "columns":
        t1 = rng.uniform(0.20, 0.55)
    elif e1 == "slices":
        t1 = rng.uniform(0.20, 0.40)
    elif e1 == "prism":
        t1 = rng.uniform(0.30, 0.60)
    elif e1 == "blocks":
        t1 = rng.uniform(0.30, 0.60)
    elif e1 == "wave":
        t1 = rng.uniform(0.10, 0.30)
    else:
        t1 = rng.uniform(0.30, 0.80)

    # Secondary effect (subtle)
    e2_pool = [e for e in SECONDARY_EFFECTS if e != e1]
    e2 = rng.choices(e2_pool, weights=[SECONDARY_WEIGHTS[SECONDARY_EFFECTS.index(e)] for e in e2_pool])[0]
    t2 = rng.uniform(0.10, 0.25)

    # Pass 3: Chromatic aberration
    ca_strength = rng.uniform(18, 54)


    # Halo (v19)
    halo_color, halo_name = rng.choice(HALO_PALETTE)
    halo_r = rng.uniform(3, 10)
    halo_angle = rng.uniform(0, 360)

    # Build (using font_size_render for 2x supersampling)
    grad_img = make_gradient_map(WIDTH, HEIGHT, color_a, color_b, grad_angle)
    tile = make_word_tile_gradient(day, font_path, font_index, font_size_render,
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
    
    # Chromatic aberration
    bg = apply_chromatic_aberration(bg, ca_strength)

    # Restore original dimensions and downscale with antialiasing (supersampling)
    WIDTH, HEIGHT = ORIG_WIDTH, ORIG_HEIGHT
    bg = bg.resize((ORIG_WIDTH, ORIG_HEIGHT), Image.LANCZOS)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = (f"{e1}{int(t1*100)}_{e2}{int(t2*100)}"
             f"_ca{int(ca_strength)}"
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
