# Tune-images repo reorganization + PDF render-selection — design

_2026-06-12_

## Problem

`notation_pipeline/` began as an experiment and became core, but the directory is a flat
dump of ~50 items mixing live pipeline code, concluded dead-ends, docs, and scratch. At the
same time the repo root holds 294 loose source-scan PNGs alongside the scripts. And the end
goal — a `WOFTA_tunes.pdf` that swaps messy scans for clean engravings as tunes are finished —
isn't wired up: `make_pdf.py` would emit a tune twice if both its scan and its final ABC were
in the glob.

## Goal

1. Reorganize the whole repo so a human can grok it at a glance: working pipeline separated
   from docs, data, and disposable scratch; source scans in their own directory.
2. Make `make_pdf.py` emit, **per tune**, the clean engraving where one is verified and the
   original scan otherwise — so the book improves automatically as tunes are signed off.
3. Encode transcription state in the **filename** (not a ledger column) so the publish gate
   can't drift out of sync.

## Decisions (from brainstorming)

- **Full restructure** of `notation_pipeline/`: live scripts into `bin/`, docs into `docs/`,
  rewrite all cross-script + venv relative paths so everything still runs.
- **Delete dead-ends** rather than archive — it's a git repo, nothing is lost.
- **Source scans** move to `source_images/` at the repo root.
- **PDF embeds vector** rendered from the verified ABC (what `make_pdf` already does for ABCs),
  falling back to the raster scan.
- **ABC tier rename**: `-final` → two tiers, `-candidate` (machine-checked) and `-verified`
  (human signed-off). `-verified` is the PDF gate. The 9 existing `-final.abc` migrate to
  `-verified` (trusted).
- Also delete the 22 stray `angeline_oemer*.png` scratch files in the repo root.

## Target structure

```
tune_images/
├── source_images/       ← 294 source scans <Tune>.png   (moved out of the root)
├── notation_pipeline/
│   ├── README.md        ← NEW: what this is, the 2-phase workflow, script index
│   ├── .gitignore       ← NEW: batch_output/, __pycache__/, *.pyc, *.ly, *.cropped.png
│   ├── bin/             ← all live scripts (flat) + the new promote_tune.sh
│   ├── docs/            ← next_steps.md, omr_findings.md, abandoned_transcription_attempts.md
│   ├── abc/             ← *-draft / *-candidate / *-verified / *-gold
│   ├── renders/         ← engraving renders (consumed by the report)
│   ├── reports/         ← finalized_report.html
│   ├── batch_output/    ← intermediate .omr/.mxl checkpoints (gitignored, kept on disk)
│   ├── health_scores.tsv
│   └── tracking.md
├── old_images/  staff_reinforcement/  docs/
├── make_pdf.py / make_pdf.sh   ← per tune: verified ABC if it exists, else source scan
└── WOFTA_tunes.pdf             (output)
```

**Why a flat `bin/`:** the two-phase model is already documented in `next_steps.md`, and
several scripts (`clean_omr`, `clean_mxl`, `health_score`, `compare_abc`) are shared across
both phases — physically splitting them forces an awkward `lib/` and lengthens every
cross-reference. A flat `bin/` plus a README that groups scripts by phase gives the same
clarity without the path pain.

## ABC tier model

| File                     | Meaning                                                       | Made by |
|--------------------------|--------------------------------------------------------------|---------|
| `<Tune>-draft.abc`       | Phase 1 auto batch (Audiveris). Rough, unverified.           | `batch_tune.sh` (unchanged) |
| `<Tune>-candidate.abc`   | Phase 2: GUI-corrected + chords/title, passed automated `validate_abc.py`. **Not** yet eyeball-checked. | `export_tune.sh` / `cleanup_loop.sh` (renamed from `-final`) |
| `<Tune>-verified.abc`    | Human eyeballed engraving vs scan and signed off. **PDF gate.** | `promote_tune.sh` (new tier) |

`-gold.abc` is **retired**: the 6 gold tunes are exactly the ones whose `-final` was promoted
from gold, so each will have an identical `-verified.abc`; gold's only other role (accuracy
benchmark for `compare_abc.py` during preprocessing experiments) is moot now those experiments
are concluded dead ends. The 6 gold files are deleted (git keeps the history). `abc/` is left
with just `-draft` (working queue) and `-verified` (signed-off).

A tune is in at most one Phase-2 tier: **promotion renames** `-candidate.abc` → `-verified.abc`
(`git mv`), which *is* the verification act. If a verified tune is later re-exported, a fresh
`-candidate.abc` appears alongside the stale `-verified.abc`; the human re-eyeballs and
re-promotes (overwriting `-verified`).

## PDF render-selection

`make_pdf.py` builds the book from a canonical tune list = **union** of `source_images/*.png`
stems and `notation_pipeline/abc/*-verified.abc` stems (the union is belt-and-suspenders; in
practice every tune's scan, including Honest John's, lives in `source_images/`). For each tune:

- if `notation_pipeline/abc/<Tune>-verified.abc` exists → render it as **vector** via LilyPond;
- else → embed `source_images/<Tune>.png` as raster.

Match key = ABC stem with `-verified` stripped, equal to the PNG stem. Existing packing /
page-layout logic is unchanged; it already mixes vector-ABC and raster-PNG pages.

Result today: 0 verified tunes → the PDF is all scans (correct — nothing is signed off yet).
Each `promote_tune.sh` run swaps one more scan for an engraving on the next build.

## Tooling changes (the `-final` → `-candidate`/`-verified` rename + paths)

