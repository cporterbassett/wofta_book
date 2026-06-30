#!/usr/bin/env bash
# Build WOFTA_tunes.pdf into output/ and open it in Firefox.
# (The scan-vs-engraving comparison PDF is built separately: bin/build_comparison.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-"$ROOT/output/WOFTA_tunes.pdf"}"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$ROOT/.venv/bin/python3" "$ROOT/book/make_wofta.py" "$OUT"

# full book (engraved preferred, sepia, with table of contents)
firefox "$OUT" &
