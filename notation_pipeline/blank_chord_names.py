#!/usr/bin/env python3
"""
Blank out chord names and text annotations above staff lines before Audiveris OMR.

Strategy:
  1. Detect staff lines (long horizontal runs) via morphological opening.
  2. Group lines into 5-line staff systems.
  3. White-out the region ABOVE each system's top line (where chord names sit).
  4. Optionally also white-out the instrument label zone on the far left.

Usage:
  python3 blank_chord_names.py input.png output.png [--show-debug]
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def find_staff_line_ys(gray, min_run_fraction=0.35):
    """Return sorted list of y-coords that contain long horizontal black runs."""
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    min_run = int(gray.shape[1] * min_run_fraction)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_run, 1))
    staff_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    ys = []
    for y in range(staff_mask.shape[0]):
        if staff_mask[y].any():
            ys.append(y)
    return ys


def group_staff_lines(ys, cluster_gap=8):
    """Cluster nearby y-values into bands, then split into systems at large gaps."""
    if not ys:
        return []

    # Step 1: cluster contiguous pixel rows into single representative y per line
    bands = []
    cluster = [ys[0]]
    for y in ys[1:]:
        if y - cluster[-1] <= cluster_gap:
            cluster.append(y)
        else:
            bands.append(int(np.median(cluster)))
            cluster = [y]
    bands.append(int(np.median(cluster)))

    if len(bands) < 2:
        return [bands]

    # Step 2: split bands into staff systems wherever the gap is much larger than normal.
    # Within a system, staff lines are roughly equally spaced (~20-30px at 2× scale).
    # Between systems the gap is typically 5-15× that.
    gaps = [bands[i+1] - bands[i] for i in range(len(bands) - 1)]
    median_gap = float(np.median(gaps))
    split_threshold = median_gap * 2.5

    systems = []
    current = [bands[0]]
    for i, gap in enumerate(gaps):
        if gap <= split_threshold:
            current.append(bands[i + 1])
        else:
            systems.append(current)
            current = [bands[i + 1]]
    systems.append(current)

    # Discard fragments with fewer than 3 detected lines
    systems = [s for s in systems if len(s) >= 3]
    return systems


def blank_chord_name_regions(img, systems, above_margin=4, label_strip_px=0):
    """
    White-out regions above each staff system's top line.
    also optionally strip the leftmost label_strip_px columns.

    img: BGR or grayscale numpy array (modified in place copy returned).
    """
    result = img.copy()
    h, w = img.shape[:2]

    # Blank above the first system
    if systems:
        top = systems[0][0]
        y0 = max(0, top - above_margin)
        result[0:y0, :] = 255

    # Blank between consecutive systems
    for i in range(len(systems) - 1):
        bot = systems[i][-1]
        top_next = systems[i+1][0]
        y0 = bot + above_margin
        y1 = max(y0, top_next - above_margin)
        result[y0:y1, :] = 255

    # Optionally strip left-side instrument label
    if label_strip_px > 0:
        result[:, 0:label_strip_px] = 255

    return result


def process(src_path, dst_path, debug=False):
    img = cv2.imread(str(src_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    ys = find_staff_line_ys(gray)
    if not ys:
        print(f"WARNING: no staff lines detected in {src_path}", file=sys.stderr)
        cv2.imwrite(str(dst_path), img)
        return

    systems = group_staff_lines(ys)
    print(f"  Found {len(ys)} staff line rows → {len(systems)} system(s)", file=sys.stderr)
    for idx, sys_ in enumerate(systems):
        print(f"    System {idx+1}: lines at y={sys_}", file=sys.stderr)

    result = blank_chord_name_regions(img, systems, above_margin=4)
    cv2.imwrite(str(dst_path), result)
    print(f"  Saved: {dst_path}", file=sys.stderr)

    if debug:
        # draw green lines at detected staff positions
        dbg = result.copy()
        for s in systems:
            for y in s:
                cv2.line(dbg, (0, y), (dbg.shape[1], y), (0, 200, 0), 1)
        debug_path = Path(dst_path).with_suffix('.debug.png')
        cv2.imwrite(str(debug_path), dbg)
        print(f"  Debug: {debug_path}", file=sys.stderr)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    debug = '--show-debug' in sys.argv or '--debug' in sys.argv

    if len(args) != 2:
        print(f"Usage: {sys.argv[0]} input.png output.png [--debug]")
        sys.exit(1)

    process(Path(args[0]), Path(args[1]), debug=debug)
