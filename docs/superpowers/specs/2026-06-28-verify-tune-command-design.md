# `/verify-tune` slash command — design

**Date:** 2026-06-28
**Status:** approved (pending spec review)

## Problem

The AI-in-the-middle verify loop was specced on 2026-06-24
(`2026-06-24-ai-in-the-middle-verify-loop-design.md`) and its *script-side* work
is already done: `bin/verify_tune.sh` has `--export-only` and `--no-export`, and
the live-compare watcher is extracted into `bin/live_compare.sh`. What was never
built is the piece that spec assumed — *"Claude drives the per-tune loop
interactively."* There is no command to start that driver.

We want a slash command that works **just like `verify_tune.sh`** but injects a
Claude cleanup pass between Audiveris export and EasyABC review.

## Delivery

A project-local slash command at `.claude/commands/verify-tune.md` (travels
with the repo; `.claude/` is not gitignored). Invoked inside a Claude Code
session. No changes to any bash script — the command is pure orchestration over
the existing pipeline scripts.

## Interface (mirrors `verify_tune.sh`)

- `/verify-tune` — auto-pick the next tune (worst-first via `health_scores.tsv`).
- `/verify-tune "Tune Name"` — a specific tune.
- `/verify-tune --queue` / `--queue --loop` — draw from `verify_queue.txt` in
  file order; `--loop` walks the whole queue.
- `/verify-tune --list` — print remaining eligible tunes and stop (no GUI).
- `/verify-tune --skip ["Tune"]` — park a tune in `verify_skip.txt`, advance.

Tune selection is delegated to `verify_tune.sh` (its `eligible` / `pick_next_tune`
logic), so eligibility and ordering stay identical to the manual loop.

## The 3 stages, per tune

### Stage 1 — export (delegated)

Run `bash bin/verify_tune.sh --export-only [TUNE | --queue ...]`. This:
- opens Audiveris (maximized) on `scratch/batch_output/<Tune>/clean.omr` and the
  raw scan in Firefox; blocks until the human closes Audiveris (the human still
  owns OMR note correction);
- runs `export_tune.sh` → `abc/<Tune>-candidate.abc` (+ automatic movement merge);
- stops before the title fix and EasyABC.

Claude parses stdout to learn the selected tune name (the
`Auto-selected next tune ...: <Tune>` line, or the explicit argument) and the
candidate ABC path (`abc/<Tune>-candidate.abc`).

`--export-only` has no `read` prompt, so running it through the Bash tool is safe.

### Stage 2 — Claude cleanup pass

Read the scan PNG (`sources/scans/<Tune>.png`, fallback
`sources/scans/verified/<Tune>.png`) and the candidate ABC, then edit the
candidate ABC in place. Scope is exactly the 2026-06-24 spec's Stage 2:

**Header / metadata**
- `T:` canonical title — the authoritative WOFTA-list spelling (cross-check against
  the WOFTA list / `tin_whistle_list.txt`), not merely `$TUNE`; `C:` attribution
  from the scan; `M:` meter(s) including mid-tune changes and cut-time `M:C|`; `K:`
  key(s) including mid-tune changes; `L:` default note length.

**Structure**
- Line lengths: one source line per scan system (`$` linebreaks).
- **Measures-per-system match:** count measures in each scan system vs. the ABC
  and align the `$` breaks to match. Catches dropped/extra measures (the most
  common OMR structural error). Per memory: an "extra measure" means a misplaced
  `$` break to move, not a measure to delete; a genuinely dropped line/measure is
  re-OMR'd at 150% (flag it — do not fabricate).
- Repeats `|:` `:|` `::` and 1st/2nd (volta) endings `|1 … :|2 … |` with
  `%%contbarnb 1` so voltas don't add a phantom measure. **Balance check:** every
  `|:` has a matching `:|`, voltas are well-formed, and the tune ends on `|]`.
- **Anacrusis / pickup:** detect a pickup in the scan and set the meter numbering
  correctly — use the real meter (`M:4/4`) matching the scan, or `%%measurefirst 0`
  in the tune header — knowing the final measure is intentionally short and its
  missing final rest is not an error.
- Slurs OMR dropped or mangled.

**Known OMR export-artifact fixes** (per the user's 2026-06-28 confirmation these
count as mechanical, not melody note-reading)
- Octave errors — a staff section exported an octave off.
- Voice-residue `[xy]` chords — collapsed Audiveris 2nd voice; keep the upper
  note, check for a dropped slur.
- Two-voice splits — merge complementary `z`-rest masks (take the non-rest voice
  per measure).

