# WOFTA Combined Book — Image Processing History

Each directory represents a stage in the pipeline. This document records what was done in each stage, which Claude session did it, and how to reproduce it.

---

## Directory 1: `1 original_tune_images`

**Status:** Untouched originals — do not modify.

**Contents:** 348 PNG images in `new_book/` (101) and `old_book/` (247) subdirs. Filenames are `tune_NNN.png`.

**Source:** Extracted from the original PDFs using scripts in `../originals/` (`tune_cutter.py`, `split_tunes.py`).

---

## Directory 2: `2 remove footers`

**Session:** Jun 8, 2025 — Claude session `0f8eb876` in project `Combined-Book`
**Result:** 281 images (93 new_book + 188 old_book) — 67 removed from the original 348.

**What was done:**
Blank pages, title pages, and mostly-white non-music pages were identified and removed. These were footer/front-matter pages with little or no musical notation.

**Method:**
1. Analyzed each image's white-pixel ratio using Python/Pillow.
2. Built a histogram of white-pixel ratios across all 348 images.
3. Found a natural break: 6 images at ≥99% white, 61 at ≥99% (including the first 6).
4. The 6 most-white images were moved to `mostly_white_review/` for manual review, confirmed as not needed, and deleted.
5. The remaining 55 images at ≥99% white were moved to `mostly_white_review/` and deleted.
6. Total removed: 67 images.

**Reproduce:**
```bash
cd /path/to/source_dir
python3 - <<'EOF'
from PIL import Image
import os

results = []
for subdir in ['new_book', 'old_book']:
    for fname in os.listdir(subdir):
        if not fname.endswith('.png'):
            continue
        path = os.path.join(subdir, fname)
        img = Image.open(path).convert('L')
        pixels = list(img.getdata())
        white_ratio = sum(1 for p in pixels if p >= 250) / len(pixels)
        results.append((white_ratio, subdir, fname))

results.sort(reverse=True)
# Review images with white_ratio >= 0.99 for removal
for ratio, subdir, fname in results:
    if ratio >= 0.99:
        print(f'{ratio:.3f}  {subdir}/{fname}')
EOF
```

---

## Directory 3: `3 more trim`

**Session:** Jun 9, 2025 08:05 — Claude session `6bffb0a5` in project `combined-book-3`
**Result:** 281 images with whitespace trimmed from all four edges. Files still in `new_book/` and `old_book/` subdirs as `tune_NNN.png`.

**What was done:**
Images had uneven borders and photocopy artifacts along the left edge (a ~7-8px-wide shadow at brightness ~191/255). A naive `mogrify -trim` would use this shadow as the background reference color, preventing correct trimming.

**Solution — per-image pipeline:**
1. Scan the left 15px of each image for non-white pixels.
2. If a photocopy shadow is detected (medium-brightness pixels, not actual notation which is very dark), calculate where the artifact ends.
3. Chop off just past the artifact, then trim normally with a 1px white border and 20% fuzz.
4. Fall back to simple trim if no artifact detected.
5. 8 `new_book` tunes (029, 030, 038, 049, 057, 067, 093, 095) were restored to the simple-trim version (artifact detection overcropped them).
6. All 188 `old_book` tunes were kept with simple trim (no per-image artifact processing needed).

**Key commands:**
```bash
# Simple trim (used for old_book and fallback new_book tunes):
convert input.png -bordercolor white -border 1 -fuzz 20% -trim +repage output.png

# Artifact-aware trim (used for most new_book tunes):
# 1. Determine chop width N by scanning left edge for shadow artifact
# 2. Chop, then trim:
convert input.png -chop Npx+0 -bordercolor white -border 1 -fuzz 20% -trim +repage output.png
```

**Comparison pages** were generated as HTML (original vs. trimmed, side by side) and reviewed in Firefox.

---

## Directory 4: `4-named`

**Sessions:**
- Jun 9, 2025 08:21 — Claude session `d042e57b` in project `combined-book-4` (renaming)
- Jun 9, 2025 08:23 — Claude session `d8157509` in project `combined-book-4` (article sorting)

**Result:** 281 flat PNG files (no subdirs) named by tune title. Files sorted with "The X" → "X, The".

### Part A: Rename by tune title

**What was done:**
Files were renamed from `tune_NNN.png` to the actual tune name visible at the top of each image. 6 parallel sub-agents visually read batches of ~47 images each, extracting tune names. 279 of 281 files were renamed:
- `tune_001.png` — kept as-is ("hints and guidelines" page, not a tune)
- `tune_174.png` — kept as-is (no visible title)
- Slashes in names replaced with ` - `
- Duplicate name ("Soldier's Joy") resolved as `Soldier's Joy (2).png`
- 12 filenames present in both `old_book/` and `new_book/` resolved with `(old)` and `(new)` suffixes

All files moved from `new_book/` and `old_book/` subdirs into the flat `4-named/` directory.

### Part B: Article sorting ("The X" → "X, The")

**What was done:**
17 files whose names started with `The ` were renamed to move the article to the end for proper alphabetical sorting.

**Reproduce:**
```bash
cd /path/to/4-named
for f in The\ *.png; do
    [ -f "$f" ] || continue
    newname="${f#The }"
    newname="${newname%.png}, The.png"
    mv "$f" "$newname"
done
```

**Examples:** `The Gale.png` → `Gale, The.png` | `The Girl I Left Behind Me.png` → `Girl I Left Behind Me, The.png`

---

## Directory 5: `5-deskew`

**Session:** Jun 9, 2025 08:44 — Claude session `b729bb18` in project `combined-book-5`
**Result:** 279 images. 81 corrected for skew; 198 left untouched.

