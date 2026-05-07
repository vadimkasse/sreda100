#!/usr/bin/env python3
"""
sreda100_bg_test.py — Экспериментальный стенд для тестирования фонов.
Откат к версии: White on Black + Chromatic Aberration (Color Reflects).
"""

import os
import random
import math
import argparse
import subprocess
import shutil
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import sreda100 as gen

OUTPUT_DIR = os.path.expanduser("~/sreda100_output/bg_test")

def create_bg_layer(mode, params, bw=False, frame_params=None):
    w2, h2 = gen.WIDTH * 2, gen.HEIGHT * 2
    bg = Image.new("RGBA", (w2, h2), (0, 0, 0, 255))
    rng = random.Random(params['seed'] + 999)
    # Если bw=True, используем белый
    color_a = (255, 255, 255) if bw else params['color_a']

    if mode == "grid":
        layer = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        step = rng.randint(60, 120)
        line_w = rng.randint(2, 4)
        bright = 1.0 if bw else rng.uniform(0.12, 0.20)
        grid_color = (*tuple(int(c * bright) for c in color_a), 255)
        for x in range(0, w2, step): draw.line([(x, 0), (x, h2)], fill=grid_color, width=line_w)
        for y in range(0, h2, step): draw.line([(0, y), (w2, y)], fill=grid_color, width=line_w)
        if frame_params:
            dx, dy = gen.displacement(frame_params['t1'], frame_params['eff_seed'], frame_params['e1'], w2, h2)
            layer = gen.warp_rgba(layer, 0, dx, dy, w2, h2)
        bg = Image.alpha_composite(bg, layer)
    return bg

def render_common(mode, day, seed, bw=False, frame_params=None):
    rng = random.Random(seed)
    f_path, f_idx, f_lbl = rng.choice(gen.AVAILABLE_FONTS)
    ls, target = rng.randint(-10, 80), rng.uniform(0.65, 0.95)
    fs = gen.fit_font_to_width(day.upper(), f_path, f_idx, target, gen.WIDTH)
    fs_render = fs * 2
    
    if bw:
        color_a, color_b = (255, 255, 255), (255, 255, 255)
    else:
        n_pal = len(gen.PALETTE_WHEEL); b_idx = rng.randint(0, n_pal-1); n_idx = (b_idx + rng.choice([-2,-1,1,2])) % n_pal
        color_a, color_b = gen.PALETTE_WHEEL[b_idx][1], gen.PALETTE_WHEEL[n_idx][1]
    
    grad_img = gen.make_gradient_map(gen.WIDTH*2, gen.HEIGHT*2, color_a, color_b, rng.uniform(0, 360))
    tile = gen.make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, ls, grad_img)
    e1 = rng.choices(gen.PRIMARY_EFFECTS, weights=gen.PRIMARY_WEIGHTS)[0]
    t1 = rng.uniform(0.20, 0.40) if e1 in ["shatter", "slices"] else rng.uniform(0.20, 0.55) if e1 == "columns" else rng.uniform(0.30, 0.65)
    
    params = {"seed": seed, "day": day, "tile": tile, "f_path": f_path, "f_idx": f_idx, "f_lbl": f_lbl,
              "fs_render": fs_render, "color_a": color_a, "color_b": color_b, "e1": e1, "t1": t1}
    
    bg = create_bg_layer(mode, params, bw=bw, frame_params=frame_params)
    grid_w, pad = gen.make_grid(tile, gen.WIDTH*2, gen.HEIGHT*2)
    
    cur_t1 = frame_params['t1'] if frame_params else t1
    cur_e1 = frame_params['e1'] if frame_params else e1
    cur_seed = frame_params['eff_seed'] if frame_params else seed
    
    dx, dy = gen.displacement(cur_t1, cur_seed, cur_e1, gen.WIDTH*2, gen.HEIGHT*2)
    word_layer = gen.warp_rgba(grid_w, pad, dx, dy, gen.WIDTH*2, gen.HEIGHT*2)
    
    final = Image.alpha_composite(bg, word_layer).convert("RGB")
    # Аберрация даст цветные рефлекты на белых краях
    ca = frame_params['ca'] if frame_params else (rng.uniform(18, 54) if not bw else 25)
    
    final = gen.apply_chromatic_aberration(final, ca, cur_seed)
    return final.resize((gen.WIDTH, gen.HEIGHT), Image.LANCZOS), f_lbl

def generate_video_test(mode, day, seed, bw=False):
    tmp_dir = f"temp_vbg_{seed}"; os.makedirs(tmp_dir, exist_ok=True)
    rng = random.Random(seed)
    frames_left, state = 0, "HOLD"
    curr_e1, curr_t1, f_seed = rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(0.2, 0.4), seed
    
    print(f"Video {mode} (Reflects Mode) seed={seed}...")
    for f in range(gen.TOTAL_FRAMES):
        if frames_left <= 0:
            if state == "HOLD": state, frames_left = "BURST", rng.randint(1, 4)
            else:
                state, frames_left = "HOLD", rng.randint(8, 25)
                curr_e1, curr_t1, f_seed = rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(0.25, 0.45), seed+f
        if state == "BURST": t1, e1, ca, eff_seed = rng.uniform(0.4, 0.8), rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(30, 60), seed+f*10
        else: t1, e1, ca, eff_seed = curr_t1 + math.sin(f*0.5)*0.05, curr_e1, 8 + math.sin(f*0.2)*4, f_seed
        
        f_params = {"t1": t1, "e1": e1, "eff_seed": eff_seed, "ca": ca}
        img, f_lbl = render_common(mode, day, seed, bw=bw, frame_params=f_params)
        img.save(os.path.join(tmp_dir, f"frame_{f:04d}.png"))
        frames_left -= 1
        
    sfx = "_reflects" if bw else ""
    out_path = os.path.join(OUTPUT_DIR, mode, f"v_{mode}{sfx}_{f_lbl}_s{seed}.mp4")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-framerate", str(gen.FPS), "-i", f"{tmp_dir}/frame_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp_dir)
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["grid", "halo", "debris", "all"], default="grid")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--day", default=datetime.now().strftime("%A").upper())
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--bw", action="store_true")
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for i in range(args.count):
        seed = (args.seed if args.seed is not None else 6000) + i
        if args.video:
            p = generate_video_test(args.mode, args.day, seed, args.bw)
            print(f"Video saved: {p}")
        else:
            img, lbl = render_common(args.mode, args.day, seed, args.bw)
            img.save(os.path.join(OUTPUT_DIR, args.mode, f"{args.mode}_reflects_{i:02d}_{lbl}_s{seed}.png"))
