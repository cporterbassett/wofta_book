#!/usr/bin/env bash
# Phase 1 batch: run batch_tune.sh over all 269 WOFTA tune PNGs.
# Resumable: tunes with batch_output/<Tune Name>/clean.omr are skipped.
#
# Usage (from anywhere):
#   bash batch_all.sh               # process all unprocessed tunes
#   bash batch_all.sh --dry-run     # print what would run without running
#   SCALE=200 bash batch_all.sh     # override scale for all tunes
#
# Logs per-tune output to batch_output/batch_all.log

set -euo pipefail

IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
BATCH_DIR="${PIPELINE_DIR}/batch_output"
SCRIPT="${PIPELINE_DIR}/batch_tune.sh"
LOG="${BATCH_DIR}/batch_all.log"
DRY_RUN=0

for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=1
done

mkdir -p "$BATCH_DIR"

# Collect the 269 real tune PNGs (exclude test/scratch files)
mapfile -t PNGS < <(
    find "$IMAGES_DIR" -maxdepth 1 -name "*.png" \
        ! -name "*oemer*" \
        ! -name "*cropped*" \
        ! -name "*teaser*" \
        ! -name "*_updated*" \
        | sort
)

TOTAL=${#PNGS[@]}
SKIPPED=0
DONE=0
FAILED=0

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "batch_all.sh — $(date '+%Y-%m-%dT%H:%M')"
echo "Tunes found: $TOTAL"
[[ $DRY_RUN -eq 1 ]] && echo "(DRY RUN — nothing will be executed)"
echo "Log: $LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

{
    echo "batch_all.sh started $(date '+%Y-%m-%dT%H:%M:%S')"
    echo "Scale: ${SCALE:-150}%"
    echo "Total PNGs: $TOTAL"
} >> "$LOG"

for PNG in "${PNGS[@]}"; do
    TUNE=$(basename "$PNG" .png)
    CHECKPOINT="${BATCH_DIR}/${TUNE}/clean.omr"

    if [[ -f "$CHECKPOINT" ]]; then
        echo "SKIP  [$((DONE+SKIPPED+FAILED+1))/$TOTAL] $TUNE"
        (( SKIPPED++ )) || true
        continue
    fi

    echo "RUN   [$((DONE+SKIPPED+FAILED+1))/$TOTAL] $TUNE"

    if [[ $DRY_RUN -eq 1 ]]; then
        continue
    fi

    if bash "$SCRIPT" "$TUNE" >> "$LOG" 2>&1; then
        (( DONE++ )) || true
        echo "  OK" | tee -a "$LOG"
    else
        (( FAILED++ )) || true
        echo "  FAIL — see $LOG for details"
        echo "FAIL: $TUNE" >> "$LOG"
    fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done. Processed: $DONE  Skipped: $SKIPPED  Failed: $FAILED"
{
    echo "batch_all.sh finished $(date '+%Y-%m-%dT%H:%M:%S')"
    echo "Processed: $DONE  Skipped: $SKIPPED  Failed: $FAILED"
} >> "$LOG"
