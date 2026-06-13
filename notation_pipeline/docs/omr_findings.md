# OMR Pipeline Findings
_Sessions: 2026-06-11_

## What we set out to answer
Is the `2× Lanczos + unsharp` preprocessing pipeline (established on Angeline the Baker)
general enough to use on all 277 WOFTA tunes?

## Test tunes (chosen for diversity)

| Tune | Key | Meter | DPI (est.) | Image type |
|------|-----|-------|-----------|------------|
| Arkansas Traveler | D major | 4/4 | ~154 | Clean typeset |
| Ashokan Farewell | D major | 3/4 | ~152 | Clean typeset, copyrighted |
| Cincinnati Hornpipe | D major | 4/4 | ~168 | Clean typeset |
| Blackberry Blossom | G major | cut time | ~164 | Photocopy/scan |

---

## What we discovered

### 1. The 2× upscale breaks key signature detection for some tunes

| Tune | Original image | 2× + unsharp |
|------|---------------|-------------|
| Arkansas Traveler | K:D ✓  M:4/4 ✓ | K:none ✗  M:4/4 ✓ |
| Ashokan Farewell  | K:G ✗  M:none ✗ | K:none ✗  M:none ✗ |
| Cincinnati Hornpipe | K:D ✓  M:4/4 ✓ | K:D ✓  M:4/4 ✓ |
| Blackberry Blossom | (not tested) | K:G ✓  M:2/2 ✓ |

### 2. When key detection fails, note pitches are also wrong

Without `<key>` in MXL measure 1, Audiveris writes F as natural (alter=nat) instead
of F♯ (alter=1). The key detection failure corrupts the entire pitch content, not just
the header. Confirmed by inspecting MXL note elements directly.

### 3. Chord-name blanking was a dead end

Hypothesis: chord symbols above the staff confuse Audiveris's key sig recognizer.
Test: detect staff systems → white out inter-system bands → re-run Audiveris.
Result: made things WORSE (also removed notes below the bottom staff line — the
`above_margin=4` was too small to protect low ledger-line notes). Chord names were
never the cause of the key detection failure.

### 4. The staff-size theory was wrong

Initial hypothesis: tunes with larger original staves tolerate the 2× upscale better
because the sharp symbols land in Audiveris's recognizable size window.
Debunked: Cincinnati Hornpipe detects K:D correctly at BOTH original and 2× scale.
So it's not a general DPI/size effect — something specific to those images (possibly
the typesetting style or exact sharp symbol shape) determines whether Audiveris can
recognize the key signature.

### 5. Unsharp-only does not improve note detection

| Variant | Angeline the Baker score |
|---------|------------------------|
| Original (no preprocessing) | 13/19 (68%) |
| 2× Lanczos only | 14/19 (74%) |
| Unsharp + 2× (single-pass) | 15/19 (79%) |
| Unsharp only (no resize) | 13/19 (68%) — same as original |
| **2× Lanczos → unsharp (two passes)** | **19/19 (100%) ← best** |
| **Bilateral filter → 2× Lanczos** | **19/19 (100%) ← best** |

The 100% score was established in an earlier session (see memory) using two-pass
approaches. The single-pass `convert -unsharp 0x1 -filter Lanczos -resize 200%` only
achieves 79% — order and pass-separation matter. Unsharp alone adds nothing; the gain
comes from the 2× resize, with mild sharpening as a further boost when applied correctly.

### 6. The 100% on Angeline may not generalise

The variants that achieve 100% note accuracy on Angeline also break key detection on
some tunes (Arkansas Traveler gets K:none at 2×). We don't know if the key detection
failure rate is 25%, 50%, or higher across the full 277-tune set.

---

## Root cause analysis: Ashokan Farewell key/time signature failure

_Session: 2026-06-11, based on .omr XML inspection (no GUI needed)_

The Audiveris `.omr` file is a ZIP archive containing `sheet#1/sheet#1.xml` with full
recognition data including glyph bounding boxes, confidence grades, and header boundaries.
This allows precise diagnosis without the GUI.

### The failure mechanism (system 1, original DPI)

The Audiveris `HEADERS` step sets a `stop` boundary for each system's header region.
Any musical glyph (clef, key sig, time sig) outside that boundary is classified as note
content, not header content.

In Ashokan Farewell system 1, the header runs from x=115 to **x=190** (75 px total):

```
x=115          x=178 x=190   x=192
   |___clef_____|_F#_|  |  rest|
                           ^-- header stop
```

