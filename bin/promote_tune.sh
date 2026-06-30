#!/usr/bin/env bash
# Promote a tune from -candidate to -verified: the human sign-off gesture.
# After you've eyeballed the engraving against the scan (and edited the
# -candidate.abc if needed), run this to publish it into the book.
#
# Usage: promote_tune.sh "Tune Name"
#
# Effect:
#   abc/<Tune>-candidate.abc  ->  abc/<Tune>-verified.abc   (git mv)
#   re-renders renders/<Tune>-verified.render.png
#   re-runs validate_abc.py as a final sanity check (advisory)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
IMAGES_DIR="${PIPELINE_DIR}"
VENV="${IMAGES_DIR}/.venv/bin/python3"

TUNE="${1:?usage: promote_tune.sh \"Tune Name\"}"
CAND="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
VERIFIED="${PIPELINE_DIR}/abc/${TUNE}-verified.abc"

if [[ ! -f "$CAND" ]]; then
    echo "No candidate to promote: $CAND" >&2
    exit 1
fi

# Use -f so a re-promotion (verified already exists from an earlier sign-off)
# overwrites the old engraving instead of failing. Without -f, git mv refuses
# to clobber an existing destination; under the verify pipeline that failure was
# swallowed, leaving the candidate in place and the verified file stale — which
# silently lost re-edited work.
if [[ -f "$VERIFIED" ]]; then
    echo "Re-promoting: overwriting existing ${TUNE}-verified.abc"
fi
git -C "$IMAGES_DIR" mv -f "$CAND" "$VERIFIED"
echo "Promoted: ${TUNE} -> -verified.abc"

RENDER="${PIPELINE_DIR}/scratch/renders/${TUNE}-verified.render.png"
bash "${HERE}/render_abc.sh" "$VERIFIED" "$RENDER" 2>&1 | tail -1
# clean up the now-stale candidate render if present
rm -f "${PIPELINE_DIR}/scratch/renders/${TUNE}-candidate.render.png" \
      "${PIPELINE_DIR}/scratch/renders/${TUNE}-candidate.trim.png"

"$VENV" "${HERE}/validate_abc.py" "$TUNE" || true
echo "Run build_tracking_sheet.py and build_report.sh to refresh the ledger/report."

# Progress summary (against the authoritative book roster)
WOFTA_LIST="${PIPELINE_DIR}/book/wofta_tunes.txt"
TOTAL=$(grep -v '^\s*#' "$WOFTA_LIST" | grep -c '\S' || true)
DONE=$(grep -v '^\s*#' "$WOFTA_LIST" | grep '\S' | while IFS= read -r name; do
    if [[ -f "${PIPELINE_DIR}/abc/${name}-verified.abc" ]]; then echo y; fi
done | wc -l)
LEFT=$((TOTAL - DONE))
PCT=$(awk -v done="$DONE" -v total="$TOTAL" 'BEGIN { printf "%.1f", done/total*100 }')
echo ""
echo "── WOFTA progress: ${DONE}/${TOTAL} verified (${PCT}%) — ${LEFT} left ──"
