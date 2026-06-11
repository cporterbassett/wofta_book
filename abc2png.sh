#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") input.abc [output.png]" >&2
    exit 1
}

[[ $# -lt 1 ]] && usage

ABC="$1"
BASE="${ABC%.abc}"
LY="${BASE}.ly"
OUTPUT="${2:-${BASE}.png}"

# ABC → LilyPond
abc2ly "$ABC" -o "$LY"

# Patch: abc2ly doesn't set indent=0, causing first staff to be misaligned
python3 - "$LY" <<'EOF'
import re, sys
content = open(sys.argv[1]).read()
content = re.sub(r'(\\version[^\n]*\n)', r'\1\\paper {\n\tindent = 0\n}\n', content, count=1)
open(sys.argv[1], 'w').write(content)
EOF

# LilyPond → cropped PNG
lilypond --png -dresolution=150 -dcrop "$LY"

# Add white border
convert "${BASE}.cropped.png" -bordercolor white -border 20x20 "$OUTPUT"

echo "$OUTPUT"
