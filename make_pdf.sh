#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-"$SCRIPT_DIR/WOFTA_tunes.pdf"}"
HTML_OUTPUT="${OUTPUT%.pdf}_verified.html"

cd "$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/make_pdf.py" "$OUTPUT"

firefox "$HTML_OUTPUT" &
firefox "$OUTPUT" &
