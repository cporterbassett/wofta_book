#!/usr/bin/env bash
# Run the best preprocessing pipeline on a tune and produce an ABC file.
# Default scale: 1.5× Lanczos + unsharp 0x1 (18/19 = 95% on Angeline; best key detection
# across 20-tune survey: 79% vs 68% for both 1× and 2×).
# The earlier 2× default gave 100% note accuracy on Angeline but broke key detection on
# more tunes than 1.5×.
#
# Usage (from notation_pipeline/):
#   bash run_tune_pipeline.sh "Tune Name"
#   SCALE=200 bash run_tune_pipeline.sh "Tune Name"   # override to 2× if needed
#
# Output:
#   abc/<Tune Name>-audiveris-raw.abc

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 \"Tune Name\""
    exit 1
fi

TUNE="$1"
IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
SRC="${IMAGES_DIR}/${TUNE}.png"
VENV="${IMAGES_DIR}/.venv/bin/python3"
WORKDIR="${IMAGES_DIR}/notation_pipeline"
OUT_ABC="${WORKDIR}/abc/${TUNE}-audiveris-raw.abc"
TMPDIR="${WORKDIR}/tmp_pipeline/${TUNE}"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: source image not found: $SRC"
    exit 1
fi

mkdir -p "$TMPDIR/mxl" "${WORKDIR}/abc"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Tune : $TUNE"
W=$(identify -format "%w" "$SRC")
H=$(identify -format "%h" "$SRC")
echo "Image: ${W}×${H}px  (est. ~$(( W * 10 / 85 )) DPI on 8.5\" width)"

# ── Step 1: Preprocess ────────────────────────────────────────────────────────
PREPROCESSED="${TMPDIR}/preprocessed.png"
SCALE="${SCALE:-150}"
echo "Step 1: preprocess (Lanczos ${SCALE}% + unsharp 0x1)..."
convert "$SRC" -unsharp 0x1 -filter Lanczos -resize "${SCALE}%" "$PREPROCESSED"
PW=$(identify -format "%w" "$PREPROCESSED")
PH=$(identify -format "%h" "$PREPROCESSED")
echo "        → ${PW}×${PH}px"

# ── Step 2: Audiveris ─────────────────────────────────────────────────────────
echo "Step 2: Audiveris OMR (this takes 1–3 min)..."
flatpak run org.audiveris.audiveris -batch -export -output "$TMPDIR/mxl" "$PREPROCESSED" \
    > "$TMPDIR/audiveris.log" 2>&1 || true

MXL=$(find "$TMPDIR/mxl" -name "*.mxl" | head -1)
if [[ -z "$MXL" ]]; then
    echo "ERROR: Audiveris produced no MXL"
    tail -5 "$TMPDIR/audiveris.log" | sed 's/^/  /'
    exit 1
fi
echo "        → $MXL"

# ── Step 3: MXL → ABC ─────────────────────────────────────────────────────────
echo "Step 3: MXL → ABC..."
"$VENV" -c "
from abc_xml_converter import convert_xml2abc
result = convert_xml2abc(file_to_convert='$MXL', output_directory='')
print(result)
" > "$OUT_ABC" 2>/dev/null

if [[ ! -s "$OUT_ABC" ]]; then
    echo "ERROR: ABC conversion produced empty file"
    exit 1
fi

# Quick summary of what was produced
MEASURES=$(grep -oP '\|' "$OUT_ABC" | wc -l || echo "?")
KEY=$(grep -m1 '^K:' "$OUT_ABC" | sed 's/^K://' | tr -d ' ' || echo "?")
METER=$(grep -m1 '^M:' "$OUT_ABC" | sed 's/^M://' | tr -d ' ' || echo "?")
UNIT=$(grep -m1 '^L:' "$OUT_ABC" | sed 's/^L://' | tr -d ' ' || echo "?")

echo "        → $OUT_ABC"
echo "        Key=${KEY}  Meter=${METER}  L=${UNIT}  ~${MEASURES} barlines"
echo "Done."
