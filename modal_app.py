"""
modal_app.py — SREDA100 infrastructure layer (v20.6 Parallel)
Optimized for fast video generation using Modal's parallel mapping.
"""

import io
import os
import random
from datetime import date, datetime
import boto3
import modal

# ---------------------------------------------------------------------------
# Image & App Setup
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("Pillow", "numpy", "boto3", "fastapi[standard]")
    .add_local_dir("fonts", remote_path="/fonts")
    .add_local_file("sreda100.py", remote_path="/root/sreda100.py")
)

app = modal.App("sreda100", image=image)
r2_secret = modal.Secret.from_name("sreda100-r2")

LINUX_FONTS = [
    ("/fonts/Inter-Bold.ttf", 0, "inter_bold"), ("/fonts/Inter-Black.ttf", 0, "inter_black"),
    ("/fonts/Outfit-Bold.ttf", 0, "outfit_bold"), ("/fonts/BarlowCondensed-Bold.ttf", 0, "barlow_cond_bold"),
    ("/fonts/BarlowCondensed-ExtraBold.ttf", 0, "barlow_cond_extrabold"), ("/fonts/PlayfairDisplay-Bold.ttf", 0, "playfair_bold"),
    ("/fonts/Lato-Bold.ttf", 0, "lato_bold"), ("/fonts/Lato-Black.ttf", 0, "lato_black"),
    ("/fonts/Anton-Regular.ttf", 0, "anton"), ("/fonts/RobotoSlab-Bold.ttf", 0, "roboto_slab_bold"),
    ("/fonts/NunitoSans-ExtraBold.ttf", 0, "nunito_sans_extrabold"), ("/fonts/DMSans-Bold.ttf", 0, "dm_sans_bold"),
    ("/fonts/PlusJakartaSans-Bold.ttf", 0, "plus_jakarta_bold"),
]

def patch_fonts():
    import sreda100 as gen
    available = []
    # Priority 1: Container paths (/fonts)
    # Priority 2: Local paths (./fonts)
    for p, i, l in LINUX_FONTS:
        if os.path.exists(p):
            available.append((p, i, l))
        else:
            local_p = p.lstrip("/")
            if os.path.exists(local_p):
                available.append((local_p, i, l))
    gen.AVAILABLE_FONTS = available

# ---------------------------------------------------------------------------
# Parallel Worker for Frame Rendering
# ---------------------------------------------------------------------------

@app.function()
def render_frame_worker(tile, t1, eff_seed, e1, ca, width, height, background_mode, color_a):
    import sreda100 as gen
    import io
    img = gen.render_video_frame(tile, t1, eff_seed, e1, ca, width, height, background_mode, color_a)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Core Generation Logic
# ---------------------------------------------------------------------------

PROJECT_START_DATE = date(2026, 3, 19)

def get_day_number():
    delta = date.today() - PROJECT_START_DATE
    return delta.days + 1

