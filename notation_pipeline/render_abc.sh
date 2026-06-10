#!/usr/bin/env bash
# Render an ABC file to PNG using abcm2ps + ImageMagick / Ghostscript.
#
# Usage: render_abc.sh <tune.abc> [out.png]
#   out.png defaults to <tune-stem>.render.png
#
# Requires: abcm2ps, ghostscript (gs)

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: render_abc.sh <tune.abc> [out.png]" >&2
    exit 1
fi

ABC="$1"
STEM="${ABC%.abc}"
OUT="${2:-${STEM}.render.png}"
PS="${STEM}.render.ps"
TMPSVG="${STEM}.render.svg"

# Resolution for the PNG (match scan width ~1300px at 150dpi comes out ~1350px)
DPI=150

# Render to PostScript first (abcm2ps PostScript output is the most faithful)
abcm2ps \
    -O "$PS" \
    -s 1.0 \
    -m 0.5cm \
    "$ABC"

# Convert PS → PNG via Ghostscript
gs -dBATCH -dNOPAUSE -dQUIET \
   -sDEVICE=pnggray \
   -r${DPI} \
   -sOutputFile="${OUT%.png}-%d.png" \
   "$PS"

# If multi-page, stitch pages vertically
PAGES=( "${OUT%.png}"-*.png )
if [[ ${#PAGES[@]} -eq 1 ]]; then
    mv "${PAGES[0]}" "$OUT"
else
    # use ImageMagick to stack pages
    convert -append "${PAGES[@]}" "$OUT"
    rm "${PAGES[@]}"
fi

rm -f "$PS"

echo "Rendered: $OUT"
