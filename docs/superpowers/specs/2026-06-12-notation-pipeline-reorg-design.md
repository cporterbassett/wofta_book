# notation_pipeline/ reorganization — design

_2026-06-12_

## Problem

`notation_pipeline/` began as an experiment and became a core part of the project, but
the directory is a flat dump of ~50 top-level items mixing four unrelated kinds of thing:
live pipeline code, concluded dead-end experiments, docs, and data/scratch. It is hard for
a human to grok which scripts are actually part of the working pipeline.

## Goal

Reorganize into a structure a human can read at a glance, with the working pipeline clearly
separated from docs, data, and disposable scratch. The working pipeline must still run after
the move.

## Decisions (from brainstorming)

- **Full restructure** — move live scripts into subfolders and rewrite all cross-script and
  venv relative paths so everything still runs.
- **Delete dead-ends** rather than archive — it is a git repo, nothing is lost.
- **Track** the live, viewable, small generated set (9 final renders + the live report);
  delete experiment renders and the stale Phase-1 report.
- Also delete the 22 stray `angeline_oemer*.png` scratch files in the parent `tune_images/`.

## Target structure

```
notation_pipeline/
├── README.md            ← NEW: what this is, the 2-phase workflow, script index
├── .gitignore           ← NEW: batch_output/, __pycache__/, *.pyc, *.ly, *.cropped.png
├── bin/                 ← all 15 live scripts (flat)
│   ├── batch_tune.sh   batch_all.sh                       (phase 1)
│   ├── cleanup_loop.sh  cleanup_keep.sh  export_tune.sh   (phase 2)
│   ├── normalize_interline.py  clean_omr.py  clean_mxl.py
│   ├── health_score.py  compare_abc.py  validate_final.py
│   ├── build_tracking_sheet.py  render_abc.sh  build_report.sh  overlay_diff.py
├── docs/
│   ├── next_steps.md  omr_findings.md  abandoned_transcription_attempts.md
├── abc/                 ← source of truth: *-draft / *-final / *-gold only
├── renders/             ← *-final renders only (consumed by the report)
├── reports/
│   └── finalized_report.html
├── batch_output/        ← intermediate .omr/.mxl checkpoints (gitignored, kept on disk)
├── health_scores.tsv    ← live data (top level; scripts reference it)
└── tracking.md          ← live human-facing ledger (top level)
```

**Why a flat `bin/` rather than phase-split folders:** the two-phase model is already
documented in `next_steps.md`, and several scripts (`clean_omr`, `clean_mxl`,
`health_score`, `compare_abc`) are shared across both phases — physically splitting them
forces an awkward `lib/` and lengthens every cross-reference. A flat `bin/` plus a README
that groups scripts by phase gives the same clarity without the path pain.

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
`angeline_audiveris_updated.cropped.png`, and the stale `omr_report.html`.

**Dead `abc/` variants (~20):** `*-audiveris-*`, `*-blanked`, `*-original*`, `*-raw`,
`*-1.5x`, `*-thesession`, `*-abcnotation`, bare `Arkansas Traveler.abc` /
`Blackberry Blossom.abc`, and `Angeline the Baker.ly`. Keeps the ~283 draft/final/gold.

**Dead renders:** the `*-audiveris-*`, `*-thesession`, `*-l4`/`-l8`, `Angeline_audiveris.png`
experiment renders. Keeps the 9 tunes' `*-final.render.png` / `*-final.trim.png`.

**Parent-dir scratch:** the 22 `angeline_oemer*.png` files in `tune_images/`.

## Path handling (the risk, made uniform)

Every script in `bin/` gets the same root computation derived from its own location:

- shell: `PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`,
  `IMAGES_DIR="$(cd "${PIPELINE_DIR}/.." && pwd)"`
- python: `HERE = dirname(abspath(__file__))`, `ROOT = dirname(HERE)`; data refs
  (`batch_output`, `health_scores.tsv`, `tracking.md`, `abc/`) hang off `ROOT`;
  `sys.path.insert(0, HERE)` keeps sibling imports (`compare_abc`, `validate_final`) working.

All data refs (`abc/`, `renders/`, `batch_output/`, `health_scores.tsv`, `tracking.md`,
sibling scripts) route through `PIPELINE_DIR`; the venv through `IMAGES_DIR/.venv`.

This also fixes a latent bug: `batch_tune.sh` and `cleanup_loop.sh` currently **hardcode**
`/home/porter/Documents/banjo/WOFTA/tune_images`, which breaks on macOS. Deriving the root
from script location makes them machine-independent — relevant because the same configs are
used on both Linux Mint and macOS.

`build_report.sh` / `finalized_report.html` need their relative links updated for the new
`reports/` location: report → renders becomes `../renders/...`, report → scan becomes
`../../<Tune>.png`.

## Verification

After the move, with no manual GUI step required:

1. `bin/health_score.py` runs and reproduces `health_scores.tsv` rows (reads `batch_output/`).
2. `bin/render_abc.sh "abc/<a final>.abc" /tmp/out.png` renders without path errors.
3. `bin/validate_final.py --all` runs (imports `compare_abc`, reads `health_scores.tsv`).
4. `bin/build_tracking_sheet.py --check` runs (imports `validate_final`, reads the tsv).
5. `bin/build_report.sh` regenerates `reports/finalized_report.html` with working image links.

Each of these is read-only or idempotent — none requires Audiveris or the GUI.

## Out of scope

- No logic changes to any script beyond path resolution.
- `batch_tune.sh` / `cleanup_loop.sh` GUI/Audiveris behavior unchanged.
- `next_steps.md` content is preserved as-is (only moved to `docs/`); its many internal
  references to script names stay valid because the names are unchanged — only their
  directory moved. A short note about the new `bin/` location will be added to `next_steps.md`.
```
