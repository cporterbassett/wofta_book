#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-"$SCRIPT_DIR/../WOFTA_tunes.pdf"}"

cd "$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/make_pdf.py" "$OUTPUT"
