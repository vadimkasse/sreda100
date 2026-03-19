"""
modal_app.py — SREDA100 infrastructure layer

What this does:
  - Exposes generate() from sreda100_v20.py as an HTTP endpoint
  - Uploads result to Cloudflare R2
  - Returns JSON: { url, filename, day, seed }

Make calls POST /generate with { "day": "WEDNESDAY" }
and gets back a public URL to post to Instagram / LinkedIn / Drive.

Environment secrets (set in Modal dashboard):
  R2_ENDPOINT_URL   — https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME
  R2_PUBLIC_BASE_URL — https://pub-<hash>.r2.dev  (public bucket URL)
"""

import io
import os
import random
from datetime import datetime

import boto3
import modal

# ---------------------------------------------------------------------------
# Image — Python deps + fonts bundled into the container
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("Pillow", "numpy", "boto3", "fastapi[standard]")
    # Fonts folder is copied from your repo into the container at build time.
    # Put your .ttf / .ttc files in repo/fonts/ — see README for which ones.
    .add_local_dir("fonts", remote_path="/fonts")
    # The generation script lives next to this file in the repo.
    .add_local_file("sreda100_v20.py", remote_path="/app/sreda100_v20.py")
)

app = modal.App("sreda100", image=image)

# ---------------------------------------------------------------------------
# Secrets — pulled from Modal secret store, never hardcoded
# ---------------------------------------------------------------------------

r2_secret = modal.Secret.from_name("sreda100-r2")


# ---------------------------------------------------------------------------
# Patched font list for Linux container
# ---------------------------------------------------------------------------

LINUX_FONTS = [
    ("/fonts/Inter-Bold.ttf",                0, "inter_bold"),
    ("/fonts/Inter-Black.ttf",               0, "inter_black"),
    ("/fonts/Outfit-Bold.ttf",               0, "outfit_bold"),
    ("/fonts/BarlowCondensed-Bold.ttf",      0, "barlow_cond_bold"),
    ("/fonts/BarlowCondensed-ExtraBold.ttf", 0, "barlow_cond_extrabold"),
    ("/fonts/PlayfairDisplay-Bold.ttf",      0, "playfair_bold"),
    ("/fonts/Lato-Bold.ttf",                 0, "lato_bold"),
    ("/fonts/Lato-Black.ttf",                0, "lato_black"),
    ("/fonts/Anton-Regular.ttf",             0, "anton"),
    ("/fonts/RobotoSlab-Bold.ttf",           0, "roboto_slab_bold"),
    ("/fonts/NunitoSans-ExtraBold.ttf",      0, "nunito_sans_extrabold"),
    ("/fonts/DMSans-Bold.ttf",               0, "dm_sans_bold"),
    ("/fonts/PlusJakartaSans-Bold.ttf",      0, "plus_jakarta_bold"),
]


def patch_fonts():
    """Replace macOS font paths with Linux paths before calling generate()."""
    import sreda100_v20 as gen
    available = [(p, i, l) for p, i, l in LINUX_FONTS if os.path.exists(p)]
    if not available:
        raise RuntimeError(
            "No fonts found in /fonts. "
            "Copy .ttf files from your Mac into repo/fonts/ and redeploy."
        )
    gen.AVAILABLE_FONTS = available


def generate_to_bytes(day: str, seed: int | None = None) -> tuple[bytes, str]:
    """
    Run generation, return (png_bytes, filename) without touching disk.
    Patches font paths and hijacks the save call.
    """
    import sreda100_v20 as gen

    patch_fonts()

    # Monkey-patch Image.save so we capture bytes instead of writing a file.
    captured = {}
    original_save = gen.Image.Image.save

    def fake_save(self, fp, fmt=None, **kwargs):
        buf = io.BytesIO()
        original_save(self, buf, format="PNG")
        captured["data"] = buf.getvalue()

    gen.Image.Image.save = fake_save

    try:
        # generate() returns the would-be file path — we use it for the filename
        out_path = gen.generate(day, seed)
        filename = os.path.basename(out_path)
    finally:
        gen.Image.Image.save = original_save  # always restore

    if "data" not in captured:
        raise RuntimeError("Image was never saved — check generate() logic.")

    return captured["data"], filename


def upload_to_r2(data: bytes, filename: str) -> str:
    """Upload PNG bytes to R2, return public URL."""
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = os.environ["R2_BUCKET_NAME"]
    s3.put_object(
        Bucket=bucket,
        Key=filename,
        Body=data,
        ContentType="image/png",
    )
    base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")
    return f"{base}/{filename}"


# ---------------------------------------------------------------------------
# Modal web endpoint
# ---------------------------------------------------------------------------

@app.function(secrets=[r2_secret], timeout=120)
@modal.fastapi_endpoint(method="POST")
def generate_endpoint(body: dict) -> dict:
    """
    POST /generate
    Body: { "day": "WEDNESDAY", "seed": 12345 }  — seed is optional

    Returns:
    {
        "url": "https://pub-xxx.r2.dev/earthquake57_..._WEDNESDAY_20260318_s123.png",
        "filename": "earthquake57_..._WEDNESDAY_20260318_s123.png",
        "day": "WEDNESDAY",
        "seed": 12345
    }
    """
    day = body.get("day", datetime.now().strftime("%A")).upper()
    seed = body.get("seed", None)
    if seed is None:
        seed = random.randint(0, 2**32)

    png_bytes, filename = generate_to_bytes(day, seed)
    url = upload_to_r2(png_bytes, filename)

    return {
        "url": url,
        "filename": filename,
        "day": day,
        "seed": seed,
    }
