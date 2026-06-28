#!/usr/bin/env bash
# Build the Tin Whistle book into output/ and open it in Firefox.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-"$ROOT/output/Tin Whistle.pdf"}"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$ROOT/.venv/bin/python3" "$ROOT/book/make_tin_whistle_pdf.py" "$OUT"
firefox "$OUT" &
