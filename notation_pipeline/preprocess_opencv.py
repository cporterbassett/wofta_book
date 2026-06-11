#!/usr/bin/env python3
"""
Generate preprocessing variants using OpenCV for Audiveris OMR testing.
Saves images to preprocessing_tests/images/NN-name.png.
"""

import cv2
import numpy as np
from pathlib import Path

SRC = "/home/porter/Documents/banjo/WOFTA/tune_images/Angeline the Baker.png"
OUT = Path("preprocessing_tests/images")
OUT.mkdir(parents=True, exist_ok=True)

img = cv2.imread(SRC, cv2.IMREAD_GRAYSCALE)
h, w = img.shape
print(f"Source: {w}x{h}")


def save(name, arr):
    path = OUT / f"{name}.png"
    cv2.imwrite(str(path), arr)
    print(f"  Wrote {name}.png  ({arr.shape[1]}x{arr.shape[0]})")


def upscale(arr, factor=2):
    return cv2.resize(arr, (arr.shape[1]*factor, arr.shape[0]*factor),
                      interpolation=cv2.INTER_LANCZOS4)


def upscale_bicubic(arr, factor=2):
    return cv2.resize(arr, (arr.shape[1]*factor, arr.shape[0]*factor),
                      interpolation=cv2.INTER_CUBIC)


# ── Adaptive threshold variants ───────────────────────────────────────────────
# ADAPTIVE_THRESH_GAUSSIAN_C handles uneven lighting better than global thresh.

for block, C in [(11, 3), (15, 5), (21, 8), (31, 10)]:
    adapted = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block, C)
    save(f"24-adaptive-b{block}c{C}-up2x", upscale(adapted))

# ── Bilateral filter (edge-preserving denoise) ────────────────────────────────

for d, sc, ss in [(5, 25, 25), (7, 40, 40), (9, 75, 75)]:
    filtered = cv2.bilateralFilter(img, d, sc, ss)
    save(f"25-bilateral-d{d}s{sc}-up2x", upscale(filtered))

# ── Staff line reinforcement via horizontal morphology ────────────────────────
# Close horizontal gaps to reinforce staff lines, then upscale.

for kw in [20, 40, 60]:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 1))
    # Extract horizontal structures
    horizontal = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
    # Reinforce: wherever horizontal lines are, darken them in original
    reinforced = np.minimum(img.astype(np.int16), 255 - horizontal.astype(np.int16) // 2)
    reinforced = np.clip(reinforced, 0, 255).astype(np.uint8)
    save(f"26-staffreinforce-k{kw}-up2x", upscale(reinforced))

# ── Bilateral + adaptive threshold ────────────────────────────────────────────

filtered = cv2.bilateralFilter(img, 7, 40, 40)
adapted = cv2.adaptiveThreshold(
    filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY, 15, 5)
save("27-bilateral-adaptive-up2x", upscale(adapted))

# ── CLAHE (contrast limited adaptive histogram equalization) ──────────────────
# Improves local contrast; good for faded or unevenly-lit scans.

clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
cl = clahe.apply(img)
save("28-clahe-up2x", upscale(cl))

clahe2 = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
cl2 = clahe2.apply(img)
save("29-clahe-tight-up2x", upscale(cl2))

# CLAHE + adaptive threshold
adapted_cl = cv2.adaptiveThreshold(
    cl, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY, 15, 5)
save("30-clahe-adaptive-up2x", upscale(adapted_cl))

# ── Bicubic vs Lanczos (same unsharp, different interpolation) ────────────────
# The winning variant used Lanczos; bicubic is softer but fewer ringing artifacts.

unsharp = cv2.addWeighted(img, 1.5, cv2.GaussianBlur(img, (0,0), 1), -0.5, 0)
save("31-unsharp-up2x-bicubic", upscale_bicubic(unsharp))

# ── Morphological notehead cleanup ───────────────────────────────────────────
# Small closing to fill notehead gaps, then upscale.

kernel_nh = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
closed = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel_nh)
save("32-morph-close-up2x", upscale(closed))

print(f"\nDone.")
