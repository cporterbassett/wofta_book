# 2026 add-ons & redos — handoff (Deliverables 2 & 3)

Spec: `docs/superpowers/specs/2026-06-21-2026-addons-redos-design.md`
Source PDFs: `/home/porter/Documents/banjo/WOFTA/2026/2026 add-ons & redos copy/` (58)

## Done (Deliverable 1)
The 11 already-verified tunes were diffed and their `-verified.abc` files edited per
the user's calls. Reports: `notation_pipeline/reports/2026_verified_diff.pdf` (11) and
`2026_verified_diff_4tunes.pdf` (the 4 re-touched). No further action unless the user
revisits **Clinch Mountain Backstep** (the one verified tune left unedited).

## Reusable tooling
- **`2026_diff_work/compose_diff.py`** — builds a side-by-side landscape comparison PDF:
  left = `<key>-cur.png`, right = `<key>-new.png`, one tune per page, with a per-tune
  "What's different" text band from a descriptions JSON. Robust content-crop (ink-density,
  ignores specks/©). Invocation:
  ```
  python3 notation_pipeline/reports/2026_diff_work/compose_diff.py \
     <work_dir> <out.pdf> <map.txt> "<LEFT_LABEL>" <descriptions.json>
  ```
  `map.txt` lines are `key|...`; the script uses the first `|`-field as `<key>`.
- Activate venv first: `source .venv/bin/activate`.
- Rasterize a PDF page: `gs -q -dNOPAUSE -dBATCH -sDEVICE=pnggray -r150 -dFirstPage=1 -dLastPage=1 -sOutputFile=out.png "<pdf>"`.

## Deliverable 2 — replace diff report (23 tunes)  ✅ DONE (2026-06-21)
Map: **`2026_diff_work/replace_map.txt`** (`tune|pdf_basename`). Left = the EXISTING
`source_images/<tune>.png` scan (no verified ABC yet); right = the new PDF.
Report: **`notation_pipeline/reports/2026_replace_diff.pdf`** (23 pages, one tune each).
Pairs in `2026_diff_work/replace/`, descriptions in `descriptions_replace.json`.
Rebuild command:
```
python3 notation_pipeline/reports/2026_diff_work/compose_diff.py \
  notation_pipeline/reports/2026_diff_work/replace \
  notation_pipeline/reports/2026_replace_diff.pdf \
  notation_pipeline/reports/2026_diff_work/replace_map.txt \
  "EXISTING SCAN" \
  notation_pipeline/reports/2026_diff_work/descriptions_replace.json \
  "What's different (left = existing scan, right = new 2026 PDF):"
```
### Swaps applied (2026-06-21, per user decisions)
**20 of 23** `source_images/<tune>.png` were replaced with the new PDF (rasterized 200dpi
gray → trim → deskew≥0.3 → normalized to 1500px wide for oversized scans; sigmoidal
`8,50%` contrast on the 3 faded scans **Morrison's Jig**, **Gypsy Waltz**, **Clearwater
Stomp**). Staged copies in `2026_diff_work/replace/staged/`; originals preserved in git and
as `replace/<tune>-cur.png`. Not committed.
**Kept original (NOT swapped):**
- **Ross's Reel #4** — new PDF is the same setting at poorer quality.
- **Me and My Fiddle** — revisit later (ending re-annotated Coda→"End with 1A").
- **Road House Ramble** — revisit later (ending re-annotated To Coda→"Final Ending").

These tunes have no verified ABC yet, so the new scan just becomes the OMR/verify source.

Findings worth the user's attention before swapping:
- **Far From Home** — genuinely different chord setting (B part Em-D-C-G vs current
  Em-Bm-Em-G); the others are same-setting re-engravings or annotation tweaks.
- **Red Apple Rag** — new ADDS chords (current had none) + explicit repeats.
- **Miss McCloud's Reel** / **Morrison's Jig** — big legibility upgrade (current nearly
  illegible / faded; new is a clean transcription).
- **Me and My Fiddle**, **Road House Ramble** — ending instruction re-annotated
  (Coda/D.C. → "End with 1A" / "Final Ending").
- Two new PDFs have a literal trailing space in the filename ("Clearwater Stomp fixed .pdf",
  "Road House Ramble fixed .pdf") — the build script tolerates it.

compose_diff.py gained two things this round: an optional 6th arg `band_header`, and it now
skips `#` comment lines in the map.

## Deliverable 3 — prep + draft the 24 new tunes
Map: **`2026_diff_work/new_map.txt`** (`pdf_basename|proposed_canonical`).
1. **Confirm the canonical name list with the user first** (leading "The" → ", The", key
   suffixes stripped, etc.).
2. Per tune: PDF → cleaned PNG per `docs/raw_image_prep.md` (rasterize, trim, deskew,
   sigmoidal-contrast as needed) → `source_images/<canonical>.png`.
3. Phase-1 OMR: `bash notation_pipeline/bin/batch_tune.sh "<canonical>"` (or batch_all.sh)
   → `abc/<canonical>-draft.abc`, queued for the user's Phase-2 cleanup loop.
4. `python3 notation_pipeline/bin/build_tracking_sheet.py` to refresh the ledger.

## User preferences locked in this work
- Comparison PDFs: side-by-side (left=current, right=new) + per-tune "what's different"
  text band on the page. "Only tell me what's different" — never restate what's the same.
- EasyABC launcher is `/home/porter/bin/easyabc` and needs an ABSOLUTE file path.
- abcm2ps text placement: `%%begintext right` + a small negative `%%vskip` to seat a
  performance note snug, right-justified, below the last staff.
