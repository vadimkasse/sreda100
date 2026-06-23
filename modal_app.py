"""
modal_app.py — SREDA100 infrastructure layer (v22.0 Organic Aggression)
Upgraded to support 6 new styles, CA flag, color inversion, and edge fixes.
"""

import io
import os
import random
from datetime import date, datetime
import math
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
    for p, i, l in LINUX_FONTS:
        if os.path.exists(p): available.append((p, i, l))
        else:
            local_p = p.lstrip("/")
            if os.path.exists(local_p): available.append((local_p, i, l))
    gen.AVAILABLE_FONTS = available

# ---------------------------------------------------------------------------
# Parallel Worker for Frame Rendering
# ---------------------------------------------------------------------------

@app.function()
def render_frame_worker(grid_bytes, pad, dx, dy, ca, width, height, color_a, ca_seed, style, apply_ca):
    import sreda100 as gen
    import io
    from PIL import Image
    
    grid = Image.open(io.BytesIO(grid_bytes))
    img = gen.render_frame_composite(grid, pad, dx, dy, ca, width, height, color_a, ca_seed, style, apply_ca)
    
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

@app.function(timeout=600)
def generate_video_parallel(day: str, seed: int, style: str = "feedback", invert: bool = False, apply_ca: bool = True):
    import sreda100 as gen
    import math
    import subprocess
    import shutil
    import io
    import numpy as np
    
    patch_fonts()
    rng = random.Random(seed)
    if style == "random": style = rng.choice(gen.STYLES)
    
    f_path, f_idx, f_lbl = rng.choice(gen.AVAILABLE_FONTS)
    fs = gen.fit_font_to_width(day.upper(), f_path, f_idx, rng.uniform(0.65, 0.95), gen.WIDTH)
    fs_render = fs * 2
    color_a = (255, 255, 255)
    
    grid, pad = gen.build_scene_layer(style, day, f_path, f_idx, fs_render, seed, color_a)
    buf = io.BytesIO()
    grid.save(buf, format="PNG")
    grid_bytes = buf.getvalue()
    
    def get_aggressive_anchor():
        mode = rng.choice(gen.PRIMARY_EFFECTS)
        s, t = rng.randint(0, 2**32), rng.uniform(0.65, 0.95)
        return gen.displacement(t, s, mode, gen.WIDTH*2, gen.HEIGHT*2)

    dx_start, dy_start = get_aggressive_anchor()
    dx_end, dy_end = get_aggressive_anchor()
    trans_duration = gen.FPS * 1.2
    frames_in_trans = 0
    
    frame_params = []
    for f in range(gen.TOTAL_FRAMES):
        alpha = frames_in_trans / trans_duration
        alpha_ease = 0.5 - 0.5 * math.cos(alpha * math.pi)
        
        dx = dx_start * (1 - alpha_ease) + dx_end * alpha_ease
        dy = dy_start * (1 - alpha_ease) + dy_end * alpha_ease
        drift_amp = 30; dx += drift_amp * math.sin(f * 0.3 + seed); dy += drift_amp * math.cos(f * 0.4 + seed*1.1)
        ca = (20 * (1 - alpha_ease) + 40 * alpha_ease) * 0.7
        
        frame_params.append((grid_bytes, pad, dx, dy, ca, gen.WIDTH*2, gen.HEIGHT*2, color_a, seed, style, apply_ca))
        
        frames_in_trans += 1
        if frames_in_trans >= trans_duration:
            dx_start, dy_start = dx_end, dy_end
            dx_end, dy_end = get_aggressive_anchor()
            frames_in_trans = 0

    print(f"Launching {len(frame_params)} parallel renderers for {style}...")
    frame_data_list = list(render_frame_worker.map(*zip(*frame_params)))

    tmp_dir = f"/tmp/frames_{seed}"; os.makedirs(tmp_dir, exist_ok=True)
    
    feedback_state = None
    for i, data in enumerate(frame_data_list):
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        
        if style == "ink_bleed":
            img = gen.apply_ink_bleed(img)
        elif style == "feedback":
            arr = np.array(img).astype(np.float32)
            if feedback_state is None: 
                feedback_state = arr
            else:
                shift_y = 15; shift_x = 0
                shifted = np.roll(feedback_state, shift_y, axis=0)
                feedback_state = np.maximum(arr, shifted * 0.85)
            img = Image.fromarray(np.clip(feedback_state, 0, 255).astype(np.uint8), "RGB")
            
        with open(f"{tmp_dir}/frame_{i:04d}.png", "wb") as f:
            img.save(f, format="PNG")
            
    out_path = f"/tmp/video_{seed}.mp4"
    
    ffmpeg_cmd = ["ffmpeg", "-y", "-framerate", str(gen.FPS), "-i", f"{tmp_dir}/frame_%04d.png"]
    if invert:
        ffmpeg_cmd.extend(["-vf", "negate"])
    ffmpeg_cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path])
    
    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    with open(out_path, "rb") as f:
        video_bytes = f.read()
    
    shutil.rmtree(tmp_dir); os.remove(out_path)
    
    color_label = "wb" if invert else "bw"
    filename = f"video_{style}_{color_label}_{f_lbl}_{day}_{datetime.now().strftime('%Y%m%d')}_s{seed}.mp4"
    meta = {
        "font": f_lbl, "fs": fs, "video": True,
        "day_number": get_day_number(),
        "style": style, "invert": invert, "ca": apply_ca
    }
    return video_bytes, filename, meta

