#!/usr/bin/env bash
# Claude-free per-tune verify pipeline.
#
# A standalone reimplementation of the per-tune verify workflow that previously
# only existed as a Claude-driven background task. Pure orchestration over the
# existing pipeline scripts — no Claude, no chord auto-transcription (you add
# chords by hand in EasyABC).
#
# Flow:
#   1. Open the cleaned OMR in the Audiveris GUI (maximized) + the raw scan in
#      Firefox for reference. Block until Audiveris closes.
#   2. export_tune.sh  → candidate ABC + render.
#   3. Force the canonical title T:<Tune>, re-render (all mechanical fixes happen
#      BEFORE EasyABC — when it opens you only do musical edits).
#   4. Open a LIVE side-by-side compare in Firefox (auto-refreshing page) and the
#      candidate ABC in EasyABC. A background watcher rebuilds the compare every
#      time you SAVE in EasyABC, so you see edits without closing it.
#   5. On EasyABC close: prompt "Promote & commit? [y/N]".
#
# Usage:
#   bash verify_tune.sh                 # auto-pick the next tune (worst-first)
#   bash verify_tune.sh "Tune Name"     # a specific tune
#   bash verify_tune.sh --skip          # park the current auto-pick, run the next
#   bash verify_tune.sh --skip "Tune"   # park a named tune, run the next
#
# Parked tunes live in notation_pipeline/verify_skip.txt (one name per line) and
# are stepped over by auto-pick until you remove them (e.g. `vi` the file).
#
# Linux/Mint-bound (flatpak Audiveris, wmctrl, easyabc, firefox).

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"          # notation_pipeline/
IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"    # tune_images/
AUDIVERIS="flatpak run org.audiveris.audiveris"
HEALTH_TSV="${PIPELINE_DIR}/health_scores.tsv"
SKIP_FILE="${PIPELINE_DIR}/verify_skip.txt"

is_skipped() {  # $1=tune — true if parked in the skip list
    [[ -f "$SKIP_FILE" ]] && grep -qxF "$1" "$SKIP_FILE"
}

# Next tune to verify: worst-first (health_scores.tsv is sorted worst-first),
# must have a clean.omr, not already verified, not parked. Prints the name, or
# returns non-zero if none remain.
pick_next_tune() {
    [[ -f "$HEALTH_TSV" ]] || return 1
    local tune
    while IFS=$'\t' read -r tune _; do
        [[ -n "$tune" ]] || continue
        [[ -f "${PIPELINE_DIR}/batch_output/${tune}/clean.omr" ]] || continue
        [[ -f "${PIPELINE_DIR}/abc/${tune}-verified.abc" ]] && continue
        is_skipped "$tune" && continue
        printf '%s\n' "$tune"
        return 0
    done < <(tail -n +2 "$HEALTH_TSV" | cut -f1)
    return 1
}

# ── Argument parsing: optional --skip, optional tune name ─────────────────────
DO_SKIP=0
MVT=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip) DO_SKIP=1; shift ;;
        --mvt)  MVT="${2:?--mvt needs a movement number}"; shift 2 ;;
        *)      ARGS+=("$1"); shift ;;
    esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}

