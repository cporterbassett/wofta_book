# OMR Pipeline Findings
_Session: 2026-06-11_

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

## Open questions

1. **Why does Cincinnati Hornpipe survive 2× but Arkansas Traveler doesn't?**
   Cincinnati has larger note heads (interline=15 vs 13–14), a much wider first-system
   header, and both sharps recognized with grades ≥ 0.538. The larger symbols apparently
   keep the header stop further right even after doubling.

2. **How many of the 277 WOFTA tunes will have key detection failures?**
   If ~50% fail (as suggested by this 4-tune sample), the pipeline needs rethinking.
   Need to run a larger survey before committing to a strategy.

3. **Is a two-pass Audiveris approach viable?**
   Run Audiveris on original image → extract key/meter.
   Run Audiveris on 2×+unsharp → extract note content.
   Combine: patch key/meter from pass 1 into pass 2's ABC.
   BUT: without a correct key in the MXL, pass 2's pitch content is already wrong
   (F natural instead of F♯). Patching the ABC header doesn't fix the pitches in
   the note content. Would need to patch the MXL `<key>` element BEFORE xml2abc
   conversion — possible in theory (inject `<key><fifths>N</fifths></key>` into
   measure 1), but unverified.

4. **Can the MXL be patched before xml2abc conversion?**
   If we inject `<key><fifths>2</fifths></key>` into measure 1 of the pass-2 MXL,
   would xml2abc then produce correct pitches? The note `<pitch>` elements in MXL
   already have absolute `<alter>` values set at recognition time — patching the key
   element won't retroactively fix those. So probably not.

5. **Is the thesession.org ABC a viable shortcut for gold standards?**
   For traditional tunes: yes as a starting point, but arrangements differ.
   - Arkansas Traveler: thesession uses B,C pickup; WOFTA uses D pickup. Different.
   - Blackberry Blossom: thesession M:4/4, WOFTA M:2/2; B section goes to Em in
     WOFTA but stays in G on thesession. Different arrangement.
   Manual correction still required for each tune.

---

## TODOs

### Immediate
- [x] ~~Try Audiveris GUI on Ashokan Farewell~~ — diagnosed via .omr XML (see above)
- [ ] Create gold standard ABCs for the 4 test tunes (manual correction from image)
- [ ] Score all 4 tunes' raw Audiveris output once gold standards exist

### Pipeline strategy
- [ ] Survey key/meter detection across ~20 more WOFTA tunes (original DPI, no preprocessing)
      to understand the failure rate before deciding on preprocessing strategy
- [ ] Investigate whether a two-pass approach (key from original, notes from 2×) is
      salvageable — specifically whether injecting correct accidentals post-hoc is feasible
- [ ] Consider whether running Audiveris at original DPI (no preprocessing) gives
      acceptable note accuracy across the board, even if slightly below 2×+unsharp

### Tooling
- [ ] Fix `blank_chord_names.py` margin logic if chord-name blanking is ever revisited
      (current `above_margin=4` removes low ledger-line notes; needs to detect actual
      note extent below each system's bottom line before blanking)
- [ ] Update `omr_report.html` once gold standards and final scores are available

---

## Files produced this session

### Scripts
- `run_tune_pipeline.sh` — generalized pipeline: preprocess → Audiveris → ABC
- `blank_chord_names.py` — chord-name blanking (dead end for key detection, but kept)

### ABCs
- `abc/{Tune}-audiveris-raw.abc` — 2×+unsharp Audiveris output (all 4 tunes)
- `abc/{Tune}-audiveris-original.abc` — original-DPI Audiveris output (Ark. Traveler, Ashokan, Cincinnati)
- `abc/{Tune}-thesession.abc` — reference from thesession.org (Ark. Traveler, Blackberry)

### Report
- `omr_report.html` — visual comparison: original WOFTA sheets vs. all preprocessing
  variants, with explanations. Open in Firefox to review.
