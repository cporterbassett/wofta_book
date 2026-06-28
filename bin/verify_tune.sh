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
#   bash verify_tune.sh --queue         # auto-pick from verify_queue.txt (in order)
#   bash verify_tune.sh --queue-file F  # auto-pick from a custom queue file
#   bash verify_tune.sh --queue --loop  # walk the whole queue, one tune after another
#   bash verify_tune.sh --queue --list  # print the remaining eligible tunes and exit (no GUI)
#   bash verify_tune.sh --no-export "Tune"  # skip Audiveris AND re-export; reuse the
#                                           # existing candidate ABC (e.g. one you hand-fixed)
#                                           # and go straight to live compare + EasyABC
#   bash verify_tune.sh --export-only "Tune"  # Audiveris + export, then STOP (no
#                                             # title fix, no EasyABC). Seam for an
#                                             # AI cleanup pass; resume with --no-export.
#
# Parked tunes live in verify_skip.txt (one name per line) and
# are stepped over by auto-pick until you remove them (e.g. `vi` the file).
#
# QUEUE MODE: with --queue, auto-pick draws from a queue file (one canonical tune
# name per line; '#' comments and blanks ignored) IN FILE ORDER instead of
# worst-first health order. A tune drops out once its -verified.abc exists.
# --loop re-runs the whole flow for the next queue tune after each one finishes;
# tunes you DON'T promote are remembered for the session (a temp seen-list) so the
# loop advances past them without permanently parking them in verify_skip.txt.
#
# Linux/Mint-bound (flatpak Audiveris, wmctrl, easyabc, firefox).

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"          # repo root (tune_images/)
IMAGES_DIR="${PIPELINE_DIR}"                      # tune_images/ — same as PIPELINE_DIR after reorg
AUDIVERIS="flatpak run org.audiveris.audiveris"
HEALTH_TSV="${PIPELINE_DIR}/health_scores.tsv"
SKIP_FILE="${PIPELINE_DIR}/verify_skip.txt"
DEFAULT_QUEUE="${PIPELINE_DIR}/verify_queue.txt"
QUEUE=""                               # set by --queue / --queue-file
SEEN_FILE="${VERIFY_SEEN_FILE:-}"      # session seen-list (loop mode), via env

is_skipped() {  # $1=tune — true if parked in the skip list
    [[ -f "$SKIP_FILE" ]] && grep -qxF "$1" "$SKIP_FILE"
}

is_seen() {  # $1=tune — true if already handled this loop session
    [[ -n "${SEEN_FILE:-}" && -f "${SEEN_FILE:-}" ]] && grep -qxF "$1" "$SEEN_FILE"
}

eligible() {  # $1=tune — true if it has a clean.omr, isn't verified/skipped/seen
    [[ -n "$1" ]] || return 1
    [[ -f "${PIPELINE_DIR}/scratch/batch_output/${1}/clean.omr" ]] || return 1
    [[ -f "${PIPELINE_DIR}/abc/${1}-verified.abc" ]] && return 1
    is_skipped "$1" && return 1
    is_seen "$1" && return 1
    return 0
}

# Names from the queue file, in file order ('#' comments + blanks stripped).
queue_names() {
    [[ -n "$QUEUE" && -f "$QUEUE" ]] || return 1
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        printf '%s\n' "$line"
    done < "$QUEUE"
}

# Next tune to verify. With a queue: first eligible name in queue order. Without:
# worst-first (health_scores.tsv is sorted worst-first). Prints the name, or
# returns non-zero if none remain.
pick_next_tune() {
    local tune
    if [[ -n "$QUEUE" ]]; then
        while IFS= read -r tune; do
            eligible "$tune" && { printf '%s\n' "$tune"; return 0; }
        done < <(queue_names)
        return 1
    fi
    [[ -f "$HEALTH_TSV" ]] || return 1
    while IFS=$'\t' read -r tune _; do
        eligible "$tune" && { printf '%s\n' "$tune"; return 0; }
    done < <(tail -n +2 "$HEALTH_TSV" | cut -f1)
    return 1
}

