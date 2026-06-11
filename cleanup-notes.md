# Image Cleanup Notes

## What was done

32 PNG files with gray backgrounds (visible when printed, subtle on screen) were
cleaned using ImageMagick's sigmoidal contrast filter. The cleaned versions replace
the originals. Originals are backed up in `originals_backup/`.

## Why sigmoidal contrast

Hard thresholding (`-threshold 65%`) removed gray backgrounds but broke thin notation
lines (dark-gray lines fell below the cutoff and became intermittent). Sigmoidal
contrast boosts contrast gradually, whitening light backgrounds while preserving
dark notation pixels.

## Command used

```bash
convert INPUT.png -colorspace Gray -sigmoidal-contrast 5,50% OUTPUT.png
```

## To reproduce for a single file

```bash
convert "Fisher's Hornpipe.png" -colorspace Gray -sigmoidal-contrast 5,50% "Fisher's Hornpipe.png"
```

## To reproduce for all 32 files

```bash
cd /home/porter/Documents/banjo/WOFTA/combined_book/6

for f in \
  "Eighth of January.png" "Little Burnt Potato.png" "Fisher's Hornpipe.png" \
  "Pretty Little Dog (old).png" "Centralia Waltz.png" "Elmer's Waltz.png" \
  "My Darling Asleep.png" "Kerry Mills' Barn Dance.png" "Needle Case.png" \
  "Liberty.png" "Honest John.png" "Spotted Dog (old).png" \
  "Clearwater Stomp.png" "Star of the County Down (in 4-4).png" \
  "Miss McCloud's Reel.png" "Sarah Armstrong.png" "New Five Cent Piece.png" \
  "Laura Susan.png" "Demented Dog (old), The.png" "Over the Waterfall.png" \
  "Boggy Road to Texas, The.png" "Kittens on Catnip (old).png" "Hey Polka.png" \
  "Cindy.png" "Skippin' Cat (old).png" "Off to California.png" \
  "Cat on a Leash (old).png" "Border Collie (old).png" \
  "Cat in the Hopper (old).png" "Granny Will Your Dog Bite (old).png" \
  "Bull Moose.png" "Boys of Blue Hill, The.png"; do
  convert "$f" -colorspace Gray -sigmoidal-contrast 5,50% "$f"
done
```

---

## 2026-06-10: Grayscale conversion + global sig_8 cleanup

All 267 PNGs converted to grayscale and cleaned in one pass:

- **255 files** (>5% gray content): `convert -colorspace Gray -sigmoidal-contrast 8,50%`
- **12 files** (<5% gray, already clean): `convert -colorspace Gray` only

The 32 files previously treated with sig_5 still showed 13–19% gray — sig_5 was not enough. sig_8 addressed the remaining gray on those and on the many other files that had never been processed.

### Chinese Breakdown

Had heavy scattered dot noise (manually partially cleaned). Applied `sigmoidal-contrast 15,50%` specifically for this file.

---

## 2026-06-10: PDF generation pipeline

Scripts added to `tune_images/`:
- `make_pdf.sh` — shell wrapper
- `make_pdf.py` — full logic (requires `.venv/` with img2pdf, Pillow, scipy)

**Layout:**
- All images scaled to the same width (widest image = 1605px)
- Images packed vertically onto pages (greedy, alphabetical order)
- Per-page margin/gap: preferred margin=80px / gap=40px if it fits, else margin=40px / gap=20px
- Images centered horizontally
- Output: `../WOFTA_tunes.pdf` (267 images → 158 pages)

**File mtimes** set in alphabetical order (2020-01-01 UTC + 1s per file) so file managers sort correctly.

---

## 2026-06-10: Gray-interior fix (sig_15,85%)

Some scans have thick ink strokes with dark outer edges but gray interiors (80–90% brightness) — a low-resolution scan artifact where ink coverage was uneven. Standard sig_8,50% doesn't help because it's centered at 50% and these pixels are above 85%.

Fix: shift the sigmoid center to 85%, which aggressively pushes sub-85% pixels toward black while keeping the near-white background clean.

```bash
convert INPUT.png -colorspace Gray -sigmoidal-contrast 15,85% OUTPUT.png
```

**Applied to:** Gypsy Waltz.png only.

**Investigated but not applied:** Chicken Under the Washtub (all variants looked worse), Peekaboo Waltz (no visible improvement).

**Note:** A 50–90% mid-gray pixel metric was used to identify candidates but proved unreliable — most flagged images didn't have the thick-stroke interior problem. Visual inspection is necessary.

---

## How files were identified

Pixel analysis using ImageMagick's `-fx` operator to count pixels in the mid-gray
range (40–94% brightness) — neither pure white background nor black notation.
Files with more than ~13% of pixels in that range were flagged as needing cleanup.

```bash
for f in *.png; do
  gray_pct=$(convert "$f" -colorspace Gray \
    -fx "(u>0.40 && u<0.94) ? 1 : 0" \
    -format "%[fx:mean*100]" info:)
  echo "$gray_pct $f"
done | sort -rn
```
