# SREDA100 — Infrastructure Setup

## Repo structure

```
sreda100_v20.py        ← generation logic (edit freely)
modal_app.py           ← infrastructure: endpoint + R2 upload (edit rarely)
requirements.txt
fonts/                 ← TTF copies of macOS fonts (copy once, never touch)
  Helvetica-Bold.ttf
  HelveticaNeue-Bold.ttf
  HelveticaNeue-CondBold.ttf
  HelveticaNeue-Black.ttf
  Futura-Bold.ttf
  Futura-CondExtraBold.ttf
  Didot-Bold.ttf
  GillSans-Bold.ttf
  GillSans-UltraBold.ttf
  Impact.ttf
  Rockwell-Bold.ttf
.github/
  workflows/
    deploy.yml         ← auto-deploy on push to main
```

---

## One-time setup

### 1. Copy fonts from Mac

Fonts live in `/System/Library/Fonts/` and `/System/Library/Fonts/Supplemental/`.
TTC files contain multiple fonts — extract the bold variant as TTF:

```bash
# Install fonttools
pip install fonttools

# Extract bold variant from TTC (index numbers match sreda100_v20.py)
python3 - <<'EOF'
from fontTools.ttLib import TTCollection
import os

extractions = [
    ("/System/Library/Fonts/Helvetica.ttc",                    1, "fonts/Helvetica-Bold.ttf"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                1, "fonts/HelveticaNeue-Bold.ttf"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                4, "fonts/HelveticaNeue-CondBold.ttf"),
    ("/System/Library/Fonts/HelveticaNeue.ttc",                9, "fonts/HelveticaNeue-Black.ttf"),
    ("/System/Library/Fonts/Supplemental/Futura.ttc",          2, "fonts/Futura-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Futura.ttc",          4, "fonts/Futura-CondExtraBold.ttf"),
    ("/System/Library/Fonts/Supplemental/Didot.ttc",           2, "fonts/Didot-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/GillSans.ttc",        1, "fonts/GillSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/GillSans.ttc",        6, "fonts/GillSans-UltraBold.ttf"),
]

os.makedirs("fonts", exist_ok=True)
for src, idx, dst in extractions:
    ttc = TTCollection(src)
    ttc.fonts[idx].save(dst)
    print(f"✅ {dst}")
EOF

# Impact and Rockwell are plain TTF — just copy
cp /System/Library/Fonts/Supplemental/Impact.ttf fonts/Impact.ttf
cp /System/Library/Fonts/Supplemental/Rockwell.ttc fonts/Rockwell-Bold.ttf
```

Commit the `fonts/` folder. You only need to do this once (or when adding new fonts).

---

### 2. Cloudflare R2

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → R2
2. Create a bucket, e.g. `sreda100`
3. Enable **Public Access** on the bucket → note the `pub-xxx.r2.dev` URL
4. Create an **API Token** with R2 read+write permissions
5. Note: Account ID, Access Key ID, Secret Access Key, bucket name, public URL

---

### 3. Modal secrets

```bash
pip install modal
modal token new   # opens browser, saves token locally

# Create secret with R2 credentials
modal secret create sreda100-r2 \
  R2_ENDPOINT_URL="https://<account_id>.r2.cloudflarestorage.com" \
  R2_ACCESS_KEY_ID="<key_id>" \
  R2_SECRET_ACCESS_KEY="<secret>" \
  R2_BUCKET_NAME="sreda100" \
  R2_PUBLIC_BASE_URL="https://pub-<hash>.r2.dev"
```

---

### 4. First deploy

```bash
modal deploy modal_app.py
```

Modal prints the endpoint URL:
```
✓ Created web endpoint https://vadimkasse--sreda100-generate-endpoint.modal.run
```

Save this URL — you'll paste it into Make.

---

### 5. GitHub Actions (auto-deploy on push)

In your GitHub repo → Settings → Secrets and variables → Actions, add:

| Secret | Value |
|--------|-------|
| `MODAL_TOKEN_ID` | from `~/.modal.toml` on your Mac |
| `MODAL_TOKEN_SECRET` | from `~/.modal.toml` on your Mac |

After this, every `git push` to `main` redeploys automatically.

---

### 6. Make scenario

```
[Schedule: every day at 10:00]
  │
  ├─ [HTTP: POST https://...modal.run/generate]
  │    Body (JSON): { "day": "{{formatDate(now; "DDDD")}}" }
  │    Response mapping: url, filename, day, seed
  │
  ├─ [Instagram for Business: Create a Photo Post]
  │    Photo URL: {{url}}
  │    Caption: {{day}}
  │
  ├─ [LinkedIn: Create a Share]
  │    Content: {{day}}
  │    Media URL: {{url}}
  │
  └─ [Google Drive: Upload a File]
       File URL: {{url}}
       File name: {{filename}}
       Folder: /sreda100-archive/
```

**Notes:**
- Make's `formatDate(now; "DDDD")` returns the full day name in uppercase — matches what the script expects.
- Instagram requires the image to be publicly accessible via URL — R2 public bucket handles this.
- LinkedIn media upload requires the URL to be reachable without auth — same.
- Google Drive module in Make: use **Upload a File** → set source to URL → paste `{{url}}`.

---

## Updating the generation script

Just edit `sreda100_v20.py` and push to `main`.
GitHub Actions redeploys `modal_app.py` which re-bundles the updated script.
Make and the endpoint URL are unaffected.

## Migrating to video

When you switch to video generation:
1. Update `sreda100_v20.py` to produce an MP4/MOV instead of PNG
2. Update `modal_app.py`: change `ContentType` to `video/mp4`, adjust filename
3. In Make: swap Instagram Photo Post → Instagram Reel, update media field
4. Everything else (URL flow, Drive archive) stays identical

## Modal endpoint URL

https://kassevadim--sreda100-generate-endpoint.modal.run
