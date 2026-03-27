# SREDA100

A 100-day generative typography project. Each day produces a unique visual artifact based on a single word — the day of the week — processed through a parametric displacement pipeline. Fully automated: generation, upload, and posting require zero manual steps.

## Concept

The word is not placed on a canvas. It becomes the canvas.

A grid of the word is tiled across the full frame, then deformed through one or two displacement passes — earthquake, gravity, chaos, shatter — freezing the process at a specific moment in time. The result changes every run: different font, different size, different effect combination, different intensity.

No manual composition. No design decisions at runtime. The system decides.

## How it works

```
word → bold font (random) → tiled grid → displacement pass 1 → displacement pass 2 (subtle) → PNG → R2 → Instagram + Bluesky
```

**Variables per render:**
- Font: 13 bold/heavy typefaces (Google Fonts, open license)
- Size: fits 20–95% of canvas width, minimum 90px
- Letter spacing: −10 to +80px
- Gradient: two adjacent colors from an 11-color palette wheel, random angle
- Halo: chromatic fringe effect, random color + direction
- Effect 1: `earthquake` / `gravity` / `chaos` / `shatter` / `noise_flow`
- Effect 2: subtle secondary deformation (t = 0.10–0.25)
- Seed: reproducible via `--seed`

**Displacement effects:**
- `earthquake` — horizontal band shifts, like tectonic layers
- `gravity` — pull toward a random horizon line
- `chaos` — layered sine fields, bimodal intensity (low or high, never mid)
- `shatter` — Voronoi-based fragment displacement
- `noise_flow` — smooth vector field, liquid motion

## Output

`1080 × 1920px` PNG, filename encodes all parameters:
```
shatter52_twist22_violet-ice_halopink3_outfit_bold_fs125_ls-10_THURSDAY_20260319_s890859871.png
```

## Usage

```bash
pip install Pillow numpy

# Generate 20 variants for today
python sreda100_v20.py

# Specific day, batch of 40
python sreda100_v20.py --day TUESDAY --batch 40

# Reproducible result
python sreda100_v20.py --day MONDAY --seed 3846787293
```

## Automation pipeline

```
[Make: Schedule daily]
    → [HTTP POST → Modal endpoint]
        → generates PNG
        → uploads to Cloudflare R2
        → returns url, filename, day, seed, day_number, effect1, effect2, intensity1, intensity2, font, gradient
    → [Instagram for Business: Create a Photo Post]
    → [Google Drive: Upload a File → /sreda100-archive/]
    → [HTTP → Bluesky Auth → Download PNG → Bluesky Upload → Bluesky Post]
```

Caption is generated dynamically:
```
Day N/100 — font · effect1 intensity / effect2 intensity
```

Note: Bluesky posting uses direct AT Protocol API calls via HTTP modules (Make's native Bluesky module does not correctly handle blob refs).

LinkedIn: manual posts only (project announcements, milestones).

## Development history

| Version | Key change |
|---------|-----------|
| v7 | Grid tiling + displacement map architecture |
| v8 | Letter spacing variable, 8 effects |
| v9 | New effects: vortex, fold, earthquake, noise_flow, ripple |
| v10 | Effect curating, effect+intensity in filename |
| v11 | Two-pass displacement system |
| v12 | Secondary pass weakened 3×, drift removed |
| v13 | Correct bold ttc indices, font size capped at 200px |
| v14 | Earthquake + gravity primary only, font inspector tool |
| v15 | Bimodal chaos, twist removed, min font size 90px |
| v17 | Gradient applied to word tile |
| v19 | Monochrome halo split as final color pass |
| v20 | Full pipeline: gradient + two-pass displacement + halo |

## Stack

- Python 3.x
- Pillow — image rendering and composition
- NumPy — displacement field computation
- Google Fonts (open license TTF) — 13 bold/heavy typefaces
- Modal — serverless endpoint
- Cloudflare R2 — image storage and public CDN
- Make — scheduling and social posting

## Roadmap

- Font quality: replace current set with higher-quality alternatives (current fonts render with minor artifacts)
- Video: migrate from PNG to MP4, switch Instagram Photo → Reel

## Project status

Active. Started 19 March 2026. Daily posts on [Instagram](https://www.instagram.com/vadimkassepro/) and [Bluesky](https://bsky.app/profile/vadimkasse.bsky.social).