**Chords** (best-effort from the scan)
- Capital roots (`"F#m"` not `"f#m"`); placed at the beat position over which the
  chord sits in the scan (not defaulted to the downbeat); both-sides space
  mid-measure, no left space when the chord opens a measure.

**Degraded / handwritten scans**
- If OMR-proof, produce a SKELETON only (chords + structure, melody as rests). No
  fabricated notes. No auto-promote — hand back to Porter.

**Flag-only (report to chat, do NOT fix — these are note/rhythm reading Porter
owns in EasyABC)**
- Per-measure beat-count: run `bin/validate_abc.py` and list measures whose
  durations don't sum to the meter (points straight at OMR misreads).
- Suspected dropped triplets/tuplets (`(3`) and dropped grace notes / ornaments
  visible in the scan.
- Tie-vs-slur ambiguity where both endpoints share a pitch.

Every flag-only finding is reported **by measure number**, and those measure
numbers drive the review-render marking in Stage 3 (below).

**Out of scope for Stage 2:** correcting notes that are simply misread vs. the
scan (Porter does that in EasyABC). Only the export artifacts above touch pitch.

After editing, run `bash bin/render_abc.sh` once to confirm the ABC parses, then
print a short **Stage 2 report** to chat: what was fixed + the flag-only findings,
so Porter walks into EasyABC knowing exactly where to look. THEN proceed to
Stage 3.

### Stage 3 — Claude-driven review

Not a blind shell-out to `--no-export` (its `read -p "Promote?"` gate can't
receive Porter's answer through a non-interactive Bash call). Claude drives it:

- **Marked review render.** The compare PNG is built from a *review render* that
  (a) numbers every measure (`%%measurenb 1`) so the chat report's "measure N"
  references map onto the picture, and (b) highlights the measures Claude flagged
  in Stage 2 (e.g. a colored bar/annotation). This marking is **render-only**:
  injected into a temp copy of the ABC, never into `<Tune>-candidate.abc` or the
  promoted `<Tune>-verified.abc`, so the book output stays clean.
- Start the live-compare watcher in the background pointed at that review render
  (auto-refreshing side-by-side compare in Firefox; rebuilds on every save).
- Launch `easyabc <candidate.abc>` (foreground GUI; the Bash call blocks until
  Porter closes it).
- **Mid-review edits:** EasyABC does not reload externally-edited files. If Porter
  asks Claude to change the ABC while EasyABC is open, Claude kills EasyABC, edits,
  relaunches it (new PID). The watcher refreshes the compare from the file change.
- On Porter's close: stop the watcher, rebuild the final compare, then ask in chat
  **"Promote & commit?"**. On yes: `git add` the candidate, `bin/promote_tune.sh
  "<Tune>"`, `git add` the verified ABC, `git commit -m "feat: verify <Tune>"`.
  On no: leave as candidate and print the manual promote command.

### Loop

In `--loop` mode Claude repeats the 3 stages, getting each next tune from
`verify_tune.sh`'s picker, until the queue is exhausted.

## What changes in code

1. New file: `.claude/commands/verify-tune.md` (the command itself).
2. A **review-render** path for the marked compare (bar numbers + highlighted
   suspect measures). To keep `<Tune>-candidate.abc` / `<Tune>-verified.abc` clean,
   the marking is injected into a temp copy of the ABC before rendering — e.g. a
   small `bin/render_review.sh` wrapper (or a `--review`/`--mark "N,M"` flag on
   `render_abc.sh`) that prepends `%%measurenb 1`, applies the highlight to the
   given measure numbers, then defers to `render_abc.sh`. The Stage-3 watcher uses
   this review render for the compare PNG. (Exact abcm2ps highlight mechanism is an
   implementation detail for the plan.)

No changes to `export_tune.sh`, `promote_tune.sh`, `make_compare.sh`, or the
`verify_tune.sh` flags (the command calls `--export-only` and the existing
helpers). `live_compare.sh` may need a small tweak to render via the review path.

## Out of scope

- Headless `claude -p` automation (Claude drives interactively).
- Changing the human Audiveris correction step.
- Any change to the OMR / phase-1 batch pipeline.

## Related

- Prior spec: `2026-06-24-ai-in-the-middle-verify-loop-design.md` (script-side
  infra, now implemented).
- Memory: `project_verify_workflow`, `feedback_verify_workflow`,
  `feedback_chord_placement`, `project_pipeline_fixes`, `project_octave_fix`,
  `project_voice_residue_chord`, `project_two_voice_split`,
  `project_degraded_scans`, `feedback_line_length_layout`,
  `feedback_easyabc_absolute_path`, `feedback_easyabc_venv_wx`.
