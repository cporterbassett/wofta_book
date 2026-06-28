# /verify-tune Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/verify-tune` slash command that runs the per-tune verify loop exactly like `verify_tune.sh`, but inserts a Claude cleanup pass (mechanical fixes + chords + measure-marking) between Audiveris export and EasyABC review.

**Architecture:** Pure orchestration over the existing pipeline scripts plus one tiny enabling change. The command drives three stages per tune — Stage 1 delegates to `verify_tune.sh --export-only` (Audiveris GUI + export), Stage 2 is Claude editing the candidate ABC in place, Stage 3 is a Claude-driven live compare + EasyABC + promote gate (Claude owns the promote prompt in chat because a non-interactive Bash call can't answer the script's `read`). The only script change is making the render's measure-number directive overridable so the review compare can number every bar.

**Tech Stack:** Bash (pipeline scripts), abcm2ps + Ghostscript + ImageMagick (rendering), EasyABC + Audiveris (GUI), Firefox (compare view), Python venv at `.venv/` (helpers), Claude Code slash command (markdown with YAML frontmatter).

## Global Constraints

- Linux/Mint-bound runtime: flatpak Audiveris, `wmctrl`, `easyabc`, `firefox`. Configs must also be sane on macOS where feasible, but this command targets the Linux verify station.
- Repo layout (post 2026-06-27 reorg): ABC in `abc/`, scripts in `bin/`, scans in `sources/scans/` (fallback `sources/scans/verified/`), cleaned OMR in `scratch/batch_output/<Tune>/clean.omr`, renders in `scratch/renders/`, Python venv at `.venv/`.
- Candidate ABC: `abc/<Tune>-candidate.abc`; verified ABC: `abc/<Tune>-verified.abc`.
- The promoted `-verified.abc` and `-candidate.abc` MUST stay free of review-only directives/annotations (measure numbering, highlight marks). Marking lives only in a throwaway temp ABC.
- Launch EasyABC with the FULL ABSOLUTE path (relative paths open blank — `feedback_easyabc_absolute_path`).
- NEVER `source .venv/bin/activate` before launching `easyabc` (shadows system wxPython → crash — `feedback_easyabc_venv_wx`). Call venv Python by absolute path (`.venv/bin/python3`) instead.
- Commit messages must not mention Claude as author/co-author.
- Stage 2 must NOT fabricate notes. Degraded/handwritten scans → chord+structure SKELETON with melody as rests, no auto-promote.

---

## File Structure

- `bin/render_abc.sh` (MODIFY) — make the hardcoded `%%measurenb 0` overridable via a `RENDER_MEASURENB` env var (default `0`, unchanged behavior). Enables every-measure numbering in the review compare without touching the book render.
- `.claude/commands/verify-tune.md` (CREATE) — the slash command: argument handling, the 3-stage per-tune flow, the loop, and the Stage-2 cleanup checklist Claude follows.

No other files change. `verify_tune.sh`, `export_tune.sh`, `live_compare.sh`, `make_compare.sh`, `promote_tune.sh`, and `validate_abc.py` are consumed as-is.

---

### Task 1: Make the render's measure numbering overridable

