# Raw Image Preparation Guide

How to turn freshly scanned / photocopied tune images into clean PNGs ready for the
OMR pipeline (`notation_pipeline/`). This is the **pre-OMR** stage: it ends with one
clean, trimmed, deskewed `<Tune>.png` per tune dropped into `source_images/`.

This guide is distilled from the original combined-book build (June 2026). The
extraction/cleanup tools live in **`image_prep/`** at the repo root. ImageMagick
(`convert`) and Python+Pillow are the workhorses.

> **Golden rule learned the hard way:** every "global" fix has tunes it breaks. Work
> per-image where you can, generate a side-by-side HTML comparison page (original vs.
> result), and eyeball it in a browser before committing. Visual inspection beats every
> automated metric here.

---

## The stages (in order)

### 0. Extract individual tune images from a source PDF
If you start from a scanned book PDF rather than per-tune PNGs:
- `image_prep/tune_cutter.py <file.pdf> [out_dir]` — interactive cutter (you confirm
  each boundary).
- `image_prep/split_tunes.py` — automatic boundary detection (a tune boundary = a
  whitespace gap followed by narrow-spread content, i.e. title text rather than a
  full-width staff line).

Output: one PNG per tune, e.g. `tune_001.png`.

### 1. Remove blank / title / front-matter pages
Score each image by its white-pixel ratio and drop the near-blank ones. In the original
build, ≥99% white was a clean natural break (67 of 348 pages removed).
```python
from PIL import Image
import os
for fname in os.listdir('.'):
    if not fname.endswith('.png'): continue
    img = Image.open(fname).convert('L')
    px = list(img.getdata())
    white = sum(1 for p in px if p >= 250) / len(px)
    if white >= 0.99:
        print(f'{white:.3f}  {fname}')   # review, then delete
```
Always eyeball the flagged list before deleting — a sparse-but-real tune can score high.

### 2. Trim whitespace — and beware the photocopy shadow
Photocopies often have a ~7–8px medium-brightness shadow down the left edge (~191/255).
A naive `-trim` treats that shadow as the background reference and refuses to crop.
- **No artifact:** `convert in.png -bordercolor white -border 1 -fuzz 20% -trim +repage out.png`
- **Left-edge shadow:** scan the left ~15px for medium-brightness (not-quite-black,
  not-white) pixels to find where the artifact ends, then chop past it before trimming:
  `convert in.png -chop Npx+0 -bordercolor white -border 1 -fuzz 20% -trim +repage out.png`

Artifact detection can overcrop some tunes — keep a simple-trim fallback and visually
compare. (In the original build, 8 of ~93 artifact-processed tunes had to be reverted to
the simple trim.)

### 3. Name by tune title
Read the title off the top of each image and rename `tune_NNN.png` → `<Title>.png`.
Reading a batch of images visually (e.g. via parallel sub-agents) is reliable for the
large, crisp title text. Conventions:
- Slashes in a title → ` - `.
- Duplicate titles → ` (2)`; same title in two source books → ` (old)` / ` (new)`.
- **Article sorting:** rename `The X.png` → `X, The.png` so the book sorts alphabetically.
  ```bash
  for f in The\ *.png; do n="${f#The }"; mv "$f" "${n%.png}, The.png"; done
  ```

### 4. Deskew
Scans come in slightly crooked. Use ImageMagick's Hough-transform deskew, but only when
it's worth the resample — apply at angle ≥ 0.3°.
```bash
angle=$(convert "$f" -deskew 40% -verbose info: 2>&1 | grep -oP 'Deskew angle: \K[\d.]+' || echo 0)
(( $(echo "$angle >= 0.3" | bc -l) )) && convert "$f" -deskew 40% -trim +repage "$f"
```
**Do NOT** use a hand-rolled scipy projection-profile deskew — in the original build its
sign was inverted and it made images *more* crooked. ImageMagick `-deskew` is the tool.

### 5. Clean gray backgrounds (sigmoidal contrast)
Photocopy/JPEG artifacts leave a gray fill between staff lines — subtle on screen, ugly
in print, and noise for the OMR. Whiten the background while preserving thin dark notation
with sigmoidal contrast (grayscale first):
```bash
convert in.png -colorspace Gray -sigmoidal-contrast 8,50% out.png
```
- **Default:** `sigmoidal-contrast 8,50%` (whole corpus pass; `8` proved stronger than the
  earlier `5`, which left 13–19% gray on the worst files).
- **Gray-interior thick strokes** (dark edges, 80–90% gray centers — uneven low-res ink):
  shift the sigmoid center up: `sigmoidal-contrast 15,85%`. Used on *Gypsy Waltz* only.
- **Heavy scattered dot noise:** `sigmoidal-contrast 15,50%`. Used on *Chinese Breakdown*.
- Files that are already clean (<5% gray): just `-colorspace Gray`, no contrast.

**Identify candidates** by the mid-gray pixel fraction (neither white background nor black
notation); >~13% is a flag — but treat it as a hint, not a verdict (it produced many false
positives; confirm visually):
```bash
for f in *.png; do
  pct=$(convert "$f" -colorspace Gray -fx "(u>0.40 && u<0.94) ? 1 : 0" -format "%[fx:mean*100]" info:)
  echo "$pct $f"
done | sort -rn
```
Back up originals before an in-place pass.

### 6. Hand off to the OMR pipeline
Drop the finished `<Tune>.png` into `source_images/`. From there `notation_pipeline/`
takes over (batch OMR → GUI cleanup → ABC). See `notation_pipeline/README.md`.

---

## What did NOT work (don't retry)
- **Hard threshold** (`-threshold 65%`) to drop gray — breaks thin notation lines (dark-gray
  staff/note pixels fall below the cutoff and go intermittent). Sigmoidal contrast instead.
- **scipy projection-profile deskew** — sign inverted, worsened skew. Use `convert -deskew`.
- **Mid-gray pixel metric as a sole signal** — unreliable; most flagged files didn't have the
  problem. It narrows the candidate list; your eyes make the call.

## Proofing utility
`image_prep/abc2png.sh tune.abc [out.png]` renders an ABC to PNG for a quick look. (For the
real engraving path used in the book, see `notation_pipeline/bin/render_abc.sh` and
`make_pdf.py`, which render via `abcm2ps`.)