- The first sharp (F#, pitch=-4) fits: x=178, w=13, grade=**0.485** (low but in header)
- The **second sharp (C#, pitch=-1)** would be at x≈190–203 — but instead Audiveris
  classifies it as a **`QUARTER_REST`** (x=192, y=108, grade=0.537) and places it in
  **measure 1**, not the header
- The header stop is set at x=190 precisely because something that looks like note
  content appears at x=192
- Result: only 1 sharp in header → **K:G (fifths=1)**, not K:D
- Time sig digits (3 and 4) are entirely outside the header → **M:none**

The `QUARTER_REST` at x=192 in measure 1 is almost certainly the second sharp glyph
misclassified. The curved top of a sharp symbol can resemble a rest at 150 DPI.

This is a **glyph classification error**, not a header-boundary bug. Audiveris's
classifier doesn't recognize the second sharp as a `SHARP` shape, so it never joins the
header as a key-alter.

### Why don't Arkansas Traveler and Cincinnati Hornpipe fail?

| Tune | System 1 header | Key pos | Sharp grades | Notes |
|------|----------------|---------|-------------|-------|
| Ashokan Farewell | stop=190 (75 px) | x=178, w=13 | **0.485** (only 1) | 2nd sharp misclassified as rest |
| Arkansas Traveler | stop=249 (133 px) | x=181, w=26 | 0.523, 0.781 | Both sharps recognized |
| Cincinnati Hornpipe | stop=153 (152 px) | x=71, w=34 | 0.798, 0.538 | Both sharps recognized |

In the other tunes, both sharps are classified with high enough confidence as `SHARP`
glyphs that they stay in the header. Ashokan Farewell's second sharp drops below the
threshold, gets reassigned as a rest, and prematurely terminates the header.

The `Fiddle` instrument label appears in all three images and is NOT a factor — the staff
start position is almost identical (x=115–116) across all tunes. The real variable is
individual sharp-symbol recognition confidence.

### Why 2× upscaling makes it worse

At 2×, the image is 2592×1278. Glyph x-coordinates roughly double. But Audiveris's
header stop detection doesn't scale proportionally (it's driven by barline detection,
which depends on content structure, not DPI).

Result for Ashokan Farewell at 2×:

| System | Header stop | Key detected | Why |
|--------|------------|-------------|-----|
| 1 | x=327 | **none** | Key would start at x≈356 — past header stop |
| 2 | x=144 | none | Key would start at x≈174 — past stop |
| 3 | x=226 | **K:D (fifths=2)** | Key at x=174 — just inside stop |
| 4 | x=144 | none | Same as system 2 |

Only system 3 finds the key, but that's in the middle of the piece, not measure 1.
The exported MXL has no key in measure 1 → K:none.

The same mechanism explains Arkansas Traveler at 2×: system 1 header stop=331, key would
be at x≈362 → missed; only system 2 finds a key (K:G, grade=0.03 — barely above noise).

### Key confidence grades across all systems (Ashokan Farewell, original DPI)

| System | Sharps found | Grades | Key detected |
|--------|-------------|--------|-------------|
| 1 | 1 of 2 | 0.485 | **K:G (fifths=1)** ← exported, WRONG |
| 2 | 2 of 2 | 0.630, **0.036** | K:D (fifths=2, grade=0.333) |
| 3 | 2 of 2 | 0.200, 0.281 | K:D (fifths=2, grade=0.240) |
| 4 | 2 of 2 | 0.553, 0.357 | K:D (fifths=2, grade=0.455) |

Systems 2–4 get the right answer (K:D) but with very low confidence. The second sharp
in all systems has grade ≤ 0.357, suggesting the Ashokan Farewell sharp style is
consistently harder for Audiveris to classify, regardless of DPI.

### GUI investigation answers

These questions were posed at the start of this investigation. The .omr XML answers them
without needing the GUI:

**Q1: What does the GUI show for the key sig region?**
System 1 would show one sharp glyph (F#) colored orange/red (grade=0.485 — low confidence),
inside the header region. The second sharp (C#) would appear as a QUARTER_REST shape at
x=192 in measure 1, also low confidence. The time sig digits would not appear at all —
they were either not detected or absorbed into unrecognized blobs.

**Q2: Does the GUI allow manual key sig correction and re-export?**
Yes. In the Audiveris GUI: right-click the QUARTER_REST at x=192 in measure 1, re-assign
it to KEY_SHARP, then drag it into the header. Similarly, add a 3/4 time sig via the
Symbols panel. File > Export Scores then generates a corrected MXL. This is the only
reliable path for Ashokan Farewell — batch-mode preprocessing can't fix a classifier
failure on a specific glyph.

**Q3: Recognition confidence view?**
Yes — Audiveris GUI colors glyphs by `grade` value (green=high, red=low). The `ctx-grade`
(contextual grade, after neighborhood context is factored in) is also shown. These are the
same values visible in the `sheet#1.xml` XML.

**Q4: Does the pickup measure confuse the system?**
Indirectly yes. A pickup measure means the first barline is closer to the header area,
leaving less horizontal room between the header symbols and note content. But the primary
failure is the misclassification of the second sharp as a rest — a classifier issue, not
a structural one.

---

---

## Batch preprocessing experiment results
_Session: 2026-06-11 (second pass)_

Four candidate strategies were tested to address the key-detection / note-accuracy tension.

---

### Experiment 1: MXL key injection (DEAD END)

**Hypothesis:** Run Audiveris at 2× → inject correct `<key><fifths>N</fifths></key>`
into MXL measure 1 before xml2abc conversion → does this fix pitch content?

**Test:** Arkansas Traveler at 2× (correct key: 2 sharps = D major). The 2× MXL had
`<fifths>1</fifths>` in the first key element (G major, wrong), then `<fifths>0</fifths>`
later. Patched both to `<fifths>2</fifths>` using Python's xml.etree.

**Findings:**
- The 2× MXL had **21 F notes** in the piece: **16 with `<alter>none`** (F natural, wrong),
  **5 with `<alter>1`** (F♯, correct).
- Patching the `<fifths>` element changed the key in the ABC header and inline key changes,
  but did **not change any `<alter>` values on individual notes** — xml2abc writes those
  from the MXL `<pitch>` elements verbatim.
- Patched output: `K:D` in some inline markers, but the 16 wrongly-detected F-natural notes
  appeared as explicit `=F` (natural sign in a D-major context) — still wrong pitches.
- Even the ABC-level equivalent (transposing K:none → K:D post-hoc) scored only **2/18**
  measures correct against the original-DPI output, because the 2× run had structural
  differences throughout the piece (different barlines, different note groupings) caused by
  the cascading effect of the key detection failure.

**Conclusion:** `<alter>` values are baked into the MXL at recognition time. If Audiveris
doesn't recognize the key signature during processing, individual notes with accidentals that
"should" be in-key are written as naturals. Patching the key element downstream — at either
the MXL or ABC level — cannot recover this information.

---

### Experiment 2: abcnotation.com lookup (DIFFERENT ARRANGEMENT)

**Hypothesis:** Search abcnotation.com for Arkansas Traveler in K:D, download the ABC, use
as gold standard or as transcription.

**Test:** Queried `q=arkansas+traveler+K%3AD&f=c`. Retrieved a version from banjolin.co.uk.

**Findings:**
- Key and meter correct: K:D, M:4/4.
- But the arrangement is **completely different** from the WOFTA book:
  - abcnotation.com starts with `A2 |: dfed B2B2` (2-beat pickup A, then runs in D5 register)
  - WOFTA/Audiveris starts with `DFED B,2 B,2` (pickup D4, runs in D4 register)
  - All 18 content measures differ — 0/18 match between abcnotation.com and WOFTA.
- The WOFTA collection has its own arrangements; internet sources use different fingerings,
  octave registers, and occasionally different structures (B sections, number of repeats).

**Conclusion:** abcnotation.com (and thesession.org) lookups cannot be used as gold standards
for scoring WOFTA transcriptions. The key field is reliable (K:D is correct), so lookups are
useful for **validating detected key** — but not for comparing note content.

---

### Experiment 3: Ensemble voting across preprocessing variants

**Test:** `ensemble_abc.py` with 37 Angeline the Baker variants (from preprocessing_tests/).
Gold standard: `abc/Angeline the Baker-l8.abc` (19 measures).

**Individual scores across 37 variants:**
| Score | Variants | Names |
|-------|---------|-------|
| 100% | 5 | 14-unsharp1x1-up2x, 20-adaptive-sharpen-up2x, 22-up2x-unsharp0x1, 25-bilateral-d5s25-up2x, 25-bilateral-d7s40-up2x |
| 95%  | 7 | 09, 11, 15, 16, 19, 23, 25-d9s75, 28 |
| 89%  | 2 | 02, 21 |
| ≤84% | 23 | (includes complete failures: staff-reinforce, adaptive-b, clahe-adaptive) |

**Ensemble (all 37 variants): 19/19 (100%)**

**Conclusion:** Ensemble trivially achieves 100% when multiple individuals already hit 100%.
The relevant test is whether ensemble helps when the **best individual is sub-100%** — which
requires gold standards for more tunes. Without those, ensemble utility is unproven.

The 37 variants were all tuned on Angeline the Baker's specific image; generalization to other
tunes is unknown. The 5 variants that achieve 100% individually are better candidates for a
"safe default" than ensemble — they're faster to run and cheaper to diagnose when they fail.

---

### Experiment 4a: Key detection survey — 20 tunes at original DPI

**Method:** Ran Audiveris (no preprocessing) on 20 untested WOFTA tunes. Extracted
`<fifths>`, `<mode>`, and `<time>` from MXL measure 1. Script: `survey_key_detection.sh`.
Results: `survey_results.tsv`.

| Tune | Detected key | Meter | Notes |
|------|-------------|-------|-------|
| Bill Cheatham | G (1♯) | 2/4 | ✓ |
| Billy in the Lowground | **none** | 4/4 | ✗ key missing |
| Booth Shot Lincoln | A (3♯) | 4/4 | ✓ (A major) |
| Calliope House | E (4♯) | 6/8 | ✗ likely wrong (expect A minor or D) |
| Cherokee Shuffle | A (3♯) | **?** | ✓ key / ✗ meter missing |
| Cluck Old Hen | G (1♯) | 4/4 | ✓? |
| Devil's Dream | A (3♯) | 2/2 | ✓ |
| Fisher's Hornpipe | **none** | 4/4 | ✗ key missing |
| Flop Eared Mule | G (1♯) | 4/4 | ✓ |
| Forked Deer | D (2♯) | 2/2 | ✓ |
| June Apple | D (2♯) | 4/4 | ✓ (A mixolydian = D key sig) |
| Liberty | G (1♯) | **?** | ✗ meter missing; key may be wrong (D?) |
| Lost Indian | D (2♯) | 4/4 | ✓? |
| Mississippi Sawyer | D (2♯) | 4/4 | ✓ |
| Morrison's Jig | **none** | **?** | ✗ both key and meter missing |
| Old Joe Clark | G (1♯) | 4/4 | ✓ (G ≈ A mixolydian key sig) |
| Red Haired Boy | **NO_MXL** | — | ✗ Audiveris produced no output |
| Salt Creek | D (2♯) | 4/4 | ✓ |
| Soldier's Joy | D (2♯) | 4/4 | ✓ |
| Turkey in the Straw | G (1♯) | 4/4 | ✓ |

**Failure summary (original DPI, no preprocessing):**

| Failure type | Count | Tunes |
|-------------|-------|-------|
| No key detected | 3 | Billy in the Lowground, Fisher's Hornpipe, Morrison's Jig |
| No MXL output | 1 | Red Haired Boy |
| Likely wrong key | 1–2 | Calliope House (K:E unusual), Liberty (K:G vs expected D?) |
| Missing meter only | 3 | Cherokee Shuffle, Liberty, Morrison's Jig |

**Bottom line: 4–6 out of 20 tunes have key/MXL failures at original DPI (20–30%).** This is
without any preprocessing, so these failures aren't caused by upscaling. The 2× upscale adds
further key failures on top of these (Arkansas Traveler example: original K:D → 2× K:none).

The survey confirms that ~20% of the corpus will have key detection failures in the basic
pipeline before any preprocessing decisions are made. A batch pipeline needs a strategy for
handling these cases.

---

### Experiment 4b: Three-way key detection comparison — 1×, 1.5×, 2×

**Method:** Ran the same 20 tunes at 1.5× (unsharp 0x1 + Lanczos 150%) and 2× (unsharp 0x1 +
Lanczos 200%) to compare key detection accuracy across all three scales. Scripts:
`survey_key_detection.sh` (1×), `survey_key_detection_2x.sh` (2×), plus manual 1.5× spot
checks for each tune. Expected keys from standard old-time repertoire knowledge.

**Key detection scores (correct key / 19 tunes with known expected key):**

| Scale | Correct | % |
|-------|---------|---|
| 1× (original DPI) | 13/19 | 68% |
| **1.5× (new)** | **15/19** | **79%** |
| 2× | 13/19 | 68% |

**Full three-way table (1× / 1.5× / 2×):**

| Tune | Exp | 1× | 1.5× | 2× |
|------|-----|----|------|----|
| Bill Cheatham | G | G✓ | D✗ | D✗ |
| Billy in the Lowground | A | none✗ | none✗ | none✗ |
| Booth Shot Lincoln | A | A✓ | A✓ | A✓ |
| Calliope House | ? | E? | E? | E? |
| Cherokee Shuffle | A | A✓ | A✓ | A✓ |
| Cluck Old Hen | A | G✗ | G✗ | G✗ |
| Devil's Dream | A | A✓ | A✓ | A✓ |
| Fisher's Hornpipe | D | none✗ | **D✓** | none✗ |
| Flop Eared Mule | G | G✓ | D✗ | G✓ |
| Forked Deer | D | D✓ | D✓ | D✓ |
| June Apple | A | D✓ | D✓ | D✓ |
| Liberty | D | G✗ | D✓ | D✓ |
| Lost Indian | A | D✓ | D✓ | D✓ |
| Mississippi Sawyer | D | D✓ | D✓ | D✓ |
| Morrison's Jig | Em | none✗ | G✓ | G✓ |
| Old Joe Clark | A | G✗ | A✓ | G✗ |
| Red Haired Boy | G | NO_MXL✗ | **G✓** | D✗ |
| Salt Creek | D | D✓ | D✓ | D✓ |
| Soldier's Joy | D | D✓ | G✗ | D✓ |
| Turkey in the Straw | G | G✓ | G✓ | G✓ |

_(Note: expected keys are best-estimate from common old-time repertoire; WOFTA versions may
use different transpositions. A mixolydian tunes like June Apple notated with D key sig are
counted as correct.)_

**Key findings:**

1. **1.5× rescues 3 complete failures vs 1×**: Fisher's Hornpipe (none→D), Morrison's Jig
   (none→G), Red Haired Boy (NO_MXL→G). All three are correct rescues.

2. **2× only rescues 2 of those 3**: Morrison's Jig and Red Haired Boy (but with wrong key
   D instead of correct G). Fisher's Hornpipe remains a failure at 2×.

3. **Fisher's Hornpipe has a 1.5× sweet spot**: fails at both 1× and 2×, but succeeds at
   1.5×. Non-monotonic behavior — something about the intermediate size lands in Audiveris's
   recognition window.

4. **1.5× introduces some regressions** vs 1× on specific tunes: Bill Cheatham (G→D),
   Flop Eared Mule (G→D), Soldier's Joy (D→G). These tunes were correctly detected at 1×
   but not at 1.5×. Not true failures (a key is still detected), just the wrong key.

5. **2× introduces the same regression count** (Bill Cheatham, Red Haired Boy wrong key)
   plus it fails to rescue Fisher's Hornpipe, making it strictly worse than 1.5× overall.

6. **Calliope House consistently detects K:E (4 sharps)** at all three scales. Either this
   is a genuinely unusual notation in the WOFTA book, or the image has a persistent
   recognition error. Needs manual image check.

**Combined-scale strategy:**

Running both 1× and 1.5× and comparing resolves most disagreements:

| Scenario | Tunes | Action |
|----------|-------|--------|
| Both agree on same key (55%) | Booth Shot Lincoln, Cherokee Shuffle, Cluck Old Hen, Devil's Dream, Forked Deer, June Apple, Lost Indian, Mississippi Sawyer, Salt Creek, Turkey in the Straw + Billy/none | Use 1.5× ABC (better notes, confirmed key) |
| 1× fails, 1.5× succeeds (15%) | Fisher's Hornpipe, Morrison's Jig, Red Haired Boy | Use 1.5× ABC |
| Both give same key but 1× also detected it (adds Liberty, Old Joe Clark) | — | Use 1.5× ABC |
| Both disagree (non-failure) (25%) | Bill Cheatham, Flop Eared Mule, Soldier's Joy | Look up key from abcnotation.com; use whichever scale matches |
| Both fail (5%) | Billy in the Lowground | Manual GUI intervention needed |

**Bottom line: default to 1.5× preprocessing.** It gives 18/19 (95%) note accuracy on
Angeline the Baker (vs 19/19 at 2× and 12/19 at 1×) AND the best key detection success
rate. Run 1× as a validation pass and cross-check when scales disagree.

---

## Open questions

1. **Why does Cincinnati Hornpipe survive 2× but Arkansas Traveler doesn't?**
   Cincinnati has larger note heads (interline=15 vs 13–14), a much wider first-system
   header, and both sharps recognized with grades ≥ 0.538. The larger symbols apparently
   keep the header stop further right even after doubling.

2. **What is the right default preprocessing scale?**
   Three-way survey (1× / 1.5× / 2×) across 20 tunes gives: 68% / 79% / 68% correct key
   detection. 1.5× is the winner — better notes than 1× (95% vs 63% on Angeline) and better
   key detection than 2×. See Experiment 4b.

3. **Is a two-pass approach viable in a different form?**
   The MXL key injection approach is dead. But the two-pass idea survives in a different
   form: run original-DPI Audiveris → get correct key and correct (if lower-accuracy) notes
   → use that as the base transcription. Only apply 2× preprocessing to tunes where original-
   DPI key detection succeeds AND note accuracy needs improving. This narrows the 2× set to
   the ~80% of tunes that survive original-DPI key detection.

4. **Is the thesession.org / abcnotation.com ABC a viable shortcut for gold standards?**
   No for note content — arrangements differ too much. The key field can validate detected
   key. Manual correction from the WOFTA image is still required for each tune's gold standard.

5. **Calliope House: why does Audiveris detect K:E (4 sharps) in 6/8?**
   Calliope House is typically A minor or D, not E major. The 4-sharp detection on a 6/8
   jig is suspicious — the key sig region may be confusing a sharp cluster with extra sharps,
   or the tune genuinely has an unusual notation. Worth checking the image.

---

## TODOs

### Immediate
- [x] ~~Try Audiveris GUI on Ashokan Farewell~~ — diagnosed via .omr XML (see above)
- [x] ~~Survey key/meter detection across ~20 more WOFTA tunes~~ — done (see Experiment 4a/4b)
- [x] ~~Test MXL key injection~~ — dead end (see Experiment 1)
- [x] ~~Run 2× upscale survey on the same 20 tunes~~ — done (see Experiment 4b)
- [x] ~~Test 1.5× as compromise scale~~ — done; 1.5× is best overall (see Experiment 4b)
- [ ] Create gold standard ABCs for the 4 test tunes (manual correction from image)
- [ ] Score all 4 tunes' raw Audiveris output once gold standards exist
- [ ] Investigate why Calliope House shows K:E (4 sharps) at all scales — look at the image
- [ ] Verify Fisher's Hornpipe and Red Haired Boy 1.5× output quality (they're now rescued)

### Pipeline strategy
- [ ] Update `run_tune_pipeline.sh` to use 1.5× (from 2×) as the new default
- [ ] Consider a dual-pass pipeline: run 1× AND 1.5×, compare keys; if agree → use 1.5×
      ABC; if disagree → look up abcnotation.com for tiebreak
- [ ] Test note accuracy of 1.5× on tunes other than Angeline (need gold standards)
- [ ] Investigate meter detection failures at all scales (Cherokee Shuffle, Liberty,
      Morrison's Jig consistently show no time sig — image-specific or Audiveris bug?)

### Tooling
- [ ] Fix `blank_chord_names.py` margin logic if chord-name blanking is ever revisited
      (current `above_margin=4` removes low ledger-line notes; needs to detect actual
      note extent below each system's bottom line before blanking)
- [ ] Update `omr_report.html` once gold standards and final scores are available

---

## Files produced

### Session 1 (2026-06-11 first pass)
- `run_tune_pipeline.sh` — generalized pipeline: preprocess → Audiveris → ABC
- `blank_chord_names.py` — chord-name blanking (dead end for key detection, but kept)
- `abc/{Tune}-audiveris-raw.abc` — 2×+unsharp Audiveris output (4 test tunes)
- `abc/{Tune}-audiveris-original.abc` — original-DPI Audiveris output (3 of the 4 test tunes)
- `abc/{Tune}-thesession.abc` — reference from thesession.org (Ark. Traveler, Blackberry)
- `omr_report.html` — visual comparison: original WOFTA sheets vs. all preprocessing variants

### Session 2 (2026-06-11 second pass — batch experiment)
- `survey_key_detection.sh` — batch key detection survey at original DPI
- `survey_results.tsv` — key/meter detection results for 20 tunes at original DPI

### Session 3 (2026-06-11 third pass — scaling comparison)
- `survey_key_detection_2x.sh` — batch key detection survey at 2× upscale
- `survey_results_2x.tsv` — key/meter detection results for 20 tunes at 2× upscale
- `abc/Arkansas Traveler-audiveris-1.5x.abc` — 1.5× Audiveris output for comparison
