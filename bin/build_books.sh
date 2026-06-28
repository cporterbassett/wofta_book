#!/usr/bin/env bash
# Build all three books into output/. Does NOT open anything (use the
# per-book scripts if you want the result opened in Firefox).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python3"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$PY" "$ROOT/book/make_wofta.py" "$ROOT/output/WOFTA_tunes.pdf"
"$PY" "$ROOT/book/make_tin_whistle_pdf.py" "$ROOT/output/Tin Whistle.pdf"
"$PY" "$ROOT/book/make_sand_and_sawdust_pdf.py" "$ROOT/output/Sand and Sawdust 2026.pdf"
echo "Built 3 books into $ROOT/output/"
