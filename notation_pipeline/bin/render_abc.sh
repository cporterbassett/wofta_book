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

# Inject measure-number directive (number at the start of each staff line, like
# the WOFTA scans) without modifying the source ABC.
TMPABC="${STEM}.render.tmp.abc"
# measure numbers at each line start; bold chord symbols and bold 1./2. volta numbers.
# %%contbarnb 1 = count 1st/2nd endings as SEPARATE measures (matches the WOFTA
# scans' numbering, e.g. line 3 of Jerusalem's Ridge starts at m10 not m9).
render() {
    local extra="$1"
    {
        printf '%s' "$extra"
        printf '%%%%measurenb 0\n%%%%contbarnb 1\n%%%%gchordfont Helvetica-Bold 12\n%%%%repeatfont Helvetica-Bold 12\n'
        cat "$ABC"
    } > "$TMPABC"
    abcm2ps -O "$PS" -s 1.0 -m 0.5cm "$TMPABC" 2>&1
}

# Render to PostScript first (abcm2ps PostScript output is the most faithful).
# abcm2ps exits non-zero on cosmetic warnings (e.g. "Line too much shrunk" on
# long/dense tunes) while still emitting a valid PS — don't let that abort the
# script (and, downstream, the verify pipeline's commit). Only a MISSING PS is a
# real failure. Mirrors the abcm2ps tolerance in make_pdf.py.
#
# abcm2ps's default page width is narrow enough that a dense line (lots of
# 16th notes + chord symbols) can overflow by even 1pt, silently triggering an
# UNWANTED extra auto-wrap that splits one intended staff line into two — which
# then throws off line-by-line lyric alignment (each w: line attaches to the
# music line above it). make_pdf.py already retries wider on this; mirror that
# here so the standalone live-compare view matches the book's rendering.
STDERR="$(render '' || true)"
if grep -qi "overfull\|shrunk" <<<"$STDERR"; then
    STDERR="$(render '%%pagewidth 1000pt
' || true)"
fi
echo "$STDERR" >&2

rm -f "$TMPABC"

if [[ ! -s "$PS" ]]; then
    echo "render_abc.sh: abcm2ps produced no PostScript for $ABC" >&2
    exit 1
fi

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
    # use ImageMagick to stack pages — trim each page's whitespace FIRST so the
    # page-break margin (page-1 bottom + page-2 top) doesn't become a huge gap
    # between systems when a tune spills just over one page.
    convert "${PAGES[@]}" -trim +repage -append "$OUT"
    rm "${PAGES[@]}"
fi

rm -f "$PS"

echo "Rendered: $OUT"
