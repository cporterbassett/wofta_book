---
description: AI-in-the-loop per-tune verify — Audiveris → Claude cleanup → EasyABC → promote. Mirrors verify_tune.sh.
argument-hint: ["Tune Name" | --queue | --queue --loop | --list | --skip ["Tune"] | --mvt N]
---

You are running the **AI-in-the-loop per-tune verify** for the WOFTA tune-images
project. This works exactly like `bin/verify_tune.sh`, but YOU (Claude) do a
cleanup pass on the candidate ABC between Audiveris export and EasyABC, and YOU
own the promote prompt (a non-interactive Bash call can't answer the script's
`read`). Work from the repo root `/home/porter/Documents/banjo/WOFTA/tune_images`.

Arguments (passed through as `$ARGUMENTS`): `[ "Tune Name" | --queue | --queue --loop | --list | --skip ["Tune"] ]`.

## Pass-through cases (no AI in the loop)

- `--list` (optionally with `--queue`): run `bash bin/verify_tune.sh $ARGUMENTS`,
  show the output, and STOP. Do not start a verify pass.
- `--skip` (optionally with a tune name): park the tune yourself (do NOT call
  `bin/verify_tune.sh --skip`), then continue to the normal per-tune AI flow for
  the NEXT tune:
  1. Determine the tune to park:
     - If a tune name was given alongside `--skip`, park that name.
     - Otherwise park the auto-pick = the first tune name from the `--list` output:
       run `bash bin/verify_tune.sh <--queue/--queue-file args if present> --list`
       and take the tune name from the first numbered line (format: `  1. Tune Name`).
  2. Append that name to `verify_skip.txt` at the repo root if not already present:
     ```
     grep -qxF "<Tune>" verify_skip.txt 2>/dev/null || printf '%s\n' "<Tune>" >> verify_skip.txt
     ```
  3. Proceed to Stage 1 `--export-only` with any `--queue`/`--queue-file` args and
     NO tune name — auto-pick will now skip the parked tune and select the next one.

## The per-tune flow (3 stages)

Determine queue context from `$ARGUMENTS`: if it contains `--queue`, pass
`--queue` (or `--queue-file F` if given) to the export step; track `--loop`.

### Stage 1 — export (delegated; human owns OMR)

Run, passing through the tune name and any `--queue`/`--queue-file`/`--mvt`:
```
bash bin/verify_tune.sh --export-only <TUNE-or-queue-args>
```
This opens Audiveris (maximized) on `scratch/batch_output/<Tune>/clean.omr` and
the scan in Firefox, blocks until the human closes Audiveris, then exports
`abc/<Tune>-candidate.abc`. Read stdout to learn the tune name: it prints
`Auto-selected next tune (...): <Tune>` when auto-picked, else it's the argument.
If it prints "No ... left to do" / "Queue complete", report that and STOP.

Set, for the rest of this tune:
- `CAND=abc/<Tune>-candidate.abc`
- `SCAN=sources/scans/<Tune>.png` (if missing, `sources/scans/verified/<Tune>.png`)
- `RENDER=scratch/renders/<Tune>-candidate.render.png`

### Stage 2 — Claude cleanup pass (edit CAND in place)

Read the scan PNG (`SCAN`) and `CAND`. Edit `CAND` to fix what OMR reliably gets
wrong and add chords. Scope:

**Header / metadata**
- `T:` = the canonical WOFTA-list title spelling (cross-check `tin_whistle_list.txt`
  and the WOFTA list; fall back to `<Tune>` if no better spelling found).
- `C:` attribution from the scan; `M:` meter(s) incl. mid-tune changes and cut-time
  `M:C|`; `K:` key(s) incl. mid-tune changes; `L:` default note length.

**Structure**
- One source line per scan system (`$` linebreaks).
- Measures-per-system match: count measures in each scan system vs. the ABC and
  align `$` breaks. An "extra measure" means a misplaced `$` to move, NOT a measure
  to delete. A genuinely dropped measure/line → FLAG it (re-OMR @150%); do not
  fabricate.
- Repeats `|:` `:|` `::` and 1st/2nd (volta) endings `|1 … :|2 … |` with
  `%%contbarnb 1`. Verify every `|:` has a matching `:|`, voltas are well-formed,
  and the tune ends on `|]`.
- Anacrusis/pickup: if the scan has a pickup, set the meter numbering correctly —
  real meter (`M:4/4`) matching the scan, or `%%measurefirst 0` in the tune header.
  The final measure is intentionally short; its missing final rest is not an error.
- Slurs OMR dropped or mangled.

**Known OMR export-artifact fixes** (mechanical, allowed)
- Octave errors — a staff section exported an octave off.
- Voice-residue `[xy]` chords — collapsed Audiveris 2nd voice; keep the upper note,
  check for a dropped slur.
- Two-voice splits — merge complementary `z`-rest masks (take the non-rest voice
  per measure).

**Chords (best-effort from the scan)**
- Capital roots (`"F#m"` not `"f#m"`); place each at the beat position it sits over
  in the scan (not defaulted to the downbeat); space on both sides mid-measure, no
  left space when the chord opens a measure.

