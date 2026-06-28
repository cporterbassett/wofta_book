#!/usr/bin/env bash
# Build WOFTA_tunes.pdf (+ _comparison.pdf) into output/ and open both in Firefox.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-"$ROOT/output/WOFTA_tunes.pdf"}"
COMP="${OUT%.pdf}_comparison.pdf"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$ROOT/.venv/bin/python3" "$ROOT/book/make_wofta.py" "$OUT"

# 1. full book (engraved preferred, sepia, with table of contents)
# 2. portrait scan-vs-engraved comparison (packed multiple tunes per page)
firefox "$OUT" &
firefox "$COMP" &
