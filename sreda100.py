#!/usr/bin/env python3
"""
SREDA100 v22.0 (Organic Aggression)
Art project: Rhythmic geometric typography.
Unified engine: Smooth transitions, aggressive distortion, flicker-free sub-pixel CA.
Supports 6 styles, random color inversion, and video rendering.
"""

import argparse
import random
import math
import numpy as np
import os
import subprocess
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

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
if not AVAILABLE_FONTS:
    AVAILABLE_FONTS = [("/System/Library/Fonts/Helvetica.ttc", 1, "helvetica")]

PRIMARY_EFFECTS = ["shatter", "earthquake", "columns", "prism", "slices", "blocks",
                   "glitch", "scatter", "fold", "melt", "wave"]

STYLES = ["classic", "pattern", "outline", "micro_typo", "feedback", "ink_bleed"]

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
    # Fix for edge smearing: mask out pixels that fall out of bounds
    valid_mask = (sy_f >= 0) & (sy_f < gn.shape[0]-1) & (sx_f >= 0) & (sx_f < gn.shape[1]-1)
    
    sy0, sx0 = np.clip(np.floor(sy_f).astype(np.int32), 0, gn.shape[0]-2), np.clip(np.floor(sx_f).astype(np.int32), 0, gn.shape[1]-2)
    fy, fx = (sy_f - sy0)[..., None], (sx_f - sx0)[..., None]
    v00, v01, v10, v11 = gn[sy0, sx0], gn[sy0, sx0+1], gn[sy0+1, sx0], gn[sy0+1, sx0+1]
    interp = v00*(1-fy)*(1-fx) + v01*(1-fy)*fx + v10*fy*(1-fx) + v11*fy*fx
    interp = interp * valid_mask[..., None]
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

def make_background_layer(width, height, color, dx=None, dy=None, draw_grid=True):
    bg = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    if draw_grid:
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        step, line_w, draw_color = 120, 4, (*color, 255)
        for x in range(0, width, step): draw.line([(x, 0), (x, height)], fill=draw_color, width=line_w)
        for y in range(0, height, step): draw.line([(0, y), (width, y)], fill=draw_color, width=line_w)
        if dx is not None and dy is not None:
            layer = warp_rgba(layer, 0, dx, dy, width, height)
        bg = Image.alpha_composite(bg, layer)
    return bg

def apply_ink_bleed(img):
    blur = img.filter(ImageFilter.GaussianBlur(3))
    arr = np.array(blur.convert("L"))
    arr = np.where(arr > 100, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "L").convert("RGB")

def build_scene_layer(style, day, f_path, f_idx, fs_render, seed, color_a):
    rng = random.Random(seed)
    
    if style in ["classic", "feedback", "ink_bleed"]:
        grad_img = make_gradient_map(WIDTH*2, HEIGHT*2, color_a, color_a, 0)
        tile = make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, rng.randint(-10, 80), grad_img)
        grid, pad = make_grid(tile, WIDTH*2, HEIGHT*2)
        return grid, pad
    else:
        grid = Image.new("RGBA", (WIDTH*2, HEIGHT*2), (0,0,0,0))
        draw = ImageDraw.Draw(grid)
        font_large = get_font(f_path, int(fs_render*0.6), f_idx)
        
        if style == "pattern":
            for y in range(0, HEIGHT*2, int(fs_render*0.6)):
                for x in range(-200, WIDTH*2, int(fs_render*2.5)):
                    draw.text((x + (y%2)*150, y), day.upper(), font=font_large, fill=(*color_a, 255))
        elif style == "micro_typo":
            draw.text((WIDTH, HEIGHT), day.upper(), font=font_large, fill=(*color_a, 255), anchor="mm")
            font_small = get_font(f_path, 80, f_idx)
            for x, y in [(100, 100), (WIDTH*2-300, 100), (100, HEIGHT*2-100), (WIDTH*2-300, HEIGHT*2-100)]:
                draw.text((x, y), f"SREDA100 v22\nSEED: {seed}\nSYS: ERR", font=font_small, fill=(*color_a, 255))
        elif style == "outline":
            draw.text((WIDTH, HEIGHT), day.upper(), font=font_large, fill=(0,0,0,255), stroke_width=8, stroke_fill=(*color_a, 255), anchor="mm")
            
        return grid, 0