# ── Argument parsing: optional --skip/--queue/--loop/--list, optional tune ────
DO_SKIP=0
DO_LIST=0
LOOP=0
MVT=""
NO_EXPORT=0
EXPORT_ONLY=0
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip)        DO_SKIP=1; shift ;;
        --queue)       QUEUE="$DEFAULT_QUEUE"; shift ;;
        --queue-file)  QUEUE="${2:?--queue-file needs a path}"; shift 2 ;;
        --loop)        LOOP=1; shift ;;
        --list)        DO_LIST=1; shift ;;
        --mvt)         MVT="${2:?--mvt needs a movement number}"; shift 2 ;;
        --no-export)   NO_EXPORT=1; shift ;;
        --export-only) EXPORT_ONLY=1; shift ;;
        *)             ARGS+=("$1"); shift ;;
    esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}

if [[ $EXPORT_ONLY -eq 1 && $NO_EXPORT -eq 1 ]]; then
    echo "--export-only and --no-export are opposites; pick one." >&2
    exit 2
fi

# --list / --loop default to the standard queue file when none was named.
if [[ ( $DO_LIST -eq 1 || $LOOP -eq 1 ) && -z "$QUEUE" ]]; then
    QUEUE="$DEFAULT_QUEUE"
fi

# --list: print the remaining eligible tunes (queue order, or worst-first) and exit.
if [[ $DO_LIST -eq 1 ]]; then
    if [[ -z "$QUEUE" && ! -f "$HEALTH_TSV" ]]; then
        echo "No health_scores.tsv at $HEALTH_TSV — run phase-1 scoring, or use --queue." >&2
        exit 1
    fi
    src="${QUEUE:+queue: $QUEUE}"; echo "Remaining verify-eligible tunes (${src:-worst-first}):"
    n=0
    while IFS= read -r tune; do
        if [[ -n "$QUEUE" ]]; then eligible "$tune" || continue
        else IFS=$'\t' read -r tune _ <<<"$tune"; eligible "$tune" || continue; fi
        n=$((n+1)); printf '  %2d. %s\n' "$n" "$tune"
    done < <([[ -n "$QUEUE" ]] && queue_names || tail -n +2 "$HEALTH_TSV" | cut -f1)
    echo "($n eligible)"
    exit 0
fi

# Loop mode: create a per-session seen-list so un-promoted tunes don't re-appear.
if [[ $LOOP -eq 1 && -z "${VERIFY_SEEN_FILE:-}" ]]; then
    export VERIFY_SEEN_FILE="$(mktemp "${TMPDIR:-/tmp}/verify_seen.XXXXXX")"
fi
SEEN_FILE="${VERIFY_SEEN_FILE:-}"

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
        if [[ -n "$QUEUE" ]]; then
            echo "Queue complete — no verify-eligible tunes left in $QUEUE."
            [[ -n "$SEEN_FILE" && -f "$SEEN_FILE" ]] && rm -f "$SEEN_FILE"
            exit 0
        fi
        echo "No unverified tune with a clean.omr left to do." >&2
        exit 1
    }
    echo "Auto-selected next tune (${QUEUE:+queue order}${QUEUE:-worst-first}): $TUNE"
fi

CLEAN_OMR="${PIPELINE_DIR}/scratch/batch_output/${TUNE}/clean.omr"
CAND_ABC="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
VERIFIED_ABC="${PIPELINE_DIR}/abc/${TUNE}-verified.abc"
SCAN="${IMAGES_DIR}/sources/scans/${TUNE}.png"
[[ ! -f "$SCAN" ]] && SCAN="${IMAGES_DIR}/sources/scans/verified/${TUNE}.png"

