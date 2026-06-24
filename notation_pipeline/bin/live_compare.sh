#!/usr/bin/env bash
# Live auto-refreshing side-by-side compare for the verify loop.
#
# Builds a source-vs-render compare PNG, writes a self-refreshing HTML page that
# reloads the PNG every 1.5s (so external EasyABC saves show up without piling
# new Firefox tabs), opens it in Firefox, then polls the candidate ABC's mtime
# and rebuilds the compare on every save. Blocks until killed (the caller owns
# the lifecycle — e.g. kills it when EasyABC closes).
#
# Usage: live_compare.sh <candidate_abc> <render_png> <scan_png>
#
# Linux/Mint-bound (firefox, ImageMagick via the pipeline helpers).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CAND_ABC="${1:?usage: live_compare.sh <candidate_abc> <render_png> <scan_png>}"
RENDER="${2:?missing render png path}"
SCAN="${3:?missing scan png path}"

SLUG="$(basename "$CAND_ABC" | tr -c 'A-Za-z0-9' '_')"
COMPARE_PNG="/tmp/${SLUG}.compare.png"
COMPARE_HTML="/tmp/${SLUG}.compare.html"

build_compare() {  # (re)build the side-by-side compare from the current render
    bash "${HERE}/render_abc.sh" "$CAND_ABC" "$RENDER" >/dev/null 2>&1 || return 1
    bash "${HERE}/make_compare.sh" "$SCAN" "$RENDER" "$COMPARE_PNG" >/dev/null 2>&1 || return 1
}

build_compare || echo "  (initial compare build had a hiccup — continuing)"

cat > "$COMPARE_HTML" <<HTML
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>$(basename "$CAND_ABC") — compare</title>
<style>body{margin:0;background:#222;text-align:center}
img{display:inline-block;max-width:100%;height:auto}</style>
</head><body>
<img id="c" src="${SLUG}.compare.png" alt="compare">
<script>
setInterval(function(){
  document.getElementById('c').src='${SLUG}.compare.png?t='+Date.now();
}, 1500);
</script></body></html>
HTML
firefox "$COMPARE_HTML" >/dev/null 2>&1 &

# Rebuild on every save (mtime poll — no inotify dependency).
trap 'exit 0' INT TERM
last=$(stat -c %Y "$CAND_ABC" 2>/dev/null || echo 0)
while sleep 1; do
    now=$(stat -c %Y "$CAND_ABC" 2>/dev/null || echo 0)
    if [[ "$now" != "$last" ]]; then
        last="$now"
        build_compare
    fi
done