- `export_tune.sh`, `cleanup_loop.sh` — write `abc/<Tune>-candidate.abc`.
- `validate_final.py` → rename **`validate_abc.py`**; validates `-candidate` (and `-verified`);
  `--all` discovers both tiers. (Update the `build_tracking_sheet.py` import.)
- **`promote_tune.sh`** (NEW, in `bin/`) — `git mv` candidate→verified, re-render, re-validate.
- `build_tracking_sheet.py` — `Verified?` column becomes **auto-derived** (`Yes` iff a
  `-verified.abc` exists); only `Notes` stays hand-edited. `Finalized?` = has candidate-or-verified.
- `build_report.sh` / `finalized_report.html` — include both tiers, badge which are verified;
  output to `reports/`. Relative links updated for the new location: report→renders becomes
  `../renders/...`, report→scan becomes `../../source_images/<Tune>.png`.
- `make_pdf.py` / `make_pdf.sh` — selection logic above; glob `source_images/` + `abc/*-verified.abc`.

## Path handling (made uniform)

Every script in `bin/` derives its root from its own location:

- shell: `PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`,
  `IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"`
- python: `HERE = dirname(abspath(__file__))`, `ROOT = dirname(HERE)`; data refs
  (`batch_output`, `health_scores.tsv`, `tracking.md`, `abc/`) hang off `ROOT`;
  `sys.path.insert(0, HERE)` keeps sibling imports working.

Data refs route through `PIPELINE_DIR`; the venv through `IMAGES_DIR/.venv`. This also fixes a
latent bug: `batch_tune.sh` and `cleanup_loop.sh` currently **hardcode**
`/home/porter/Documents/banjo/WOFTA/tune_images`, which breaks on macOS — relevant because the
same configs run on both Linux Mint and macOS.

## What gets deleted (git preserves all of it)

**Dead-end scripts (15):** `sweep_constants.py`, `glyph_cleanup_sweep.py`, `verify_mxl.py`,
`ensemble_abc.py`, `blank_chord_names.py`, `preprocess_opencv.py`, `transcribe.py`,
`fetch_abc.py`, `process_tune.sh`, `run_tune_pipeline.sh`, `survey_key_detection.sh`,
`survey_key_detection_2x.sh`, `test_preprocessing.sh`, `test_preprocessing2.sh`,
`test_preprocessing3.sh`.

**Dead data / dirs:** `tmp_pipeline/`, `preprocessing_tests/`, `web_images/`, `tests/`
(only tested a deleted script), `__pycache__/`, `diffs/`, `dilation_sweep_results.txt`,
`survey_results.tsv`, `survey_results_2x.tsv`, the stray
`Angeline the Baker.{musicxml,mxl,omr}`, `Angeline the Baker-20260611T0908.log`,
`Angeline the Baker_teaser.png`, `angeline_audiveris_updated.png`,
`angeline_audiveris_updated.cropped.png`, the stale `omr_report.html`.

**Dead `abc/` variants (~20 + 6 gold):** `*-audiveris-*`, `*-blanked`, `*-original*`, `*-raw`,
`*-1.5x`, `*-thesession`, `*-abcnotation`, bare `Arkansas Traveler.abc` /
`Blackberry Blossom.abc`, `Angeline the Baker.ly`, and the 6 now-redundant `*-gold.abc`
(see tier model). Keeps `-draft` + the migrated `-verified`. (`compare_abc.py` stays — it's
imported by `validate_abc.py` for measure-splitting, not for gold comparison.)

**Dead renders:** the `*-audiveris-*`, `*-thesession`, `*-l4`/`-l8`, `Angeline_audiveris.png`
experiment renders. Keeps the 9 tunes' engraving renders (renamed to the new tier).

**Repo-root scratch:** the 22 `angeline_oemer*.png` files in `tune_images/`.

## Migration

- `git mv` the 9 `abc/<Tune>-final.abc` → `abc/<Tune>-verified.abc`; rename their renders.
- 294 root PNGs → `source_images/` (`git mv`). mtime ordering preserved (move doesn't touch
  mtimes; `make_pdf` sorts by name anyway).
- Honest John's scan: `git mv old_images/Honest John.png source_images/` so all source scans
  live in one place. (Its `-gold.abc`, which referenced the `old_images/` path, is deleted in
  this same change, so nothing is left pointing at the old location.)

## Verification

After the move, with no Audiveris/GUI step required:

1. `bin/health_score.py` runs and reproduces `health_scores.tsv` rows (reads `batch_output/`).
2. `bin/render_abc.sh "abc/<a verified>.abc" /tmp/out.png` renders without path errors.
3. `bin/validate_abc.py --all` runs (imports `compare_abc`, reads `health_scores.tsv`).
4. `bin/build_tracking_sheet.py --check` runs; `Verified?` shows the 9 as `Yes`.
5. `bin/build_report.sh` regenerates `reports/finalized_report.html` with working image links.
6. `make_pdf.sh` runs end-to-end; spot-check that a verified tune appears as a crisp vector
   engraving and an unverified tune as its scan, with no tune duplicated.

## Out of scope

- No logic changes to any script beyond path resolution, the tier rename, and the
  `make_pdf` selection.
- Audiveris/GUI behavior of `batch_tune.sh` / `cleanup_loop.sh` is unchanged.
- `next_steps.md` content is preserved (only moved to `docs/`); a short header note records
  the new `bin/` location and the `-candidate`/`-verified` tier rename. Its runnable command
  examples (`python3 build_tracking_sheet.py`, etc.) are not individually rewritten.
- `old_images/`, `staff_reinforcement/`, and the repo-root `docs/` are left as-is.
```
