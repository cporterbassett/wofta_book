#!/usr/bin/env bash
# Post-GUI export for one tune: take the user's saved clean.omr, batch-export to
# MXL, clean it, convert to final ABC, and render for visual check.
#
# Handles the movement-split case: when Audiveris splits a score into movements,
# batch export writes clean.mvt1.mxl / clean.mvt2.mxl ... instead of clean.mxl.
# In that case the top-level clean.mxl is STALE — this script refuses to use it,
# lists the movement files, converts each to ABC for inspection, and stops so a
# human can pick the right movement (mvt1 is usually the tune; later movements are
# often alternates or stray fragments).
#
# Usage:
#   bash export_tune.sh "Tune Name"            # normal: expects single clean.mxl
#   bash export_tune.sh "Tune Name" --mvt 1    # force a specific movement as final
#
# Output: abc/<Tune>-final.abc  +  renders/<Tune>-final.render.png

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="$(cd "${HERE}/.." && pwd)"
VENV="${IMAGES_DIR}/.venv/bin/python3"
AUDIVERIS="flatpak run org.audiveris.audiveris"

TUNE="${1:?usage: export_tune.sh \"Tune Name\" [--mvt N]}"
FORCE_MVT=""
if [[ "${2:-}" == "--mvt" ]]; then FORCE_MVT="${3:?--mvt needs a number}"; fi

TDIR="${HERE}/batch_output/${TUNE}"
OMR="${TDIR}/clean.omr"
[[ -f "$OMR" ]] || { echo "No clean.omr for '$TUNE' at $OMR"; exit 1; }

mxl2abc() {  # $1=mxl in  $2=abc out
    local cleaned="${TDIR}/exported_clean.mxl"
    "$VENV" "${HERE}/clean_mxl.py" "$1" "$cleaned" >/dev/null
    MXL_IN="$cleaned" ABC_OUT="$2" "$VENV" -c "
import os
from abc_xml_converter import convert_xml2abc
open(os.environ['ABC_OUT'],'w').write(convert_xml2abc(file_to_convert=os.environ['MXL_IN'], output_directory=''))
" 2>/dev/null
    # Strip the "Voice" voice-name labels abc_xml_converter emits on the V: line.
    sed -i 's/ nm="[^"]*" snm="[^"]*"//' "$2"
}

# Clear old movement files so we only see this run's output.
rm -f "$TDIR"/clean.mvt*.mxl

echo "Exporting $TUNE ..."
$AUDIVERIS -batch -export "$OMR" -output "$TDIR" 2>&1 \
    | grep -Ei "exported|exception|error" | sed 's/^/  /' || true

shopt -s nullglob
MVTS=("$TDIR"/clean.mvt*.mxl)
shopt -u nullglob

FINAL_ABC="${HERE}/abc/${TUNE}-final.abc"
mkdir -p "${HERE}/abc" "${HERE}/renders"

if [[ ${#MVTS[@]} -gt 0 ]]; then
    echo ""
    echo "⚠ MOVEMENT SPLIT — Audiveris wrote ${#MVTS[@]} movement file(s); top-level clean.mxl is STALE."
    for m in "${MVTS[@]}"; do
        base="$(basename "$m")"
        abc="${HERE}/abc/${TUNE}-${base%.mxl}.abc"
        mxl2abc "$m" "$abc"
        bars=$(grep -oc '|' "$abc" 2>/dev/null || echo "?")
        echo "  $base → $abc  (~$bars barlines)"
    done
    if [[ -n "$FORCE_MVT" ]]; then
        SRC="$TDIR/clean.mvt${FORCE_MVT}.mxl"
        [[ -f "$SRC" ]] || { echo "No movement $FORCE_MVT"; exit 1; }
        mxl2abc "$SRC" "$FINAL_ABC"
        echo "→ final = mvt${FORCE_MVT}: $FINAL_ABC"
    else
        echo ""
        echo "Inspect the per-movement ABCs above, then re-run with --mvt N to pick the tune."
        echo "(mvt1 is usually the main tune.)"
        exit 2
    fi
else
    mxl2abc "$TDIR/clean.mxl" "$FINAL_ABC"
    echo "→ final: $FINAL_ABC"
fi

RENDER="${HERE}/renders/${TUNE}-final.render.png"
bash "${HERE}/render_abc.sh" "$FINAL_ABC" "$RENDER" 2>&1 | tail -1

KEY=$(grep -m1 '^K:' "$FINAL_ABC" | sed 's/^K://;s/ //g')
METER=$(grep -m1 '^M:' "$FINAL_ABC" | sed 's/^M://;s/ //g')
BARS=$(grep -oc '|' "$FINAL_ABC" || true)
echo "  Key=$KEY  Meter=$METER  ~$BARS barlines  →  $RENDER"