# Which ABC does this session actually edit?
#   - --no-export on an ALREADY-VERIFIED tune (no candidate present): edit the
#     -verified.abc IN PLACE. No candidate is created or left lying around, so a
#     re-edit can never again silently fail to reach the book.
#   - everything else (a fresh Audiveris export, or a still-unverified draft):
#     the -candidate.abc, promoted to verified on sign-off.
if [[ $NO_EXPORT -eq 1 && -f "$VERIFIED_ABC" && ! -f "$CAND_ABC" ]]; then
    EDIT_ABC="$VERIFIED_ABC"; EDITING_VERIFIED=1
    RENDER="${PIPELINE_DIR}/scratch/renders/${TUNE}-verified.render.png"
else
    EDIT_ABC="$CAND_ABC"; EDITING_VERIFIED=0
    RENDER="${PIPELINE_DIR}/scratch/renders/${TUNE}-candidate.render.png"
fi

# Safe slug for /tmp filenames (avoids spaces/apostrophes in file:// URLs).
SLUG="$(basename "$EDIT_ABC" | tr -c 'A-Za-z0-9' '_')"
COMPARE_PNG="/tmp/${SLUG}.compare.png"

# ── Precondition ──────────────────────────────────────────────────────────────
if [[ $NO_EXPORT -eq 1 ]]; then
    # Reusing existing ABC — no Audiveris/export, so clean.omr isn't needed, but
    # the file to edit (verified if present, else candidate) must already exist.
    if [[ ! -f "$EDIT_ABC" ]]; then
        echo "No verified or candidate ABC for '$TUNE' at:" >&2
        echo "  $EDIT_ABC" >&2
        echo "--no-export reuses an existing ABC; run a normal verify pass first." >&2
        exit 1
    fi
elif [[ ! -f "$CLEAN_OMR" ]]; then
    echo "No clean.omr for '$TUNE' at:" >&2
    echo "  $CLEAN_OMR" >&2
    echo "Run phase-1 OMR first:" >&2
    echo "  bash ${HERE}/batch_tune.sh \"$TUNE\"" >&2
    exit 1
fi

build_compare() {  # (re)build the side-by-side compare PNG from the current render
    bash "${HERE}/render_abc.sh" "$EDIT_ABC" "$RENDER" >/dev/null 2>&1 || return 1
    bash "${HERE}/make_compare.sh" "$SCAN" "$RENDER" "$COMPARE_PNG" >/dev/null 2>&1 || return 1
}

# ── Step 1: Audiveris review ──────────────────────────────────────────────────
# Skipped when --mvt N is given: the OMR was already corrected + saved on the
# first pass, so re-picking a movement just re-exports — no need to redo the GUI.
if [[ $NO_EXPORT -eq 1 ]]; then
    if [[ $EDITING_VERIFIED -eq 1 ]]; then
        echo "--no-export given — editing the VERIFIED ABC in place (no candidate)."
    else
        echo "--no-export given — skipping Audiveris; reusing existing candidate ABC."
    fi
elif [[ -z "$MVT" ]]; then
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
if [[ $NO_EXPORT -eq 1 ]]; then
    echo "Skipping export — using existing ABC:"
    echo "  $EDIT_ABC"
else
    echo "Exporting → candidate ABC..."
    if ! bash "${HERE}/export_tune.sh" "$TUNE" ${MVT:+--mvt "$MVT"}; then
        echo "" >&2
        echo "export_tune.sh did not finish." >&2
        if [[ -z "$MVT" ]]; then
            echo "A movement split is merged automatically now; if a later movement is" >&2
            echo "actually a stray fragment, force a single one (no need to redo Audiveris):" >&2
            echo "  bash ${HERE}/$(basename "${BASH_SOURCE[0]}") \"$TUNE\" --mvt 1" >&2
        else
            echo "Resolve the error above, then re-run." >&2
        fi
        exit 2
    fi
fi

