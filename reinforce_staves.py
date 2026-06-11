#!/usr/bin/env python3
"""Detect and redraw clean staff lines on sheet music images."""

import numpy as np
import cv2
from scipy.signal import find_peaks
from pathlib import Path


def extract_staff_line_rows(img_gray):
    """Use morphological ops to isolate staff lines, return row y-positions."""
    _, binary = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Dilate horizontally to fill small gaps (barlines, stems break staff lines)
    fill_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
    filled = cv2.dilate(binary, fill_kernel)

    # Erode with long kernel — only long horizontal runs survive
    long_width = max(50, int(img_gray.shape[1] * 0.25))
    long_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (long_width, 1))
    horizontal = cv2.erode(filled, long_kernel)

    row_sums = horizontal.sum(axis=1).astype(float) / 255
    # distance=8: prevents multiple peaks for a single fuzzy staff line (lines are ~10-15px apart)
    peaks, _ = find_peaks(row_sums, height=5, distance=8, prominence=3)
    return peaks, row_sums


def cluster_into_staves(peaks):
    """Cluster peaks into groups of ~5 lines (one per staff system)."""
    if len(peaks) == 0:
        return []

    staves, current = [], [peaks[0]]
    for i in range(1, len(peaks)):
        if peaks[i] - peaks[i - 1] < 30:
            current.append(peaks[i])
        else:
            staves.append(current)
            current = [peaks[i]]
    staves.append(current)

    return [s for s in staves if 3 <= len(s) <= 7]


def fit_five_lines(staff_peaks, row_sums):
    """Given ~5 detected peaks, return exactly 5 equidistant center y-positions."""
    staff_peaks = sorted(staff_peaks)

    if len(staff_peaks) > 5:
        densities = [row_sums[p] for p in staff_peaks]
        top5 = sorted(
            sorted(range(len(densities)), key=lambda i: -densities[i])[:5]
        )
        staff_peaks = [staff_peaks[i] for i in top5]

    gaps = [staff_peaks[i + 1] - staff_peaks[i] for i in range(len(staff_peaks) - 1)]
    spacing = np.median(gaps)
    center = np.median(staff_peaks)

    offsets = np.array([-2, -1, 0, 1, 2])
    return np.round(center + offsets * spacing).astype(int)


def track_line_slope(gray, y_center, half_band=6, step=4):
    """Sample actual line y-position column-by-column, return (slope, intercept)."""
    h, w = gray.shape
    xs, ys = [], []

    for x in range(0, w, step):
        y0 = max(0, y_center - half_band)
        y1 = min(h, y_center + half_band + 1)
        col_band = gray[y0:y1, x].astype(float)
        darkness = 255 - col_band
        total = darkness.sum()
        if total > 20:  # enough dark pixels to trust
            center_of_mass = y0 + (darkness * np.arange(len(darkness))).sum() / total
            xs.append(x)
            ys.append(center_of_mass)

    if len(xs) < 10:
        return 0.0, float(y_center)

    xs, ys = np.array(xs), np.array(ys)
    slope, intercept = np.polyfit(xs, ys, 1)
    return slope, intercept


def reinforce_staves(input_path, output_path, line_thickness=1):
    """Detect staff lines and draw clean slope-aware replacements."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise ValueError(f"Cannot load: {input_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = img.copy()

    peaks, row_sums = extract_staff_line_rows(gray)
    staves = cluster_into_staves(peaks)

    print(f"  {Path(input_path).name}: {len(staves)} staves detected")
    w = out.shape[1]
    for i, staff_peaks in enumerate(staves):
        center_positions = fit_five_lines(staff_peaks, row_sums)

        # Fit slope from the middle line (most reliable signal)
        mid_y = int(center_positions[2])
        slope, _ = track_line_slope(gray, mid_y)

        print(f"    Staff {i + 1}: centers={center_positions.tolist()}, slope={slope:.4f}")

        for y_center in center_positions:
            # All 5 lines share the same slope; intercept shifts per line
            intercept = y_center - slope * (w / 2)
            y_left = int(round(slope * 0 + intercept))
            y_right = int(round(slope * (w - 1) + intercept))
            cv2.line(out, (0, y_left), (w - 1, y_right), (0, 0, 0), line_thickness)

    cv2.imwrite(str(output_path), out)
    return staves


if __name__ == "__main__":
    targets = [
        "Indian Point.png",
        "Sarah Armstrong.png",
        "Peekaboo Waltz.png",
    ]

    base = Path(__file__).parent
    for name in targets:
        src = base / name
        dst = base / (Path(name).stem + ".staffed.png")
        reinforce_staves(src, dst)
    print("Done.")
