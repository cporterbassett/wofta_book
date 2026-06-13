# WOFTA tune book

Turning ~270 scanned/photocopied old-time & Celtic tune images into a single clean,
engraved book — `WOFTA_tunes.pdf`. The book improves tune-by-tune: each tune starts as
its raw scan and is replaced by a clean engraving once it's been transcribed and verified.

## The flow

```
raw scans ──▶ source_images/ ──▶ notation_pipeline (OMR + GUI cleanup) ──▶ abc/*-verified.abc
                   │                                                              │
                   └──────────────────────── make_pdf.py ─────────────────────────┘
                                    (verified engraving per tune, else the scan)
```

1. **Prep raw images** → clean `<Tune>.png` in `source_images/`. See **`docs/raw_image_prep.md`**.
2. **Transcribe** each scan to ABC via Audiveris OMR + manual GUI cleanup. See
   **`notation_pipeline/README.md`** (and `notation_pipeline/docs/next_steps.md` for the
   live worklist).
3. **Assemble the book**: `./make_pdf.sh` → `WOFTA_tunes.pdf`. For each tune it embeds the
   `-verified` ABC as crisp vector if one exists, otherwise the original scan.

## Directory map

| Path | What |
|------|------|
| `source_images/` | The clean source scans, one `<Tune>.png` per tune (the canonical tune list). |
| `notation_pipeline/` | The OMR → ABC transcription pipeline. Has its own README. |
| `image_prep/` | Tools that extract/clean raw images *before* `source_images/` (PDF cutters, ABC→PNG proof). |
| `make_pdf.py` / `make_pdf.sh` | Builds `WOFTA_tunes.pdf` from scans + verified ABCs. |
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
