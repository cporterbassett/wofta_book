# Staff Line Reinforcement — Investigation

## Goal

Some sheet music images in this collection have fuzzy, uneven staff lines from the original photocopies/scans. The idea: detect the staff lines algorithmically and draw clean new lines on top to improve readability in the PDF output.

Use case is purely visual (human-readable PDFs), not OMR — so slight positional imprecision is acceptable.

## Approach

`reinforce_staves.py` processes a single image or a list of images:

1. **Morphological detection** — binarize, dilate horizontally (fills barline gaps), erode with a long kernel (~25% image width). Only long horizontal runs survive, filtering out notes, stems, and beams.

2. **Row histogram peaks** — find y-positions of surviving dark rows using `scipy.signal.find_peaks` with `distance=8` (prevents multi-peak firing per fuzzy line).

3. **Cluster into staves** — group peaks with gaps < 30px as one staff system; filter to groups of 3–7 lines.

4. **Fit 5 equidistant lines** — compute median spacing and center y for each staff cluster; project exactly 5 positions at equal spacing.

5. **Slope + intercept fitting** — for each of the 5 lines, sample actual pixel positions column-by-column (center-of-mass in a ±6px band). Fit a **shared slope** across all 5 lines (robust), with a **per-line intercept** using the median residual. Margins (~8% each side) excluded to avoid clef/barline distortion.

6. **Draw** — `cv2.line` at the fitted slope/intercept for each of the 5 lines, 1px black.

## Test images

| Image | Staves | Slope | Notes |
|---|---|---|---|
| Indian Point.png | 4 | ~0.001 | Good result |
| Sarah Armstrong.png | 3 | ~0.004 | Good, minor residual doubling in bottom-right |
| Peekaboo Waltz.png | 8 | ~0.002 | Good result |

## Status

Working well. Known remaining issue: **slight residual doubling on Sarah Armstrong bottom staff**, likely because the staff lines have a mild bow (quadratic curvature) that a linear slope can't fully capture. The fix would be either:

- `np.polyfit(..., deg=2)` quadratic fit per line, with column-by-column drawing
- Or: smooth the raw column-by-column samples directly and draw from those

Paused here — worth revisiting if the PDF output looks rough after applying to the full image set.

## Usage

```bash
source ../.venv/bin/activate
python reinforce_staves.py
```

Output files written as `<stem>.staffed.png` alongside the originals (currently hardcoded to the three test images at the bottom of the script; easy to extend to a glob).
