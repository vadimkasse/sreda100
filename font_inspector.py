#!/usr/bin/env python3
"""
Run this on your Mac to find bold font indices.
Output will show exactly which index = Bold for each font.
"""
from PIL import ImageFont
import os

FONTS_TO_CHECK = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/Supplemental/Didot.ttc",
    "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "/System/Library/Fonts/Supplemental/GillSans.ttc",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Optima.ttc",
    "/System/Library/Fonts/Supplemental/Palatino.ttc",
    "/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc",
    "/System/Library/Fonts/Supplemental/Rockwell.ttc",
]

print("\n=== FONT INDEX INSPECTOR ===\n")
for path in FONTS_TO_CHECK:
    if not os.path.exists(path):
        print(f"MISSING: {path}\n")
        continue
    print(f"{'─'*50}")
    print(f"  {os.path.basename(path)}")
    for i in range(12):
        try:
            f = ImageFont.truetype(path, 40, index=i)
            name = f.getname()
            bold_marker = " ← BOLD" if any(
                b in name[1].lower() for b in ["bold", "heavy", "black", "extrabold", "semibold"]
            ) else ""
            print(f"  index={i}  {name[0]} / {name[1]}{bold_marker}")
        except Exception:
            break
    print()
