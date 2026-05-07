#!/usr/bin/env python3
"""
SREDA100 VIDEO v1.2 (Hold & Burst)
Art project: Rhythmic geometric typography.
Focuses on long static holds and sudden aggressive glitch bursts.
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

PRIMARY_EFFECTS = ["shatter", "earthquake", "columns", "prism", "slices", "blocks", "glitch", "fold"]

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
    r = (color_a[0] * (1-proj) + color_b[0] * proj).astype(np.uint8)
    g = (color_a[1] * (1-proj) + color_b[1] * proj).astype(np.uint8)
    b = (color_a[2] * (1-proj) + color_b[2] * proj).astype(np.uint8)
    return Image.fromarray(np.stack([r, g, b], axis=2), "RGB")

def make_word_tile_gradient(word, font_path, font_index, font_size, letter_spacing=0, gradient_img=None):
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
    tile_h, tile_w = max(bb[3]-bb[1]+font_size//2, 10), max(int(x+font_size//4), 10)
    mask = mask.crop((0, 0, tile_w, tile_h))
    grad_tile = gradient_img.resize((tile_w, tile_h), Image.LANCZOS)
    tile = Image.new("RGBA", (tile_w, tile_h), (0,0,0,0))
    tile.paste(grad_tile.convert("RGBA"), mask=mask)
    return tile

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
    return dx, dy

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
    res = np.zeros_like(arr)
    h, w = arr.shape[:2]
    sx, sy = int(dx), int(dy)
    src_x0, src_x1 = max(0, -sx), min(w, w-sx)
    dst_x0, dst_x1 = max(0,  sx), min(w, w+sx)
    src_y0, src_y1 = max(0, -sy), min(h, h-sy)
    dst_y0, dst_y1 = max(0,  sy), min(h, h+sy)
    if dst_x1 > dst_x0 and dst_y1 > dst_y0:
        res[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]
    return res

def apply_chromatic_aberration(img, max_str, seed):
    rng = random.Random(seed)
    arr = np.array(img)
    out = np.zeros_like(arr); out[:,:,1] = arr[:,:,1] # Green anchor
    for ch in [0, 2]:
        ang = rng.uniform(0, 2*math.pi)
        dist = rng.uniform(max_str*0.4, max_str)
        out[:,:,ch] = spatial_shift(arr[:,:,ch:ch+1], dist*math.cos(ang), dist*math.sin(ang))[:,:,0]
    return Image.fromarray(out, "RGB")

def generate_video(day, seed=None):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    
    # 1. Base style (fixed for entire video)
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    ls = rng.randint(-10, 80)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    
    n_pal = len(PALETTE_WHEEL)
    b_idx = rng.randint(0, n_pal-1); n_idx = (b_idx + rng.choice([-2,-1,1,2])) % n_pal
    color_a, color_b = PALETTE_WHEEL[b_idx][1], PALETTE_WHEEL[n_idx][1]
    grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_b, rng.uniform(0, 360))
    tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, ls, grad_img)
    
    tmp_dir = f"temp_frames_{seed}"
    os.makedirs(tmp_dir, exist_ok=True)
    
    # 2. State Machine Logic
    # States: "HOLD" (stable, low noise), "BURST" (rapid chaotic jumps)
    frames_left = 0
    state = "HOLD"
    
    current_e1 = rng.choice(PRIMARY_EFFECTS)
    current_t1 = rng.uniform(0.2, 0.4)
    f_seed = seed
    
    print(f"Rendering {TOTAL_FRAMES} frames for {f_lbl}...")
    
    for f in range(TOTAL_FRAMES):
        if frames_left <= 0:
            if state == "HOLD":
                # Start a BURST (quick chaotic frames)
                state = "BURST"
                frames_left = rng.randint(1, 4)
            else:
                # Start a HOLD (long stable period)
                state = "HOLD"
                frames_left = rng.randint(8, 25)
                # Pick a new baseline structure for the hold
                current_e1 = rng.choice(PRIMARY_EFFECTS)
                current_t1 = rng.uniform(0.25, 0.45)
                f_seed = seed + f

        if state == "BURST":
            # Rapidly changing structure
            t1 = rng.uniform(0.4, 0.8)
            e1 = rng.choice(PRIMARY_EFFECTS)
            ca = rng.uniform(30, 60)
            eff_seed = seed + f * 10 # Change seed every frame in burst
        else:
            # Stable hold with subtle "drift"
            t1 = current_t1 + math.sin(f * 0.5) * 0.05
            e1 = current_e1
            ca = 8 + math.sin(f * 0.2) * 4 # Subtle breathing CA
            eff_seed = f_seed # KEEP seed fixed for structure consistency

        # Build frame
        grid = Image.new("RGBA", (WIDTH*2 + WIDTH*4, HEIGHT*2 + HEIGHT*4), (0,0,0,0))
        pad = WIDTH*2
        gx, gy = pad + WIDTH - tile.width//2, pad + HEIGHT - tile.height//2
        grid.paste(tile, (gx, gy), tile)
        
        dx1, dy1 = displacement(t1, eff_seed, e1, WIDTH*2, HEIGHT*2)
        p1 = warp_rgba(grid, pad, dx1, dy1, WIDTH*2, HEIGHT*2)
        bg = Image.new("RGB", (WIDTH*2, HEIGHT*2), (0,0,0))
        bg.paste(p1.convert("RGB"), mask=p1.split()[3])
        
        bg = apply_chromatic_aberration(bg, ca, eff_seed)
        bg = bg.resize((WIDTH, HEIGHT), Image.LANCZOS)
        bg.save(os.path.join(tmp_dir, f"frame_{f:04d}.png"))
        frames_left -= 1
    
    # 3. Assemble
    date_str = datetime.now().strftime("%Y%m%d")
    out_name = f"video_{f_lbl}_{day}_{date_str}_s{seed}.mp4"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{tmp_dir}/frame_%04d.png",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp_dir)
    print(f"✅ Video saved: {out_path}")
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--batch", type=int, default=5)
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for _ in range(args.batch):
        generate_video(args.day)
