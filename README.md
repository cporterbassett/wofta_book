# WOFTA tune book

Turning ~270 scanned/photocopied old-time & Celtic tune images into a single clean,
engraved book — `WOFTA_tunes.pdf`. The book improves tune-by-tune: each tune starts as
its raw scan and is replaced by a clean engraving once it's been transcribed and verified.

## The flow

```
raw scans ──▶ sources/scans/ ──▶ transcribe/ (OMR + GUI cleanup) ──▶ abc/*-verified.abc
                   │                                                          │
                   └──────────────────── book/make_wofta.py ──────────────────┘
                                  (verified engraving per tune, else the scan)
```

**1. Prep raw images** → clean `<Tune>.png` in `sources/scans/`.
Tools in `image_prep/`, driven by the step-by-step guide **`docs/raw_image_prep.md`**
(extract from PDF → de-blank → trim → name → deskew → de-gray). No single command — it's
a per-image, eyeball-as-you-go process.

**2. Transcribe** each scan to ABC (Audiveris OMR + manual GUI cleanup). Two phases —
see **`transcribe/README.md`**, live worklist in `transcribe/docs/next_steps.md`. Scripts
live in the top-level `bin/`:
```bash
# Phase 1 — batch OMR (unattended): scans → abc/<Tune>-draft.abc
bin/batch_all.sh            # all (resumable);  bin/batch_tune.sh "Tune" for one

# Phase 2 — GUI cleanup (one tune at a time), worst-first
bin/cleanup_keep.sh         # keep-list subset (cleanup_loop.sh for full corpus)
#   ↑ opens clean.omr in Audiveris → fix, Ctrl+S, close → writes abc/<Tune>-candidate.abc
bin/promote_tune.sh "Tune"  # sign off: candidate → -verified (publishes to the book)
bin/build_tracking_sheet.py # refresh tracking.md ledger
```

**3. Assemble the books** → `output/` (per tune: `-verified` engraving as crisp
vector if it exists, else the original scan):
```bash
./make_pdf.sh                                   # WOFTA_tunes.pdf (+ _comparison.pdf)
.venv/bin/python3 book/make_tin_whistle_pdf.py "output/Tin Whistle.pdf"
.venv/bin/python3 book/make_sand_and_sawdust_pdf.py "output/Sand and Sawdust 2026.pdf"
```

## Directory map

| Path | What |
|------|------|
| `abc/` | Verified ABC transcriptions, `<Tune>-verified.abc` — the most important artifact in the repo. |
| `sources/` | All raw tune source material (tracked, one non-churning copy each). |
| `sources/scans/` | Clean source scans, one `<Tune>.png` per tune (the canonical tune list); `verified/` = verified-clean scans; `originals/` = each tune's oldest raw scan. |
| `sources/pdfs/` | Published lead-sheet PDFs (incl. the `add-ons-2026/` batch); see `MANIFEST.md`. |
| `sources/odt/` · `sources/text/` | LibreOffice originals and lyric/chord text pages used by some tunes. |
| `bin/` | The transcription pipeline scripts (batch OMR, cleanup, verify, promote). Add to `PATH` for convenience. |
| `transcribe/` | The OMR → ABC pipeline's docs, reference material, and tracking. Has its own README. |
| `book/` | PDF build code. `make_pdf.py` = shared engine (renderer registry + `build_book` + comparison), imported by the three book scripts. `make_wofta.py` / `make_sand_and_sawdust_pdf.py` / `make_tin_whistle_pdf.py` = thin per-book configs. |
| `image_prep/` | Tools that extract/clean raw images *before* `sources/scans/` (PDF cutters, ABC→PNG proof). |
| `staff_reinforcement/` | Experimental scan material (staff-line reinforcement). |
| `docs/` | Project docs (see below). |
| `output/` | Generated book PDFs. Git-ignored (reproducible from sources + code). |
| `scratch/` | OMR intermediates (`batch_output/`, `renders/`). Git-ignored. |

## Where to read for what

- **Cleaning new raw scans** → `docs/raw_image_prep.md`
- **The transcription pipeline (the bulk of the work)** → `transcribe/README.md`
- **What to work on next / current status** → `transcribe/docs/next_steps.md`
- **Why the OMR is set up the way it is (experiment history, dead ends)** →
  `transcribe/docs/omr_findings.md`, `abandoned_transcription_attempts.md`
- **Design/plan history for past changes** → `docs/superpowers/{specs,plans}/`
  (process artifacts; not needed to get started)

A new agent should need only this README plus the one doc for the task at hand.

## Environment

Python venv at `.venv/` (img2pdf, pikepdf, Pillow, opencv, music21, abc_xml_converter).
External tools: Audiveris (flatpak), abcm2ps, Ghostscript, ImageMagick.
