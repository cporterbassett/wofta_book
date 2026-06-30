#!/usr/bin/env bash
# Build WOFTA_tunes_comparison.pdf (portrait scan-vs-engraved, packed multiple
# tunes per page, in CREATION order) into output/ and open it in Firefox.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMP="${1:-"$ROOT/output/WOFTA_tunes_comparison.pdf"}"

mkdir -p "$ROOT/output"
cd "$ROOT"
"$ROOT/.venv/bin/python3" "$ROOT/book/make_comparison.py" "$COMP"

firefox "$COMP" &
