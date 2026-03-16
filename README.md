# SREDA100

A 100-day generative typography project. Each day produces a unique visual artifact based on a single word — the day of the week — processed through a parametric displacement pipeline.

## Concept

The word is not placed on a canvas. It becomes the canvas.

A grid of the word is tiled across the full frame, then deformed through one or two displacement passes — earthquake, gravity, chaos, shatter — freezing the process at a specific moment in time. The result changes every run: different font, different size, different effect combination, different intensity.

No manual composition. No design decisions at runtime. The system decides.

## How it works

```
word → bold font (random) → tiled grid → displacement pass 1 → displacement pass 2 (subtle) → PNG
```

**Variables per render:**
- Font: 11 bold/heavy typefaces (system fonts + custom)
- Size: fits 20–95% of canvas width, minimum 90px
- Letter spacing: −10 to +80px
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
earthquake57_shatter19_helvetica_neue_black_fs199_ls3_MONDAY_20260316_s3846787293.png
```

## Usage

```bash
pip install Pillow numpy

# Generate 20 variants for today
python sreda100_v15.py

# Specific day, batch of 40
python sreda100_v15.py --day TUESDAY --batch 40

# Reproducible result
python sreda100_v15.py --day MONDAY --seed 3846787293

# With chromatic aberration glitch pass
python sreda100_v15.py --day FRIDAY --batch 20 --glitch
```

## Development history

The visual system was built iteratively — each version refining effect parameters, font selection, and displacement logic based on output evaluation.

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

## Stack

- Python 3.x
- Pillow — image rendering and composition
- NumPy — displacement field computation
- macOS system fonts (TTC/TTF with explicit bold index)

## Tools

`font_inspector.py` — scans system font files, identifies bold variant indices for TTС collections.

## Project status

Active. Daily posts on [Instagram](https://instagram.com) and [LinkedIn](https://linkedin.com/in/vadimkasse).
