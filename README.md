# WOFTA tune book

Turning ~270 scanned/photocopied old-time & Celtic tune images into a single clean,
engraved book — `WOFTA_tunes.pdf`. The book improves tune-by-tune: each tune starts as
its raw scan and is replaced by a clean engraving once it's been transcribed and verified.

## The flow

```
raw scans ──▶ source_images/ ──▶ notation_pipeline (OMR + GUI cleanup) ──▶ abc/*-verified.abc
                   │                                                              │
                   └─────────────────────── make_wofta.py ────────────────────────┘
                                    (verified engraving per tune, else the scan)
```

**1. Prep raw images** → clean `<Tune>.png` in `source_images/`.
Tools in `image_prep/`, driven by the step-by-step guide **`docs/raw_image_prep.md`**
(extract from PDF → de-blank → trim → name → deskew → de-gray). No single command — it's
a per-image, eyeball-as-you-go process.

**2. Transcribe** each scan to ABC (Audiveris OMR + manual GUI cleanup). Two phases —
see **`notation_pipeline/README.md`**, live worklist in `notation_pipeline/docs/next_steps.md`:
```bash
# Phase 1 — batch OMR (unattended): scans → abc/<Tune>-draft.abc
bash notation_pipeline/bin/batch_all.sh            # all (resumable);  batch_tune.sh "Tune" for one

# Phase 2 — GUI cleanup (one tune at a time), worst-first
bash notation_pipeline/bin/cleanup_keep.sh         # keep-list subset (cleanup_loop.sh for full corpus)
#   ↑ opens clean.omr in Audiveris → fix, Ctrl+S, close → writes abc/<Tune>-candidate.abc
bash notation_pipeline/bin/promote_tune.sh "Tune"  # sign off: candidate → -verified (publishes to the book)
python3 notation_pipeline/bin/build_tracking_sheet.py   # refresh tracking.md ledger
```

**3. Assemble the book** → `WOFTA_tunes.pdf` (per tune: `-verified` engraving as crisp
vector if it exists, else the original scan):
```bash
./make_pdf.sh
```

## Directory map

| Path | What |
|------|------|
| `source_images/` | The clean source scans, one `<Tune>.png` per tune (the canonical tune list). |
| `notation_pipeline/` | The OMR → ABC transcription pipeline. Has its own README. |
| `image_prep/` | Tools that extract/clean raw images *before* `source_images/` (PDF cutters, ABC→PNG proof). |
| `make_pdf.py` | Shared PDF engine (renderer registry + `build_book` + comparison). Imported by the three book scripts; not run directly. |
| `make_wofta.py` / `make_pdf.sh` | Builds `WOFTA_tunes.pdf` (+ `_comparison.pdf`) from scans + verified ABCs, via the `make_pdf.py` engine. |
| `make_sand_and_sawdust_pdf.py` / `make_tin_whistle_pdf.py` | The other two books — thin `build_book` configs on the same engine. |
| `docs/` | Project docs (see below). |
| `staff_reinforcement/` | Experimental scan material (staff-line reinforcement). |

## Where to read for what

- **Cleaning new raw scans** → `docs/raw_image_prep.md`
- **The transcription pipeline (the bulk of the work)** → `notation_pipeline/README.md`
- **What to work on next / current status** → `notation_pipeline/docs/next_steps.md`
- **Why the OMR is set up the way it is (experiment history, dead ends)** →
  `notation_pipeline/docs/omr_findings.md`, `abandoned_transcription_attempts.md`
- **Design/plan history for past changes** → `docs/superpowers/{specs,plans}/`
  (process artifacts; not needed to get started)

A new agent should need only this README plus the one doc for the task at hand.

## Environment

Python venv at `.venv/` (img2pdf, pikepdf, Pillow, opencv, music21, abc_xml_converter).
External tools: Audiveris (flatpak), abcm2ps, Ghostscript, ImageMagick.
