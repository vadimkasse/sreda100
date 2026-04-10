#!/usr/bin/env python3
"""
SREDA100 v20.5 (Unified Engine)
Art project: Rhythmic geometric typography.
Supports static image generation and 'Hold & Burst' rhythmic video sequences.
"""

import argparse
import random
import math
import numpy as np
import os
import subprocess
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
OUTPUT_DIR = os.path.expanduser("~/sreda100_output")
FPS = 10
DURATION = 5  # seconds
TOTAL_FRAMES = FPS * DURATION

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

PALETTE_WHEEL = [
    ("red",     (255,  50,  50)), ("orange",  (255, 120,   0)), ("yellow",  (255, 220,   0)),
    ("lime",    (180, 255,   0)), ("green",   (  0, 255, 100)), ("teal",    (  0, 220, 160)),
    ("cyan",    (  0, 210, 255)), ("ice",     (120, 200, 255)), ("violet",  (140,  80, 255)),
    ("magenta", (255,   0, 200)), ("pink",    (255, 100, 180)),
]

HALO_PALETTE = [((0, 200, 255), "cyan"), ((255, 220, 0), "yellow"), ((120, 200, 255), "ice")]

PRIMARY_EFFECTS = ["shatter", "earthquake", "columns", "prism", "slices", "blocks",
                   "glitch", "shear", "tilt", "drift", "scatter", "fold", "melt", "wave"]
PRIMARY_WEIGHTS = [4, 6, 4, 3, 3, 4, 2, 2, 2, 3, 2, 2, 2, 2]

SECONDARY_EFFECTS = ["columns", "prism", "slices", "blocks", "shatter"]
SECONDARY_WEIGHTS = [4, 3, 3, 4, 3]

def get_font(path, size, index=0):
    try: return ImageFont.truetype(path, size, index=index)
    except: return ImageFont.load_default()

def fit_font_to_width(word, font_path, font_index, target_fraction, canvas_w):
    lo, hi = 90, 400
    for _ in range(20):
        mid = (lo + hi) // 2
        font = get_font(font_path, mid, font_index)
        tmp = Image.new("RGB", (1, 1))
        bb = ImageDraw.Draw(tmp).textbbox((0, 0), word, font=font)
        lo, hi = (mid, hi) if bb[2]-bb[0] < target_fraction*canvas_w else (lo, mid)
    return min(lo, 400)

def make_gradient_map(width, height, color_a, color_b, angle_deg):
    angle_rad = math.radians(angle_deg)
    xi, yi = np.meshgrid(np.arange(width), np.arange(height))
    proj = xi * math.cos(angle_rad) + yi * math.sin(angle_rad)
    proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-8)
    proj = proj ** 0.7
    r, g, b = [(c1*(1-proj) + c2*proj).astype(np.uint8) for c1, c2 in zip(color_a, color_b)]
    return Image.fromarray(np.stack([r, g, b], axis=2), "RGB")

