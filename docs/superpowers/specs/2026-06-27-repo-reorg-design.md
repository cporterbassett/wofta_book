# Repo Reorganization — Design

Date: 2026-06-27
Status: Approved design, pending implementation plan

## Problem

The `tune_images` repo has grown messy across several axes:

1. **Code is half-separated.** Image-cleanup / OMR / transcription code lives in
   `notation_pipeline/` (22 scripts in `bin/`), `image_prep/`, and
   `staff_reinforcement/`. PDF-building code lives at the repo root
   (`make_pdf.py` engine + `make_wofta.py` / `make_sand_and_sawdust_pdf.py` /
   `make_tin_whistle_pdf.py` thin book configs). The split is informal and the
   directory names do not advertise it.

2. **The scripts directory is buried.** `notation_pipeline/bin/` is two levels
   deep and not on `PATH`.

3. **Disk bloat.** The working tree is ~8.1 G. Breakdown:
   - `.venv/` = 6.5 G — gitignored, rebuildable, not a repo problem.
   - `.git/` = 1.2 G — **history bloat** from repeatedly committed *derivative*
     images (`new_book/tune_NNN.png`, `old_book/*`, duplicate `Title.png`, etc.).
     History holds **1,249 image blobs**; the working tree has **965**. Each tune
     has 4–7 historical versions ("dozens per tune" over the project's life).
   - `notation_pipeline/batch_output/` (329 M) + `reports/` (101 M) = regenerable
     OMR scratch.

4. **Source material is scattered.** A tune's source can be a scan (`.png`), a
   published lead sheet (`.pdf`), a LibreOffice page (`.odt`), or verified ABC.
   These live in *four* different places: repo root (loose `.odt`),
   `notation_pipeline/reference_sources/` (`.pdf` + `.odt`), `source_images/`
   (`.png`), and the sibling `../2026/` folder (`.pdf`).

5. **`../2026` is not incorporated.** That sibling holds ~216 published tune PDFs
   (one clean PDF per tune, tagged by source collection — `[KDEd]`, `[PC1]`,
   `[NEFR]`, `[WOTFA]`, …) plus a `2026 add-ons & redos copy/` subfolder of 58
   PDFs. These are the *same kind of thing* as the scans — tune source material —
   just one clean PDF per tune instead of dozens of scan versions.

## Key facts that shaped the design

- **The books build directly from scan PNGs.** All three book builders read
  `source_images/*.png` as input; `make_sand_and_sawdust_pdf.py` additionally
  pulls per-tune sources by `kind` (`abc | png | pdf | odt | text`) from the
  scattered locations above.
- **Cleaned scans cannot be regenerated** from a recorded recipe (cleanup
  included manual/GUI steps). They must be *preserved*, not recomputed.
- **The bloat was churn, not originals.** A single committed copy of a file never
  changes and adds no ongoing weight. The 1.2 G came from re-committing changing
  versions.
- **Raw originals live only in git history** (the corpus moved repo-root →
  `new_book/` → `source_images/` with renames). A naive history purge would
  destroy them, so originals must be *extracted first*.
- **Scans and PDFs largely cover the same tunes.** Of ~290 scanned tunes and ~274
  PDF tunes, well over 182 overlap (fuzzy matching undercounts); the rest are new
  additions or scans without a clean PDF.
- No git remote, single `master` branch, single worktree → a history rewrite is
  safe with nothing to coordinate.

## Decisions (from brainstorming)

- **One repo**, not two. ~400 M of tracked content post-cleanup is trivial and
  gives free sync across the user's Linux Mint + macOS machines.
- **History will be rewritten** with `git-filter-repo` to reclaim the 1.2 G.
- **Per file, preserve the oldest version + the latest version; drop the middle.**
  Oldest = first blob in history (following renames); latest = current working
  tree. Intermediate churn is discarded.
- **Keep one non-churning copy of originals in the repo** (no separate assets
  repo, no external archive) — agreed it adds no churn weight.
- **Clean code/data separation.** Pipeline code in `transcribe/`, book builder in
  `book/`, scripts in a top-level `bin/` on `PATH`.
- **The ABCs are the most important artifact** in the repo and get a top-level
  `abc/`, not a folder buried under the pipeline.
- **All raw source material is unified under `sources/`** (scans + pdfs + odt),
  fixing the four-way scatter. ABC is excluded — it is the *product* of the
  transcription work, not a raw source, and lives in `abc/`.

## Target layout

```
tune_images/                 git repo — small, clean history
  abc/                       verified ABC transcriptions ── tracked (the crown jewels)
  bin/                       all scripts, added to PATH
  transcribe/                OMR / cleanup pipeline code (was notation_pipeline/)
    docs/
  book/                      PDF builder
    make_pdf.py              shared engine
    make_wofta.py            book config
    make_sand_and_sawdust_pdf.py
    make_tin_whistle_pdf.py
  sources/                   all raw tune source material ── tracked
    scans/                   scan imagery, three tiers (was source_images/)
      *.png                  170 latest working scans (unverified tunes)
      verified/              120 verified-clean scans (engrave from ABC)
      originals/             one oldest copy per tune (~290), recovered from history
    pdfs/                    published lead sheets (was ../2026/ + reference_sources/ PDFs)
      add-ons-2026/          the 58-PDF "add-ons & redos" working batch
    odt/                     LibreOffice originals (loose root .odt + reference_sources/ .odt)
  docs/
  output/                    generated book PDFs          ── ignored
  scratch/                   batch_output, reports, renders, *.cropped.png ── ignored
```

### What lives in `sources/scans/`

`sources/scans/` is the home for scan imagery and nothing else. The 290 scanned
tunes form a clean partition — **zero filename overlap** between the two existing
tiers — plus a new originals tier:

| Contents | Count | Role |
| --- | --- | --- |
| `sources/scans/*.png` | 170 | Latest working scans the book builders read directly (unverified tunes) |
| `sources/scans/verified/*.png` | 120 | Verified-clean scans, kept for reference/comparison (these tunes engrave from ABC) |
| `sources/scans/originals/*.png` | ~290 | **New** — oldest committed version of each tune, recovered from history; one flat copy per tune name |

The originals extraction (execution step 1) must cover **both** existing tiers —
all 290 tunes (top-level *and* `verified/`), not just the 170. `originals/` is a
single flat folder keyed by tune name; it does not mirror the verified/unverified
split.

### Tracked vs ignored

| Path | Tracked? | Why |
| --- | --- | --- |
| `abc/` | yes | verified transcriptions — text, irreplaceable, primary artifact |
| `bin/`, `transcribe/` (code), `book/`, `docs/` | yes | source code / text |
| `sources/scans/` (latest + verified + originals) | yes | book source of truth; can't regenerate; one non-churning copy each |
| `sources/pdfs/`, `sources/odt/` | yes | published/original source material; small, useful offline |
| `scratch/` (batch_output, reports, renders, cropped) | no | regenerable from sources + code |
| `output/` (book PDFs) | no | regenerable by `book/make_*.py` |
| `.venv/`, `__pycache__/`, crash logs | no | rebuildable / runtime noise |

## Execution order

Originals are protected before anything destructive happens.

1. **Extract originals.** For each current scan in **both** tiers
   (`source_images/*.png` and `source_images/verified/*.png` — 290 tunes total),
   find its first committed version following renames
   (`git log --follow --diff-filter=A`) and write the oldest blob to the future
   `sources/scans/originals/<name>.png`. **Verify the recovered count (~290)
   before continuing.**
2. **Snapshot** the current working tree to an out-of-repo backup (belt and
   suspenders) before rewriting history.
3. **Rewrite history.** Install `git-filter-repo`; purge the derivative/duplicate
   image churn (`old_book/`, `new_book/`, `web_images/`, old `renders/`, dropped
   `*.png`) from all history. Confirm `.git` shrinks (~1.2 G → small).
4. **Restructure directories.** Create `abc/`, `bin/`, `transcribe/`, `book/`,
   `sources/{scans,pdfs,odt}/`; move existing files into place (ABC →
   `abc/`; scripts → `bin/`; `source_images/` → `sources/scans/`; loose `.odt`
   and `reference_sources/` `.odt` → `sources/odt/`; `reference_sources/` PDFs →
   `sources/pdfs/`).
5. **Fix paths.** Update hardcoded paths in the scripts and `make_*` files to the
   new layout (`source_images` → `sources/scans`; `notation_pipeline` →
   `transcribe`; `ABC_DIR` → `abc/`; `REF_DIR`/`ODT_DIR` → `sources/`; scratch
   and output locations). Add `bin/` to `PATH` via a mechanism that works on both
   Mint and macOS.
6. **Import `../2026`** into `sources/pdfs/` (top-level PDFs) and
   `sources/pdfs/add-ons-2026/` (the 58-PDF subfolder); generate a tracked
   manifest of what was imported.
7. **Write the new `.gitignore`** encoding the tracked/ignored split above.
8. **Verify** the three book builders still produce their PDFs from the new
   layout.

## Net result

~8.1 G → roughly **~400 M of tracked content** (originals + latest scans + source
PDFs/ODT + small code/ABC) plus a small clean git history. The 6.5 G `.venv`
stays ignored and rebuildable. Cleanup code is cleanly separated from
book-building code, `bin/` is on `PATH`, the ABCs sit front-and-center at `abc/`,
all tune source material is unified under `sources/`, `../2026` is folded in, and
every file keeps its oldest + latest version with the churn gone.

## Out of scope

- No change to the OMR / transcription *workflow* itself, only where its code,
  sources, and scratch live.
- No change to book layout/output format.
- No second repo, no git-lfs, no external asset store.
