#!/usr/bin/env bash
# Build a side-by-side compare image: source scan (LEFT) + sepia engraved render
# (RIGHT), normalized so the two panels are approximately the same size.
#
# Both are trimmed and scaled to the SAME width. The render mirrors the scan's
# line breaks (same notes per system), so equal width == equal staff scale —
# this matches the music size even when the scan has extra title/footer
# whitespace that would throw off a height match. Then both are centre-padded to
# the SAME (max) height so the two panels end up identical dimensions.
#
# Usage: make_compare.sh <source.png> <render.png> <out.png>
set -euo pipefail
SRC="$1"; REN="$2"; OUT="$3"
W=950
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(cd "${HERE}/.." && pwd)/.venv/bin/python3"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# Drop a stray bottom-of-page copyright/credit so it doesn't bloat the trim box
# and shrink the music; fall back to the raw scan if the helper isn't available.
"$PY" "${HERE}/crop_music_block.py" "$SRC" "$TMP/src_crop.png" 2>/dev/null || cp "$SRC" "$TMP/src_crop.png"
convert "$TMP/src_crop.png" -trim +repage -resize "${W}x" "$TMP/src.png"
convert "$REN" -trim +repage -sepia-tone 80% -resize "${W}x" "$TMP/ren.png"
SH=$(identify -format "%h" "$TMP/src.png")
RH=$(identify -format "%h" "$TMP/ren.png")
H=$(( SH > RH ? SH : RH ))
convert "$TMP/src.png" -background white -gravity center -extent "${W}x${H}" "$TMP/src2.png"
convert "$TMP/ren.png" -background white -gravity center -extent "${W}x${H}" "$TMP/ren2.png"
convert "$TMP/src2.png" "$TMP/ren2.png" +append \
  -background white -bordercolor white -border 15 "$OUT"
