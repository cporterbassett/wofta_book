# AI-in-the-middle verify loop — SOP

Per-tune procedure for the verify loop with Claude doing the ABC cleanup pass
between Audiveris and EasyABC. Design rationale: see
`docs/superpowers/specs/2026-06-24-ai-in-the-middle-verify-loop-design.md`.

Three stages per tune. Stage 1 is scripted and human-driven (OMR correction).
Stage 2 is Claude's interactive cleanup (not scripted). Stage 3 is live review
with Claude owning the EasyABC process.

Paths used throughout (substitute the real tune name for `<Tune>`):

```
notation_pipeline/abc/<Tune>-candidate.abc
notation_pipeline/renders/<Tune>-candidate.render.png
source_images/<Tune>.png
```

## Stage 1 — Audiveris correction + export

```bash
bash notation_pipeline/bin/verify_tune.sh --export-only "<Tune>"
```

(Omit the tune name to auto-pick the next one worst-first, or add `--queue` /
`--queue-file FILE` to draw from a queue instead.)

What it does:
- Opens Audiveris (maximized) on `notation_pipeline/batch_output/<Tune>/clean.omr`,
  plus the raw scan (`source_images/<Tune>.png`) in Firefox for reference.
- Blocks until the human closes Audiveris. The human does all OMR note
  correction here — this is still the highest-accuracy place to do it.
- Runs `export_tune.sh` to produce the candidate ABC (movement splits are
  merged automatically).
- **Stops.** No title fix, no EasyABC. This is the seam for stage 2.

Output: `notation_pipeline/abc/<Tune>-candidate.abc` ready for AI cleanup.

If export fails because a later "movement" is actually a stray OMR fragment,
force a single movement (no need to redo Audiveris):

```bash
bash notation_pipeline/bin/verify_tune.sh "<Tune>" --mvt 1
```

## Stage 2 — Claude cleanup

Claude reads `source_images/<Tune>.png` and the candidate ABC, then edits the
candidate ABC in place. This stage is interactive judgment, not scripted —
there is no `--stage2` flag. Scope:

**Header / metadata**
- `T:` — canonical title, matching the source-image filename / tune name.
- `C:` — attribution / composer, read off the scan.
- `M:` — meter(s), including mid-tune meter changes; preserve cut-time as
  `M:C|` (not `M:2/2`) when that's how the scan shows it.
- `K:` — key signature(s), including mid-tune key changes.
- `L:` — default note length.

**Structure**
- Linebreaks (`$`) — **REQUIRED, verify by hand every tune.** The layout must
  match the scan: **one ABC source line per scan system**, so the source text,
  the engraved render, and the original scan all break at the same places (this
  is what makes the result navigable side-by-side). Do NOT trust the export's
  auto-normalizer — it routinely gets the first system or two right and dumps
  the rest onto one giant line. Procedure: count the scan's systems and the
  measures in each; then for each system boundary put a `$` AND a real newline
  in the source (`… |$`). No trailing `$` on the last line (page-gap gotcha).
  After editing, render and confirm the engraved line count equals the scan's
  system count before handing to stage 3. (If the candidate is mis-barred, the
  per-line measure counts won't match the scan exactly yet — lay the lines out
  to approximate the systems anyway; the source↔engraving match still holds and
  the note fixes happen in EasyABC.)
- Repeats: `|:` `:|` `::` matching the scan's repeat barlines.
- Return / volta endings: `|1 … :|2 … |` with `%%contbarnb 1` set so the
  voltas don't add a phantom measure.
- Slurs: restore slurs OMR dropped or mangled.

**Known OMR error patterns** (see memory for fuller writeups)
- Octave errors — a staff section exported a full octave off.
- Voice-residue `[xy]` chords — a collapsed Audiveris 2nd voice rendered as a
  chord; grep for `[` to find them, keep the upper note, and check for a
  slur that got dropped along with it.
- Two-voice splits — two complementary voices each masked with `z`-rests;
  merge by taking the non-rest voice per measure.

**Chords** (best-effort, added before EasyABC opens)
- Capital roots always (`"F#m"`, never `"f#m"`).
- Place each chord at the beat position it actually sits over in the scan —
  do not default to the measure downbeat. This matters for multi-chord
  measures and endings.
- Spacing convention: a space on both sides of the chord mid-measure; no
  leading space when the chord is the first thing in the measure.

**Directive text — "To Coda" / "D.C." / "Fine" etc.** (engraving notes; both
`render_abc.sh` and the final `make_pdf.py` use **abcm2ps**, so abcm2ps text
directives carry through to the handout — they are NOT abc2ly/LilyPond):
- Write the words as a text annotation, e.g. `"^To Coda"` (the leading `^`/`_`/
  `<`/`>`/`@` marks it as an annotation, not a chord — without it, it's parsed
  as a chord symbol).