if [[ $DO_SKIP -eq 1 ]]; then
    # Park the named tune, or (no name) whatever auto-pick would have chosen.
    if [[ $# -ge 1 ]]; then SKIP_TUNE="$1"; else SKIP_TUNE="$(pick_next_tune || true)"; fi
    if [[ -n "$SKIP_TUNE" ]]; then
        is_skipped "$SKIP_TUNE" || printf '%s\n' "$SKIP_TUNE" >> "$SKIP_FILE"
        echo "Parked '$SKIP_TUNE' in $SKIP_FILE — auto-pick will skip it."
    fi
    set --   # clear args so we fall through to auto-pick the NEXT tune
fi

# Tune name is optional: with no argument, auto-pick the next one to verify.
if [[ $# -ge 1 ]]; then
    TUNE="$1"
else
    TUNE="$(pick_next_tune)" || {
        echo "No unverified tune with a clean.omr left to do." >&2
        exit 1
    }
    echo "Auto-selected next tune (worst-first): $TUNE"
fi

CLEAN_OMR="${PIPELINE_DIR}/batch_output/${TUNE}/clean.omr"
CAND_ABC="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
RENDER="${PIPELINE_DIR}/renders/${TUNE}-candidate.render.png"
SCAN="${IMAGES_DIR}/source_images/${TUNE}.png"

# Safe slug for /tmp filenames (avoids spaces/apostrophes in file:// URLs).
SLUG="$(printf '%s' "$TUNE" | tr -c 'A-Za-z0-9' '_')"
COMPARE_PNG="/tmp/${SLUG}.compare.png"
COMPARE_HTML="/tmp/${SLUG}.compare.html"

# ── Precondition ──────────────────────────────────────────────────────────────
if [[ ! -f "$CLEAN_OMR" ]]; then
    echo "No clean.omr for '$TUNE' at:" >&2
    echo "  $CLEAN_OMR" >&2
    echo "Run phase-1 OMR first:" >&2
    echo "  bash ${HERE}/batch_tune.sh \"$TUNE\"" >&2
    exit 1
fi

build_compare() {  # (re)build the side-by-side compare PNG from the current render
    bash "${HERE}/render_abc.sh" "$CAND_ABC" "$RENDER" >/dev/null 2>&1 || return 1
    bash "${HERE}/make_compare.sh" "$SCAN" "$RENDER" "$COMPARE_PNG" >/dev/null 2>&1 || return 1
}

# ── Step 1: Audiveris review ──────────────────────────────────────────────────
# Skipped when --mvt N is given: the OMR was already corrected + saved on the
# first pass, so re-picking a movement just re-exports — no need to redo the GUI.
if [[ -z "$MVT" ]]; then
    echo "Opening Audiveris on clean.omr (close the window when corrections are done)..."
    $AUDIVERIS "$CLEAN_OMR" >/dev/null 2>&1 &
    APID=$!
    # Maximize the Audiveris window once it appears.
    ( for _ in $(seq 1 30); do
          wmctrl -l 2>/dev/null | grep -qi audiveris && {
              wmctrl -r Audiveris -b add,maximized_vert,maximized_horz; break; }
          sleep 1
      done ) >/dev/null 2>&1 &
    # Open the raw scan for reference during review.
    [[ -f "$SCAN" ]] && firefox "$SCAN" >/dev/null 2>&1 &
    wait "$APID"
    echo "Audiveris closed."
else
    echo "--mvt $MVT given — skipping Audiveris re-open; re-exporting from the saved clean.omr."
fi

# ── Step 2: Export ────────────────────────────────────────────────────────────
echo "Exporting → candidate ABC..."
if ! bash "${HERE}/export_tune.sh" "$TUNE" ${MVT:+--mvt "$MVT"}; then
    echo "" >&2
    echo "export_tune.sh did not finish." >&2
    if [[ -z "$MVT" ]]; then
        echo "If it reported a MOVEMENT SPLIT: inspect the per-movement ABCs it listed," >&2
        echo "then re-run picking the movement (no need to redo Audiveris):" >&2
        echo "  bash ${HERE}/$(basename "${BASH_SOURCE[0]}") \"$TUNE\" --mvt 1" >&2
    else
        echo "Resolve the error above, then re-run." >&2
    fi
    exit 2
fi

# ── Step 3: Mechanical title fix (BEFORE EasyABC) ─────────────────────────────
# Force the canonical title. Pass $TUNE via the ENVIRONMENT — never interpolate
# into the source (an apostrophe like "Devil's Dream" would break the literal).
echo "Forcing canonical title T:${TUNE} ..."
TUNE="$TUNE" ABC="$CAND_ABC" "${IMAGES_DIR}/.venv/bin/python3" - <<'PY'
import os, re
t = os.environ['TUNE']
f = os.environ['ABC']
txt = open(f).read()
if re.search(r'^T:', txt, re.MULTILINE):
    txt = re.sub(r'^T:.*$', 'T:' + t, txt, count=1, flags=re.MULTILINE)
else:
    txt = re.sub(r'^(X:\d+\n)', r'\g<1>T:' + t + '\n', txt, count=1, flags=re.MULTILINE)
open(f, 'w').write(txt)
PY

# ── Step 4: Live compare + EasyABC ────────────────────────────────────────────
echo "Building initial compare..."
build_compare || echo "  (compare build had a hiccup — continuing)"

# Auto-refreshing page: the <img> reloads itself with a cache-buster so saves
# show up without piling new Firefox tabs. img src is the basename (same dir).
cat > "$COMPARE_HTML" <<HTML
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>${TUNE} — compare</title>
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

# Background watcher: poll the candidate ABC's mtime (no inotify dependency) and
# rebuild the compare on every save from EasyABC.
(
    last=$(stat -c %Y "$CAND_ABC" 2>/dev/null || echo 0)
    while sleep 1; do
        now=$(stat -c %Y "$CAND_ABC" 2>/dev/null || echo 0)
        if [[ "$now" != "$last" ]]; then
            last="$now"
            build_compare
        fi
    done
) &
WATCHER=$!
# Make sure the watcher dies with us no matter how we exit.
trap 'kill "$WATCHER" 2>/dev/null' EXIT

echo "Opening EasyABC — edit notes/chords; SAVE to refresh the compare; CLOSE when done."
easyabc "$CAND_ABC"

# ── Step 5: EasyABC closed → stop watcher, final rebuild, promote gate ────────
kill "$WATCHER" 2>/dev/null
trap - EXIT
echo "EasyABC closed. Rebuilding final compare..."
build_compare || true

echo ""
read -r -p "Promote & commit \"${TUNE}\"? [y/N] " ans
if [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; then
    git -C "$IMAGES_DIR" add "$CAND_ABC" \
        && bash "${HERE}/promote_tune.sh" "$TUNE" \
        && git -C "$IMAGES_DIR" add "${PIPELINE_DIR}/abc/${TUNE}-verified.abc" \
        && git -C "$IMAGES_DIR" commit -m "feat: verify ${TUNE}" \
        && echo "Promoted + committed: ${TUNE}"
else
    echo "Left as candidate. Promote later with:"
    echo "  git add \"$CAND_ABC\" && bash ${HERE}/promote_tune.sh \"$TUNE\" \\"
    echo "    && git add \"${PIPELINE_DIR}/abc/${TUNE}-verified.abc\" \\"
    echo "    && git commit -m \"feat: verify ${TUNE}\""
fi
