# OMR Pipeline — Next Steps

_Written 2026-06-11 (Opus session) as a cold-start brief for a follow-up session._
_Updated 2026-06-11 (Sonnet session) after scoring work and pipeline architecture decisions._
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
to fall back on. **Any upscale is interpolation, not new detail.** Do not waste time hunting
for a better source or feeding the PDF to Audiveris.

---

## Pipeline architecture (decided 2026-06-11)

Two phases, always run in order:

**Phase 1 — batch (unattended, run overnight)**
```
for each tune PNG:
  preprocess (1.5× Lanczos + unsharp) → Audiveris batch → clean_omr.py → clean_mxl.py → abc_xml_converter → draft ABC
```
Scripts needed: `batch_tune.sh` (single tune, refactor of current `run_tune_pipeline.sh`),
`batch_all.sh` (all 269 tunes).

**Phase 2 — cleanup loop (interactive, one tune at a time)**
```
for each tune (sorted worst-first by health_score.py):
  open cleaned .omr in Audiveris GUI → user fixes → user exports MXL → clean_mxl.py → abc_xml_converter → final ABC
```
Script needed: `cleanup_loop.sh` — opens Audiveris GUI with the .omr, waits for close,
then finds the exported MXL and converts to ABC.

**Key design points:**
- `clean_omr.py` strips slur, wedge, articulation, bow, ornament, dynamics inters (and
  their SIG relations) from the .omr **before** the user opens it in the GUI. Audiveris
  cannot be configured to suppress these; the .omr surgery is the only pre-GUI fix.
- `clean_mxl.py` strips the same categories from MXL (for batch-only path) plus repeated
  key signatures.
- The .omr is the checkpoint between phases: if phase 2 is interrupted, resume from .omr.
- `health_score.py` (Experiment B) sorts the phase 2 queue — worst tunes first so GUI
  time is spent where it matters.

---

## Reframe #1 — score on correction effort, not key-binary (partially done)

**Status:** Gold standards created; Arkansas Traveler scored. Soldier's Joy and Mississippi
Sawyer MXLs exist in tmp_pipeline/ but have not been converted to ABC yet.

**Gold standard ABCs** (in `abc/`, transcribed directly from WOFTA images):
- `Arkansas Traveler-gold.abc` — 18 measures, K:D
- `Soldier's Joy-gold.abc` — 16 measures + pickup, K:D
- `Mississippi Sawyer-gold.abc` — 16 measures + pickup, K:D