# ── --export-only: stop here. Claude's stage-2 cleanup owns the title fix,
# chords, linebreaks, etc., then resumes review via the live compare + EasyABC.
if [[ $EXPORT_ONLY -eq 1 ]]; then
    echo ""
    echo "--export-only done. Candidate ABC ready for AI cleanup:"
    echo "  $EDIT_ABC"
    exit 0
fi

# ── Step 3: Mechanical title fix (BEFORE EasyABC) ─────────────────────────────
# Force the canonical title. Pass $TUNE via the ENVIRONMENT — never interpolate
# into the source (an apostrophe like "Devil's Dream" would break the literal).
echo "Forcing canonical title T:${TUNE} ..."
TUNE="$TUNE" ABC="$EDIT_ABC" "${IMAGES_DIR}/.venv/bin/python3" - <<'PY'
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
echo "Starting live compare watcher..."
"${HERE}/live_compare.sh" "$EDIT_ABC" "$RENDER" "$SCAN" &
WATCHER=$!
# Make sure the watcher dies with us no matter how we exit.
trap 'kill "$WATCHER" 2>/dev/null' EXIT

echo "Opening EasyABC — edit notes/chords; SAVE to refresh the compare; CLOSE when done."
easyabc "$EDIT_ABC"

# ── Step 5: EasyABC closed → stop watcher, final rebuild, promote/commit gate ──
kill "$WATCHER" 2>/dev/null
trap - EXIT
echo "EasyABC closed. Rebuilding final compare..."
build_compare || true

echo ""
if [[ $EDITING_VERIFIED -eq 1 ]]; then
    # Already verified, edited in place — nothing to promote; just commit.
    read -r -p "Commit changes to verified \"${TUNE}\"? [y/N] " ans
    if [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; then
        git -C "$IMAGES_DIR" add "$VERIFIED_ABC" \
            && git -C "$IMAGES_DIR" commit -m "fix: update verified ${TUNE}" \
            && echo "Committed: ${TUNE}"
    else
        echo "Left uncommitted. Commit later with:"
        echo "  git add \"$VERIFIED_ABC\" && git commit -m \"fix: update verified ${TUNE}\""
    fi
else
    read -r -p "Promote & commit \"${TUNE}\"? [y/N] " ans
    if [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; then
        git -C "$IMAGES_DIR" add "$CAND_ABC" \
            && bash "${HERE}/promote_tune.sh" "$TUNE" \
            && git -C "$IMAGES_DIR" add "$VERIFIED_ABC" \
            && git -C "$IMAGES_DIR" commit -m "feat: verify ${TUNE}" \
            && echo "Promoted + committed: ${TUNE}"
    else
        echo "Left as candidate. Promote later with:"
        echo "  git add \"$CAND_ABC\" && bash ${HERE}/promote_tune.sh \"$TUNE\" \\"
        echo "    && git add \"$VERIFIED_ABC\" \\"
        echo "    && git commit -m \"feat: verify ${TUNE}\""
    fi
fi

# ── Loop: advance to the next queue tune ──────────────────────────────────────
if [[ $LOOP -eq 1 ]]; then
    # Remember this tune for the session so the loop steps past it even if it
    # wasn't promoted (promoted ones drop out via their -verified.abc anyway).
    [[ -n "$SEEN_FILE" ]] && printf '%s\n' "$TUNE" >> "$SEEN_FILE"
    if NEXT="$(pick_next_tune)"; then
        echo ""
        echo "── Next in queue: $NEXT ──"
        exec "${HERE}/$(basename "${BASH_SOURCE[0]}")" \
            ${QUEUE:+--queue-file "$QUEUE"} --loop
    else
        echo ""
        echo "Queue complete — no more verify-eligible tunes."
        [[ -n "$SEEN_FILE" && -f "$SEEN_FILE" ]] && rm -f "$SEEN_FILE"
    fi
fi
