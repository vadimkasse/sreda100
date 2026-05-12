#!/usr/bin/env python3
"""
SREDA100 v21.0 (Organic Aggression)
Art project: Rhythmic geometric typography.
Unified engine: Smooth transitions, aggressive distortion, flicker-free sub-pixel CA.
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

# Only destructive effects for maximum aggression
PRIMARY_EFFECTS = ["shatter", "earthquake", "columns", "prism", "slices", "blocks",
                   "glitch", "scatter", "fold", "melt", "wave"]

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
    amp = t * 500
    dx, dy = np.zeros((h,w), np.float32), np.zeros((h,w), np.float32)

    if mode == "shatter":
        n = rng.randint(10, 25)
        px, py = rng.uniform(0, w, n), rng.uniform(0, h, n)
        sox, soy = rng.uniform(-amp, amp, n), rng.uniform(-amp*0.6, amp*0.6, n)
        dists = (xi[..., None]-px)**2 + (yi[..., None]-py)**2
        owner = np.argmin(dists, axis=2)
        for i in range(n):
            mv = (owner == i); dx += mv * sox[i]; dy += mv * soy[i]
    elif mode == "columns":
        n_cols = rng.randint(12, 24); bw = w // n_cols
        for i in range(n_cols):
            mask = (xi >= i*bw) & (xi < (i+1)*bw); dy += mask * rng.uniform(-amp, amp)
    elif mode == "prism":
        for _ in range(rng.randint(4, 8)):
            ang = rng.uniform(0, 2*math.pi); nx, ny = math.cos(ang), math.sin(ang)
            proj = xi*nx + yi*ny
            mid = rng.uniform(proj.min() + (proj.max()-proj.min())*0.15, proj.max() - (proj.max()-proj.min())*0.15)
            mask = proj > mid; shift = rng.uniform(-amp, amp)
            dx += mask * shift * nx; dy += mask * shift * ny
    elif mode == "slices":
        ang = rng.uniform(0, math.pi); nx, ny = math.cos(ang), math.sin(ang)
        proj = xi*nx + yi*ny; n_sl = rng.randint(10, 20); sl_w = (proj.max()-proj.min())/n_sl
        for i in range(n_sl):
            mask = (proj >= proj.min()+i*sl_w) & (proj < proj.min()+(i+1)*sl_w)
            sh = rng.uniform(-amp, amp); dx += mask * sh * nx; dy += mask * sh * ny
    elif mode == "blocks":
        for _ in range(rng.randint(15, 30)):
            bw, bh = rng.uniform(w*0.1, w*0.5), rng.uniform(h*0.05, h*0.2)
            bx, by = rng.uniform(-bw*0.5, w), rng.uniform(-bh*0.5, h)
            mask = (xi >= bx) & (xi < bx+bw) & (yi >= by) & (yi < by+bh)
            dx += mask * rng.uniform(-amp, amp); dy += mask * rng.uniform(-amp*0.5, amp*0.5)
    elif mode == "earthquake":
        n_b = rng.randint(12, 30); bh = h // n_b
        for i in range(n_b):
            mask = (yi >= i*bh) & (yi < (i+1)*bh); dx += mask * rng.uniform(-amp, amp)
    elif mode == "scatter":
        block_size = rng.randint(150, 400)
        blocks_y, blocks_x = (h+block_size-1)//block_size, (w+block_size-1)//block_size
        bd = rng.uniform(-amp, amp, (blocks_y, blocks_x, 2))
        for y in range(h):
            for x in range(w):
                by, bx = min(y//block_size, blocks_y-1), min(x//block_size, blocks_x-1)
                dx[y,x], dy[y,x] = bd[by,bx,0], bd[by,bx,1]
    elif mode in ["glitch", "fold", "melt", "wave"]:
        if mode == "glitch":
            for _ in range(rng.randint(8, 20)):
                y0, y1 = rng.randint(0, h), min(rng.randint(0, h)+100, h)
                mask = (yi >= y0) & (yi < y1); dx += mask * rng.uniform(-amp, amp)
        elif mode == "fold":
            for _ in range(2):
                axis = rng.choice(["v", "h"])
                if axis == "v":
                    fx = rng.uniform(w*0.2, w*0.8); dx += amp * 0.8 * np.sign(xi - fx) * (1.0 - np.exp(-np.abs(xi-fx)/100))
                else:
                    fy = rng.uniform(h*0.2, h*0.8); dy += amp * 0.8 * np.sign(yi - fy) * (1.0 - np.exp(-np.abs(yi-fy)/100))
        elif mode == "melt":
            dy = amp * (yi/h) * 0.8 + amp * 0.4 * np.sin(xi*0.012 + rng.uniform(0, 6.28))
        elif mode == "wave":
            for _ in range(rng.randint(4, 10)):
                dx += amp * 0.4 * np.sin(yi*rng.uniform(0.005, 0.02) + rng.uniform(0, 6.28)) / 5
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

def apply_chromatic_aberration(img, max_str, seed):
    rng = random.Random(seed)
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]; out = np.zeros_like(arr); out[:,:,1] = arr[:,:,1]
    for ch in [0, 2]:
        ang = rng.uniform(0, 2*math.pi); dist = rng.uniform(max_str*0.5, max_str)
        tx, ty = dist * math.cos(ang), dist * math.sin(ang)
        yy, xx = np.indices((h, w), dtype=np.float32)
        sx_f, sy_f = xx - tx, yy - ty
        sx0, sy0 = np.clip(np.floor(sx_f).astype(np.int32), 0, w-2), np.clip(np.floor(sy_f).astype(np.int32), 0, h-2)
        fx, fy = sx_f - sx0, sy_f - sy0
        v00, v01, v10, v11 = arr[sy0, sx0, ch], arr[sy0, sx0+1, ch], arr[sy0+1, sx0, ch], arr[sy0+1, sx0+1, ch]
        out[:,:,ch] = v00*(1-fx)*(1-fy) + v01*fx*(1-fy) + v10*(1-fx)*fy + v11*fx*fy
    return Image.fromarray(out.astype(np.uint8), "RGB")

def make_background_layer(mode, width, height, color, dx=None, dy=None):
    bg = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    if mode == "grid":
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        step, line_w, draw_color = 120, 4, (*color, 255)
        for x in range(0, width, step): draw.line([(x, 0), (x, height)], fill=draw_color, width=line_w)
        for y in range(0, height, step): draw.line([(0, y), (width, y)], fill=draw_color, width=line_w)
        if dx is not None and dy is not None: layer = warp_rgba(layer, 0, dx, dy, width, height)
        bg = Image.alpha_composite(bg, layer)
    return bg

def generate_static(day, seed=None, background_mode="grid", palette_mode="mono"):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    color_a = (255, 255, 255)
    grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_a, 0)
    tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, rng.randint(-10, 80), grad_img)
    
    e1 = rng.choice(PRIMARY_EFFECTS); t1 = rng.uniform(0.65, 0.95)
    dx1, dy1 = displacement(t1, seed, e1, WIDTH*2, HEIGHT*2)
    bg = make_background_layer(background_mode, WIDTH*2, HEIGHT*2, color_a, dx1, dy1)
    grid, pad = make_grid(tile, WIDTH*2, HEIGHT*2)
    p1 = warp_rgba(grid, pad, dx1, dy1, WIDTH*2, HEIGHT*2)
    
    final = Image.alpha_composite(bg, p1).convert("RGB")
    ca_str = rng.uniform(20, 40)
    final = apply_chromatic_aberration(final, ca_str, seed)
    final = final.resize((WIDTH, HEIGHT), Image.LANCZOS)
    
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"{e1}_{f_lbl}_{day}_{date_str}_s{seed}.png")
    final.save(out_path, "PNG")
    return out_path, {"effect": e1, "font": f_lbl, "seed": seed}

def render_video_frame_manual(tile, dx, dy, ca, width, height, background_mode, color_a, ca_seed):
    bg = make_background_layer(background_mode, width, height, color_a, dx, dy)
    grid, pad = make_grid(tile, width, height)
    p1 = warp_rgba(grid, pad, dx, dy, width, height)
    final = Image.alpha_composite(bg, p1).convert("RGB")
    final = apply_chromatic_aberration(final, ca, ca_seed)
    return final.resize((width // 2, height // 2), Image.LANCZOS)

def generate_video(day, seed=None, background_mode="grid", palette_mode="mono"):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    color_a = (255, 255, 255)
    grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_a, 0)
    tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, rng.randint(-10, 80), grad_img)
    
    tmp_dir = os.path.join(os.getcwd(), f"temp_frames_{seed}")
    if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    def get_aggressive_anchor():
        mode, s, t = rng.choice(PRIMARY_EFFECTS), rng.randint(0, 2**32), rng.uniform(0.65, 0.95)
        return displacement(t, s, mode, WIDTH*2, HEIGHT*2)

    dx_start, dy_start = get_aggressive_anchor()
    dx_end, dy_end = get_aggressive_anchor()
    trans_duration, frames_in_trans = FPS * 1.2, 0

    print(f"Rendering {TOTAL_FRAMES} organic frames for {f_lbl} (seed: {seed})...")
    for f in range(TOTAL_FRAMES):
        alpha = frames_in_trans / trans_duration
        alpha_ease = 0.5 - 0.5 * math.cos(alpha * math.pi)
        dx = dx_start * (1 - alpha_ease) + dx_end * alpha_ease
        dy = dy_start * (1 - alpha_ease) + dy_end * alpha_ease
        drift_amp = 30; dx += drift_amp * math.sin(f * 0.3 + seed); dy += drift_amp * math.cos(f * 0.4 + seed*1.1)
        ca = (20 * (1 - alpha_ease) + 40 * alpha_ease) * 0.7
        img = render_video_frame_manual(tile, dx, dy, ca, WIDTH*2, HEIGHT*2, background_mode, color_a, seed)
        img.save(os.path.join(tmp_dir, f"frame_{f:04d}.png"))
        frames_in_trans += 1
        if frames_in_trans >= trans_duration:
            dx_start, dy_start = dx_end, dy_end; dx_end, dy_end = get_aggressive_anchor(); frames_in_trans = 0
            
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"video_{f_lbl}_{day}_{date_str}_s{seed}.mp4")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{tmp_dir}/frame_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp_dir)
    return out_path, {"font": f_lbl, "video": True}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--background_mode", default="grid")
    parser.add_argument("--palette_mode", default="mono")
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for _ in range(args.batch):
        if args.video: generate_video(args.day, args.seed, args.background_mode, args.palette_mode)
        else: generate_static(args.day, args.seed, args.background_mode, args.palette_mode)