def make_word_tile_gradient(word, font_path, font_index, font_size, letter_spacing=0, gradient_img=None):
    font = get_font(font_path, font_size, font_index)
    chars = list(word)
    tmp = Image.new("L", (1, 1))
    cw = [ImageDraw.Draw(tmp).textbbox((0,0), ch, font=font)[2] for ch in chars]
    total_w, total_h = max(sum(cw) + letter_spacing*(len(chars)-1) + font_size, 10), font_size * 3
    mask = Image.new("L", (int(total_w), total_h), 0); draw = ImageDraw.Draw(mask)
    x = font_size // 4
    for i, ch in enumerate(chars):
        draw.text((x, font_size//3), ch, font=font, fill=255)
        x += cw[i] + letter_spacing
    bb = draw.textbbox((font_size//4, font_size//3), word, font=font)
    tile_h, tile_w = max(bb[3]-bb[1]+font_size//2, 10), max(int(x+font_size//4), 10)
    mask = mask.crop((0, 0, tile_w, tile_h))
    grad_tile = gradient_img.resize((tile_w, tile_h), Image.LANCZOS)
    tile = Image.new("RGBA", (tile_w, tile_h), (0,0,0,0))
    tile.paste(grad_tile.convert("RGBA"), mask=mask)
    return tile

def make_grid(tile, pad_w, pad_h):
    pad = max(pad_w, pad_h)
    gw, gh = pad_w + pad*2, pad_h + pad*2
    grid = Image.new("RGBA", (gw, gh), (0,0,0,0))
    gx, gy = pad + pad_w//2 - tile.width//2, pad + pad_h//2 - tile.height//2
    grid.paste(tile, (gx, gy), tile)
    return grid, pad

def displacement(t, seed, mode, w, h):
    rng = np.random.RandomState(seed)
    xi, yi = np.meshgrid(np.arange(w), np.arange(h))
    amp = t * 200
    dx, dy = np.zeros((h,w), np.float32), np.zeros((h,w), np.float32)

    if mode == "shatter":
        n = rng.randint(6, 20)
        px, py = rng.uniform(0, w, n), rng.uniform(0, h, n)
        sox, soy = rng.uniform(-amp, amp, n), rng.uniform(-amp*0.6, amp*0.6, n)
        dists = (xi[..., None]-px)**2 + (yi[..., None]-py)**2
        owner = np.argmin(dists, axis=2)
        for i in range(n):
            mv = (owner == i)
            dx += mv * sox[i]; dy += mv * soy[i]
    elif mode == "columns":
        n_cols = rng.randint(8, 20); bw = w // n_cols
        for i in range(n_cols):
            mask = (xi >= i*bw) & (xi < (i+1)*bw)
            dy += mask * rng.uniform(-amp, amp)
    elif mode == "prism":
        for _ in range(rng.randint(3, 6)):
            ang = rng.uniform(0, 2*math.pi); nx, ny = math.cos(ang), math.sin(ang)
            proj = xi*nx + yi*ny
            mid = rng.uniform(proj.min() + (proj.max()-proj.min())*0.15, proj.max() - (proj.max()-proj.min())*0.15)
            mask = proj > mid
            shift = rng.uniform(-amp, amp)
            dx += mask * shift * nx; dy += mask * shift * ny
    elif mode == "slices":
        ang = rng.uniform(0, math.pi); nx, ny = math.cos(ang), math.sin(ang)
        proj = xi*nx + yi*ny
        n_sl = rng.randint(6, 15); sl_w = (proj.max()-proj.min())/n_sl
        for i in range(n_sl):
            mask = (proj >= proj.min()+i*sl_w) & (proj < proj.min()+(i+1)*sl_w)
            sh = rng.uniform(-amp, amp)
            dx += mask * sh * nx; dy += mask * sh * ny
    elif mode == "blocks":
        for _ in range(rng.randint(10, 20)):
            bw, bh = rng.uniform(w*0.1, w*0.6), rng.uniform(h*0.05, h*0.25)
            bx, by = rng.uniform(-bw*0.5, w), rng.uniform(-bh*0.5, h)
            mask = (xi >= bx) & (xi < bx+bw) & (yi >= by) & (yi < by+bh)
            dx += mask * rng.uniform(-amp, amp); dy += mask * rng.uniform(-amp*0.5, amp*0.5)
    elif mode == "earthquake":
        n_b = rng.randint(8, 25); bh = h // n_b
        for i in range(n_b):
            mask = (yi >= i*bh) & (yi < (i+1)*bh)
            dx += mask * rng.uniform(-amp, amp)
    elif mode == "scatter":
        block_size = rng.randint(200, 500); blend_width = block_size // 4
        blocks_y, blocks_x = (h+block_size-1)//block_size, (w+block_size-1)//block_size
        bd = rng.uniform(-amp, amp, (blocks_y, blocks_x, 2))
        for y in range(h):
            for x in range(w):
                by, bx = min(y//block_size, blocks_y-1), min(x//block_size, blocks_x-1)
                dx[y,x], dy[y,x] = bd[by,bx,0], bd[by,bx,1]
    elif mode in ["glitch", "shear", "tilt", "drift", "fold", "melt", "wave"]:
        # Standard logic as in v20.4
        if mode == "glitch":
            for _ in range(rng.randint(4, 12)):
                y0, y1 = rng.randint(0, h), min(rng.randint(0, h)+80, h)
                mask = (yi >= y0) & (yi < y1)
                dx += mask * rng.uniform(-amp, amp)
        elif mode == "fold":
            axis = rng.choice(["v", "h"])
            if axis == "v":
                fx = rng.uniform(w*0.2, w*0.8); dx = amp * 0.8 * np.sign(xi - fx) * (1.0 - np.exp(-np.abs(xi-fx)/100))
            else:
                fy = rng.uniform(h*0.2, h*0.8); dy = amp * 0.8 * np.sign(yi - fy) * (1.0 - np.exp(-np.abs(yi-fy)/100))
        elif mode == "melt":
            dy = amp * (yi/h) * 0.7 + amp * 0.3 * np.sin(xi*0.01 + rng.uniform(0, 6.28))
        elif mode == "wave":
            for _ in range(rng.randint(3, 8)):
                dx += amp * 0.3 * np.sin(yi*rng.uniform(0.003, 0.015) + rng.uniform(0, 6.28)) / 5
        elif mode == "shear":
            s = rng.uniform(-0.5, 0.5); dx, dy = amp * s * (yi/h-0.5), amp * s * (xi/w-0.5)
        elif mode == "tilt":
            tx, ty = rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3); dx, dy = amp * tx * (yi/h-0.5), amp * ty * (xi/w-0.5)
        elif mode == "drift":
            nb = rng.randint(6, 15); bh = h//nb; ps = 0
            for i in range(nb):
                s = ps + (rng.uniform(-amp, amp) - ps) * 0.6; mask = (yi >= i*bh) & (yi < (i+1)*bh)
                dx += mask * s; ps = s
    return dx.astype(np.float32), dy.astype(np.float32)

def warp_rgba(grid, pad, dx, dy, w, h):
    gn = np.array(grid.convert("RGBA"), dtype=np.float32)
    sy_f, sx_f = np.indices((h, w)).astype(np.float32)
    sy_f, sx_f = sy_f + pad + dy, sx_f + pad + dx
    sy0, sx0 = np.clip(np.floor(sy_f).astype(np.int32), 0, gn.shape[0]-2), np.clip(np.floor(sx_f).astype(np.int32), 0, gn.shape[1]-2)
    fy, fx = (sy_f - sy0)[..., None], (sx_f - sx0)[..., None]
    v00, v01, v10, v11 = gn[sy0, sx0], gn[sy0, sx0+1], gn[sy0+1, sx0], gn[sy0+1, sx0+1]
    interp = v00*(1-fy)*(1-fx) + v01*(1-fy)*fx + v10*fy*(1-fx) + v11*fy*fx
    return Image.fromarray(interp.astype(np.uint8), "RGBA")

def spatial_shift(arr, dx, dy):
    res = np.zeros_like(arr); h, w = arr.shape[:2]; sx, sy = int(dx), int(dy)
    dx0, dx1, dy0, dy1 = max(0, sx), min(w, w+sx), max(0, sy), min(h, h+sy)
    sx0, sx1, sy0, sy1 = max(0, -sx), min(w, w-sx), max(0, -sy), min(h, h-sy)
    if dx1 > dx0 and dy1 > dy0: res[dy0:dy1, dx0:dx1] = arr[sy0:sy1, sx0:sx1]
    return res

def apply_chromatic_aberration(img, max_str, seed):
    rng = random.Random(seed); arr = np.array(img); out = np.zeros_like(arr); out[:,:,1] = arr[:,:,1]
    for ch in [0, 2]:
        ang, dist = rng.uniform(0, 2*math.pi), rng.uniform(max_str*0.4, max_str)
        out[:,:,ch] = spatial_shift(arr[:,:,ch:ch+1], dist*math.cos(ang), dist*math.sin(ang))[:,:,0]
    return Image.fromarray(out, "RGB")

def generate_static(day, seed=None):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    ls, target = rng.randint(-10, 80), rng.uniform(0.65, 0.95)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, target, WIDTH)
    fs_render = fs * 2
    
    n_pal = len(PALETTE_WHEEL); b_idx = rng.randint(0, n_pal-1); n_idx = (b_idx + rng.choice([-2,-1,1,2])) % n_pal
    color_a, color_b = PALETTE_WHEEL[b_idx][1], PALETTE_WHEEL[n_idx][1]
    grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_b, rng.uniform(0, 360))
    tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, ls, grad_img)
    grid, pad = make_grid(tile, WIDTH*2, HEIGHT*2)
    
    e1 = rng.choices(PRIMARY_EFFECTS, weights=PRIMARY_WEIGHTS)[0]
    t1 = rng.uniform(0.20, 0.40) if e1 in ["shatter", "slices"] else rng.uniform(0.20, 0.55) if e1 == "columns" else rng.uniform(0.30, 0.65)
    
    dx1, dy1 = displacement(t1, seed, e1, WIDTH*2, HEIGHT*2)
    p1 = warp_rgba(grid, pad, dx1, dy1, WIDTH*2, HEIGHT*2)
    bg = Image.new("RGB", (WIDTH*2, HEIGHT*2), (0,0,0)); bg.paste(p1.convert("RGB"), mask=p1.split()[3])
    
    # Secondary effect
    e2 = rng.choice([e for e in SECONDARY_EFFECTS if e != e1])
    dx2, dy2 = displacement(rng.uniform(0.1, 0.25), seed+1, e2, WIDTH*2, HEIGHT*2)
    bg = Image.fromarray(np.array(bg, dtype=np.float32).astype(np.uint8), "RGB") # dummy for warp
    # For simplicity in static, skip warp_rgb for secondary and just do independent CA
    ca_str = rng.uniform(18, 54)
    bg = apply_chromatic_aberration(bg, ca_str, seed)
    
    bg = bg.resize((WIDTH, HEIGHT), Image.LANCZOS)
    date_str = datetime.now().strftime("%Y%m%d")
    fname = f"{e1}{int(t1*100)}_{f_lbl}_fs{fs}_{day}_{date_str}_s{seed}.png"
    out_path = os.path.join(OUTPUT_DIR, fname); bg.save(out_path, "PNG")
    print(f"✅ Static saved: {fname}")
    return out_path

def generate_video(day, seed=None):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    n_pal = len(PALETTE_WHEEL); b_idx = rng.randint(0, n_pal-1); n_idx = (b_idx + rng.choice([-2,-1,1,2])) % n_pal
    color_a, color_b = PALETTE_WHEEL[b_idx][1], PALETTE_WHEEL[n_idx][1]
    grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_b, rng.uniform(0, 360))
    tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, rng.randint(-10, 80), grad_img)
    
    tmp_dir = f"temp_frames_{seed}"; os.makedirs(tmp_dir, exist_ok=True)
    frames_left, state = 0, "HOLD"
    current_e1, current_t1, f_seed = rng.choice(PRIMARY_EFFECTS), rng.uniform(0.2, 0.4), seed
    
    print(f"Rendering {TOTAL_FRAMES} frames for {f_lbl}...")
    for f in range(TOTAL_FRAMES):
        if frames_left <= 0:
            if state == "HOLD": state, frames_left = "BURST", rng.randint(1, 4)
            else:
                state, frames_left = "HOLD", rng.randint(8, 25)
                current_e1, current_t1, f_seed = rng.choice(PRIMARY_EFFECTS), rng.uniform(0.25, 0.45), seed+f
        
        if state == "BURST":
            t1, e1, ca, eff_seed = rng.uniform(0.4, 0.8), rng.choice(PRIMARY_EFFECTS), rng.uniform(30, 60), seed+f*10
        else:
            t1, e1, ca, eff_seed = current_t1 + math.sin(f*0.5)*0.05, current_e1, 8 + math.sin(f*0.2)*4, f_seed
        
        grid, pad = make_grid(tile, WIDTH*2, HEIGHT*2)
        dx1, dy1 = displacement(t1, eff_seed, e1, WIDTH*2, HEIGHT*2)
        p1 = warp_rgba(grid, pad, dx1, dy1, WIDTH*2, HEIGHT*2)
        bg = Image.new("RGB", (WIDTH*2, HEIGHT*2), (0,0,0)); bg.paste(p1.convert("RGB"), mask=p1.split()[3])
        bg = apply_chromatic_aberration(bg, ca, eff_seed)
        bg.resize((WIDTH, HEIGHT), Image.LANCZOS).save(os.path.join(tmp_dir, f"frame_{f:04d}.png"))
        frames_left -= 1
    
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"video_{f_lbl}_{day}_{date_str}_s{seed}.mp4")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{tmp_dir}/frame_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp_dir)
    print(f"✅ Video saved: {out_path}")
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for _ in range(args.batch):
        if args.video: generate_video(args.day, args.seed)
        else: generate_static(args.day, args.seed)
