#!/usr/bin/env bash
# Full pipeline for one tune: transcribe → render → diff
#
# Usage: process_tune.sh "Booth Shot Lincoln.png"
#
# Outputs (in abc/ and renders/ subdirs):
#   abc/<stem>.abc
#   renders/<stem>.render.png
#   diffs/<stem>.diff.png
#
# Requires: abcm2ps, ghostscript, python3 (with anthropic + opencv in .venv)

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: process_tune.sh <tune.png>" >&2
    exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY is not set." >&2
    exit 1
fi

PNG="$1"
STEM="${PNG%.png}"
STEM="${STEM##*/}"   # basename without extension

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv/bin/python3"

mkdir -p "$DIR/abc" "$DIR/renders" "$DIR/diffs"

ABC="$DIR/abc/${STEM}.abc"
RENDER="$DIR/renders/${STEM}.render.png"
DIFF="$DIR/diffs/${STEM}.diff.png"

echo "=== $STEM ==="

# Step 1: Transcribe (skip if .abc already exists)
if [[ -f "$ABC" ]]; then
    echo "  [skip] $ABC already exists"
else
    "$VENV" "$DIR/transcribe.py" "$PNG" "$ABC"
fi

# Step 2: Render
"$DIR/render_abc.sh" "$ABC" "$RENDER"

# Step 3: Diff overlay
"$VENV" "$DIR/overlay_diff.py" "$PNG" "$RENDER" "$DIFF"

echo "  Done. Open diff: firefox '$DIFF' &"
