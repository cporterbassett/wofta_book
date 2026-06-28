#!/usr/bin/env python3
"""Crop a scanned tune page to its main music block, dropping a stray
bottom-of-page copyright/credit (e.g. a lone "(c)") that survives a plain -trim
and otherwise leaves the trimmed image mostly empty vertical space.

Strategy: threshold to ink, find per-row ink counts, then find the largest run
of (near-)empty rows. If that gap sits below the bulk of the ink and there is
only a little ink beneath it, crop everything above the gap. Then tight-trim.

Usage: crop_music_block.py <in.png> <out.png>
"""
import sys
import numpy as np
from PIL import Image

inp, outp = sys.argv[1], sys.argv[2]
im = Image.open(inp).convert("L")
a = np.asarray(im)
ink = (a < 128)
row_ink = ink.sum(axis=1)
thresh = max(2, row_ink.max() * 0.01)  # a row "has ink" if above ~1% of densest
has = row_ink > thresh

rows = np.where(has)[0]
if len(rows) == 0:
    im.save(outp)
    sys.exit(0)

# Find runs of empty rows between the first and last inked row.
top, bot = rows[0], rows[-1]
empty = ~has
best_gap = None  # (length, start, end)
i = top
while i <= bot:
    if empty[i]:
        j = i
        while j <= bot and empty[j]:
            j += 1
        if best_gap is None or (j - i) > best_gap[0]:
            best_gap = (j - i, i, j)
        i = j
    else:
        i += 1

cut = bot + 1
if best_gap is not None:
    gap_len, gs, ge = best_gap
    ink_above = row_ink[top:gs].sum()
    ink_below = row_ink[ge:bot + 1].sum()
    # Only treat it as a footer gap if the gap is sizable and the stuff below it
    # is a small fraction of the page's ink (a lone copyright mark / credit).
    if gap_len > 40 and ink_below < 0.06 * ink_above:
        cut = gs

a2 = a[:cut, :]
out = Image.fromarray(a2)
out.save(outp)