**Degraded / handwritten scans**
- If OMR-proof, produce a SKELETON only (chords + structure, melody as rests). No
  fabricated notes. Do NOT auto-promote — hand back to Porter.

**Flag-only — do NOT fix; these are note/rhythm reading Porter owns in EasyABC.**
Note them by measure number for the report and the highlight:
- Per-measure beat-count: run `.venv/bin/python3 bin/validate_abc.py "<Tune>"` and
  list measures whose durations don't sum to the meter.
- Suspected dropped triplets/tuplets (`(3`) and dropped grace notes/ornaments
  visible in the scan.
- Tie-vs-slur ambiguity where both endpoints share a pitch.

Out of scope: correcting notes simply misread vs. the scan (Porter does that in
EasyABC). Only the export artifacts above may touch pitch.

After editing, confirm `CAND` parses:
```
bash bin/render_abc.sh "<CAND>" "<RENDER>"
```
If it errors, fix the ABC until it renders.

### Stage 2.5 — marked review snapshot + report

Build a one-time highlighted snapshot so Porter sees the flagged bars up front,
WITHOUT polluting `CAND`:
1. Copy `CAND` to `scratch/<Tune>.review.abc`.
2. At each flagged bar, insert the annotation token `"^!!"` (placed above the bar)
   just before that measure's first note. (You know each suspect bar's location in
   the ABC text from Stage 2 — place it directly; no counting needed.)
   Note: use plain ASCII like `"^!!"` — Unicode characters such as ⚑ cause a
   buffer overflow crash in abcm2ps.
3. Render the snapshot and build a compare image:
   ```
   RENDER_MEASURENB=1 bash bin/render_abc.sh "scratch/<Tune>.review.abc" "scratch/<Tune>.review.png"
   bash bin/make_compare.sh "<SCAN>" "scratch/<Tune>.review.png" "scratch/<Tune>.review.compare.png"
   ```
4. Show `scratch/<Tune>.review.compare.png` and print a **Stage 2 report**: what
   you fixed, and the flag-only findings by measure number. Then delete the temp:
   `rm -f scratch/<Tune>.review.abc`.

### Stage 3 — Claude-driven live review

1. Start the live compare watcher in the background, numbering every bar:
   ```
   RENDER_MEASURENB=1 bash bin/live_compare.sh "<CAND>" "<RENDER>" "<SCAN>"
   ```
   (Run it in the background so it keeps refreshing the Firefox compare on every
   EasyABC save. Remember its PID to kill later.)
2. Launch EasyABC on the ABSOLUTE path of `CAND` (foreground; it blocks until
   Porter closes it). Do NOT activate the venv first.
   ```
   easyabc "/home/porter/Documents/banjo/WOFTA/tune_images/abc/<Tune>-candidate.abc"
   ```
3. Mid-review edits: EasyABC does not reload externally-edited files. If Porter
   asks you to change the ABC while EasyABC is open, kill the EasyABC process,
   make the edit, and relaunch EasyABC (new PID). The watcher refreshes the
   compare from the file change automatically.
4. On Porter's close (EasyABC exits and you did NOT kill it): kill the watcher,
   rebuild the final compare once:
   ```
   bash bin/render_abc.sh "<CAND>" "<RENDER>"
   bash bin/make_compare.sh "<SCAN>" "<RENDER>" "/tmp/<Tune>.compare.png"
   ```

### Promote gate (you ask in chat)

Ask: **"Promote & commit \"<Tune>\"? [y/N]"**. On yes:
```
git add "abc/<Tune>-candidate.abc"
bash bin/promote_tune.sh "<Tune>"
git add "abc/<Tune>-verified.abc"
git commit -m "feat: verify <Tune>"
```
On no: leave as candidate; print the manual promote command. Never claim Claude
authored/co-authored the commit.

## Loop

If `$ARGUMENTS` contained `--loop`:

**Setup — once, before the first tune's Stage 1:** create a session seen-file and
export it so every `--export-only` call inherits it:
```
export VERIFY_SEEN_FILE="$(mktemp "${TMPDIR:-/tmp}/verify_seen.XXXXXX")"
```
Keep that same `$VERIFY_SEEN_FILE` path for every Stage 1 `--export-only` call in
the loop. `verify_tune.sh`'s `eligible()` function reads this env var and skips
tunes already listed in it, so un-promoted tunes are not re-picked endlessly.

**After each tune's promote gate** (whether promoted or declined), append the tune
name to the seen-file before re-running Stage 1 for the next tune:
```
printf '%s\n' "<Tune>" >> "$VERIFY_SEEN_FILE"
```

**Next tune:** re-run Stage 1 `--export-only` with the same `--queue`/`--queue-file`
args (no tune name) — it auto-picks the next eligible, unseen tune.

**When the queue is complete** (Stage 1 reports "Queue complete" / no eligible tune
remains), clean up:
```
rm -f "$VERIFY_SEEN_FILE"
```
Then stop.
