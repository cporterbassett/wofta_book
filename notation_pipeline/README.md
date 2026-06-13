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
