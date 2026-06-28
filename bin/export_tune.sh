#!/usr/bin/env bash
# Post-GUI export for one tune: take the user's saved clean.omr, batch-export to
# MXL, clean it, convert to final ABC, and render for visual check.
#
# Handles the movement-split case: when Audiveris splits a score into movements,
# batch export writes clean.mvt1.mxl / clean.mvt2.mxl ... instead of clean.mxl.
# In that case the top-level clean.mxl is STALE — this script ignores it and, by
# default, MERGES all movements (in numeric order) into one candidate. Audiveris
# frequently splits a single tune across movements (e.g. the first pass of the A
# part lands in mvt1, the rest in mvt2), so keeping only one silently drops real
# music — the "big chunks missing" bug. Per-movement ABCs are still written for
# inspection. Use --mvt N to force a single movement when a later one is genuinely
# a stray fragment or alternate you don't want.
#
# Usage:
#   bash export_tune.sh "Tune Name"            # single clean.mxl, or merge all movements
#   bash export_tune.sh "Tune Name" --mvt 1    # force a specific movement as final
#
# Output: abc/<Tune>-candidate.abc  +  renders/<Tune>-candidate.render.png

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"
VENV="${IMAGES_DIR}/.venv/bin/python3"
AUDIVERIS="flatpak run org.audiveris.audiveris"

TUNE="${1:?usage: export_tune.sh \"Tune Name\" [--mvt N]}"
FORCE_MVT=""
if [[ "${2:-}" == "--mvt" ]]; then FORCE_MVT="${3:?--mvt needs a number}"; fi

TDIR="${PIPELINE_DIR}/batch_output/${TUNE}"
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
    # abc_xml_converter writes M:2/2 even for cut time; restore M:C| when MXL says so.
    # (MXL files are ZIP archives, so use unzip -p to search the XML inside.)
    if unzip -p "$1" "*.xml" 2>/dev/null | grep -q 'symbol="cut"'; then
        sed -i 's/^M:2\/2$/M:C|/' "$2"
    fi
}

# Clear old movement + merge files so we only see this run's output.
rm -f "$TDIR"/clean.mvt*.mxl "$TDIR"/clean.merged.mxl

echo "Exporting $TUNE ..."
$AUDIVERIS -batch -export "$OMR" -output "$TDIR" 2>&1 \
    | grep -Ei "exported|exception|error" | sed 's/^/  /' || true

shopt -s nullglob
MVTS=("$TDIR"/clean.mvt*.mxl)
shopt -u nullglob

FINAL_ABC="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
mkdir -p "${PIPELINE_DIR}/abc" "${PIPELINE_DIR}/renders"

if [[ ${#MVTS[@]} -gt 0 ]]; then
    # Sort movements numerically (mvt1, mvt2, ... mvt10) so the merge follows the
    # score order rather than lexical glob order.
    mapfile -t MVTS < <(printf '%s\n' "${MVTS[@]}" | sort -V)
    echo ""
    echo "⚠ MOVEMENT SPLIT — Audiveris wrote ${#MVTS[@]} movement file(s); top-level clean.mxl is STALE."
    for m in "${MVTS[@]}"; do
        base="$(basename "$m")"
        abc="${PIPELINE_DIR}/abc/${TUNE}-${base%.mxl}.abc"
        mxl2abc "$m" "$abc"
        bars=$(grep -oc '|' "$abc" 2>/dev/null || echo "?")
        echo "  $base → $abc  (~$bars barlines)"
    done
    if [[ -n "$FORCE_MVT" ]]; then
        SRC="$TDIR/clean.mvt${FORCE_MVT}.mxl"
        [[ -f "$SRC" ]] || { echo "No movement $FORCE_MVT"; exit 1; }
        mxl2abc "$SRC" "$FINAL_ABC"
        echo "→ final = mvt${FORCE_MVT} (forced): $FINAL_ABC"
    else
        # Default: merge ALL movements, in order, into one candidate so a tune
        # split across movements stays whole. Override with --mvt N when a later
        # movement is genuinely a stray fragment or alternate you don't want.
        MERGED="$TDIR/clean.merged.mxl"
        "$VENV" "${HERE}/merge_movements.py" "$MERGED" "${MVTS[@]}"
        mxl2abc "$MERGED" "$FINAL_ABC"
        echo "→ final = merged ${#MVTS[@]} movements: $FINAL_ABC"
    fi
else
    mxl2abc "$TDIR/clean.mxl" "$FINAL_ABC"
    echo "→ final: $FINAL_ABC"
fi

DRAFT_ABC="${PIPELINE_DIR}/abc/${TUNE}-draft.abc"
if [[ -f "$DRAFT_ABC" ]]; then
    echo "  Normalizing linebreaks to match scan layout..."
    "$VENV" "${HERE}/normalize_linebreaks.py" "$FINAL_ABC" "$DRAFT_ABC"
fi

RENDER="${PIPELINE_DIR}/renders/${TUNE}-candidate.render.png"
bash "${HERE}/render_abc.sh" "$FINAL_ABC" "$RENDER" 2>&1 | tail -1

KEY=$(grep -m1 '^K:' "$FINAL_ABC" | sed 's/^K://;s/ //g')
METER=$(grep -m1 '^M:' "$FINAL_ABC" | sed 's/^M://;s/ //g')
BARS=$(grep -oP '\|' "$FINAL_ABC" | wc -l || true)
echo "  Key=$KEY  Meter=$METER  ~$BARS barlines  →  $RENDER"

echo ""
echo "── Validation ──────────────────────────────────────────"
"$VENV" "${HERE}/validate_abc.py" "$TUNE" || true
echo "────────────────────────────────────────────────────────"