def render_frame_composite(grid, pad, dx, dy, ca, width, height, color_a, ca_seed, style, apply_ca=False):
    draw_grid = style in ["feedback", "ink_bleed"]
    bg = make_background_layer(width, height, color_a, dx, dy, draw_grid)
    p1 = warp_rgba(grid, pad, dx, dy, width, height)
    final = Image.alpha_composite(bg, p1).convert("RGB")
    if apply_ca:
        final = apply_chromatic_aberration(final, ca, ca_seed)
    return final.resize((width // 2, height // 2), Image.LANCZOS)

def generate_static(day, seed=None, style="feedback", invert=False, apply_ca=True):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    if style == "random": style = rng.choice(STYLES)
        
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    color_a = (255, 255, 255)
    
    grid, pad = build_scene_layer(style, day, f_path, f_idx, fs_render, seed, color_a)
    
    e1 = rng.choice(PRIMARY_EFFECTS); t1 = rng.uniform(0.65, 0.95)
    dx1, dy1 = displacement(t1, seed, e1, WIDTH*2, HEIGHT*2)
    
    final = render_frame_composite(grid, pad, dx1, dy1, rng.uniform(20, 40), WIDTH*2, HEIGHT*2, color_a, seed, style, apply_ca)
    
    if style == "ink_bleed":
        final = apply_ink_bleed(final)
        
    if invert:
        final = ImageOps.invert(final)
    
    date_str = datetime.now().strftime("%Y%m%d")
    color_label = "wb" if invert else "bw"
    out_path = os.path.join(OUTPUT_DIR, f"static_{style}_{color_label}_{f_lbl}_{day}_{date_str}_s{seed}.png")
    final.save(out_path, "PNG")
    return out_path

def generate_video(day, seed=None, style="feedback", invert=False, apply_ca=True):
    if seed is None: seed = random.randint(0, 2**32)
    rng = random.Random(seed)
    if style == "random": style = rng.choice(STYLES)
        
    f_path, f_idx, f_lbl = rng.choice(AVAILABLE_FONTS)
    fs = fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), WIDTH)
    fs_render = fs * 2
    color_a = (255, 255, 255)
    
    grid, pad = build_scene_layer(style, day, f_path, f_idx, fs_render, seed, color_a)
    
    tmp_dir = os.path.join(os.getcwd(), f"temp_frames_{seed}")
    if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    def get_aggressive_anchor():
        mode = rng.choice(PRIMARY_EFFECTS)
        s, t = rng.randint(0, 2**32), rng.uniform(0.65, 0.95)
        return displacement(t, s, mode, WIDTH*2, HEIGHT*2)

    dx_start, dy_start = get_aggressive_anchor()
    dx_end, dy_end = get_aggressive_anchor()
    trans_duration, frames_in_trans = FPS * 1.2, 0

    feedback_state = None

    print(f"Rendering {TOTAL_FRAMES} frames for {f_lbl} | Style: {style} | Invert: {invert} (seed: {seed})...")
    for f in range(TOTAL_FRAMES):
        alpha = frames_in_trans / trans_duration
        alpha_ease = 0.5 - 0.5 * math.cos(alpha * math.pi)
        dx = dx_start * (1 - alpha_ease) + dx_end * alpha_ease
        dy = dy_start * (1 - alpha_ease) + dy_end * alpha_ease
        drift_amp = 30; dx += drift_amp * math.sin(f * 0.3 + seed); dy += drift_amp * math.cos(f * 0.4 + seed*1.1)
        ca = (20 * (1 - alpha_ease) + 40 * alpha_ease) * 0.7
        
        final = render_frame_composite(grid, pad, dx, dy, ca, WIDTH*2, HEIGHT*2, color_a, seed, style, apply_ca)
        
        if style == "ink_bleed":
            final = apply_ink_bleed(final)
        elif style == "feedback":
            arr = np.array(final).astype(np.float32)
            if feedback_state is None: 
                feedback_state = arr
            else:
                shift_y = 15; shift_x = 0
                shifted = np.roll(feedback_state, shift_y, axis=0)
                feedback_state = np.maximum(arr, shifted * 0.85)
            final = Image.fromarray(np.clip(feedback_state, 0, 255).astype(np.uint8), "RGB")

        final.save(os.path.join(tmp_dir, f"frame_{f:04d}.png"))
        frames_in_trans += 1
        if frames_in_trans >= trans_duration:
            dx_start, dy_start = dx_end, dy_end; dx_end, dy_end = get_aggressive_anchor(); frames_in_trans = 0
            
    date_str = datetime.now().strftime("%Y%m%d")
    color_label = "wb" if invert else "bw"
    out_path = os.path.join(OUTPUT_DIR, f"video_{style}_{color_label}_{f_lbl}_{day}_{date_str}_s{seed}.mp4")
    
    ffmpeg_cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{tmp_dir}/frame_%04d.png"]
    if invert:
        ffmpeg_cmd.extend(["-vf", "negate"])
    ffmpeg_cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path])
    
    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp_dir)
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--style", default="feedback", choices=["random"] + STYLES)
    parser.add_argument("--color", default="bw", choices=["random", "bw", "wb"])
    parser.add_argument("--ca", action="store_true", default=True, help="Enable chromatic aberration")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for _ in range(args.batch):
        current_seed = args.seed if args.seed is not None else random.randint(0, 2**32)
        
        # Decide invert based on color mode
        if args.color == "random":
            invert_flag = random.choice([True, False])
        else:
            invert_flag = True if args.color == "wb" else False
            
        if args.video: 
            generate_video(args.day, current_seed, args.style, invert_flag, args.ca)
        else: 
            generate_static(args.day, current_seed, args.style, invert_flag, args.ca)
