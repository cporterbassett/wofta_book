#!/usr/bin/env python3
"""
Produce a red/blue overlay diff between an original scan and a clean ABC render.

The render is scaled to match the original's dimensions, then blended:
  - original → red channel
  - render   → blue channel
  - matching ink → both channels fire → appears dark purple/black
  - extra ink in original only → red
  - extra ink in render only → blue

Usage:
    python overlay_diff.py <original.png> <render.png> [diff.png]

diff.png defaults to <stem>.diff.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np


def load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot load: {path}")
    return img


def binarise(gray: np.ndarray, block: int = 31, c: int = 10) -> np.ndarray:
    """Adaptive threshold → ink=0 (black), paper=255 (white)."""
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block, c,
    )


def align_to(src: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Scale src to exactly (target_h, target_w)."""
    return cv2.resize(src, (target_w, target_h), interpolation=cv2.INTER_AREA)


def make_diff(orig_path: Path, render_path: Path, out_path: Path) -> None:
    orig_gray = load_gray(orig_path)
    render_gray = load_gray(render_path)

    h, w = orig_gray.shape

    # Scale render to match original dimensions
    render_scaled = align_to(render_gray, h, w)

    # Binarise both (ink = 0)
    orig_bin = binarise(orig_gray)
    render_bin = binarise(render_scaled)

    # Invert so ink=255, paper=0 — easier arithmetic
    orig_ink = cv2.bitwise_not(orig_bin)
    render_ink = cv2.bitwise_not(render_bin)

    # Build RGB overlay
    # White background
    out = np.full((h, w, 3), 255, dtype=np.uint8)

    # Where original has ink → subtract from red (red background → dark red)
    # Where render has ink → subtract from blue
    # Overlap → subtract from both → dark/black

    # Red channel: 255 where no original ink, 0 where original ink
    r = np.clip(255 - orig_ink.astype(np.int16), 0, 255).astype(np.uint8)
    # Green channel: dark where either has ink (makes overlap look dark)
    g = np.clip(255 - np.maximum(orig_ink, render_ink).astype(np.int16), 0, 255).astype(np.uint8)
    # Blue channel: 255 where no render ink, 0 where render ink
    b = np.clip(255 - render_ink.astype(np.int16), 0, 255).astype(np.uint8)

    out[:, :, 0] = r  # B in BGR
    out[:, :, 1] = g
    out[:, :, 2] = b  # R in BGR  — wait, OpenCV is BGR

    # OpenCV stores BGR
    bgr = np.zeros((h, w, 3), dtype=np.uint8)
    bgr[:, :, 2] = r   # R
    bgr[:, :, 1] = g   # G
    bgr[:, :, 0] = b   # B

    cv2.imwrite(str(out_path), bgr)
    print(f"Diff written: {out_path}  ({w}×{h}px)")


def main():
    if len(sys.argv) < 3:
        print("Usage: overlay_diff.py <original.png> <render.png> [diff.png]", file=sys.stderr)
        sys.exit(1)

    orig = Path(sys.argv[1])
    render = Path(sys.argv[2])
    stem = orig.stem
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else orig.with_name(f"{stem}.diff.png")

    make_diff(orig, render, out)


if __name__ == "__main__":
    main()
