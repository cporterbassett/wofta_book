#!/usr/bin/env python3
"""
normalize_interline.py — scale a tune PNG so staff interline matches a target.

Measures staff-line spacing (interline) via horizontal projection autocorrelation,
then rescales with Lanczos so every image arrives at Audiveris at the same effective
interline regardless of its source DPI.

Replaces the fixed `-resize 150%` in batch_tune.sh with a per-image scale factor.

Usage:
    python3 normalize_interline.py input.png output.png [--target 18]
    python3 normalize_interline.py input.png --measure-only
    python3 normalize_interline.py *.png --measure-only   # survey mode
"""

import argparse
import sys
import numpy as np
import cv2


def measure_interline(img_gray: np.ndarray) -> float | None:
    """
    Estimate interline (px between adjacent staff lines) via direct staff-line
    detection on the horizontal projection profile.

    Staff lines are full-width horizontal strokes that register as rows with
    ≥35% dark pixels after Otsu binarization (noteheads/text rarely exceed 20%).
    Adjacent dark rows are merged into one cluster; the median of the small
    inter-cluster spacings is the interline.

    Returns interline in pixels, or None if detection fails.
    """
    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = (binary == 0).astype(np.float32)

    # Row projection: fraction of dark pixels per row
    row_profile = dark.mean(axis=1)

    # Threshold: rows above this fraction are "staff line" rows.
    # Try progressively lower thresholds if not enough lines found.
    for threshold in (0.35, 0.20, 0.10):
        is_staff = row_profile > threshold

        # Group adjacent staff rows into single clusters; record center of each
        centers: list[float] = []
        in_line = False
        line_start = 0
        for i, v in enumerate(is_staff):
            if v and not in_line:
                in_line = True
                line_start = i
            elif not v and in_line:
                in_line = False
                centers.append((line_start + i - 1) / 2.0)
        if in_line:
            centers.append((line_start + len(is_staff) - 1) / 2.0)

        if len(centers) >= 5:
            break
    else:
        return None

    spacings = np.diff(np.array(centers))

    # Filter noise gaps (< 6 px): thick staff lines can split into two adjacent
    # clusters leaving a 3–5.5 px gap; the smallest real WOFTA interlines are
    # ~6 px (very small 531 px-wide score images).
    spacings = spacings[spacings >= 6.0]
    if len(spacings) == 0:
        return None

    # Interline = small spacings (intra-staff).
    # Inter-staff gaps are >> interline; cut at 2.5× the minimum spacing.
    min_sp = spacings.min()
    intra = spacings[spacings <= min_sp * 2.5]

    if len(intra) < 4:  # need at least one full staff worth of gaps
        return None

    measured = float(np.median(intra))

    # Plausibility guard: WOFTA original images have interline 5–25 px.
    # Outside that range the detection is unreliable (dense notation or faint
    # lines prevented individual-line resolution) — signal failure so callers
    # can fall back to a fixed scale.
    if not (5.0 <= measured <= 25.0):
        return None

    return measured


def apply_unsharp(img: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Unsharp mask matching ImageMagick `-unsharp 0x1` (sigma=1, amount=1)."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 2.0, blurred, -1.0, 0)


def normalize(input_path: str, output_path: str, target: float) -> tuple[float, float]:
    """
    Measure interline, compute scale factor, write rescaled PNG.
    Returns (measured_interline, scale_factor).
    """
    img_gray = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        raise FileNotFoundError(f"Cannot read: {input_path}")

    interline = measure_interline(img_gray)
    if interline is None:
        raise RuntimeError(f"Staff detection failed: {input_path}")

    scale = target / interline

    img_color = cv2.imread(input_path)
    sharpened = apply_unsharp(img_color)
    h, w = img_color.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(sharpened, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(output_path, resized)

    return interline, scale


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize tune PNG to target staff interline for Audiveris"
    )
    parser.add_argument("input", nargs="+", help="Input PNG path(s)")
    parser.add_argument(
        "--output", "-o", help="Output PNG path (single-file mode; required without --measure-only)"
    )
    parser.add_argument(
        "--target", type=float, default=18.0,
        help="Target interline in pixels (default: 18)",
    )
    parser.add_argument(
        "--measure-only", action="store_true",
        help="Print measured interline and exit without writing output",
    )
    args = parser.parse_args()

    if args.measure_only:
        for path in args.input:
            img_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img_gray is None:
                print(f"ERROR  {path}: cannot read", file=sys.stderr)
                continue
            interline = measure_interline(img_gray)
            if interline is None:
                print(f"FAIL   {path}: staff detection failed")
            else:
                scale = args.target / interline
                h, w = img_gray.shape
                print(
                    f"{interline:5.1f}px  ×{scale:.3f} ({scale*100:.0f}%)  "
                    f"{w}×{h}  {path}"
                )
        return

    # Single-file mode
    if len(args.input) != 1 or not args.output:
        parser.error("Provide exactly one input and --output path (or use --measure-only)")

    input_path = args.input[0]
    try:
        interline, scale = normalize(input_path, args.output, args.target)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    print(
        f"interline={interline:.1f}px  scale={scale:.3f} ({scale*100:.0f}%)  "
        f"{w}×{h} → {new_w}×{new_h}  → {args.output}"
    )


if __name__ == "__main__":
    main()