def generate_video_parallel(day: str, seed: int, background_mode: str = "none", palette_mode: str = "color"):
    import sreda100 as gen
    import math
    import subprocess
    import shutil
    
    patch_fonts()
    rng = random.Random(seed)
    
    # 1. Setup Base Style
    f_path, f_idx, f_lbl = rng.choice(gen.AVAILABLE_FONTS)
    fs = gen.fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), gen.WIDTH)
    fs_render = fs * 2
    
    if palette_mode == "mono":
        color_a, color_b = (255, 255, 255), (255, 255, 255)
    else:
        n_pal = len(gen.PALETTE_WHEEL); b_idx = rng.randint(0, n_pal-1); n_idx = (b_idx + rng.choice([-2,-1,1,2])) % n_pal
        color_a, color_b = gen.PALETTE_WHEEL[b_idx][1], gen.PALETTE_WHEEL[n_idx][1]
        
    grad_img = gen.make_gradient_map(gen.WIDTH*2, gen.HEIGHT*2, color_a, color_b, rng.uniform(0, 360))
    tile = gen.make_word_tile_gradient(day.upper(), f_path, f_idx, fs_render, rng.randint(-10, 80), grad_img)
    
    # 2. Compute Parameters for all frames
    frame_params = []
    frames_left, state = 0, "HOLD"
    curr_e1, curr_t1, f_seed = rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(0.2, 0.4), seed
    curr_e2 = rng.choice([e for e in gen.PRIMARY_EFFECTS if e != curr_e1])
    
    for f in range(gen.TOTAL_FRAMES):
        if frames_left <= 0:
            if state == "HOLD": state, frames_left = "BURST", rng.randint(1, 4)
            else:
                state, frames_left = "HOLD", rng.randint(8, 25)
                curr_e1, curr_t1, f_seed = rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(0.25, 0.45), seed+f
        
        if state == "BURST":
            t1, e1, ca, eff_seed = rng.uniform(0.4, 0.8), rng.choice(gen.PRIMARY_EFFECTS), rng.uniform(30, 60), seed+f*10
        else:
            t1, e1, ca, eff_seed = curr_t1 + math.sin(f*0.5)*0.05, curr_e1, 8 + math.sin(f*0.2)*4, f_seed
        
        if palette_mode == "mono": ca = ca * 0.6
        frame_params.append((tile, t1, eff_seed, e1, ca, gen.WIDTH*2, gen.HEIGHT*2, background_mode, color_a))
        frames_left -= 1

    # 3. Parallel Map Rendering
    print(f"Launching {len(frame_params)} parallel renderers...")
    frame_data_list = list(render_frame_worker.map(*zip(*frame_params)))

    # 4. Assemble with FFmpeg
    tmp_dir = f"/tmp/frames_{seed}"; os.makedirs(tmp_dir, exist_ok=True)
    for i, data in enumerate(frame_data_list):
        with open(f"{tmp_dir}/frame_{i:04d}.png", "wb") as f:
            f.write(data)
            
    out_path = f"/tmp/video_{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(gen.FPS), "-i", f"{tmp_dir}/frame_%04d.png", 
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    with open(out_path, "rb") as f:
        video_bytes = f.read()
    
    shutil.rmtree(tmp_dir); os.remove(out_path)
    
    filename = f"video_{f_lbl}_{day}_{datetime.now().strftime('%Y%m%d')}_s{seed}.mp4"
    meta = {
        "font": f_lbl, "fs": fs, "video": True,
        "effect1": curr_e1, "effect2": curr_e2,
        "day_number": get_day_number(),
        "background_mode": background_mode, "palette_mode": palette_mode
    }
    return video_bytes, filename, meta

def upload_to_r2(data: bytes, filename: str) -> str:
    """Upload bytes to R2, return public URL."""
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = os.environ["R2_BUCKET_NAME"]
    
    if filename.endswith(".mp4"):
        ctype = "video/mp4"
    else:
        ctype = "image/png"
        
    s3.put_object(
        Bucket=bucket,
        Key=filename,
        Body=data,
        ContentType=ctype,
    )
    base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")
    return f"{base}/{filename}"

@app.function(secrets=[r2_secret], timeout=300)
@modal.fastapi_endpoint(method="POST")
def generate_endpoint(body: dict) -> dict:
    day = body.get("day", datetime.now().strftime("%A")).upper()
    seed = body.get("seed", random.randint(0, 2**32))
    is_video = body.get("video", False)
    bg_mode = body.get("background_mode", "none")
    pal_mode = body.get("palette_mode", "color")

    if is_video:
        data_bytes, filename, meta = generate_video_parallel(day, seed, bg_mode, pal_mode)
    else:
        import sreda100 as gen
        patch_fonts()
        captured = {}
        original_save = gen.Image.Image.save
        def fake_save(self, fp, fmt=None, **kwargs):
            buf = io.BytesIO(); original_save(self, buf, format="PNG"); captured["data"] = buf.getvalue()
        gen.Image.Image.save = fake_save
        try:
            out_path, meta = gen.generate_static(day, seed, bg_mode, pal_mode)
            filename = os.path.basename(out_path); data_bytes = captured["data"]
            meta["day_number"] = get_day_number()
            if "effect2" not in meta:
                rng = random.Random(seed)
                meta["effect2"] = rng.choice([e for e in gen.PRIMARY_EFFECTS if e != meta.get("effect1")])
        finally:
            gen.Image.Image.save = original_save

    url = upload_to_r2(data_bytes, filename)
    return {"url": url, "filename": filename, "day": day, "seed": seed, **meta}