**Arkansas Traveler scores** (after MXL cleaning + compare_abc space normalization):
| Scale | Score | Main failures |
|-------|-------|---------------|
| 1× | 8/18 (44%) | Spurious inline key changes corrupted pitch content — F# written as F natural, C# as C natural throughout |
| 1.5× | 16/18 (89%) | Two identical failures: `d=cdA` instead of `dcdA` at measures 7 and 15 (C natural instead of C#) |
| 2× | 11/18 (61%) | Structural failures: truncated measures, spurious rests |

**Key finding:** The "key is a 1-click fix" argument does NOT fully hold for 1× or 2×.
Both scales produce structural errors (wrong barlines, rests, truncated measures) on top of
accidental errors. 1.5× is the best single default — its two remaining failures are
systematic (same C# miss, both occurrences) and would be caught by the user in one pass.

**Next:** Convert Soldier's Joy and Mississippi Sawyer MXLs to ABC and score. MXLs are in:
- `tmp_pipeline/survey/Soldier's Joy/mxl/`
- `tmp_pipeline/survey_1.5x/Soldier's Joy/mxl/`
- `tmp_pipeline/survey_2x/Soldier's Joy/mxl/`
- (same pattern for Mississippi Sawyer)

---

## compare_abc.py — current normalization

Strips before comparing: chord symbols `"..."`, decorations `!...!`, grace notes `{...}`,
inline key changes `[K:x]`, lyric lines, comments, L: and other header lines.
Also normalizes intra-measure whitespace (spaces between notes are insignificant in ABC).

Does NOT strip: slurs `(...)`, staccato dots `.`, ties `-`. These are musically meaningful
and count as real errors if Audiveris adds them spuriously.

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
- Drop it in front of `batch_tune.sh` (replace the fixed `-resize ${SCALE}%` step).

**Validate** on a source-diverse sample (NOT just Angeline + 3) using the Reframe #1 metric.

**Pair with targeted glyph cleanup** (different mechanism than scaling, addresses the
documented thin-sharp failure): after normalizing, try a mild morphological **thicken/dilate**
so 1px sharp/stem strokes survive classification (`convert ... -morphology Thicken ...` or
`-morphology Dilate Diamond:1`), and a **despeckle / `-morphology Open Disk:1`** to kill the
xerox salt-and-pepper noise that produced phantom glyphs (the spurious low notes and the
QUARTER_REST-in-header from the Ashokan root-cause). Keep these as toggleable flags and
measure each independently.

---

## Experiment B — `.omr` health-score triage (needed for cleanup loop queue)

**Build `health_score.py`:** the `.omr` is a ZIP containing `sheet#1/sheet#1.xml` with glyph
bounding boxes, grades, and header boundaries. Per tune emit a health score from:
- key signature present in measure 1? (missing = red flag)
- time signature present? (missing = red flag)
- measure count vs. expected (anomalies = structural failure)
- average / median glyph grade (low = degraded recognition)
- **the Ashokan tell:** any `QUARTER_REST` sitting inside the header x-band (= a sharp
  misclassified as a rest → key will be wrong)

Output a sorted TSV (worst-first). This drives the phase 2 cleanup loop order.

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

**Note on Audiveris constants:** We inspected the jar and confirmed there is NO constant to
disable slur detection, key-repeat export, or decorations. The `-constant` system exposes
size/threshold tuning only. Slurs and decorations must be removed post-hoc via `clean_omr.py`.

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
- **Audiveris `-constant` or `-step` to suppress slurs/decorations** — not possible; no such
  constants exist. Use `clean_omr.py` instead.

---

## Priority order

1. **Build the two-phase pipeline** — `batch_tune.sh`, `batch_all.sh`, `cleanup_loop.sh`
2. **Score Soldier's Joy and Mississippi Sawyer** at 1×/1.5×/2× (MXLs already exist, need
   abc_xml_converter + clean_mxl + compare_abc)
3. **Experiment A** — `normalize_interline.py` + glyph-cleanup flags. (the big build)
4. **Experiment B** — `health_score.py` triage + batch-all-to-`.omr`. (needed for pipeline)
5. **Experiment C** — MXL-render overlay-diff verification.
6. **Experiment D** — Audiveris `-constant` sweeps, validated source-diversely.

## Pointers to existing tooling

- `batch_tune.sh` — rename/refactor of `run_tune_pipeline.sh`; preprocess → Audiveris batch
  → `clean_omr.py` → `clean_mxl.py` → `abc_xml_converter`
- `clean_omr.py` — strips slur/wedge/articulation/bow/ornament/dynamics inters + relations
  from .omr XML **before** GUI opens it
- `clean_mxl.py` — strips same categories from MXL + repeated `<key>` elements (batch path)
- `compare_abc.py` — normalize ABC, split into measures, diff measure-by-measure; normalizes
  intra-measure whitespace; does NOT strip slurs (they're real errors if Audiveris adds them)
- `overlay_diff.py` — red/blue mismatch overlay; extend for MXL renders (Experiment C).
- `.omr` = ZIP with `sheet#N/sheet#N.xml` (glyph boxes, grades, header stops, SIG relations)
- venv: `../.venv/bin/python3` (has opencv-python-headless, music21, abc_xml_converter).
- Audiveris: `flatpak run org.audiveris.audiveris` (supports `-batch -export -constant
  key=value -output <dir> -sheets <n>`).
- gold-standard ABCs: `abc/*-gold.abc` (Arkansas Traveler, Soldier's Joy, Mississippi Sawyer)
- Survey MXLs: `tmp_pipeline/survey/`, `tmp_pipeline/survey_1.5x/`, `tmp_pipeline/survey_2x/`
  (20 tunes each; need clean_mxl + abc_xml_converter to produce scoreable ABCs)
