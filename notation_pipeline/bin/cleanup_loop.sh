#!/usr/bin/env bash
# Phase 2 cleanup loop: open each tune's cleaned .omr in Audiveris GUI,
# wait for the user to fix and export, then convert the exported MXL to ABC.
#
# Export location: when saving from the GUI, export MXL into the tune's
# batch_output directory so this script can find it automatically.
# The script will remind you of the expected path before opening the GUI.
#
# Usage (from anywhere):
#   bash cleanup_loop.sh                    # all tunes with a clean.omr
#   bash cleanup_loop.sh "Tune Name" ...    # specific tune(s)
#   bash cleanup_loop.sh --list             # list tunes queued for cleanup
#
# Output:
#   abc/<Tune Name>-final.abc   (after GUI export + conversion)

set -euo pipefail

IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
BATCH_DIR="${PIPELINE_DIR}/batch_output"
HEALTH_TSV="${PIPELINE_DIR}/health_scores.tsv"
VENV="${IMAGES_DIR}/.venv/bin/python3"
AUDIVERIS="flatpak run org.audiveris.audiveris"

# ── Argument handling ─────────────────────────────────────────────────────────

LIST_ONLY=0
SPECIFIC_TUNES=()

for arg in "$@"; do
    if [[ "$arg" == "--list" ]]; then
        LIST_ONLY=1
    else
        SPECIFIC_TUNES+=("$arg")
    fi
done

# ── Build the queue ───────────────────────────────────────────────────────────

