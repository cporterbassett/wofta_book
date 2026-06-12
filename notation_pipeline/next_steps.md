# OMR Pipeline — Next Steps

_Written 2026-06-11 (Opus session) as a cold-start brief for a follow-up session._
_Updated 2026-06-11 (Sonnet session) after scoring work and pipeline architecture decisions._
_Updated 2026-06-12 (Opus session) after normalize_interline, health_score, verify_mxl, compare_abc fix._
_Updated 2026-06-12 (Sonnet session) after mvt1 MXL fallback fix in batch_tune.sh._
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
  normalize_interline.py (target 18px) → Audiveris batch → clean_omr.py → clean_mxl.py → abc_xml_converter → draft ABC
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

**Status:** Gold standards created; all three tunes scored at 1.5× and with interline normalization.

**Gold standard ABCs** (in `abc/`, transcribed directly from WOFTA images):
- `Arkansas Traveler-gold.abc` — 18 measures, K:D
- `Soldier's Joy-gold.abc` — 16 measures + pickup, K:D
- `Mississippi Sawyer-gold.abc` — 16 measures + pickup, K:D

**Arkansas Traveler scores** (after MXL cleaning + compare_abc normalization):
| Scale | Score | Main failures |
|-------|-------|---------------|
| 1× | 8/18 (44%) | Spurious inline key changes corrupted pitch content — F# written as F natural, C# as C natural throughout |
| 1.5× fixed | 16/18 (89%) | Two identical failures: `d=cdA` instead of `dcdA` at measures 7 and 15 (C natural instead of C#) |
| 2× | 11/18 (61%) | Structural failures: truncated measures, spurious rests |
| **interline-norm** (141%) | **17/18 (94%)** | Same single C# miss — improvement over fixed 1.5× |

**Key finding:** The "key is a 1-click fix" argument does NOT fully hold for 1× or 2×.
Both scales produce structural errors (wrong barlines, rests, truncated measures) on top of
accidental errors. Interline normalization beats fixed 1.5×.

**Soldier's Joy scores** (after MXL cleaning):
| Scale | Score | Key | Main failures |
|-------|-------|-----|---------------|
| 1× | 7/18 (39%) | K:D ✓ | Structural failure: B section completely garbled — barline confusion shifts entire note block |
| 1.5× fixed | 12/18 (67%) | K:G ❌ | Wrong key — C# written as `^c` throughout. Key detection is blocking issue. |
| 2× | 7/18 (39%) | K:D ✓ | Same structural failure as 1×; f notes appear as `=f` naturals throughout B section |
| **interline-norm** (133%) | **12/17 (71%)** | K:G ❌ still — slight % gain, key failure unchanged |

**Mississippi Sawyer scores** (after MXL cleaning):
| Scale | Score | Key | Main failures |
|-------|-------|-----|---------------|
| 1× | 12/18 (67%) | K:D ✓ | 5 consecutive B-section failures: `=f`, `=c` naturals |
| 1.5× fixed | 15/18 (83%) | K:D ✓ | 2 failures: note error + barline confusion at repeat boundary |
| 2× | 7/18 (39%) | K:D ✓ | `=f`, `=c` naturals throughout; more structural failures |
| **interline-norm** (150%) | **14/17 (82%)** | K:D ✓ — measured 12px → exactly 1.5×, effectively flat |

**Key finding:** Interline normalization equals or beats fixed 1.5× on all scored tunes with no regressions.
Soldier's Joy key detection (K:G instead of K:D) is a GUI-fix issue, not a preprocessing issue.

---

## compare_abc.py — current normalization

Strips before comparing: chord symbols `"..."`, decorations `!...!`, grace notes `{...}`,
inline key changes `[K:x]`, lyric lines, comments, L: and other header lines.
Also normalizes intra-measure whitespace (spaces between notes are insignificant in ABC).
Reduces duration fractions via `Fraction` (e.g. `6/2` → `3`) regardless of L: setting —
**bug fixed 2026-06-12** (previously skipped reduction for L:1/8 files).

Does NOT strip: slurs `(...)`, staccato dots `.`, ties `-`. These are musically meaningful
and count as real errors if Audiveris adds them spuriously.

---

## Experiment A — per-image interline-normalized scaling ✓ DONE

**Built 2026-06-12.** `normalize_interline.py` is live and integrated into `batch_tune.sh`.

**How it works:** Otsu-binarize → horizontal row projection → cluster adjacent dark rows
into staff-line groups → median of intra-staff spacings = interline. Scale factor =
18px / measured_interline. Applies unsharp mask then Lanczos resize. Falls back to fixed
1.5× if detection fails (2 out of 269 tunes: Hey Polka — dense notation fills inter-line
space; Forester's Hornpipe — faint lines).

**Coverage:** 291/293 PNGs succeed (99.3%). Scale factors range 109%–300% (tiny 531px images
get ~300%; most cluster around 129–164%).

**Validation results:** Arkansas Traveler 141% → 17/18 (94%) vs 16/18 (89%) at fixed 1.5×.
Soldier's Joy 133% → 12/17 (71%) vs 12/18 (67%). Mississippi Sawyer 150% (same as 1.5×) →
14/17 (82%) vs 15/18 (83%). No regressions.

**Audiveris confirmation:** Arkansas Traveler hit interline 17–20px after normalization
(target 18px) — landing exactly in Audiveris's sweet spot.

**Still to do (glyph cleanup):** try morphological thicken/dilate for thin sharps and
despeckle for xerox noise — these are independent of scaling, measure separately.

---

## Experiment B — `.omr` health-score triage ✓ DONE

**Built 2026-06-12.** `health_score.py` is live.

**Usage:** `python3 health_score.py` (scans all `batch_output/*/clean.omr`) or pass explicit
paths. Outputs TSV sorted worst-first.

**XML structure (actual, differs from spec):** Inters use element names directly (`<key>`,
`<time-pair>`, `<rest>`, `<head>`) inside `<sig><inters>`. Header detection via
`<header start="N" stop="M">` with child refs `<key>ID</key>`, `<time>ID</time>` (only
present if recognized). Grades: elements have `grade` and `ctx-grade` attributes.
Measure count from `<page measure-count="N">`.

**Score components:** key_ok (−40 if missing), time_ok (−20), ashokan_tell (−30 if present),
avg ctx-grade contribution, base 100. Lower = needs more GUI work.

**Sample results from first 44 tunes (worst first):**
- Big Scioty: 48 — missing both key AND time sig
- Coleraine, Billy in the Lowground, Big Con: ~68 — missing key only
- Ashokan Farewell, Colored Aristocracy: ~77 — Ashokan tell (sharp → quarter rest)
- Boys of Blue Hill + 4 others: ~88 — missing time sig only
- Most tunes: 107–109 — all clear, avg grade ~0.90+
- Arkansas Traveler: 108.32 — key ✓, time ✓, no tell, grade 0.92

Run against full corpus once current batch_all.sh completes.

---

## Experiment C — MXL-render overlay-diff ✗ DEAD END

**`verify_mxl.py` was built but is redundant.** Audiveris's own GUI already overlays
recognized glyphs directly on the original scan, colored by confidence grade — no
alignment issues, no extra tooling. The MXL→MuseScore→PNG→diff round-trip is strictly
worse: it introduces vertical misalignment (scan has title/chord text; MuseScore has clean
margins) and loses information the `.omr` already contains.

**The overlay diff does make sense for the ABC path:** comparing a final LilyPond/abcm2ps
render of a corrected ABC against the original scan as a post-GUI sanity check. That is
what `overlay_diff.py` was originally built for and where it should stay.

**For pre-GUI triage:** use `health_score.py` to sort tunes, then open the `.omr` directly
in Audiveris. No intermediate render needed.

**MuseScore** (`~/Downloads/MuseScore-Studio-4.4.4.243461245-x86_64.AppImage`) is still
useful for MIDI/audio export of a corrected MXL — a secondary listening check for tunes
Porter doesn't know by ear. That's a one-liner when needed; no script required.

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

1. ~~**Build the two-phase pipeline**~~ — **DONE** (`batch_tune.sh`, `batch_all.sh`, `cleanup_loop.sh`)
2. ~~**Score Soldier's Joy and Mississippi Sawyer**~~ — **DONE** (see Reframe #1 above)
3. ~~**Run `batch_all.sh`**~~ — **DONE** (2026-06-11, ~1 hr). 258/269 succeeded. 11 failed:
   - **No MXL output** (Audiveris crash/total failure): Kerry Mills' Barn Dance, Nixon's Farewell,
     seneca-square-dance 2, star-above-the-garter2
   - **Multi-MXL / ABC conversion error** (Audiveris exported multiple sheets, script picked wrong
     one): Boggy Road to Texas, Cherokee Shuffle, Eighth of January, Gypsy Waltz, Pat(T)'s Country,
     Road House Ramble, Westphalia Waltz (new) — 4 self-resolved in the normalize_interline re-run
     (Boggy Road to Texas G/4/4, Eighth of January D/4/4, Gypsy Waltz F, Westphalia Waltz (new));
     remaining 3 fixed by mvt1 fallback (item 8)
   - Remaining failures needing GUI intervention: Kerry Mills' Barn Dance, Nixon's Farewell,
     seneca-square-dance 2, star-above-the-garter2 (no MXL output at all)
4. ~~**Experiment A**~~ — **DONE** (`normalize_interline.py` built, integrated into `batch_tune.sh`, batch re-run in progress)
5. ~~**Experiment B**~~ — **DONE** (`health_score.py` built, tested on 44 tunes)
6. ~~**Experiment C**~~ — **DEAD END** (see above — Audiveris GUI already does this better)
7. **Run `health_score.py` on full corpus** — after current batch_all.sh completes; produces the phase 2 cleanup queue sorted worst-first
8. ~~**Fix mvt1 multi-MXL batch failures**~~ — **DONE** (2026-06-12). `batch_tune.sh` now falls back to `preprocessed.mvt1.mxl` when `preprocessed.mxl` is absent. Fixed 8 tunes: Bull Moose, Centralia Waltz, Fisher's Hornpipe (D/4/4), Me and My Fiddle (G/4/4), Morrison's Jig, Cherokee Shuffle (A/4/4), Road House Ramble (G/4/4), Pat(T)'s Country.
   - Pat(T)'s Country split into 3 movements; mvt1 yields only ~5 bars — needs GUI to reassemble.
9. **Experiment D** — Audiveris `-constant` sweeps, validated source-diversely.

## Pointers to existing tooling

- `batch_tune.sh` — phase 1 single tune: preprocess → Audiveris batch → `clean_omr.py` →
  `clean_mxl.py` → `abc_xml_converter`. Output in `batch_output/<Tune>/`. Resumable via
  `clean.omr` checkpoint. Falls back to `preprocessed.mvt1.mxl` when Audiveris splits the
  score into movements instead of exporting a single `preprocessed.mxl`.
- `batch_all.sh` — runs `batch_tune.sh` over all 269 PNGs; skips tunes with `clean.omr`;
  supports `--dry-run`. Log in `batch_output/batch_all.log`.
- `cleanup_loop.sh` — phase 2 interactive: opens `clean.omr` in Audiveris GUI, waits for
  close, finds exported MXL, runs `clean_mxl.py` → `abc_xml_converter` → final ABC.
  Supports `--list` and specific tune names as args. Output: `abc/<Tune>-final.abc`.
- `clean_omr.py` — strips slur/wedge/articulation/bow/ornament/dynamics inters + relations
  from .omr XML **before** GUI opens it
- `clean_mxl.py` — strips same categories from MXL + repeated `<key>` elements (batch path)
- `compare_abc.py` — normalize ABC, split into measures, diff measure-by-measure; normalizes
  intra-measure whitespace; does NOT strip slurs (they're real errors if Audiveris adds them)
- `normalize_interline.py` — measure staff interline via row projection; scale to target 18px; falls back to 1.5× on detection failure. `--measure-only` flag for survey mode.
- `health_score.py` — parse `clean.omr` ZIP XMLs; score key/time/Ashokan-tell/avg-grade; output worst-first TSV. Run after batch completes to get phase 2 queue.
- `verify_mxl.py` — **dead end**, see Experiment C. Audiveris GUI already does this better.
- `overlay_diff.py` — red/blue mismatch overlay for ABC renders.
- `.omr` = ZIP with `sheet#N/sheet#N.xml` (glyph boxes, grades, header stops, SIG relations)
- venv: `../.venv/bin/python3` (has opencv-python-headless, music21, abc_xml_converter).
- Audiveris: `flatpak run org.audiveris.audiveris` (supports `-batch -export -constant
  key=value -output <dir> -sheets <n>`).
- gold-standard ABCs: `abc/*-gold.abc` (Arkansas Traveler, Soldier's Joy, Mississippi Sawyer)
- Batch output: `batch_output/<Tune Name>/` with `preprocessed.png`, `preprocessed.omr`,
  `preprocessed.mxl`, `clean.omr`, `clean.mxl`. Draft ABCs: `abc/<Tune>-draft.abc`.