**Files:**
- Modify: `bin/render_abc.sh:31-39` (the `render()` function's directive block)
- Test: manual render of an existing verified ABC fixture (no unit-test framework in this repo; verification is an actual render + grep)

**Interfaces:**
- Consumes: nothing new.
- Produces: `render_abc.sh` honors env var `RENDER_MEASURENB` (string, default `"0"`) controlling the `%%measurenb` value it injects. `live_compare.sh` inherits this via the environment automatically (its `build_compare` shells out to `render_abc.sh`). Stage 2/3 of the command set `RENDER_MEASURENB=1` for the review compare.

- [ ] **Step 1: Confirm current behavior (baseline)**

Run:
```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
bash bin/render_abc.sh "abc/Sarah Armstrong-verified.abc" /tmp/vt_baseline.png && ls -l /tmp/vt_baseline.png
```
Expected: prints `Rendered: /tmp/vt_baseline.png` and the file exists (non-zero size). This proves the fixture renders before any change.

- [ ] **Step 2: Make `%%measurenb` value overridable**

In `bin/render_abc.sh`, inside `render()` (currently line ~35), change the hardcoded `%%measurenb 0` to read the env var. Replace:

```bash
        printf '%%%%measurenb 0\n%%%%contbarnb 1\n%%%%gchordfont Helvetica-Bold 12\n%%%%repeatfont Helvetica-Bold 12\n'
```

with:

```bash
        printf '%%%%measurenb %s\n%%%%contbarnb 1\n%%%%gchordfont Helvetica-Bold 12\n%%%%repeatfont Helvetica-Bold 12\n' "${RENDER_MEASURENB:-0}"
```

Rationale: `${RENDER_MEASURENB:-0}` preserves the existing default (`0` = number at each staff-line start, matching the WOFTA scans) when the var is unset. Setting it to `1` numbers every measure for the review compare.

- [ ] **Step 3: Verify default is unchanged**

Run:
```bash
bash bin/render_abc.sh "abc/Sarah Armstrong-verified.abc" /tmp/vt_default.png && ls -l /tmp/vt_default.png
```
Expected: `Rendered: /tmp/vt_default.png`, file exists. (Same path as Step 1 — default behavior intact.)

- [ ] **Step 4: Verify the override is actually injected**

The temp ABC is deleted at the end of render, so assert via a one-off that reproduces the directive line:
```bash
RENDER_MEASURENB=1 bash -c 'printf "%%%%measurenb %s\n" "${RENDER_MEASURENB:-0}"'
```
Expected output: `%%measurenb 1`

Then confirm an override render still succeeds end-to-end:
```bash
RENDER_MEASURENB=1 bash bin/render_abc.sh "abc/Sarah Armstrong-verified.abc" /tmp/vt_mnb1.png && ls -l /tmp/vt_mnb1.png
```
Expected: `Rendered: /tmp/vt_mnb1.png`, file exists. Open `/tmp/vt_mnb1.png` and `/tmp/vt_default.png` to eyeball that the `=1` version shows a number on (nearly) every barline vs. only line starts:
```bash
firefox /tmp/vt_mnb1.png /tmp/vt_default.png &
```

- [ ] **Step 5: Commit**

```bash
git add bin/render_abc.sh
git commit -m "feat: make render_abc.sh measure numbering overridable via RENDER_MEASURENB"
```

---

### Task 2: The `/verify-tune` slash command

**Files:**
- Create: `.claude/commands/verify-tune.md`
- Verify: dry-run the picker the command relies on, and a structural read-through of the command against the staged flow.

**Interfaces:**
- Consumes: `RENDER_MEASURENB` from Task 1 (sets it to `1` for the review compare). The existing scripts: `verify_tune.sh --export-only`, `live_compare.sh <cand_abc> <render_png> <scan_png>`, `render_abc.sh <abc> [out]`, `make_compare.sh <src> <ren> <out>`, `promote_tune.sh "<Tune>"`, `validate_abc.py "<Tune>"`.
- Produces: a user-invokable `/verify-tune` command. No code consumes it.

- [ ] **Step 1: Confirm the underlying picker works (pre-flight)**

The command delegates tune selection to `verify_tune.sh`. Confirm it runs without a GUI:
```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
bash bin/verify_tune.sh --list
```
Expected: prints "Remaining verify-eligible tunes (worst-first):" and a numbered list (or a clear "no health_scores.tsv" message — either proves the entry point is reachable). Also try `bash bin/verify_tune.sh --queue --list`.

- [ ] **Step 2: Write the command file**

Create `.claude/commands/verify-tune.md` with this exact content:

````markdown
---
description: AI-in-the-loop per-tune verify — Audiveris → Claude cleanup → EasyABC → promote. Mirrors verify_tune.sh.
argument-hint: ["Tune Name" | --queue | --queue --loop | --list | --skip ["Tune"]]
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
- `--skip` (optionally with a tune name): run `bash bin/verify_tune.sh $ARGUMENTS`
  to park the tune, then continue to auto-pick the next tune for a full pass
  (below), unless the user only wanted to skip.

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
2. Prepend `%%measurenb 1` as the first line of the copy (overrides the render
   default so every bar is numbered).
3. At each flagged bar, insert an annotation just before that measure's first note:
   `"^!"` immediately followed by a flag glyph, e.g. `"^⚑"`. (You know each
   suspect bar's location in the ABC text from Stage 2 — place it directly; no
   counting needed.)
4. Render the snapshot and build a compare image:
   ```
   RENDER_MEASURENB=1 bash bin/render_abc.sh "scratch/<Tune>.review.abc" "scratch/<Tune>.review.png"
   bash bin/make_compare.sh "<SCAN>" "scratch/<Tune>.review.png" "scratch/<Tune>.review.compare.png"
   ```
5. Show `scratch/<Tune>.review.compare.png` and print a **Stage 2 report**: what
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

If `$ARGUMENTS` contained `--loop`: after the promote gate, re-run the whole
per-tune flow for the next tune. Get the next tune by re-running Stage 1's
`--export-only` with the same `--queue`/`--queue-file` args (it auto-picks). Stop
when it reports the queue is complete or no eligible tune remains.
````

- [ ] **Step 3: Verify the command is discoverable and well-formed**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
head -5 .claude/commands/verify-tune.md
```
Expected: the YAML frontmatter (`---`, `description:`, `argument-hint:`, `---`).
In a Claude Code session, confirm `/verify-tune` appears in the slash-command
list (the file's mere presence registers it).

- [ ] **Step 4: Read-through against the flow**

Re-read the command file and confirm, for each stage, that every script path and
flag matches the real scripts: `verify_tune.sh --export-only`,
`live_compare.sh <cand> <render> <scan>`, `make_compare.sh <src> <ren> <out>`,
`promote_tune.sh "<Tune>"`, `validate_abc.py "<Tune>"`, and that `RENDER_MEASURENB=1`
is set wherever a numbered render is wanted. Fix any drift.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/verify-tune.md
git commit -m "feat: add /verify-tune AI-in-the-loop verify command"
```

---

## Self-Review

**Spec coverage:**
- Delivery as project-local slash command → Task 2 (`.claude/commands/verify-tune.md`). ✓
- Interface mirrors `verify_tune.sh` (name/auto-pick/`--queue`/`--loop`/`--list`/`--skip`) → command pass-through + loop. ✓
- Stage 1 export delegated to `--export-only`, human owns OMR → command Stage 1. ✓
- Stage 2 scope (header/structure/chords + 3 OMR artifacts + degraded skeleton + flag-only) → command Stage 2. ✓
- Measures-per-system, anacrusis numbering, repeat/volta/barline balance, canonical title → command Stage 2. ✓
- Render-only measure numbering → Task 1 env override + `RENDER_MEASURENB=1` in Stages 2.5/3. ✓
- Highlight suspect bars → command Stage 2.5 (Claude-placed annotations in a temp review ABC; never in candidate/verified). ✓
- Stage 3 Claude-driven review + chat promote gate + mid-review kill/reopen → command Stage 3. ✓
- Book output stays clean → marking confined to `scratch/<Tune>.review.abc` (deleted) and a `%%measurenb 1` only in env/temp. ✓

**Placeholder scan:** No TBD/TODO; all code and commands are concrete.

**Type/interface consistency:** `RENDER_MEASURENB` defined in Task 1 and consumed in Task 2 with identical name; script names/flags match the read source files.
