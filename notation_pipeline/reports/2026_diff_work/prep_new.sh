#!/usr/bin/env bash
# Prep the 24 new 2026 tune PDFs into clean grayscale PNGs for the OMR pipeline.
# Recipe matches the Deliverable-2 replace round:
#   rasterize 200dpi gray -> trim -> deskew(>=0.3) -> cap width at 1500px.
# Sigmoidal contrast is applied per-tune via the FADED list below (eyeball first).
#
# Outputs to:  2026_diff_work/new/staged/<canonical>.png   (NOT source_images yet)
# Usage:       bash prep_new.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRCDIR="/home/porter/Documents/banjo/WOFTA/2026/2026 add-ons & redos copy"
MAP="${HERE}/new_map.txt"
OUT="${HERE}/new/staged"
RASTER="${HERE}/new/raster"   # keep raw rasterizations for reference
mkdir -p "$OUT" "$RASTER"

# Tunes that need background whitening (faded/gray). Add canonical names here.
FADED=("${FADED_LIST[@]:-}")

is_faded() { local n="$1"; for f in "${FADED[@]:-}"; do [[ "$f" == "$n" ]] && return 0; done; return 1; }

while IFS='|' read -r pdfbase canon; do
  [[ "$pdfbase" =~ ^#.*$ || -z "$pdfbase" ]] && continue
  pdf="${SRCDIR}/${pdfbase}.pdf"
  if [[ ! -f "$pdf" ]]; then echo "MISS: $pdfbase"; continue; fi
  raw="${RASTER}/${canon}.png"
  dst="${OUT}/${canon}.png"

  # 1. rasterize first page at 200dpi grayscale
  gs -q -dNOPAUSE -dBATCH -sDEVICE=pnggray -r200 -dFirstPage=1 -dLastPage=1 \
     -sOutputFile="$raw" "$pdf"

  # 2. trim whitespace (small white border so -trim has a reference)
  convert "$raw" -bordercolor white -border 10 -fuzz 20% -trim +repage "$dst"

  # 3. deskew if angle >= 0.3 deg
  angle=$(convert "$dst" -deskew 40% -verbose info: 2>&1 | grep -oP 'Deskew angle: \K[\d.]+' || echo 0)
  if (( $(echo "$angle >= 0.3" | bc -l) )); then
    convert "$dst" -deskew 40% -bordercolor white -border 10 -fuzz 20% -trim +repage "$dst"
  fi

  # 4. cap width at 1500px
  w=$(identify -format "%w" "$dst")
  if (( w > 1500 )); then
    convert "$dst" -filter Lanczos -resize 1500x "$dst"
  fi

  # 5. optional background whitening
  if is_faded "$canon"; then
    convert "$dst" -colorspace Gray -sigmoidal-contrast 8,50% "$dst"
  fi

  printf "%-34s deskew=%-5s -> %s\n" "$canon" "$angle" "$(identify -format '%wx%h' "$dst")"
done < "$MAP"
