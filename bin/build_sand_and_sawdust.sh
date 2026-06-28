#!/usr/bin/env bash
# Build the Sand & Sawdust book into output/ and open it in Firefox.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-"$ROOT/output/Sand and Sawdust 2026.pdf"}"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$ROOT/.venv/bin/python3" "$ROOT/book/make_sand_and_sawdust_pdf.py" "$OUT"
firefox "$OUT" &
