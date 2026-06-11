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

## Open questions

1. **Why does Cincinnati Hornpipe survive 2× but Arkansas Traveler doesn't?**
   Both are clean typeset, similar keys (D major, 2 sharps). Something about the
   specific sharp symbol rendering or layout differs. Not yet identified.

2. **Why does Ashokan Farewell fail even at original DPI?**
   It only gets 1 sharp (K:G) instead of 2 (K:D). The pickup measure before measure 1
   may confuse Audiveris's time-sig and key-sig search. The Audiveris GUI would help
   diagnose this interactively.

3. **How many of the 277 WOFTA tunes will have key detection failures?**
   If ~50% fail (as suggested by this 4-tune sample), the pipeline needs rethinking.
   Need to run a larger survey before committing to a strategy.

4. **Is a two-pass Audiveris approach viable?**
   Run Audiveris on original image → extract key/meter.
   Run Audiveris on 2×+unsharp → extract note content.
   Combine: patch key/meter from pass 1 into pass 2's ABC.
   BUT: without a correct key in the MXL, pass 2's pitch content is already wrong
   (F natural instead of F♯). Patching the ABC header doesn't fix the pitches in
   the note content. Would need to patch the MXL `<key>` element BEFORE xml2abc
   conversion — possible in theory (inject `<key><fifths>N</fifths></key>` into
   measure 1), but unverified.

5. **Can the MXL be patched before xml2abc conversion?**
   If we inject `<key><fifths>2</fifths></key>` into measure 1 of the pass-2 MXL,
   would xml2abc then produce correct pitches? The note `<pitch>` elements in MXL
   already have absolute `<alter>` values set at recognition time — patching the key
   element won't retroactively fix those. So probably not.

6. **Is the thesession.org ABC a viable shortcut for gold standards?**
   For traditional tunes: yes as a starting point, but arrangements differ.
   - Arkansas Traveler: thesession uses B,C pickup; WOFTA uses D pickup. Different.
   - Blackberry Blossom: thesession M:4/4, WOFTA M:2/2; B section goes to Em in
     WOFTA but stays in G on thesession. Different arrangement.
   Manual correction still required for each tune.

---

## TODOs

### Immediate
- [ ] Try Audiveris GUI on Ashokan Farewell to understand the pickup-measure failure
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
