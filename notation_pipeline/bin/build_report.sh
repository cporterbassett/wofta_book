#!/usr/bin/env bash
# Build an HTML comparison page: every finalized tune (abc/<Tune>-candidate|verified.abc)
# shown as original scan above its engraved final render.
# Re-run anytime to pick up newly finalized tunes.
#
# Output: finalized_report.html  (open with: firefox finalized_report.html &)

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
cd "$PIPELINE_DIR"
mkdir -p reports

OUT="reports/finalized_report.html"
# img src paths are relative to reports/ (one level under PIPELINE_DIR):
ORIG_DIR="../../source_images"   # scans, from reports/ (for <img src>)
RENDER_DIR="../renders"          # renders, from reports/ (for <img src>)
# absolute scan dir for the -f existence test (CWD here is PIPELINE_DIR, not reports/):
SCAN_ABS_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)/source_images"

shopt -s nullglob
FINALS=(abc/*-verified.abc abc/*-candidate.abc)
shopt -u nullglob

{
echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
echo '<title>WOFTA — Finalized Tunes</title>'
cat <<'CSS'
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; background:#f4f4f4; color:#222; }
  header { background:#222; color:#fff; padding:14px 24px; position:sticky; top:0; z-index:10; }
  header h1 { margin:0; font-size:18px; font-weight:600; }
  header .count { opacity:.7; font-weight:400; }
  nav { padding:10px 24px; background:#fff; border-bottom:1px solid #ddd; font-size:14px; }
  nav a { margin-right:14px; color:#06c; text-decoration:none; white-space:nowrap; }
  .tune { background:#fff; margin:20px 24px; padding:16px 20px; border:1px solid #ddd; border-radius:8px; }
  .tune h2 { margin:0 0 12px; font-size:20px; }
  .pair { display:flex; gap:18px; align-items:flex-start; }
  .pane { flex:1 1 0; min-width:0; }
  .pane .label { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:#888; margin-bottom:4px; }
  .pane.scan .label::after  { content:" — original"; color:#bbb; }
  .pane.final .label::after { content:" — engraved from final ABC"; color:#bbb; }
  img { max-width:100%; height:auto; display:block; border:1px solid #eee; background:#fff; }
  @media (max-width: 900px) { .pair { flex-direction:column; } }
  .missing { color:#b00; font-style:italic; padding:8px; }
</style>
CSS
echo '</head><body>'
printf '<header><h1>WOFTA — Finalized Tunes <span class="count">(%s)</span></h1></header>\n' "${#FINALS[@]}"

# nav
echo '<nav>'
for abc in "${FINALS[@]}"; do
  base="$(basename "$abc")"
  if [[ "$base" == *-verified.abc ]]; then tune="${base%-verified.abc}"; tier="verified";
  else tune="${base%-candidate.abc}"; tier="candidate"; fi
  anchor="$(echo "$tune" | tr -c 'A-Za-z0-9' '-')"
  printf '<a href="#%s">%s</a>\n' "$anchor" "$tune"
done
echo '</nav>'

for abc in "${FINALS[@]}"; do
  base="$(basename "$abc")"
  if [[ "$base" == *-verified.abc ]]; then tune="${base%-verified.abc}"; tier="verified";
  else tune="${base%-candidate.abc}"; tier="candidate"; fi
  anchor="$(echo "$tune" | tr -c 'A-Za-z0-9' '-')"
  orig="${ORIG_DIR}/${tune}.png"                               # relative, for <img src>
  orig_abs="${SCAN_ABS_DIR}/${tune}.png"                       # absolute, for -f test
  render="${PIPELINE_DIR}/renders/${tune}-${tier}.render.png"   # absolute, for -f test + convert input
  trim="${PIPELINE_DIR}/renders/${tune}-${tier}.trim.png"       # absolute, for convert output
  rel_trim="${RENDER_DIR}/${tune}-${tier}.trim.png"             # relative, for <img src>

  # Trim whitespace off the render for a tight comparison (fall back to render).
  if [[ -f "$render" ]]; then
    convert "$render" -trim +repage -bordercolor white -border 12 "$trim" 2>/dev/null || cp "$render" "$trim"
    showrender="$trim"
  else
    showrender=""
  fi

  printf '<section class="tune" id="%s"><h2>%s <small>[%s]</small></h2><div class="pair">\n' "$anchor" "$tune" "$tier"
  if [[ -f "$orig_abs" ]]; then
    printf '<div class="pane scan"><div class="label">Scan</div><img src="%s" alt="scan"></div>\n' "$orig"
  else
    printf '<div class="missing">original scan not found at %s</div>\n' "$orig"
  fi
  if [[ -n "$showrender" ]]; then
    printf '<div class="pane final"><div class="label">Final</div><img src="%s" alt="final"></div>\n' "$rel_trim"
  else
    printf '<div class="missing">no render found for %s</div>\n' "$tune"
  fi
  echo '</div></section>'
done

echo '</body></html>'
} > "$OUT"

echo "Wrote $OUT (${#FINALS[@]} tunes)"