if [[ ${#SPECIFIC_TUNES[@]} -gt 0 ]]; then
    QUEUE=("${SPECIFIC_TUNES[@]}")
else
    # All tunes with a clean.omr, ordered WORST-FIRST by health_scores.tsv (which
    # is already sorted worst-first). Tunes missing from the TSV are appended
    # alphabetically so nothing is dropped.
    mapfile -t HAVE_OMR < <(
        find "$BATCH_DIR" -maxdepth 2 -name "clean.omr" \
            | sed 's|.*/batch_output/||; s|/clean.omr||' \
            | sort
    )
    declare -A HAS_OMR=()
    for t in "${HAVE_OMR[@]}"; do HAS_OMR["$t"]=1; done

    QUEUE=()
    declare -A QUEUED=()
    if [[ -f "$HEALTH_TSV" ]]; then
        while IFS=$'\t' read -r tune _; do
            [[ -n "${HAS_OMR[$tune]:-}" ]] || continue
            QUEUE+=("$tune"); QUEUED["$tune"]=1
        done < <(tail -n +2 "$HEALTH_TSV")
    fi
    for t in "${HAVE_OMR[@]}"; do
        [[ -n "${QUEUED[$t]:-}" ]] || QUEUE+=("$t")
    done
fi

if [[ ${#QUEUE[@]} -eq 0 ]]; then
    echo "No tunes queued for cleanup (no batch_output/*/clean.omr found)."
    echo "Run batch_all.sh first."
    exit 0
fi

if [[ $LIST_ONLY -eq 1 ]]; then
    echo "Tunes queued for cleanup (${#QUEUE[@]} total):"
    for TUNE in "${QUEUE[@]}"; do
        FINAL="${PIPELINE_DIR}/abc/${TUNE}-final.abc"
        STATUS="pending"
        [[ -f "$FINAL" ]] && STATUS="done"
        printf "  [%-7s] %s\n" "$STATUS" "$TUNE"
    done
    exit 0
fi

# ── Main loop ─────────────────────────────────────────────────────────────────

TOTAL=${#QUEUE[@]}
IDX=0

for TUNE in "${QUEUE[@]}"; do
    (( IDX++ )) || true
    TUNE_DIR="${BATCH_DIR}/${TUNE}"
    CLEAN_OMR="${TUNE_DIR}/clean.omr"
    FINAL_ABC="${PIPELINE_DIR}/abc/${TUNE}-final.abc"
    EXPORT_DIR="$TUNE_DIR"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[$IDX/$TOTAL] $TUNE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [[ -f "$FINAL_ABC" ]]; then
        echo "Already done (final ABC exists). Press Enter to redo, or Ctrl+C to skip."
        read -r || true
    fi

    if [[ ! -f "$CLEAN_OMR" ]]; then
        echo "WARNING: clean.omr not found at $CLEAN_OMR — skipping"
        continue
    fi

    echo ""
    echo "When saving, export MXL to:"
    echo "  $EXPORT_DIR"
    echo ""
    echo "Opening Audiveris GUI... (close the window when done)"
    echo ""

    # Record MXL files present before opening GUI
    mapfile -t BEFORE_MXLS < <(find "$EXPORT_DIR" -maxdepth 1 -name "*.mxl" 2>/dev/null | sort)

    $AUDIVERIS "$CLEAN_OMR" 2>/dev/null || true

    echo "Audiveris closed. Looking for exported MXL..."

    # Find MXL files added after GUI closed
    mapfile -t AFTER_MXLS < <(find "$EXPORT_DIR" -maxdepth 1 -name "*.mxl" 2>/dev/null | sort)

    NEW_MXL=""
    for mxl in "${AFTER_MXLS[@]}"; do
        found=0
        for old in "${BEFORE_MXLS[@]}"; do
            [[ "$mxl" == "$old" ]] && found=1 && break
        done
        if [[ $found -eq 0 ]]; then
            NEW_MXL="$mxl"
            break
        fi
    done

    # If no new MXL in the tune dir, check if user saved a raw MXL with a known name pattern
    # (e.g., Audiveris may name it after the .omr file, which is "clean")
    if [[ -z "$NEW_MXL" ]]; then
        CANDIDATE="${EXPORT_DIR}/clean.mxl"
        # Check if it's newer than clean.omr (i.e., freshly written by GUI)
        if [[ -f "$CANDIDATE" ]] && [[ "$CANDIDATE" -nt "$CLEAN_OMR" ]]; then
            NEW_MXL="$CANDIDATE"
        fi
    fi

    if [[ -z "$NEW_MXL" ]]; then
        echo ""
        echo "No new MXL found in: $EXPORT_DIR"
        echo "Options:"
        echo "  1) Enter the path to the exported MXL manually"
        echo "  2) Press Enter to skip this tune"
        echo ""
        read -r -p "MXL path (or Enter to skip): " MANUAL_PATH
        if [[ -n "$MANUAL_PATH" && -f "$MANUAL_PATH" ]]; then
            NEW_MXL="$MANUAL_PATH"
        else
            echo "Skipping $TUNE."
            continue
        fi
    fi

    echo "Found: $NEW_MXL"

    # Clean the exported MXL (strip residual slurs/decorations from user-exported file)
    CLEANED_MXL="${EXPORT_DIR}/exported_clean.mxl"
    "$VENV" "${PIPELINE_DIR}/clean_mxl.py" "$NEW_MXL" "$CLEANED_MXL"

    # Convert to ABC (use env vars to avoid quoting issues with apostrophes in tune names)
    mkdir -p "${PIPELINE_DIR}/abc"
    MXL_IN="$CLEANED_MXL" ABC_OUT="$FINAL_ABC" "$VENV" -c "
import os
from abc_xml_converter import convert_xml2abc
result = convert_xml2abc(file_to_convert=os.environ['MXL_IN'], output_directory='')
open(os.environ['ABC_OUT'], 'w').write(result)
" 2>/dev/null

    if [[ ! -s "$FINAL_ABC" ]]; then
        echo "ERROR: ABC conversion produced empty file — check $CLEANED_MXL"
        rm -f "$FINAL_ABC"
        continue
    fi

    KEY=$(grep -m1 '^K:' "$FINAL_ABC" | sed 's/^K://' | tr -d ' ' || echo "?")
    METER=$(grep -m1 '^M:' "$FINAL_ABC" | sed 's/^M://' | tr -d ' ' || echo "?")
    BARS=$(grep -oP '\|' "$FINAL_ABC" | wc -l || echo "?")
    echo "→ $FINAL_ABC"
    echo "  Key=${KEY}  Meter=${METER}  ~${BARS} barlines"

    echo ""
    echo "── Validation ──────────────────────────────────────────"
    "$VENV" "${PIPELINE_DIR}/validate_final.py" "$TUNE" || true
    echo "────────────────────────────────────────────────────────"

    echo ""
    echo "Press Enter for next tune (or Ctrl+C to stop)..."
    read -r || break
done

echo ""
echo "Cleanup loop complete. Processed $IDX/$TOTAL tunes."
