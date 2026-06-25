# Verified-tune diff notes — 2026 add-ons & redos

Companion to **`2026_verified_diff.pdf`** (current verified ABC engraving on top,
new 2026 PDF below, one tune per page). For each of the 11 tunes that already have
a signed-off `-verified.abc`, here's what differs between your current engraving and
the new PDF, so you can decide whether a redo is worth it.

Comparison basis: your verified ABC was read as source text (exact); the new PDF was
read from its rendered image. Note-by-note melody matched where legible; anything I
couldn't confirm at image resolution is flagged. **No corpus files were touched.**

Legend: 🟢 essentially identical (cosmetic only) · 🟡 minor musical/markup differences · 🔴 real musical differences to review.

---

## 🟢 Old Joe Clark
Same arrangement: A major, 4/4, 16 bars written out (no repeats), starts on the high
strain (`e f =g f`). Chords match (A / E / G). New PDF is a clean Finale engraving
("KM Finale 26", "Traditional"). The g-naturals (mixolydian 7th) are explicit in your
ABC; the new is in A-major key signature, so confirm it naturals the g's. No melodic
change detected. **Verdict: a cleaner render of the same setting — low value to redo.**

## 🟢 Chinquapin
Same: D major, 4/4, pickup, AABB with 1st/2nd endings on both strains. Chords match
(D / A7 / D / A / G / A / Em in A-part; D / G / A7 in B-part). New PDF adds a "Fiddle"
voice label and is a cleaner engraving. No melodic difference detected.

## 🟢 Crooked Stovepipe
Same: G major, cut time, A-part with 1st/2nd endings, high B-part. Chords match
(G / Am / D / C). Both carry the `^a` (G♯) accidentals. New PDF adds the performance
note **"Last time end on G chord"** and ends G→D. Cosmetic + that annotation.

## 🟢 Florida Blues
Same: D major, 4/4, pickup, AABB with 1st/2nd endings. Chords match (D / D7 / G / A).
Ties present in both. New PDF adds **"Rhythm rest to end"** annotation and a © mark,
labels "Fiddle". No melodic difference detected.

## 🟢 Starry Night for a Ramble
Same: D major, 6/8, pickup, with the distinctive **three-ending B-part** in both
(1st/2nd/3rd → the new labels the 3rd "final ending"). Chords match
(D / G / A / Em). Cosmetic only.

## 🟢 Wind That Shakes the Barley
Same: D major, 4/4, A-part written out then AABB B-part with 1st/"final ending".
Chords match (D / G / D / A / Em). Both end on a long held D. New labels "Fiddle" and
"final ending". Cosmetic only.

---

## 🟡 Magpie
Same tune & structure (G major, 4/4; A-part repeat, B-part with double-stops `[Dd]`,
`[dg]`, `[DBg]` and 1st/2nd endings). Chords match (G / D / C / D). **The win in the
new PDF is the attribution:** it reads cleanly **"from Alan Jabbour / from N.C."**,
whereas your verified ABC's composer field is OCR-garbled (`C:Alan Jabbom'fﬁ'om N.C.`).
Worth at least fixing that `C:` line in the verified ABC even if you don't redo.

## 🟡 Porter's Reel
Same: D major, cut time, triplet pickup, AABB with 1st/2nd endings on both strains.
Chords match (D / A / D / G). **New PDF expands the attribution to "Spencer and Rains
[The Old Texas Fiddle Vol II]"** — your verified has only the bracketed source. Consider
updating the `C:` line. No melodic difference detected.

---

## 🔴 Clinch Mountain Backstep
Same melodic shape (A mixolydian feel, 4/4, AABB), chords match (A / E7~E). But two
real notational differences:
- **The crooked extra-beat bar is barred differently.** Your verified inserts one
  `[M:6/4]` measure in the B-part; the new PDF instead drops to **`2/4` then back to
  `4/4`** around the same spot. Same total music is *likely*, but the measure grouping
  differs — verify the beat count lines up.
- **Key-signature notation:** your verified is `K:Amix` (sharps in the signature); the
  new PDF is written with **no key signature** (open key, accidentals inline). 
- Attribution differs: verified credits the *Bluegrass & Old Time Mandolin Newsletter
  (Nigel Gatherer)*; new credits **"Ralph Stanley"**.

## 🔴 Frosty Morning
Same key/meter/structure (G major, 4/4, pickup, AABB with 1st/2nd endings on both),
A-part chords match (Am / G). **But the B-part chords differ:** the new PDF adds an
**E chord** (end of the 3rd line) and a **C chord** (`am C dm am` in the last line)
that your verified doesn't have (verified B-part is `Am / A(opt) / G / Am / Dm / Am /
G`). New also uses lowercase chord names and drops your "(opt)" on the A. Melody tracks;
the harmonic reading is the real difference — review which chord set you want.

## 🔴 Sally Ann
Same: A major, cut time, AABB with repeats; chords match (A / D / E). **The difference
is the bass/passing-chord annotations:** your verified carries parenthetical
**`(C#)` and `(F#)`** walk-up markers in the A-part; the new PDF omits them (plain
A / D / E only). If you value those passing-chord hints, your current version is richer;
if you found them clutter, the new is cleaner.

---

### Quick triage
- **Skip (cosmetic):** Old Joe Clark, Chinquapin, Crooked Stovepipe, Florida Blues,
  Starry Night for a Ramble, Wind That Shakes the Barley.
- **Just fix the `C:` attribution line, no full redo:** Magpie, Porter's Reel.
- **Decide on substance:** Clinch Mountain Backstep (barring/key notation),
  Frosty Morning (added C/E chords), Sally Ann (dropped (C#)/(F#) passing chords).
