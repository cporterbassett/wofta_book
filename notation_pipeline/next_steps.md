# OMR Pipeline — Next Steps

_Written 2026-06-11 (Opus session) as a cold-start brief for a follow-up session._
_Read `omr_findings.md` first for the full experiment history. This file is the
forward-looking plan: what to build next, in priority order, and why._

---

## The goal (unchanged)

Produce accurate ABC notation for ~269 WOFTA tune PNGs as automatically as possible.
The human (Porter) will open **every** tune in the Audiveris GUI to validate and correct.
So the pipeline's job is to hand the GUI the **best possible starting point**, not to be
perfect on its own.

## Three facts that reframe everything

1. **The GUI-correct-every-tune step is a given.** Therefore the metric that matters is
   **correction effort (clicks/edits per tune)**, NOT "did Audiveris detect the key
   correctly (yes/no)." All prior surveys scored key-detection as a binary; that is the
   wrong objective. See "Reframe #1" below.

2. **The 269 tunes come from dozens of different sources** (different typesetters, fonts,
   scan DPIs). Porter does not know which tunes share a source and would have to eyeball
   it. Consequence: **there is no single universal preprocessing recipe.** A fixed global
   scale (the current 1.5× default) is the wrong tool for a heterogeneous corpus. This is
   why the scale surveys showed non-monotonic, tune-specific sweet spots (e.g. Fisher's
   Hornpipe succeeds at 1.5× but fails at both 1× and 2×). See "Experiment A" below.

3. **Porter can read music notation** (knows some tunes, not all). So visual verification
   is viable: render the OMR output and diff it against the scan. The README's framing of
   "user can't verify" is overstated. Audio playback is a *secondary* aid for unfamiliar
   tunes, not the primary path.

## The true source resolution is fixed

The tune PNGs (~1291×589, ~150 DPI effective) are the **original source**. `WOFTA_tunes.pdf`
was generated *from* these PNGs — it is NOT a higher-res origin. There is no 300-DPI source
to fall back to. **Any upscale is interpolation, not new detail.** Do not waste time hunting
for a better source or feeding the PDF to Audiveris.

---

## Reframe #1 — score on correction effort, not key-binary (do this first)

