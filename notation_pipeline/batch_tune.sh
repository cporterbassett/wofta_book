#!/usr/bin/env bash
# Phase 1 pipeline for a single tune.
# Preprocess (1.5× Lanczos + unsharp) → Audiveris batch → clean_omr.py →
# clean_mxl.py → abc_xml_converter → draft ABC.
#
# Output goes to:   notation_pipeline/batch_output/<Tune Name>/
#   preprocessed.png   upscaled image fed to Audiveris
#   preprocessed.omr   raw Audiveris OMR file
#   preprocessed.mxl   raw Audiveris MXL
#   clean.omr          cleaned .omr (phase 2 checkpoint — skip if present)
#   clean.mxl          cleaned MXL
# Draft ABC:         notation_pipeline/abc/<Tune Name>-draft.abc
#
# Usage (from anywhere):
#   bash batch_tune.sh "Tune Name"
#   SCALE=200 bash batch_tune.sh "Tune Name"   # override to 2×
#
# Returns 0 on success, non-zero on failure.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 \"Tune Name\""
    exit 1
fi

TUNE="$1"
IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
SRC="${IMAGES_DIR}/${TUNE}.png"
VENV="${IMAGES_DIR}/.venv/bin/python3"
OUTDIR="${PIPELINE_DIR}/batch_output/${TUNE}"
OUT_ABC="${PIPELINE_DIR}/abc/${TUNE}-draft.abc"
SCALE="${SCALE:-150}"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: source image not found: $SRC"
    exit 1
fi

# Resume checkpoint: skip if already processed
if [[ -f "${OUTDIR}/clean.omr" ]]; then
    echo "SKIP (clean.omr exists): $TUNE"
    exit 0
fi

mkdir -p "${OUTDIR}" "${PIPELINE_DIR}/abc"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Tune : $TUNE"
W=$(identify -format "%w" "$SRC")
H=$(identify -format "%h" "$SRC")
echo "Image: ${W}×${H}px  (est. ~$(( W * 10 / 85 )) DPI on 8.5\" width)"

# ── Step 1: Preprocess ────────────────────────────────────────────────────────
PREPROCESSED="${OUTDIR}/preprocessed.png"
echo "Step 1: preprocess (Lanczos ${SCALE}% + unsharp 0x1)..."
convert "$SRC" -unsharp 0x1 -filter Lanczos -resize "${SCALE}%" "$PREPROCESSED"
PW=$(identify -format "%w" "$PREPROCESSED")
PH=$(identify -format "%h" "$PREPROCESSED")
echo "        → ${PW}×${PH}px"

# ── Step 2: Audiveris ─────────────────────────────────────────────────────────
echo "Step 2: Audiveris OMR (this takes 1–3 min)..."
flatpak run org.audiveris.audiveris -batch -export -output "${OUTDIR}" "$PREPROCESSED" \
    > "${OUTDIR}/audiveris.log" 2>&1 || true

RAW_MXL=$(find "${OUTDIR}" -maxdepth 1 -name "preprocessed.mxl" | head -1)
RAW_OMR=$(find "${OUTDIR}" -maxdepth 1 -name "preprocessed.omr" | head -1)

if [[ -z "$RAW_MXL" ]]; then
    echo "ERROR: Audiveris produced no MXL — see ${OUTDIR}/audiveris.log"
    tail -5 "${OUTDIR}/audiveris.log" | sed 's/^/  /'
    exit 1
fi

# ── Step 3: Clean .omr ────────────────────────────────────────────────────────
echo "Step 3: clean .omr..."
if [[ -n "$RAW_OMR" ]]; then
    "$VENV" "${PIPELINE_DIR}/clean_omr.py" "$RAW_OMR" "${OUTDIR}/clean.omr"
else
    echo "        WARNING: no .omr produced; phase 2 GUI step will be unavailable for this tune"
fi

# ── Step 4: Clean MXL ─────────────────────────────────────────────────────────
echo "Step 4: clean MXL..."
CLEAN_MXL="${OUTDIR}/clean.mxl"
"$VENV" "${PIPELINE_DIR}/clean_mxl.py" "$RAW_MXL" "$CLEAN_MXL"

# ── Step 5: MXL → ABC ─────────────────────────────────────────────────────────
# Use env vars to pass paths — avoids shell quoting issues with apostrophes in tune names.
echo "Step 5: MXL → ABC..."
MXL_IN="$CLEAN_MXL" ABC_OUT="$OUT_ABC" "$VENV" -c "
import os
from abc_xml_converter import convert_xml2abc
result = convert_xml2abc(file_to_convert=os.environ['MXL_IN'], output_directory='')
open(os.environ['ABC_OUT'], 'w').write(result)
" 2>/dev/null

if [[ ! -s "$OUT_ABC" ]]; then
    echo "ERROR: ABC conversion produced empty file"
    exit 1
fi

KEY=$(grep -m1 '^K:' "$OUT_ABC" | sed 's/^K://' | tr -d ' ' || echo "?")
METER=$(grep -m1 '^M:' "$OUT_ABC" | sed 's/^M://' | tr -d ' ' || echo "?")
BARS=$(grep -oP '\|' "$OUT_ABC" | wc -l || echo "?")

echo "        → $OUT_ABC"
echo "        Key=${KEY}  Meter=${METER}  ~${BARS} barlines"
echo "Done: $TUNE"