def upload_to_r2(data: bytes, filename: str) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = os.environ["R2_BUCKET_NAME"]
    ctype = "video/mp4" if filename.endswith(".mp4") else "image/png"
    s3.put_object(Bucket=bucket, Key=filename, Body=data, ContentType=ctype)
    base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")
    return f"{base}/{filename}"

@app.function(secrets=[r2_secret], timeout=600)
@modal.fastapi_endpoint(method="POST")
def generate_endpoint(body: dict) -> dict:
    day = body.get("day", datetime.now().strftime("%A")).strip().upper()
    seed = body.get("seed", random.randint(0, 2**32))
    is_video = body.get("video", False)
    style = body.get("style", "feedback")
    apply_ca = body.get("ca", True)
    
    color = body.get("color", "bw")
    if color == "random":
        invert = random.choice([True, False])
    elif color == "wb":
        invert = True
    else:
        invert = False

    if is_video:
        data_bytes, filename, meta = generate_video_parallel.local(day, seed, style, invert, apply_ca)
    else:
        import sreda100 as gen
        patch_fonts()
        captured = {}
        original_save = gen.Image.Image.save
        def fake_save(self, fp, fmt=None, **kwargs):
            buf = io.BytesIO(); original_save(self, buf, format="PNG"); captured["data"] = buf.getvalue()
        gen.Image.Image.save = fake_save
        try:
            out_path = gen.generate_static(day, seed, style, invert, apply_ca)
            filename = os.path.basename(out_path); data_bytes = captured["data"]
            meta = {
                "font": "unknown", "fs": 0, "video": False,
                "day_number": get_day_number(),
                "style": style, "invert": invert, "ca": apply_ca
            }
        finally:
            gen.Image.Image.save = original_save

    url = upload_to_r2(data_bytes, filename)
    return {"url": url, "filename": filename, "day": day, "seed": seed, **meta}

@app.local_entrypoint()
def test_endpoint(day: str = None):
    if day is None: day = datetime.now().strftime("%A").upper()
    else: day = day.strip().upper()
    print(f"Test 1/1: feedback style for {day}")
    data, fname, meta = generate_video_parallel.local(day, 12345, "feedback", False, True)
    assert data, "no bytes returned"
    print(f"  ✓ {fname}, {len(data)} bytes, meta={meta}")