Why it matters: correcting the key in the Audiveris **GUI** is one drag, AND Audiveris
**recomputes note accidentals downstream** when you fix the key (it re-runs RHYTHMS/SYMBOLS
in context). That is the recovery the MXL key-injection experiment could NOT achieve
(patching XML after export can't recompute `<alter>` values). So the "wrong key corrupts all
pitches" cascade documented in `omr_findings.md` is **already solved by the accepted GUI
workflow** — fix key first in the GUI, notes largely self-correct.

Implication: **optimize preprocessing for note/notehead accuracy, and stop letting key
detection drive the scale choice.** The 2× scale gave 100% notes on Angeline and only
"broke" key detection — but key is a one-click fix. Re-scoring on note-correction-effort
may flip the default back toward 2× (or, better, toward per-image normalization — see A).

**Action:** re-score the existing scale survey outputs on note-edit-distance against the
gold-standard ABCs (build a couple more gold ABCs first if needed — Porter can read
notation, so this is feasible now). Replace the key-yes/no column with a note-error count.

---

## Experiment A — per-image interline-normalized scaling (highest leverage)

**The idea:** instead of a fixed global scale, measure each image's staff-line spacing
(interline) and scale **that image** by exactly the factor needed to land it at Audiveris's
preferred interline (~16–20 px). A 10px-interline source → ~1.8×; a 14px source → ~1.3×.
Every image arrives at Audiveris at the same effective resolution regardless of source.
This is the natural answer to fact #2 (heterogeneous sources) and needs zero knowledge of
which source a tune came from.

**Why interline:** Audiveris's recognition is driven by interline, and it reports it in the
log (e.g. `Scale{ interline(10,11,12) ...}`). Audiveris is built for interline ≥ ~16px; the
WOFTA scans are 10–12px, which is why glyph classification (esp. thin sharps) is unreliable.

**Build `normalize_interline.py`:**
- Input: a tune PNG. Output: a scaled PNG normalized to target interline (make target a
  CLI arg, default ~18).
- Measure interline directly with OpenCV — don't require an Audiveris pre-pass. Approach:
  binarize → take a horizontal projection profile of dark pixels over the staff region →
  the staff lines are the 5 strongest peaks per staff; median spacing between adjacent
  staff lines = interline. (Alternative: autocorrelation / FFT of the vertical projection;
  the dominant period in the staff band is the interline.) Cross-check the measured value
  against Audiveris's own reported interline on a few tunes to validate the measurement.
- Scale factor = target_interline / measured_interline. Resample with Lanczos.
- Drop it in front of `run_tune_pipeline.sh` (replace the fixed `-resize ${SCALE}%` step).

**Validate** on a source-diverse sample (NOT just Angeline + 3) using the Reframe #1 metric.

**Pair with targeted glyph cleanup** (different mechanism than scaling, addresses the
documented thin-sharp failure): after normalizing, try a mild morphological **thicken/dilate**
so 1px sharp/stem strokes survive classification (`convert ... -morphology Thicken ...` or
`-morphology Dilate Diamond:1`), and a **despeckle / `-morphology Open Disk:1`** to kill the
xerox salt-and-pepper noise that produced phantom glyphs (the spurious low notes and the
QUARTER_REST-in-header from the Ashokan root-cause). Keep these as toggleable flags and
measure each independently.

---

## Experiment B — `.omr` health-score triage (best automation ROI)

With heterogeneous sources you can't predict which tunes are easy, so an automated good/bad
sort is the only way to spend GUI time wisely. Batch all 269 tunes to `.omr` overnight, then
GUI work becomes open-`.omr` → fix → export (no waiting on OMR per tune).

**Build `health_score.py`:** the `.omr` is a ZIP containing `sheet#1/sheet#1.xml` with glyph
bounding boxes, grades, and header boundaries (see `omr_findings.md` root-cause section for
the XML layout — this tooling already exists in spirit). Per tune emit a health score from:
- key signature present in measure 1? (missing = red flag)
- time signature present? (missing = red flag)
- measure count vs. expected (anomalies = structural failure)
- average / median glyph grade (low = degraded recognition)
- **the Ashokan tell:** any `QUARTER_REST` sitting inside the header x-band (= a sharp
  misclassified as a rest → key will be wrong)

Output a sorted TSV (worst-first). Porter rubber-stamps the green tunes in seconds and
spends GUI time on the red ones.

---

## Experiment C — MXL-render overlay-diff (the per-tune visual check)

Porter can read notation, so a visual diff is the fastest "did this match the scan" check.
`overlay_diff.py` already does red/blue mismatch overlay for ABC renders. Extend it (or add
`verify_mxl.py`) to: render the Audiveris MXL to PNG via **MuseScore headless**
(`mscore -o out.png in.mxl` or the flatpak equivalent), then overlay-diff against the
original scan. Mismatched ink shows exactly where OMR disagrees — Porter reads those spots
against the scan instead of every notehead. Add MIDI/audio export
(`mscore -o out.mid in.mxl` → fluidsynth) as a secondary aid for unfamiliar tunes.

---

## Experiment D — Audiveris `-constant` sweeps (good, but validate source-diversely)

Drops to 4th only because A/B/C give more for less. Audiveris batch supports
`-constant key=value` (confirmed in `-help`). Untapped lever — all prior work was
ImageMagick-side. Worth probing:
- **Key-sig / sharp acceptance grade thresholds** — the Ashokan second sharp was rejected
  at grade ~0.485. Loosening the minimum grade for key-alter inters / the header region
  could keep it, fixing key at the source.
- **Classifier minimum grade** so borderline noteheads/sharps aren't dropped.
- **Binarization (Sauvola) constants** — Audiveris does its own BINARY step; tuning it for
  degraded xerox may beat ImageMagick pre-binarization entirely.

**Caution (fact #2):** what helps on one source may add false positives on another. Every
constant change MUST be validated across a source-diverse sample, not Angeline alone.
Clean experiment: same image, sweep one constant, diff the `.omr`, score with `health_score.py`.

---

## Dead ends — do NOT redo these (see `omr_findings.md` for detail)

- **MXL/ABC key-injection** — `<alter>` values are baked at recognition time; can't recompute
  downstream. The GUI does this correctly anyway.
- **thesession.org / abcnotation.com as gold standard** — different arrangements (0/18 match).
  Fine only as a key sanity-check, never for note content.
- **Chord-name blanking** — chord symbols were never the cause of key-detection failure; the
  blanking also deleted low ledger-line notes.
- **Ensemble across the 37 Angeline-tuned variants** — overfit to one image, unproven elsewhere.
- **Training Audiveris's classifier on "the WOFTA font"** — there is no single font; dozens of
  sources. Only revisit if it turns out a few sources dominate the tune count (Porter would
  have to label sources to know — not worth it now).
- **Hunting for a higher-res source / feeding the PDF to Audiveris** — the PNGs ARE the source.

---

## Priority order

1. **Reframe #1** — re-score surveys on note-correction-effort, not key-binary. (cheap, changes decisions)
2. **Experiment A** — `normalize_interline.py` + glyph-cleanup flags. (the big build)
3. **Experiment B** — `health_score.py` triage + batch-all-to-`.omr`. (automation ROI)
4. **Experiment C** — MXL-render overlay-diff verification. (fast per-tune visual check)
5. **Experiment D** — Audiveris `-constant` sweeps, validated source-diversely.

## Pointers to existing tooling

- `run_tune_pipeline.sh` — current pipeline: `convert` preprocess → `flatpak run
  org.audiveris.audiveris -batch -export` → `abc_xml_converter`. Replace its fixed-scale
  step with `normalize_interline.py`.
- `overlay_diff.py` — red/blue mismatch overlay; extend for MXL renders (Experiment C).
- `.omr` = ZIP with `sheet#1/sheet#1.xml` (glyph boxes, grades, header stops) — basis for B.
- venv: `../.venv/bin/python3` (has opencv-python-headless, music21, abc_xml_converter).
- Audiveris: `flatpak run org.audiveris.audiveris` (supports `-batch -export -constant
  key=value -output <dir> -sheets <n>`).
- gold-standard ABCs live in `abc/` (e.g. `abc/Angeline the Baker-l8.abc`, 19 measures).
