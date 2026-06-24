# AI-in-the-middle verify loop — design

**Date:** 2026-06-24
**Status:** approved (pending spec review)

## Problem

The per-tune verify loop (`notation_pipeline/bin/verify_tune.sh`) was reimplemented
in commit `a4a997e4` as a "Claude-free" shell pipeline: human corrects the OMR in
Audiveris → export → force title → live auto-refreshing side-by-side compare +
EasyABC → promote gate. That version dropped the earlier Claude-in-the-loop step
that cleaned up the ABC and added chords before EasyABC opened.

We want Claude back **in the middle** — doing its best to clean up the candidate
ABC and add chords *before* EasyABC opens — while keeping the new live-compare /
queue / loop machinery the Claude-free version added. This becomes the new SOP for
the loop.

## Shape of the loop (3 stages, per tune)

### Stage 1 — `verify_tune.sh --export-only "$TUNE"` (NEW flag)

Everything the current script does up to *but not including* the EasyABC launch:

- Open Audiveris (maximized) on `clean.omr` + open the raw scan in Firefox for
  reference. Block until the human closes Audiveris (the human still owns OMR
  note correction — highest accuracy).
- `export_tune.sh` → candidate ABC (+ automatic movement merge).
- **Stop.** Do NOT open EasyABC. Do NOT run the title fix here — stage 2 owns the
  title (see below), so `--export-only` skips the inline title-fix step.

This is a thin gate on the existing flow: reuse Audiveris-maximize, the
review-phase scan open, `export_tune.sh`, and movement merging unchanged.

### Stage 2 — AI cleanup (Claude, this session)

Read the scan PNG (`source_images/<Tune>.png`) + the candidate ABC, then edit the
candidate ABC in place to fix what OMR reliably gets wrong, and add chords. Scope:

**Header / metadata**
- `T:` canonical title (= the source-image filename / `$TUNE`).
- `C:` attribution / composer, read from the scan.
- `M:` meter(s) — including mid-tune meter changes; preserve cut-time `M:C|`.
- `K:` key signature(s) — including any mid-tune key changes.
- `L:` default note length.

**Structure**
- Line lengths: normalize `$` linebreaks so the measures-per-line match the
  scan's systems (one source line per scan system).
- Repeats / "returns": repeat barlines `|:` `:|` `::` matching the scan.
- Return endings: 1st/2nd (volta) endings `|1 … :|2 … |`, with `%%contbarnb 1`
  so voltas don't add a phantom measure.
- Slurs: restore slurs OMR dropped or mangled.

**Known OMR error patterns** (see memory)
- Octave errors — a staff section exported an octave off.
- Voice-residue `[xy]` chords — a collapsed Audiveris 2nd voice; keep the upper
  note and check for a dropped slur.
- Two-voice splits — merge complementary `z`-rest masks (take the non-rest voice
  per measure).

**Chords** (best-effort from the scan)
- Capital roots always (`"F#m"` not `"f#m"`).
- Place each chord at the beat position it sits over in the scan, not defaulted to
  the measure downbeat (matters for multi-chord measures / endings).
- Spacing: both-sides space mid-measure; no left space when the chord is the first
  thing in a measure.

**Degraded / handwritten scans**
- If the scan is OMR-proof (handwritten lead sheet), produce a SKELETON only:
  chords + structure, melody left as rests. No fabricated notes. No auto-promote —
  hand back to Porter.

After editing, render once (`render_abc.sh`) to confirm the ABC parses before
handing to stage 3.

### Stage 3 — live review, decoupled (small refactor)

The current live-compare watcher is inline in `verify_tune.sh` (≈ lines 266–301)
and is immediately followed by a foreground `easyabc` + promote gate. That coupling
prevents killing/reopening EasyABC mid-review. Decouple it:

- Extract the watcher + auto-refresh-compare logic into a reusable piece (a
  `live_compare.sh` helper, or a `--compare-only` mode) that builds the initial
  compare, writes the auto-refreshing Firefox page, opens it, and rebuilds the
  compare on every save (mtime poll) — blocking until killed. No EasyABC, no
  promote.
- Claude runs the compare-watcher in the background.
- Claude launches EasyABC and **tracks its PID**.
- **Kill/reopen rule:** EasyABC does not reload externally-edited files. So if
  Porter asks Claude to change the candidate ABC while EasyABC is open, Claude
  kills EasyABC, makes the edit, and relaunches it (new PID). The watcher refreshes
  the compare from the file change automatically.
- **Distinguishing close from kill:** Claude is the actor, so it always knows. If
  the EasyABC process exits and Claude did *not* initiate the kill, Porter closed
  it → proceed to the promote & commit gate. If Claude killed it, relaunch.
- On Porter's close: stop the watcher, rebuild the final compare, run the promote &
  commit gate (`promote_tune.sh` + the guarded `git add && … && commit` chain).

The pure-manual `--no-export` path stays unchanged for when Claude is not in the
middle.

## Looping

Claude drives the per-tune loop interactively (pick next tune worst-first or from
`verify_queue.txt`, repeat the 3 stages). The script's own `--loop` self-exec is
not used for the AI flow because Claude must inject stage 2 between export and
review.

## What changes in code

1. `verify_tune.sh`: add `--export-only` (stop after export, skip title fix +
   EasyABC).
2. Extract the live-compare watcher into a reusable `live_compare.sh` /
   `--compare-only` mode; keep `--no-export` working off it.
3. No change to `export_tune.sh`, `promote_tune.sh`, `make_compare.sh`,
   `render_abc.sh`.

## Out of scope

- Headless `claude -p` automation (Claude drives interactively instead).
- Changing the human Audiveris correction step.
- Any change to the OMR / phase-1 batch pipeline.

## Related memory

`project_verify_workflow`, `feedback_verify_workflow`, `feedback_chord_placement`,
`project_pipeline_fixes`, `project_octave_fix`, `project_voice_residue_chord`,
`project_two_voice_split`, `project_degraded_scans`, `project_phase2_cleanup`.
