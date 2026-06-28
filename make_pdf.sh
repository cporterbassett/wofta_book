#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_OUTPUT="${1:-"$SCRIPT_DIR/output/WOFTA_tunes.pdf"}"
COMP_OUTPUT="${MAIN_OUTPUT%.pdf}_comparison.pdf"

mkdir -p "$SCRIPT_DIR/output"
cd "$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/book/make_wofta.py" "$MAIN_OUTPUT"

# 1. full book (engraved preferred, sepia, with table of contents)
# 2. portrait scan-vs-engraved comparison (packed multiple tunes per page)
firefox "$MAIN_OUTPUT" &
firefox "$COMP_OUTPUT" &
