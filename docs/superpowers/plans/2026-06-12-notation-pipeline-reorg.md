# Tune-images Reorg + PDF Render-Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the `tune_images` repo so the working OMR pipeline is cleanly separated from docs/data/scratch, move source scans into `source_images/`, retier ABCs as `-candidate`/`-verified`, and make `make_pdf.py` emit the verified engraving per tune where it exists and the scan otherwise.

**Architecture:** `notation_pipeline/` live scripts move into `bin/`; each derives its root from its own location (`PIPELINE_DIR` = parent of `bin/`, `IMAGES_DIR` = repo root) so data refs and the venv resolve regardless of CWD or machine. Dead-end experiments are git-deleted. ABC publish-state is encoded in the filename; `make_pdf` gates the engraving on `-verified.abc`.

**Tech Stack:** Bash, Python 3 (venv at `tune_images/.venv` with `img2pdf`, `pikepdf`, `Pillow`, `music21`, `abc_xml_converter`), LilyPond/abcm2ps, Audiveris (not exercised by this plan).

**Spec:** `docs/superpowers/specs/2026-06-12-notation-pipeline-reorg-design.md`

**Conventions for this plan:**
- All paths below are relative to the repo root `/home/porter/Documents/banjo/WOFTA/tune_images` unless absolute.
- "NP" = `notation_pipeline`.
- The uniform shell root-derivation header (used in several tasks) is:
  ```bash
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
  IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"
  ```
- Commit messages must NOT mention Claude/AI authorship (user rule).

---

### Task 0: Create a working branch

**Files:** none (git only)

- [ ] **Step 1: Branch off the current branch**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git checkout -b reorg-notation-pipeline
git status
```
Expected: "Switched to a new branch 'reorg-notation-pipeline'".

---

### Task 1: Delete dead-end scripts, scratch, and stale artifacts

**Files:** delete only (git rm). Git history preserves everything.

- [ ] **Step 1: Remove dead-end scripts (15) under NP/**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline
git rm -q sweep_constants.py glyph_cleanup_sweep.py verify_mxl.py ensemble_abc.py \
  blank_chord_names.py preprocess_opencv.py transcribe.py fetch_abc.py \
  process_tune.sh run_tune_pipeline.sh survey_key_detection.sh survey_key_detection_2x.sh \
  test_preprocessing.sh test_preprocessing2.sh test_preprocessing3.sh
```

- [ ] **Step 2: Remove dead data files and the stale report**

```bash
git rm -q dilation_sweep_results.txt survey_results.tsv survey_results_2x.tsv omr_report.html
git rm -q "Angeline the Baker.musicxml" "Angeline the Baker.mxl" "Angeline the Baker.omr" \
  "Angeline the Baker-20260611T0908.log" "Angeline the Baker_teaser.png" \
  angeline_audiveris_updated.png angeline_audiveris_updated.cropped.png
```
Note: some of these may be untracked (e.g. `.mxl`, `.omr`, `.log`, `.musicxml`, `__pycache__`). For untracked ones `git rm` errors — fall back to plain `rm -f` for any that report "did not match any files". Run:
```bash
rm -f "Angeline the Baker.mxl" "Angeline the Baker.omr" "Angeline the Baker.musicxml" \
  "Angeline the Baker-20260611T0908.log"
```

- [ ] **Step 3: Remove dead/scratch directories**

```bash
git rm -rq tests diffs 2>/dev/null; true
rm -rf tmp_pipeline preprocessing_tests web_images __pycache__ tests/__pycache__ batch_output/../__pycache__ 2>/dev/null; true
git rm -rq web_images preprocessing_tests tmp_pipeline 2>/dev/null; true
```
Note: `tests/` (only `test_glyph_cleanup_sweep.py`, which tests a deleted script) and `diffs/` are tracked → `git rm -r`. `tmp_pipeline/`, `preprocessing_tests/`, `web_images/`, `__pycache__/` are untracked → `rm -rf`. Verify none remain: `ls -d tests diffs tmp_pipeline preprocessing_tests web_images __pycache__ 2>/dev/null` should print nothing.

- [ ] **Step 4: Remove dead ABC variants and the 6 now-redundant gold files**

```bash
cd abc
git rm -q -- *-audiveris-*.abc *-blanked.abc *-original*.abc *-raw.abc *-thesession.abc \
  *-abcnotation.abc *-1.5x.abc *-gold.abc "Angeline the Baker.ly" \
  "Arkansas Traveler.abc" "Blackberry Blossom.abc"
cd ..
```
Note: globs that match nothing make `git rm` error — that's fine, run each problematic one individually. After: `ls abc/ | grep -cE -- '-(audiveris|blanked|original|raw|thesession|abcnotation|1\.5x|gold)'` should print `0`.