**What was done:**
Many images were slightly crooked from scanning. ImageMagick's `-deskew` (Hough transform) was used to auto-detect and correct skew.

**Process:**
1. First attempt used Python/scipy projection profile method — the sign was inverted, making images MORE crooked. Those changes were discarded and files re-copied from `4-named/`.
2. Switched to ImageMagick's built-in `-deskew 40%` (uses the Hough transform internally).
3. Applied only to images with a detected skew angle ≥ 0.3° to avoid unnecessary resampling.
4. 81 images were corrected; 198 left untouched (angle below threshold).
5. A comparison HTML page (`deskew_comparison.html`) was generated showing the 24 most-skewed images (original left, corrected right), sorted worst-first.

**Key command:**
```bash
# Detect and correct skew (apply only when angle >= 0.3 degrees):
convert input.png -deskew 40% -trim +repage output.png

# To detect angle without modifying:
convert input.png -deskew 40% -verbose info: 2>&1 | grep "Deskew angle"
```

**Reproduce (selective):**
```bash
cd /path/to/source
for f in *.png; do
    angle=$(convert "$f" -deskew 40% -verbose info: 2>&1 | grep -oP 'Deskew angle: \K[\d.]+' || echo 0)
    if (( $(echo "$angle >= 0.3" | bc -l) )); then
        convert "$f" -deskew 40% -trim +repage "$f"
    fi
done
```

---

## Directory 6: `6`

**Session:** Jun 9, 2025 12:21 — Claude session `7a01a36b` in project `combined-book-6`
**Result:** 32 images cleaned of gray backgrounds. Originals backed up in `6/originals_backup/`.

**What was done:**
~32 images had gray backgrounds from photocopy artifacts and JPEG compression history. These don't show prominently on screen but print with a gray fill between staff lines.

**How problematic files were identified:**
```bash
cd /path/to/6
for f in *.png; do
    gray_pct=$(convert "$f" -colorspace Gray \
        -fx "(u>0.40 && u<0.94) ? 1 : 0" \
        -format "%[fx:mean*100]" info:)
    echo "$gray_pct $f"
done | sort -rn
# Files with >13% mid-gray pixels were flagged
```

**Approaches tested:**
1. Hard normalize + threshold (`-threshold 65%`) — broke thin notation lines
2. `-white-threshold 80%` — better, but still some line degradation
3. **`-sigmoidal-contrast 5,50%`** — chosen: whitens light backgrounds while preserving dark notation

**Key command:**
```bash
convert input.png -colorspace Gray -sigmoidal-contrast 5,50% output.png
```

See `6/cleanup-notes.md` for the full list of 32 affected files and the exact reproduce script.

---

## ABC → PDF Pipeline (for ABC-sourced tunes)

**Session:** Jun 10–11, 2026

**What was done:**
Replaced the scanned `Honest John.png` with `honest-john.abc` as the authoritative source. ABC files are now rendered to **vector PDF** via LilyPond and composited directly into the combined book PDF using pikepdf — no rasterization. This gives searchable text and perfect print quality for ABC-sourced tunes.

**Pipeline (integrated into make_pdf.py):**
```
tune.abc → abc2ly → tune.ly (patched) → lilypond --pdf -dcrop → tune.cropped.pdf → pikepdf XObject
```

`make_pdf.py` handles both `.png` (scanned tunes) and `.abc` files automatically, sorted together alphabetically by title.

**Key implementation notes:**
- `abc2ly` output must be patched to add `\paper { indent = 0 }` at the top level (not inside `\score`) — otherwise the first staff is indented relative to subsequent staves
- LilyPond `-dcrop` trims the PDF to content size; pikepdf places it as a Form XObject scaled to page width
- PNG scanned tunes are converted to PDF via `img2pdf` at assumed 150 DPI (no metadata), then placed the same way

**ABC notation notes:**
- Chord symbols: `"G"b3` — double-quoted string before the note, rendered above staff
- Only show a chord when it changes from the previous measure
- Source line breaks in ABC control staff line breaks in the rendered output
- Force line breaks with `\break` in the `.ly` file after the desired bar
- Pickup notes: `|:d|` — remove by changing to `|:` to start on the downbeat
- Pickup rests: `|:z|` — same pattern

**Scripts:**
- `make_pdf.sh` / `make_pdf.py` — full book pipeline, outputs `WOFTA_tunes.pdf` here
- `abc2png.sh` — standalone ABC→PNG utility for proofing: `./abc2png.sh tune.abc`
- `compose_page.py` — compose a list of PNGs/PDFs onto a single letter page

**Example:** `honest-john.abc` — jig in G/D, chord symbols, cleaned pickup notes.

---

## Summary Table

| Dir | Operation | Session Date | Images In | Images Out | Key Tool |
|-----|-----------|-------------|-----------|------------|----------|
| `1 original_tune_images` | Source (originals) | — | — | 348 | PDF splitter scripts |
| `2 remove footers` | Remove blank/title pages | Jun 8 | 348 | 281 | Pillow white-pixel ratio |
| `3 more trim` | Trim whitespace + fix photocopy artifact | Jun 9 08:05 | 281 | 281 | ImageMagick `-trim` + `-chop` |
| `4-named` | Rename by tune title; "The X" → "X, The" | Jun 9 08:21-23 | 281 | 279* | Visual OCR via sub-agents |
| `5-deskew` | Correct scanning skew on 81 images | Jun 9 08:44 | 279 | 279 | ImageMagick `-deskew 40%` |
| `6` | Remove gray backgrounds on 32 images | Jun 9 12:21 | 279 | 279 | ImageMagick `-sigmoidal-contrast 5,50%` |

*2 files kept with original `tune_NNN.png` names (no title found).