- **Collision bump:** annotations and chord symbols are both text scripts above
  the staff. When an annotation sits horizontally near a chord, the engraver
  stacks them and pushes the *chord* up, knocking the chord row out of level.
  A short measure has no clear gap, so nudging the annotation sideways rarely
  fixes it.
- **Fix — lift it above the chord row with an explicit offset:** `"@x,yText"`
  (x,y in points; +y is up). e.g. `"@0,11To Coda"` puts the text straight up,
  above the chord tier, so the chord drops back into line. Tune `y` to taste.
- **Bolder annotation:** `%%annotationfont Helvetica-Bold 14` in the tune header
  bolds ALL annotations (chords use the separate `%%gchordfont`, so they're
  unaffected). If a tune has other annotations you don't want bold, use an
  inline abcm2ps `$` font escape on just that string instead.

**Degraded / handwritten scans**
- If the scan is OMR-proof (e.g. a handwritten lead sheet), produce a
  SKELETON only: chords + structure, melody left as rests. Do not fabricate
  notes. Do not auto-promote — hand back to Porter for the melody.

**Before handing off to stage 3**, render once to confirm the edited ABC
parses:

```bash
bash notation_pipeline/bin/render_abc.sh \
  notation_pipeline/abc/<Tune>-candidate.abc \
  notation_pipeline/renders/<Tune>-candidate.render.png
```

## Stage 3 — live review (Claude owns the EasyABC PID)

Claude runs the auto-refreshing compare watcher in the background, then
launches EasyABC in the foreground and tracks its PID:

```bash
bash notation_pipeline/bin/live_compare.sh \
  notation_pipeline/abc/<Tune>-candidate.abc \
  notation_pipeline/renders/<Tune>-candidate.render.png \
  source_images/<Tune>.png &

easyabc notation_pipeline/abc/<Tune>-candidate.abc
```

`live_compare.sh` builds the side-by-side compare PNG, opens a self-refreshing
page in Firefox (reloads every 1.5s), and rebuilds the compare on every save
to the candidate ABC (mtime poll). It blocks until killed and exits 0 on
INT/TERM — Claude is responsible for killing it when the loop ends for this
tune.

**Kill/reopen rule:** EasyABC does not reload externally-edited files. If
Porter asks Claude to change the candidate ABC while EasyABC is open, Claude
must:
1. Kill the tracked EasyABC PID.
2. Make the edit to the candidate ABC.
3. Relaunch `easyabc` on the candidate (new PID to track).

**Gotcha — don't kill EasyABC with a self-matching `pkill -f`.** A command like
`pkill -f "easyabc.*<Tune>"` matches its OWN command line (the pattern contains
the same words), so it kills the launching shell too and returns a confusing
exit code (e.g. 144). Kill by the launched process/task handle instead, or use
a pattern that can't match the killer (e.g. anchor on the binary path, or
`pgrep`-then-`kill` the specific PID). The kill still lands, but the self-match
makes it look like it failed.

The `live_compare.sh` watcher picks up the file change automatically and
refreshes the compare — it does not need to be restarted.

**Distinguishing a human close from a Claude kill:** Claude is always the one
issuing the kill, so it always knows which case applies when the EasyABC
process exits:
- If Claude did **not** initiate the exit, Porter closed the window → proceed
  to the promote gate below.
- If Claude killed it (to make an edit), relaunch per the rule above instead
  of promoting.

**Promote gate** (only on a genuine human close, i.e. Porter closed EasyABC
without Claude having killed it):

1. Stop the `live_compare.sh` watcher (kill the backgrounded PID).
2. Rebuild the final compare once more so it reflects the last save.
3. Track the candidate, run the promote script, then the guarded add/commit:

```bash
git add "notation_pipeline/abc/<Tune>-candidate.abc" \
  && bash notation_pipeline/bin/promote_tune.sh "<Tune>" \
  && git add "notation_pipeline/abc/<Tune>-verified.abc" \
  && git commit -m "feat: verify <Tune>"
```

The leading `git add` of the candidate is required: `promote_tune.sh` does a
`git mv`, which fails on an untracked file (new candidates are untracked until
added). This mirrors the inline chain in `verify_tune.sh`.

`promote_tune.sh` does a `git mv` of the candidate ABC to
`-verified.abc`, re-renders the verified PNG, removes the now-stale candidate
render, and runs `validate_abc.py` as an advisory sanity check. It will not
overwrite an existing verified file silently — it prints a re-promotion
notice and proceeds, since `-f` is used deliberately to allow re-verifying.

If the human declines promotion (or stage 2/3 produced only a degraded-scan
skeleton that needs Porter's melody pass), leave the file as a candidate and
do not commit. The candidate stays at `notation_pipeline/abc/<Tune>-candidate.abc`
for a later pass — resume the loop at stage 3 directly with:

```bash
bash notation_pipeline/bin/verify_tune.sh --no-export "<Tune>"
```

This is the manual fallback path; it reuses the existing candidate untouched
by stage 2 cleanup and goes straight to the live compare + EasyABC (without
Claude's PID tracking), useful when Claude is not in the loop.
