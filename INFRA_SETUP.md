# SREDA100 — Infrastructure Setup

## Repo structure

```
sreda100_v20.py        ← generation logic (edit freely)
modal_app.py           ← infrastructure: endpoint + R2 upload (edit rarely)
requirements.txt
fonts/                 ← TTF files (open license, committed to repo)
  Inter-Bold.ttf
  Inter-Black.ttf
  Outfit-Bold.ttf
  BarlowCondensed-Bold.ttf
  BarlowCondensed-ExtraBold.ttf
  PlayfairDisplay-Bold.ttf
  Lato-Bold.ttf
  Lato-Black.ttf
  Anton-Regular.ttf
  RobotoSlab-Bold.ttf
  NunitoSans-ExtraBold.ttf
  DMSans-Bold.ttf
  PlusJakartaSans-Bold.ttf
.github/
  workflows/
    deploy.yml         ← auto-deploy on push to main
```

---

## One-time setup

### 1. Fonts

All fonts are open license (Google Fonts). Download TTF files and place them in `fonts/`.
Commit the `fonts/` folder — it's included in the Modal container at build time.

> Note: macOS system fonts (Helvetica, Futura, etc.) cannot be used in the cloud container due to licensing.
> Current set uses Google Fonts equivalents. Font quality improvements are planned.

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
pip install modal boto3
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
✓ Created web endpoint https://kassevadim--sreda100-generate-endpoint.modal.run
```

Save this URL — paste it into Make.

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
[Schedule: every day at N:00]
  │
  ├─ [HTTP: POST https://kassevadim--sreda100-generate-endpoint.modal.run]
  │    Body (JSON string): {"day": "{{formatDate(now; "dddd")}}"}
  │    Parse response: true
  │    Response fields: url, filename, day, seed, day_number,
  │                     effect1, effect2, intensity1, intensity2, font, gradient
  │
  ├─ [Instagram for Business: Create a Photo Post]
  │    Photo URL: {{url}}
  │    Caption: (see caption template below)
  │
  └─ [Google Drive: Upload a File]
       Data: {{url}}
       File name: {{filename}}
       Folder: /sreda100-archive/
```

**Caption template:**
```
Day {{day_number}}/100 — {{font}} · {{effect1}} {{intensity1}} / {{effect2}} {{intensity2}}

SREDA100 — generative typography project. One artifact per day, fully automated.

Pipeline: Python script renders a unique typographic artwork → Cloudflare R2 → Modal endpoint → Make schedules and posts. No manual steps, no design decisions at runtime. The system decides.

#sreda100 #generativeart #typography #automation #python #creativecoding
```

**Notes:**
- `formatDate(now; "dddd")` returns full day name (e.g. `thursday`) — script does `.upper()` internally
- `day_number` is calculated server-side from project start date (2026-03-19)
- LinkedIn is not in the auto-posting flow — post manually for announcements and milestones
- R2 public bucket makes the image URL accessible without auth — required by Instagram and Drive

---

## API response reference

`POST /generate` → returns:

| Field | Example | Description |
|-------|---------|-------------|
| `url` | `https://pub-xxx.r2.dev/shatter52_...png` | Public image URL |
| `filename` | `shatter52_twist22_...png` | Full filename with all params |
| `day` | `THURSDAY` | Day of week, uppercase |
| `seed` | `890859871` | Seed for reproducibility |
| `day_number` | `2` | Day in the 100-day series |
| `effect1` | `shatter` | Primary displacement effect |
| `effect2` | `chaos` | Secondary displacement effect |
| `intensity1` | `64` | Primary effect intensity (0–100) |
| `intensity2` | `12` | Secondary effect intensity (0–100) |
| `font` | `inter_bold` | Font label |
| `gradient` | `violet-ice` | Gradient color pair |

---

## Updating the generation script

Edit `sreda100_v20.py` and push to `main`.
GitHub Actions redeploys `modal_app.py` which re-bundles the updated script.
Make and the endpoint URL are unaffected.

---

## Migrating to video

When switching to video generation:
1. Update `sreda100_v20.py` to produce MP4 instead of PNG
2. Update `modal_app.py`: change `ContentType` to `video/mp4`, adjust filename extension
3. In Make: swap Instagram Photo Post → Instagram Reel
4. Everything else (URL flow, Drive archive, caption) stays identical

---

## Adding Bluesky

1. In Make: add **Bluesky** module after Instagram
2. Connect Bluesky account
3. Post text + image URL
4. No API cost — Bluesky API is free