- [ ] **Step 5: Remove dead experiment renders (keep the 9 finalized tunes' renders)**

```bash
cd renders
git rm -q -- *-audiveris-*.png *-thesession.render.png Angeline_audiveris.png \
  "Angeline the Baker-l4.render.png" "Angeline the Baker-l8.render.png" \
  "Angeline the Baker.render.png" "Blackberry Blossom.render.png" \
  "Blackberry Blossom-thesession.render.png" "Booth Shot Lincoln.render.png" \
  "Cincinnati Hornpipe-audiveris-raw.render.png" 2>/dev/null; true
cd ..
ls renders/
```
Expected after: only `*-final.render.png` and `*-final.trim.png` for the 9 finalized tunes remain (these get retiered in Task 7).

- [ ] **Step 6: Remove the 22 stray oemer scratch PNGs in the repo root**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
rm -f angeline_oemer-page*.png angeline_oemer_updated-page*.png \
  angeline_oemer.cropped.png angeline_oemer_updated.cropped.png
ls angeline_oemer* 2>/dev/null || echo "oemer scratch gone"
```
Expected: "oemer scratch gone".

- [ ] **Step 7: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add -A notation_pipeline
git commit -m "chore: delete concluded dead-end scripts, scratch, and stale artifacts"
```

---

### Task 2: Add NP/.gitignore

**Files:**
- Create: `notation_pipeline/.gitignore`

- [ ] **Step 1: Write the gitignore**

```bash
cat > /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/.gitignore <<'EOF'
# Intermediate Audiveris OMR checkpoints — kept on disk, never committed
batch_output/

# Python bytecode
__pycache__/
*.pyc

# LilyPond / render intermediates
*.ly
*.cropped.png
*.render.ps
*.render.svg
*.render.tmp.abc
EOF
```

- [ ] **Step 2: Verify batch_output is now ignored**

Run: `cd /home/porter/Documents/banjo/WOFTA/tune_images && git check-ignore notation_pipeline/batch_output/`
Expected: prints `notation_pipeline/batch_output/`.

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/.gitignore
git commit -m "chore: add notation_pipeline/.gitignore for intermediates"
```

---

### Task 3: Move scripts → bin/, docs → docs/, report → reports/ (pipeline temporarily broken)

**Files:** moves only (git mv). After this task the pipeline is broken until Tasks 4–5 fix paths. Do Tasks 3→4→5 back-to-back.

- [ ] **Step 1: Create target dirs and move the 14 live scripts into bin/**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline
mkdir -p bin docs reports
git mv batch_tune.sh batch_all.sh cleanup_loop.sh cleanup_keep.sh export_tune.sh \
  render_abc.sh build_report.sh build_tracking_sheet.py normalize_interline.py \
  clean_omr.py clean_mxl.py health_score.py compare_abc.py validate_final.py \
  overlay_diff.py bin/
```

- [ ] **Step 2: Move docs and the live report**

```bash
git mv next_steps.md omr_findings.md abandoned_transcription_attempts.md docs/
git mv finalized_report.html reports/
```

- [ ] **Step 3: Verify top level is now clean**

Run: `ls -p | grep -v /`
Expected: only `health_scores.tsv`, `tracking.md`, `.gitignore` remain as top-level files (plus the `Angeline the Baker_teaser.png` if still tracked — if present, `git rm -q "Angeline the Baker_teaser.png"`).

- [ ] **Step 4: Commit (the move, before path edits, keeps the diff readable)**

```bash
git add -A
git commit -m "refactor: move notation_pipeline scripts into bin/, docs into docs/, report into reports/"
```

---

### Task 4: Fix shell-script paths for the bin/ location

**Files:**
- Modify: `notation_pipeline/bin/batch_tune.sh`
- Modify: `notation_pipeline/bin/batch_all.sh`
- Modify: `notation_pipeline/bin/cleanup_loop.sh`
- Modify: `notation_pipeline/bin/export_tune.sh`
- (`cleanup_keep.sh` and `render_abc.sh` need **no** path edits — verify in Step 5.)

- [ ] **Step 1: batch_tune.sh — replace the hardcoded root + sibling-script refs**

In `bin/batch_tune.sh`, replace:
```bash
IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
```
with the uniform header:
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"
```
Then change the three sibling-script invocations from `${PIPELINE_DIR}/` to `${HERE}/`:
- `"${PIPELINE_DIR}/normalize_interline.py"` → `"${HERE}/normalize_interline.py"`
- `"${PIPELINE_DIR}/clean_omr.py"` → `"${HERE}/clean_omr.py"`
- `"${PIPELINE_DIR}/clean_mxl.py"` → `"${HERE}/clean_mxl.py"`
Leave data refs (`${PIPELINE_DIR}/batch_output`, `${PIPELINE_DIR}/abc`) and `${IMAGES_DIR}/.venv` as-is.

- [ ] **Step 2: batch_all.sh — replace the hardcoded root + the SCRIPT ref**

In `bin/batch_all.sh`, replace:
```bash
IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
```
with the uniform header (same 3 lines as Step 1). Then change:
```bash
SCRIPT="${PIPELINE_DIR}/batch_tune.sh"
```
to:
```bash
SCRIPT="${HERE}/batch_tune.sh"
```
Leave `BATCH_DIR="${PIPELINE_DIR}/batch_output"` and `LOG="${BATCH_DIR}/batch_all.log"` as-is.

- [ ] **Step 3: cleanup_loop.sh — replace the hardcoded root + sibling-script refs**

In `bin/cleanup_loop.sh`, replace:
```bash
IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
PIPELINE_DIR="${IMAGES_DIR}/notation_pipeline"
```
with the uniform header. Then change the two sibling-script invocations:
- `"${PIPELINE_DIR}/clean_mxl.py"` → `"${HERE}/clean_mxl.py"`
- `"${PIPELINE_DIR}/validate_final.py"` → `"${HERE}/validate_abc.py"` (renamed in Task 6; do the path+name change now)
Leave data refs (`${PIPELINE_DIR}/batch_output`, `${PIPELINE_DIR}/health_scores.tsv`, `${PIPELINE_DIR}/abc`) as-is. (The `-final.abc` → `-candidate.abc` change is Task 6.)

- [ ] **Step 4: export_tune.sh — add PIPELINE_DIR/IMAGES_DIR and split data vs script refs**

In `bin/export_tune.sh`, the header is currently:
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="$(cd "${HERE}/.." && pwd)"
```
Replace with:
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"
```
Then change **data** refs from `${HERE}/` to `${PIPELINE_DIR}/`:
- `TDIR="${HERE}/batch_output/${TUNE}"` → `${PIPELINE_DIR}/batch_output/${TUNE}`
- `FINAL_ABC="${HERE}/abc/..."` → `${PIPELINE_DIR}/abc/...`
- `mkdir -p "${HERE}/abc" "${HERE}/renders"` → `"${PIPELINE_DIR}/abc" "${PIPELINE_DIR}/renders"`
- `abc="${HERE}/abc/..."` (movement case) → `${PIPELINE_DIR}/abc/...`
- `RENDER="${HERE}/renders/..."` → `${PIPELINE_DIR}/renders/...`
Keep **script** refs on `${HERE}/`: `${HERE}/clean_mxl.py`, `${HERE}/render_abc.sh`, and `${HERE}/validate_final.py` (the `validate_abc.py` rename + `-final`→`-candidate` are Task 6).

- [ ] **Step 5: Verify cleanup_keep.sh and render_abc.sh need no edits**

Run: `grep -nE '/home/porter|PIPELINE_DIR|cleanup_loop' /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/bin/cleanup_keep.sh`
Expected: `cleanup_keep.sh` only has `HERE="$(cd ... )"` and calls `"${HERE}/cleanup_loop.sh"` (sibling in bin/ → still correct). No hardcoded path. `render_abc.sh` takes file args only — confirm with `grep -nE '/home/porter|PIPELINE_DIR|abc/|batch_output' bin/render_abc.sh` prints nothing.

- [ ] **Step 6: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add notation_pipeline/bin
git commit -m "refactor: derive script root from location; fix paths for bin/ layout"
```

---

### Task 5: Fix Python data-path resolution for the bin/ location

**Files:**
- Modify: `notation_pipeline/bin/health_score.py`
- Modify: `notation_pipeline/bin/validate_final.py`
- Modify: `notation_pipeline/bin/build_tracking_sheet.py`
- (`clean_omr.py`, `clean_mxl.py`, `compare_abc.py`, `normalize_interline.py`, `overlay_diff.py` reference no data dirs — no edits.)

- [ ] **Step 1: health_score.py — point BATCH_DIR at the data root**

Replace:
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BATCH_DIR = os.path.join(SCRIPT_DIR, "batch_output")
```
with:
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)          # notation_pipeline/ (parent of bin/)
BATCH_DIR = os.path.join(ROOT, "batch_output")
```

- [ ] **Step 2: validate_final.py — point data refs at the data root, keep imports on HERE**

Replace:
```python
HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, 'abc')
HEALTH_TSV = os.path.join(HERE, 'health_scores.tsv')
```
with:
```python
HERE = os.path.dirname(os.path.abspath(__file__))   # bin/ — for sibling imports
ROOT = os.path.dirname(HERE)                         # notation_pipeline/ — for data
ABC_DIR = os.path.join(ROOT, 'abc')
HEALTH_TSV = os.path.join(ROOT, 'health_scores.tsv')
```
Leave `sys.path.insert(0, HERE)` and `from compare_abc import ...` unchanged (compare_abc is a sibling in bin/). (The `-final`→tier changes are Task 6.)

- [ ] **Step 3: build_tracking_sheet.py — same ROOT split**

Replace:
```python
HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, 'abc')
HEALTH_TSV = os.path.join(HERE, 'health_scores.tsv')
OUT_PATH = os.path.join(HERE, 'tracking.md')
KEEP_SH = os.path.join(HERE, 'cleanup_keep.sh')
```
with:
```python
HERE = os.path.dirname(os.path.abspath(__file__))   # bin/ — for sibling imports
ROOT = os.path.dirname(HERE)                         # notation_pipeline/ — for data
ABC_DIR = os.path.join(ROOT, 'abc')
HEALTH_TSV = os.path.join(ROOT, 'health_scores.tsv')
OUT_PATH = os.path.join(ROOT, 'tracking.md')
KEEP_SH = os.path.join(HERE, 'cleanup_keep.sh')      # sibling script, stays on HERE
```
Leave `sys.path.insert(0, HERE)` and the `from validate_final import ...` line unchanged for now (renamed in Task 6).

- [ ] **Step 4: Verify health_score and build_tracking still run from the new location**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 notation_pipeline/bin/health_score.py | head -3
.venv/bin/python3 notation_pipeline/bin/build_tracking_sheet.py --check | head -8
```
Expected: `health_score.py` prints TSV header + rows (reads `batch_output/`); `build_tracking_sheet.py --check` prints the tracking table to stdout without a traceback.

- [ ] **Step 5: Commit**

```bash
git add notation_pipeline/bin
git commit -m "refactor: resolve Python data paths from notation_pipeline root, not bin/"
```

---

### Task 6: Rename validate_final.py → validate_abc.py and retier ABC references (-final → -candidate/-verified)

**Files:**
- Rename: `notation_pipeline/bin/validate_final.py` → `notation_pipeline/bin/validate_abc.py`
- Modify: `notation_pipeline/bin/validate_abc.py` (internal `-final` refs)
- Modify: `notation_pipeline/bin/build_tracking_sheet.py` (import + Finalized/Verified logic)
- Modify: `notation_pipeline/bin/export_tune.sh` (`-final` → `-candidate`, validate call)
- Modify: `notation_pipeline/bin/cleanup_loop.sh` (`-final` → `-candidate`)

- [ ] **Step 1: git mv the validator**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/bin
git mv validate_final.py validate_abc.py
```

- [ ] **Step 2: validate_abc.py — validate both Phase-2 tiers**

In `validate_abc.py`, the per-tune path block is currently:
```python
    final_path = os.path.join(ABC_DIR, f'{tune_name}-final.abc')
    draft_path = os.path.join(ABC_DIR, f'{tune_name}-draft.abc')
    gold_path  = os.path.join(ABC_DIR, f'{tune_name}-gold.abc')
```
Replace with (prefer verified, fall back to candidate; gold no longer exists):
```python
    verified_path  = os.path.join(ABC_DIR, f'{tune_name}-verified.abc')
    candidate_path = os.path.join(ABC_DIR, f'{tune_name}-candidate.abc')
    final_path = verified_path if os.path.exists(verified_path) else candidate_path
    draft_path = os.path.join(ABC_DIR, f'{tune_name}-draft.abc')
```
Remove any later use of `gold_path` (search the file: `grep -n gold_path validate_abc.py` and delete those lines/branches — gold is retired).
Update the not-found message:
```python
        results.append(('FAIL', 'File exists', f'abc/{tune_name}-candidate|verified.abc not found'))
```
Update `discover_all_finals()` (the `*-final.abc` glob) to discover both tiers:
```python
def discover_all_finals():
    """Return sorted tune names that have a -candidate.abc or -verified.abc."""
    names = set()
    for suffix in ('-candidate.abc', '-verified.abc'):
        for p in glob.glob(os.path.join(ABC_DIR, f'*{suffix}')):
            names.add(re.sub(re.escape(suffix) + r'$', '', os.path.basename(p)))
    return sorted(names)
```
Update the docstring line `Checks per abc/<Tune>-final.abc:` → `Checks per abc/<Tune>-{candidate,verified}.abc:` and the `'No *-final.abc files found.'` message → `'No *-candidate.abc / *-verified.abc files found.'`.

- [ ] **Step 3: build_tracking_sheet.py — update import + derive Verified from -verified existence**

Change the import:
```python
from validate_final import run_validation, discover_all_finals  # noqa: E402
```
to:
```python
from validate_abc import run_validation, discover_all_finals  # noqa: E402
```
Then make `Verified?` auto-derived. Find where the row's `Verified?` value is set from the preserved/hand-edited map and replace it with a file-presence check. Add this helper near the top (after `ABC_DIR`):
```python
def is_verified(tune_name):
    return os.path.exists(os.path.join(ABC_DIR, f'{tune_name}-verified.abc'))
```
In the row-building loop, set the Verified column to `'Yes' if is_verified(tune) else 'No'` (replace the previous logic that read it from the preserved columns). Keep `Notes` preserved/hand-edited. Update the header comment in the generated file's preamble text from "the **Verified?** and **Notes** columns are preserved" to "the **Notes** column is preserved; **Verified?** is auto-derived from the presence of a `-verified.abc`."

- [ ] **Step 4: export_tune.sh — write -candidate, render -candidate, call validate_abc**

In `bin/export_tune.sh`:
- `FINAL_ABC="${PIPELINE_DIR}/abc/${TUNE}-final.abc"` → `${PIPELINE_DIR}/abc/${TUNE}-candidate.abc`
- `RENDER="${PIPELINE_DIR}/renders/${TUNE}-final.render.png"` → `${PIPELINE_DIR}/renders/${TUNE}-candidate.render.png`
- `"${HERE}/validate_final.py"` → `"${HERE}/validate_abc.py"`
- Update the header comment `# Output: abc/<Tune>-final.abc ...` → `# Output: abc/<Tune>-candidate.abc + renders/<Tune>-candidate.render.png`
Leave the movement-case `abc="${PIPELINE_DIR}/abc/${TUNE}-${base%.mxl}.abc"` as-is (it derives from the mxl basename, not `-final`).

- [ ] **Step 5: cleanup_loop.sh — write -candidate**

In `bin/cleanup_loop.sh`:
- `FINAL="${PIPELINE_DIR}/abc/${TUNE}-final.abc"` → `${PIPELINE_DIR}/abc/${TUNE}-candidate.abc`
- `FINAL_ABC="${PIPELINE_DIR}/abc/${TUNE}-final.abc"` → `${PIPELINE_DIR}/abc/${TUNE}-candidate.abc`
- Update the header comment `# abc/<Tune Name>-final.abc` → `# abc/<Tune Name>-candidate.abc`
(The `validate_final.py` → `validate_abc.py` path was already changed in Task 4 Step 3.)

- [ ] **Step 6: Verify validate_abc + tracking sheet run end-to-end**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 notation_pipeline/bin/validate_abc.py --all | tail -5
.venv/bin/python3 notation_pipeline/bin/build_tracking_sheet.py --check | head -8
```
Expected: `validate_abc.py --all` runs without traceback. Before Task 7 migrates the finals it will report "no candidate/verified files" — that's fine; the important thing is no import or path error. `build_tracking_sheet.py --check` prints the table.

- [ ] **Step 7: Commit**

```bash
git add notation_pipeline/bin
git commit -m "refactor: rename validate_final->validate_abc; retier ABC refs to -candidate/-verified"
```

---

### Task 7: Migrate the 9 existing -final ABCs and their renders to -verified

**Files:** renames only (git mv).

- [ ] **Step 1: Rename the 9 -final.abc → -verified.abc**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/abc
for f in *-final.abc; do
  [ -e "$f" ] || continue
  git mv "$f" "${f%-final.abc}-verified.abc"
done
ls *-verified.abc | wc -l
```
Expected: `9`.

- [ ] **Step 2: Rename the matching renders -final.* → -verified.***

```bash
cd ../renders
for f in *-final.render.png *-final.trim.png; do
  [ -e "$f" ] || continue
  git mv "$f" "${f/-final./-verified.}"
done
ls *-verified.* 2>/dev/null | wc -l
```
Expected: a non-zero count (render and/or trim files for the finalized tunes).

- [ ] **Step 3: Verify the tracking sheet now shows the 9 as verified**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 notation_pipeline/bin/build_tracking_sheet.py --check | grep -c '| Yes |'
```
Expected: `9`.

- [ ] **Step 4: Regenerate tracking.md and commit**

```bash
.venv/bin/python3 notation_pipeline/bin/build_tracking_sheet.py
git add notation_pipeline/abc notation_pipeline/renders notation_pipeline/tracking.md
git commit -m "refactor: migrate 9 finalized tunes -final -> -verified (ABCs + renders)"
```

---

### Task 8: Add promote_tune.sh (the candidate → verified gesture)

**Files:**
- Create: `notation_pipeline/bin/promote_tune.sh`

- [ ] **Step 1: Write the script**

```bash
cat > /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/bin/promote_tune.sh <<'EOF'
#!/usr/bin/env bash
# Promote a tune from -candidate to -verified: the human sign-off gesture.
# After you've eyeballed the engraving against the scan (and edited the
# -candidate.abc if needed), run this to publish it into the book.
#
# Usage: promote_tune.sh "Tune Name"
#
# Effect:
#   abc/<Tune>-candidate.abc  ->  abc/<Tune>-verified.abc   (git mv)
#   re-renders renders/<Tune>-verified.render.png
#   re-runs validate_abc.py as a final sanity check (advisory)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"
VENV="${IMAGES_DIR}/.venv/bin/python3"

TUNE="${1:?usage: promote_tune.sh \"Tune Name\"}"
CAND="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
VERIFIED="${PIPELINE_DIR}/abc/${TUNE}-verified.abc"

if [[ ! -f "$CAND" ]]; then
    echo "No candidate to promote: $CAND" >&2
    exit 1
fi

git -C "$IMAGES_DIR" mv "$CAND" "$VERIFIED"
echo "Promoted: ${TUNE} -> -verified.abc"

RENDER="${PIPELINE_DIR}/renders/${TUNE}-verified.render.png"
bash "${HERE}/render_abc.sh" "$VERIFIED" "$RENDER" 2>&1 | tail -1
# clean up the now-stale candidate render if present
rm -f "${PIPELINE_DIR}/renders/${TUNE}-candidate.render.png" \
      "${PIPELINE_DIR}/renders/${TUNE}-candidate.trim.png"

"$VENV" "${HERE}/validate_abc.py" "$TUNE" || true
echo "Run build_tracking_sheet.py and build_report.sh to refresh the ledger/report."
EOF
chmod +x /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/bin/promote_tune.sh
```

- [ ] **Step 2: Verify it errors cleanly on a tune with no candidate**

Run: `cd /home/porter/Documents/banjo/WOFTA/tune_images && bash notation_pipeline/bin/promote_tune.sh "No Such Tune"; echo "exit=$?"`
Expected: prints "No candidate to promote: …" and `exit=1`.

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/bin/promote_tune.sh
git commit -m "feat: add promote_tune.sh for candidate -> verified sign-off"
```

---

### Task 9: Rewrite build_report.sh for bin/ + reports/ + both tiers + source_images

**Files:**
- Modify: `notation_pipeline/bin/build_report.sh`

This task assumes scans are already in `source_images/` — but the move is Task 11. To keep the report verifiable now, the script will reference `../source_images/<tune>.png`; that path resolves after Task 11. (If running this plan strictly in order, run Task 11 before re-verifying the report links; the script itself is correct either way.)

- [ ] **Step 1: Replace the header (location + tier-aware)**

In `bin/build_report.sh`, replace:
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

OUT="finalized_report.html"
ORIG_DIR=".."          # original scans live one level up
RENDER_DIR="renders"

shopt -s nullglob
FINALS=(abc/*-final.abc)
shopt -u nullglob
```
with:
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"
cd "$PIPELINE_DIR"
mkdir -p reports

OUT="reports/finalized_report.html"
# img src paths are relative to reports/ (one level under PIPELINE_DIR):
ORIG_DIR="../../source_images"   # scans, from reports/
RENDER_DIR="../renders"          # renders, from reports/

shopt -s nullglob
FINALS=(abc/*-verified.abc abc/*-candidate.abc)
shopt -u nullglob
```

- [ ] **Step 2: Make the tune loop tier-aware (basename + suffix)**

The loop currently does `tune="$(basename "$abc" -final.abc)"` and builds `render="${RENDER_DIR}/${tune}-final.render.png"`. Replace both loop bodies (nav loop and main loop) so they strip whichever suffix applies and pick the matching render. Use this helper logic at the top of each `for abc in "${FINALS[@]}"` body:
```bash
  base="$(basename "$abc")"
  if [[ "$base" == *-verified.abc ]]; then tune="${base%-verified.abc}"; tier="verified";
  else tune="${base%-candidate.abc}"; tier="candidate"; fi
  anchor="$(echo "$tune" | tr -c 'A-Za-z0-9' '-')"
```
In the main loop, change the render/trim/orig lines to:
```bash
  orig="${ORIG_DIR}/${tune}.png"
  render="${PIPELINE_DIR}/renders/${tune}-${tier}.render.png"   # absolute, for -f test + convert
  trim="${PIPELINE_DIR}/renders/${tune}-${tier}.trim.png"
  rel_trim="${RENDER_DIR}/${tune}-${tier}.trim.png"             # relative, for <img src>
```
and use `$rel_trim` (not `$trim`) in the `<img src=...>` for the final pane. Add a verified/candidate badge to the heading: in the `<h2>` printf, append ` <small>[${tier}]</small>`. (Because a tune may have only a candidate, dedupe is unnecessary — a verified tune has no candidate after promotion.)

- [ ] **Step 3: Update the count/echo lines**

The trailing `echo "Wrote $OUT (${#FINALS[@]} tunes)"` stays. The `<title>`/header text can stay "Finalized Tunes".

- [ ] **Step 4: Verify it generates without error**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
bash notation_pipeline/bin/build_report.sh
test -f notation_pipeline/reports/finalized_report.html && echo "report written"
```
Expected: "Wrote …/finalized_report.html (9 tunes)" then "report written". (Image links resolve fully after Task 11.)

- [ ] **Step 5: Commit**

```bash
git add notation_pipeline/bin/build_report.sh notation_pipeline/reports/finalized_report.html
git commit -m "refactor: build_report from bin/ into reports/, tier-aware, source_images scans"
```

---

### Task 10: Move 294 source scans into source_images/

**Files:** moves only (git mv). 286+ files.

- [ ] **Step 1: Create source_images/ and move all root PNG scans into it**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
mkdir -p source_images
# move every top-level .png (the tune scans) into source_images/
for f in *.png; do
  [ -e "$f" ] || continue
  git mv -- "$f" "source_images/$f" 2>/dev/null || git mv -- "$f" "source_images/$f"
done
ls *.png 2>/dev/null && echo "WARN: PNGs still at root" || echo "root PNGs moved"
ls source_images | wc -l
```
Expected: "root PNGs moved"; count ~294.

- [ ] **Step 2: Bring Honest John's scan in from old_images/**

```bash
git mv "old_images/Honest John.png" "source_images/Honest John.png"
test -f "source_images/Honest John.png" && echo "honest john scan moved"
```
Expected: "honest john scan moved".

- [ ] **Step 3: Verify the report's scan links now resolve**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
bash notation_pipeline/bin/build_report.sh >/dev/null
# spot-check one referenced scan exists at the path the report uses (reports/ -> ../../source_images)
test -f "source_images/Angeline the Baker.png" && echo "scan path ok"
```
Expected: "scan path ok".

- [ ] **Step 4: Commit**

```bash
git add -A source_images old_images notation_pipeline/reports
git commit -m "refactor: move source scans into source_images/ (incl. Honest John from old_images)"
```

---

### Task 11: Rewrite make_pdf.py for verified-engraving-else-scan selection

**Files:**
- Modify: `make_pdf.py`
- Modify: `make_pdf.sh`

- [ ] **Step 1: Update make_pdf.sh paths**

`make_pdf.sh` currently `cd`s to `SCRIPT_DIR` (repo root) and runs the venv python — that stays correct (script lives at repo root). No change needed unless the venv path differs; verify:
```bash
grep -n '.venv\|make_pdf.py' /home/porter/Documents/banjo/WOFTA/tune_images/make_pdf.sh
```
Expected: references `$SCRIPT_DIR/.venv/bin/python3` and `$SCRIPT_DIR/make_pdf.py` — both correct. No edit.

- [ ] **Step 2: Replace the file-collection block in make_pdf.py**

In `make_pdf.py`, the `main()` collection block is currently:
```python
    png_files = glob.glob("*.png")
    abc_files = glob.glob("*.abc")
    all_files = sorted(png_files + abc_files, key=sort_key)
```
Replace with per-tune selection (verified ABC wins; else scan):
```python
    HERE = os.path.dirname(os.path.abspath(__file__))
    SCAN_DIR = os.path.join(HERE, "source_images")
    ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")

    # canonical tune set = union of scans and verified ABCs
    scans = {os.path.splitext(os.path.basename(p))[0]: p
             for p in glob.glob(os.path.join(SCAN_DIR, "*.png"))}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(ABC_DIR, "*-verified.abc"))}

    tunes = sorted(set(scans) | set(verified), key=lambda s: sort_key(s))
    all_files = []
    for tune in tunes:
        if tune in verified:
            all_files.append(verified[tune])   # crisp vector engraving
        elif tune in scans:
            all_files.append(scans[tune])       # original scan
    n_eng = sum(1 for f in all_files if f.endswith(".abc"))
    n_scan = len(all_files) - n_eng
```
Then update the summary print:
```python
    print(f"Processing {len(all_files)} tunes ({n_eng} engraved, {n_scan} scanned)...")
```
(Delete the old `print(f"Processing {len(all_files)} files ...")` line and the now-unused `len(png_files)/len(abc_files)` reference.) Ensure `import os` is present (it is).

- [ ] **Step 3: Verify the PDF builds and selection is correct**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 make_pdf.py /tmp/WOFTA_test.pdf 2>&1 | head -20
.venv/bin/python3 make_pdf.py /tmp/WOFTA_test.pdf 2>&1 | grep -i "engraved" 
```
Expected: "Processing … tunes (9 engraved, 28x scanned)…", no tune listed twice, PDF written to /tmp. Spot-check a page list line shows e.g. `Angeline the Baker-verified.abc` (engraved) and an un-finalized tune as `.png`.

- [ ] **Step 4: Commit**

```bash
git add make_pdf.py
git commit -m "feat: make_pdf embeds verified engraving per tune, falls back to source scan"
```

---

### Task 12: README, next_steps header note, final docs

**Files:**
- Create: `notation_pipeline/README.md`
- Modify: `notation_pipeline/docs/next_steps.md` (header note only)

- [ ] **Step 1: Write notation_pipeline/README.md**

```bash
cat > /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/README.md <<'EOF'
# notation_pipeline

Turns the WOFTA tune scans into clean ABC notation, two phases. The published book
(`../WOFTA_tunes.pdf`, built by `../make_pdf.py`) uses the engraving for every tune that
reaches the `-verified` tier and the original scan for the rest.

## Layout

- `bin/`     — all pipeline scripts (run from anywhere; they locate their own root)
- `abc/`     — the transcriptions, in tiers (see below)
- `docs/`    — `next_steps.md` (forward plan), `omr_findings.md` (experiment history),
               `abandoned_transcription_attempts.md`
- `renders/` — engraving PNGs for the comparison report
- `reports/` — `finalized_report.html` (scan vs engraving, per finalized tune)
- `batch_output/` — intermediate Audiveris `.omr`/`.mxl` (gitignored; the resume checkpoint)
- `health_scores.tsv` — per-tune OMR quality, worst-first queue ordering
- `tracking.md` — the per-tune verification ledger (auto-generated)

## ABC tiers (in abc/)

- `<Tune>-draft.abc`     — Phase 1 automated batch output (rough)
- `<Tune>-candidate.abc` — Phase 2 GUI-corrected + chords, passed automated checks
- `<Tune>-verified.abc`  — human signed-off; **this is what the PDF publishes**

## Phase 1 — batch (unattended)

`bin/batch_all.sh` runs `bin/batch_tune.sh` over every scan:
preprocess (`normalize_interline.py`) → Audiveris → `clean_omr.py` → `clean_mxl.py` →
ABC. Output: `batch_output/<Tune>/` + `abc/<Tune>-draft.abc`. Resumable (skips tunes
with a `clean.omr`).

## Phase 2 — interactive cleanup (one tune at a time)

1. `bin/cleanup_keep.sh` (or `cleanup_loop.sh`) opens the worst-scoring tune's `clean.omr`
   in the Audiveris GUI. Fix notes/key/clef, **Save (Ctrl+S)**, close.
2. `bin/export_tune.sh "Tune"` exports → cleans → `abc/<Tune>-candidate.abc` → renders →
   `validate_abc.py`. Add title + chords to the candidate ABC by reading the scan.
3. Eyeball the render vs the scan (`bin/build_report.sh` → `reports/finalized_report.html`).
4. `bin/promote_tune.sh "Tune"` renames candidate → `-verified` (the sign-off) and re-renders.
5. `bin/build_tracking_sheet.py` refreshes `tracking.md`.

## Health / triage

`bin/health_score.py` scores every `batch_output/*/clean.omr` (key/time/Ashokan-tell/grade),
worst-first, into `health_scores.tsv` — that ordering drives the Phase-2 queue.
EOF
```

- [ ] **Step 2: Add a header note to docs/next_steps.md**

Insert near the top of `docs/next_steps.md` (after the title line `# OMR Pipeline — Next Steps`):
```markdown
> **Layout note (2026-06-12 reorg):** scripts now live in `notation_pipeline/bin/`
> (run e.g. `bash bin/cleanup_keep.sh` or `python3 bin/build_tracking_sheet.py`).
> ABC tiers were renamed: the old `-final.abc` is split into `-candidate.abc`
> (machine-checked) and `-verified.abc` (human-signed-off, the PDF gate);
> `validate_final.py` → `bin/validate_abc.py`; `-gold.abc` references are retired.
> Source scans moved to `../source_images/`. Older command examples below may show
> the pre-reorg flat paths.
```

- [ ] **Step 3: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add notation_pipeline/README.md notation_pipeline/docs/next_steps.md
git commit -m "docs: add notation_pipeline/README and reorg note in next_steps"
```

---

### Task 13: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the read-only pipeline checks**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
echo "== health_score ==";       .venv/bin/python3 notation_pipeline/bin/health_score.py | head -2
echo "== render a verified ==";  bash notation_pipeline/bin/render_abc.sh "notation_pipeline/abc/Angeline the Baker-verified.abc" /tmp/ab.png && ls -la /tmp/ab.png
echo "== validate_abc --all ==";  .venv/bin/python3 notation_pipeline/bin/validate_abc.py --all | tail -3
echo "== tracking --check ==";    .venv/bin/python3 notation_pipeline/bin/build_tracking_sheet.py --check | grep -c '| Yes |'
echo "== build_report ==";        bash notation_pipeline/bin/build_report.sh
echo "== make_pdf ==";            .venv/bin/python3 make_pdf.py /tmp/WOFTA_test.pdf 2>&1 | tail -2
```
Expected: health prints rows; render writes `/tmp/ab.png`; `validate_abc --all` runs clean; tracking `| Yes |` count = `9`; report writes; make_pdf finishes with "Done."

- [ ] **Step 2: Confirm no lingering references to old names/paths**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
echo "hardcoded paths:"; grep -rn '/home/porter/Documents/banjo/WOFTA/tune_images' notation_pipeline/bin || echo "  none"
echo "validate_final refs:"; grep -rn 'validate_final' notation_pipeline || echo "  none"
echo "-final.abc refs:"; grep -rn -- '-final\.abc' notation_pipeline/bin make_pdf.py || echo "  none"
echo "-gold refs:"; grep -rn -- '-gold' notation_pipeline/bin make_pdf.py || echo "  none"
```
Expected: each prints "none" (or only matches inside comments you intend to keep — there should be none in `bin/` or `make_pdf.py`).

- [ ] **Step 3: Open the report and a PDF spot-check visually (manual)**

```bash
firefox /home/porter/Documents/banjo/WOFTA/tune_images/notation_pipeline/reports/finalized_report.html &
firefox /tmp/WOFTA_test.pdf &
```
Manually confirm: report shows scan-vs-engraving for the 9 verified tunes with images loading; PDF shows verified tunes as crisp engravings and others as scans, none duplicated.

- [ ] **Step 4: Final top-level sanity listing**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
echo "== repo root =="; ls -p
echo "== notation_pipeline =="; ls -p notation_pipeline
```
Expected root: `source_images/`, `notation_pipeline/`, `old_images/`, `staff_reinforcement/`, `docs/`, `make_pdf.py`, `make_pdf.sh`, `WOFTA_tunes.pdf`, `.venv/`. Expected NP: `bin/ docs/ abc/ renders/ reports/ batch_output/ README.md .gitignore health_scores.tsv tracking.md`.

---

### Task 14: Update agent memory

**Files:** memory files under `/home/porter/.claude/projects/-home-porter-Documents-banjo-WOFTA-tune-images/memory/`

- [ ] **Step 1: Update the relevant memory files**

Update these memories to reflect the new layout (edit in place; keep the index `MEMORY.md` line pointers):
- `project_pdf_pipeline.md` — `make_pdf.py` now selects `notation_pipeline/abc/<Tune>-verified.abc` (vector) per tune, else `source_images/<Tune>.png`; scans live in `source_images/`.
- `project_transcription.md` / `project_phase2_cleanup.md` — scripts moved to `notation_pipeline/bin/`; ABC tiers are `-draft`/`-candidate`/`-verified` (was `-final`; `-gold` retired); `validate_final.py` → `validate_abc.py`; new `promote_tune.sh`; `Verified?` in `tracking.md` is auto-derived from `-verified.abc` presence.

- [ ] **Step 2: No commit needed** (memory dir is outside the repo). Confirm `MEMORY.md` still lists each updated file with a one-line pointer.

---

## Self-Review (completed by plan author)

- **Spec coverage:** structure (T3,T10,T12), delete dead-ends (T1), source_images (T10), ABC tiers + migration (T6,T7), gold retirement (T1 step 4 + T6), promote_tune (T8), make_pdf selection (T11), validate_abc rename (T6), build_report/tracking changes (T9,T6), path uniformity + hardcode fix (T4,T5), README/.gitignore/next_steps (T2,T12), Honest John move (T10), verification (T13), memory (T14). All spec sections map to a task.
- **Placeholder scan:** every code step shows concrete edits/commands; no TBD/TODO.
- **Type/name consistency:** `validate_abc.py`, `discover_all_finals()` (kept name, redefined body), `is_verified()`, `-candidate`/`-verified` suffixes, `PIPELINE_DIR`/`HERE`/`ROOT` used consistently across shell and Python tasks.
