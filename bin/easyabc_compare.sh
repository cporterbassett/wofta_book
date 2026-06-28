#!/usr/bin/env bash
# Open a tune's candidate ABC in EasyABC; when EasyABC is CLOSED, regenerate the
# side-by-side source/engraved comparison and display it in Firefox.
#
# This enforces Porter's SOP (2026-06-22): whenever a file is opened in EasyABC,
# closing it must generate + display a fresh comparison.
#
# Usage:  easyabc_compare.sh "Tune Name"
# Run it with run_in_background:true — it blocks on EasyABC internally, then builds
# the compare on close.
set -uo pipefail

TUNE="${1:?Usage: easyabc_compare.sh \"Tune Name\"}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"            # repo root (tune_images/)
IMAGES="${ROOT}"                            # tune_images/ — same as ROOT after reorg
ABC="${ROOT}/abc/${TUNE}-candidate.abc"
REN="${ROOT}/scratch/renders/${TUNE}-candidate.render.png"
SRC="${IMAGES}/sources/scans/${TUNE}.png"
CMP="/tmp/${TUNE} - compare.png"

easyabc "$ABC"                              # foreground — blocks until the window closes

# ── EasyABC closed → regenerate + display the comparison ──────────────────────
bash "${HERE}/render_abc.sh" "$ABC" "$REN" >/dev/null 2>&1 || true
# -trim so the music fills the frame (render is a mostly-blank letter page);
# match heights; +append = SIDE-BY-SIDE (source left, sepia engraved right).
convert "$REN" -trim +repage -sepia-tone 80% -resize x1700 /tmp/cmp_ren.png
convert "$SRC" -trim +repage -resize x1700 /tmp/cmp_src.png
convert /tmp/cmp_src.png /tmp/cmp_ren.png +append -background white -bordercolor white -border 15 "$CMP"
firefox "$CMP" >/dev/null 2>&1 &
echo "EasyABC closed → regenerated compare: $CMP"
