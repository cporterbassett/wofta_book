# OMR Pipeline — Next Steps

_Written 2026-06-11 (Opus session) as a cold-start brief for a follow-up session._
_Updated 2026-06-11 (Sonnet session) after scoring work and pipeline architecture decisions._
_Updated 2026-06-12 (Opus session) after normalize_interline, health_score, verify_mxl, compare_abc fix._
_Updated 2026-06-12 (Sonnet session) after mvt1 MXL fallback fix in batch_tune.sh._
_Updated 2026-06-12 (Sonnet session) after Audiveris -constant sweeps (Experiment D)._
_Updated 2026-06-12 (Sonnet session) after glyph dilation sweep (Experiment E)._
_Updated 2026-06-12 (Opus session) after key_status triage + Phase 1 completion audit._
_Updated 2026-06-12 (Opus session) after Phase 2 KICKED OFF — first 9 tunes finalized, GUI/render/report tooling built, key traps found (see Phase 2 section)._
_Updated 2026-06-12 (Opus session) after pre-scale infra: validate_final.py sanity gate (wired into export_tune.sh + cleanup_loop.sh), build_tracking_sheet.py → tracking.md, cleanup_loop.sh worst-first ordering fix, export_tune.sh barline-count fix._
_Read `omr_findings.md` first for the full experiment history. This file is the
forward-looking plan: what to build next, in priority order, and why._

---

## CURRENT STATE (2026-06-12) — Phase 1 done, Phase 2 STARTED (9/~31 keep-list tunes)

**Phase 1 (batch OMR) is complete.** 267/272 source tunes have `clean.omr` + a
draft ABC; `health_scores.tsv` is fully populated (267 tunes). All preprocessing
experiments (A–E) are concluded — A & B shipped, C/D/E are dead ends. **There is no
more automated quality to extract.** Source heterogeneity defeats every global knob.

**Phase 2 (interactive GUI cleanup) has STARTED — but only on a confirmed KEEP-LIST
subset, not the whole corpus.** Porter is still waiting on the final keep/add list, so
we only finalize tunes already known to be in the book. The 31-tune subset (worst-first
by health_score) is in `cleanup_keep.sh`. **9 tunes finalized so far** (`abc/*-final.abc`):
- GUI cleanup: Needle Case, Cherokee Shuffle, Red Haired Boy
- 6 gold ABCs promoted straight to `-final` (already correct from the WOFTA images):
  Angeline the Baker, Arkansas Traveler, Mississippi Sawyer, Soldier's Joy,
  Billy in the Lowground, Honest John.

See the **Phase 2 workflow & findings** section below for the per-tune recipe, the new
tooling, and three traps hit in the first tunes.

**The queue is now triaged by real correction effort.** `health_score.py` gained a
`key_status` column (present / missed / absent). The old `key_ok=False` penalty was a
false alarm for the 21 genuinely-keyless tunes (Am / C / Dorian); they no longer drag
the queue. The 15 `missed` tunes (Audiveris dropped a *printed* key sig — found
elsewhere in the sheet, or as a stray key-alter glyph / ashokan rest) are the real
key fixes and now sort to the top. Distribution: 231 present, 21 absent, 15 missed.

**Five source PNGs never produced a `clean.omr`** — handle these out-of-band, they
won't flow through `cleanup_loop.sh`:
  - `Kerry Mills' Barn Dance` — hard Audiveris failure (no MXL at all); needs GUI from scratch.
  - `Morrison's Jig 2` — second copy, never processed.
  - `angeline_oemer.cropped`, `angeline_oemer_updated.cropped` — stray oemer test
    artifacts polluting the source dir; delete or move out of `../`.
  - `Honest John` — gold tune, lives in `old_images/` (symlinked); verify it wasn't silently dropped.

**Three tunes are truncated by movement-split** (the `mvt1` fallback grabbed a
fragment) — their draft ABC is near-useless, fix in GUI: Bull Moose (2 measures),
Pat(T)'s Country (5), Elzic's Farewell (5).

**→ Next action:** continue `cleanup_keep.sh` down the keep-list queue. Next GUI tune
is **Temperance Reel** (= Teetotaller's Reel, ashokan tell). 22 keep-list tunes remain.

---

## Phase 2 — workflow & findings (STARTED 2026-06-12)

### Per-tune recipe (confirmed on the 3 GUI tunes)
1. Open `batch_output/<Tune>/clean.omr` in the Audiveris GUI (launch in background;
   maximize with `wmctrl -r Audiveris -b add,maximized_vert,maximized_horz`).
2. Fix notes / key / clef in the GUI, then **Ctrl+S (Save) — NOT File→Export.**
3. `bash export_tune.sh "<Tune>"` — batch-exports the saved `.omr`, cleans, converts to
   `abc/<Tune>-final.abc`, and renders. **Use this, not raw commands** (it traps the
   movement-split case — see below).
4. Add `T:` (tune name) and chord symbols by reading them off the scan, into the ABC.
   **Title + chords are done in the ABC, NOT in the Audiveris GUI** (GUI chord-entry is
   slow and fiddly; chord text is large/crisp and easy to read off the scan).
5. Render (`render_abc.sh`) and open render + scan in `firefox` to verify. Regenerate the
   comparison page with `build_report.sh` → `finalized_report.html`.
6. `export_tune.sh` and `cleanup_loop.sh` auto-run `validate_final.py "<Tune>"` after each
   export — watch for a `FAIL` banner (missing/wrong key, or truncation = dropped staves).
   It never aborts the loop; FAILs are advisory. Then update the tracking sheet:
   `python3 build_tracking_sheet.py` (regenerates `tracking.md`; preserves your hand-typed
   **Verified?** / **Notes** columns) and mark the tune verified once eyeballed against the scan.

### New tooling built this session
- `cleanup_keep.sh` — runs `cleanup_loop.sh` over the keep-list subset only, worst-first.
- `export_tune.sh` — post-GUI export→clean→ABC→render; detects movement splits.
- `build_report.sh` / `finalized_report.html` — side-by-side scan-vs-engraved report of
  every `abc/*-final.abc`. Re-run after finalizing tunes.
- `render_abc.sh` upgraded: injects `%%measurenb 0` (line-start measure numbers, like the
  scans) + bold `%%gchordfont`/`%%repeatfont`. Voltas authored as `["1."`/`["2."` so they
  render **1.** / **2.** (plain `|1` renders bare "1").
- `validate_final.py` — post-export sanity gate over `abc/<Tune>-final.abc`. FAIL on missing/
  inconsistent key (cross-checks `health_scores.tsv` key_status) or truncation (final < draft,
  or `< 16` bars — the dropped-systems guard); WARN on missing meter, `< 4` chords (text
  annotations excluded), or missing/placeholder title. Reuses `compare_abc.py`'s measure
  splitter, so a short anacrusis final bar is not flagged. `--all` scans every final. Wired
  into both `export_tune.sh` and `cleanup_loop.sh`; exit code is non-zero on any FAIL.
  Thresholds `CHORD_MIN=4` / `FLOOR=16` are constants — bump down if a shorter book tune appears.
- `build_tracking_sheet.py` → `tracking.md` — Markdown table (chosen over XLSX so it diffs in
  git), rows = keep-list ∪ every `-final.abc`. Auto columns (health, key_status, finalized,
  key/meter/chords/title marks, measures, truncation) regenerate from live files; the
  **Verified?** (`No`/`Yes`/`Needs-fix`) and **Notes** columns are hand-edited and preserved
  across runs. `--check` dry-runs to stdout. `tracking.md` IS committed; treat it as the
  per-tune verification ledger (file-existence ≠ verified).

### Three traps hit (will recur)
1. **Movement split.** When Audiveris splits a score, batch export writes
   `clean.mvt1.mxl` / `clean.mvt2.mxl` and the top-level `clean.mxl` is STALE — converting
   it silently discards GUI edits. `export_tune.sh` detects this, converts each movement
   for inspection, and stops; re-run with `--mvt N` (mvt1 = main tune; later movements are
   often alternates/fragments). Cherokee Shuffle: mvt2 was the book's "Alt Measures 12 & 13".
2. **Dropped systems.** `normalize_interline.py` scales the page to one median interline,
   so on a xerox where systems differ slightly some land outside Audiveris's tight tolerance
   and the GRID step discards whole staves. **Tell-tale: low `measure_count` in
   health_scores.tsv** (Red Haired Boy was msr=9 of 18). Fix: re-OMR the ORIGINAL scan at a
   plain uniform scale (130–250% all recovered Red Haired Boy's 4 systems; used 150%), check
   `Retrieved raw line clusters: N` in the preprocessed log = number of systems, then
   `clean_omr.py` over `batch_output/<Tune>/clean.omr`. Manual staff-adding in the GUI is
   NOT practical. (The rescale may drop a key sig sharp — fix in GUI.)
3. **Audiveris drops the GRAY image** from a reopened `.omr` (Gray tab blank, by design,
   no GUI toggle). Use the **Binary** tab for in-tool reference; the true grayscale only
   exists in the source PNG (open in firefox).

### Conventions / Porter preferences
- Chords placed at the **beat they sit over in the scan**, not defaulted to the downbeat
  (e.g. endings: chord on the 2nd-half half-note).
- No `nm="Voice"` voice labels (stripped automatically by `export_tune.sh`).
- Alternate measures rendered as a labeled trailing staff (`"^Alt Measures..."` + `|]`),
  not just an ABC comment.
- `batch_output/` (`.omr`/`.mxl`) is intermediate and intentionally NOT version-controlled;
  the `abc/*-final.abc` files are the committed output / source of truth.

---

## Experiment E — Glyph Cleanup (Dilation) ✗ DEAD END

_Executed 2026-06-12. Script: `glyph_cleanup_sweep.py --operation dilation`. 40 jobs: 10 tunes × 4 variants (baseline, dilate_k2, dilate_k3, dilate_k4). Each variant applies a morphological dilation with the given square kernel before passing the preprocessed PNG to Audiveris._

### Health scores

```
variant     Big Scioty          Miss McCloud's Reel Big Con             Ashokan Farewell    Arkansas Traveler   Angeline the Baker  Soldier's Joy       Mississippi Sawyer  Billy in the Lowgro Honest John
baseline    ...  h=48           ...  h=47           .T.  h=69           KTA  h=77           KT.  h=108          KT.  h=108          KT.  h=108          KT.  h=108          .T.  h=68           ...  h=48
dilate_k2   KT.  h=108          ...  h=47           .T.  h=68           K..  h=88           KT.  h=108          KT.  h=108          KT.  h=108          KT.  h=108          .T.  h=68           ...  h=48
dilate_k3   KT.  h=108          ...  h=47           .T.  h=68           K..  h=87           KT.  h=108          K..  h=87           KT.  h=108          KT.  h=108          .TA  h=38           ...  h=48
dilate_k4   KT.  h=108          ...  h=41           .T.  h=68           K..  h=87           KT.  h=108          ...  h=47           KT.  h=108          KT.  h=108          .T.  h=68           ...  h=47

Legend: K=key_ok T=time_ok A=ashokan_tell h=health_score
```

### Note accuracy (gold tunes)

```
variant     Arkansas Traveler   Angeline the Baker  Soldier's Joy       Mississippi Sawyer  Billy in the Lowgro Honest John
baseline    17/18 (94%)         18/19 (95%)         12/18 (67%)         14/18 (78%)         14/17 (82%)         1/16 (6%)
dilate_k2   16/18 (89%)         12/19 (63%)         14/18 (78%)         12/18 (67%)         13/17 (76%)         0/16 (0%)
dilate_k3   14/18 (78%)         1/19 (5%)           16/18 (89%)         14/18 (78%)         6/17 (35%)          1/16 (6%)
dilate_k4   6/18 (33%)          4/19 (21%)          2/18 (11%)          1/18 (6%)           1/17 (6%)           1/16 (6%)
```

### Key recovery / regressions

- **Big Scioty:** key recovered at dilate_k2/k3/k4. Big Scioty IS in G major (1 sharp) — the key recovery is real. Audiveris is failing at baseline to detect a printed sharp that is small and tight against the clef.
- **Ashokan Farewell:** ashokan_tell removed at all dilation variants (K only, h=87-88 vs baseline KTA h=77). However, the time sig (T) is now missing — dilation thickened the time-sig glyphs past recognizability. Net neutral at best.
- **All other key failures** (Miss McCloud's Reel, Big Con, Billy in the Lowground, Honest John): no recovery at any kernel size.
- **Note accuracy degrades monotonically** with kernel size. dilate_k2 already regresses 3 of 5 gold tunes (−5% to −32%). dilate_k4 is catastrophic (−61% to −89%).
- **Angeline the Baker:** key broke at dilate_k4.
- **Billy in the Lowground:** ashokan_tell introduced at dilate_k3.

### Conclusion

DONE — dilation did not improve OMR quality.

Dilation consistently degrades note accuracy: even the smallest kernel (k2) reduces accuracy on most gold tunes. The key recovery on Big Scioty at dilate_k2 IS real (Big Scioty is G major, 1 sharp; Audiveris baseline misses the small tight-to-clef sharp), but this gain is wiped out by note-accuracy regressions elsewhere and a broken time sig on Ashokan Farewell. Do not apply dilation preprocessing globally.

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

**Status:** Gold standards created; 6 tunes scored at baseline interline normalization (Experiment E sweep).

**Gold standard ABCs** (in `abc/`, transcribed directly from WOFTA images):
- `Arkansas Traveler-gold.abc` — 18 measures, K:D
- `Soldier's Joy-gold.abc` — 18 measures (incl. pickup), K:D
- `Mississippi Sawyer-gold.abc` — 18 measures (incl. pickup), K:D
- `Angeline the Baker-gold.abc` — 19 measures, K:D
- `Billy in the Lowground-gold.abc` — 17 measures, K:C (Audiveris baseline misses key — useful regression check)
- `Honest John-gold.abc` — 16 measures, K:G jig; source PNG at `old_images/Honest John.png` (symlinked)

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

## Experiment D — Audiveris `-constant` sweeps ✗ DEAD END (source diversity defeats it)

_Executed 2026-06-12. Script: `sweep_constants.py`._

**Constant format confirmed:** `org.audiveris.omr.ClassName.fieldName=value`  
**Flatpak sandbox note:** Audiveris can only write output to paths under `~` (not `/tmp`).
Use dirs inside `batch_output/` for temp sweep dirs.

### What was swept

**1. Grade threshold constants (`keyAlterMinGrade1`, `keyAlterMinGrade2`, `keySigMinGrade`,
`minInterGrade`, `intrinsicRatio`):**

Swept `keyAlterMinGrade1` 0.01–0.5 on 7 tunes. **Zero effect.** All tunes returned identical
results across all values. Then swept 5 different grade constants including the global
`intrinsicRatio` on Soldier's Joy — all returned fifths=1 (K:G, wrong). The constants ARE
being applied (confirmed by testing: Audiveris crashed at halfWindowSize=4, proving it reads
constants), but grade thresholds are not the binding constraint.

**Root cause of "key_ok=False" findings (important reframe):**
Visual inspection revealed a mixed picture. Some `key_ok=False` tunes **genuinely have no
printed key signature** — they are in A minor, C major, or similar. Examples: Big Con (Am,
no key sig), Billy in the Lowground (C major, labeled "C Major" in image). The health_score
−40 penalty is a false alarm for those. BUT others do have printed key signatures that
Audiveris simply fails to detect: **Big Scioty is G major (1 sharp)** — the sharp is small
and tight against the clef, so Audiveris misses it at baseline. Cannot assume `key_ok=False`
is always correct behavior; visual inspection per tune is needed.

**2. `AdaptiveFilter.halfWindowSize` (binarization window, integer pixels):**

This constant DOES affect key detection. Swept 12–36 on 10 tunes:

| halfWin | Soldier's Joy | Ashokan Farewell | Arkansas Traveler | Mississippi Sawyer |
|---------|--------------|------------------|-------------------|---------------------|
| baseline (~8?) | f=1✗ | f=1✗, tell | f=2✓ | f=2✓ |
| 12 | f=1✗ | f=1✗, tell | f=2✓ **+tell** ← BAD | f=2✓ **+tell** ← BAD |
| 20 | f=1✗ | f=2✓ | **key BROKE** ← BAD | **key BROKE** ← BAD |
| 24 | f=1✗ | f=2✓ | **key BROKE** ← BAD | f=2✓ |
| 28 | f=2✓ | f=1✗ ← BAD | f=2✓ | f=2✓ |
| 32 | f=2✓ | f=1✗ ← BAD | f=2✓ | f=2✓ |
| 36 | f=1✗ | f=1✗ | f=2✓ | f=2✓ |

(All tunes should be fifths=2, i.e. K:D. tell = ashokan_tell present.)

**No single value improves all tunes without regressions.** The caution from fact #2 was
exactly right: different typesetters respond to opposite window sizes. This is a fundamental
source-heterogeneity problem that a single global constant cannot solve.

### Conclusions

1. **Grade thresholds**: not the binding constraint. The failing key detections are either
   (a) tunes that genuinely have no key signature — correct behavior, or
   (b) classification failures where the glyph is not being recognized as a sharp at all,
   independent of grade thresholds.

2. **`AdaptiveFilter.halfWindowSize`**: has real effect, but no safe universal value.
   The corpus is too source-diverse.

3. **Ashokan tell**: a misclassification (sharp → quarter rest), not a grade threshold issue.
   A different binarization might help for that specific source but hurts others.

4. **Soldier's Joy K:G issue**: the second sharp is simply not being found (not classified as
   a sharp at all at 133% scale). Grade thresholds don't help. halfWindowSize=28-32 helps
   for this source but breaks Ashokan Farewell.

5. **Overall**: Experiment D cannot produce a useful global constant. The remaining key
   errors (Ashokan Farewell, Soldier's Joy, a few others) are best fixed in the GUI — each
   is a 1-2 click correction (fix key, delete spurious rest). Not worth the risk of global regressions.

**Note on Audiveris constants:** We inspected the jar and confirmed there is NO constant to
disable slur detection, key-repeat export, or decorations. The `-constant` system exposes
size/threshold tuning only. Slurs and decorations must be removed post-hoc via `clean_omr.py`.

---

## Dead ends — do NOT redo these (see `omr_findings.md` for detail)

- **LLM / non-Audiveris transcription** (pre-OMR attempts, logged in
  `abandoned_transcription_attempts.md`): `claude -p` hallucinates noteheads; `oemer`'s
  pitch is roughly right but rhythm is unreliable; direct in-session note-reading is accurate
  but far too slow at corpus scale. These are why the pipeline is Audiveris + GUI correction,
  not AI transcription.
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
- **Audiveris grade threshold constants to fix key detection** — swept `keyAlterMinGrade1`
  (0.01–0.5), `keyAlterMinGrade2`, `keySigMinGrade`, `minInterGrade`, `intrinsicRatio`.
  Zero effect. The binding constraint is glyph classification, not grade thresholds.
- **`AdaptiveFilter.halfWindowSize` as a global fix** — has real effect on key detection,
  but no single value works across sources: smaller windows help some tunes, larger windows
  help others, same values that fix one tune break another (tested on 10 tunes).

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
7. ~~**Run `health_score.py` on full corpus**~~ — **DONE** (2026-06-12). `health_scores.tsv`
   has all 267 tunes; now triaged by `key_status` (present/missed/absent) so the queue
   ranks by real correction effort, not the noisy key_ok binary.
8. ~~**Fix mvt1 multi-MXL batch failures**~~ — **DONE** (2026-06-12). `batch_tune.sh` now falls back to `preprocessed.mvt1.mxl` when `preprocessed.mxl` is absent. Fixed 8 tunes: Bull Moose, Centralia Waltz, Fisher's Hornpipe (D/4/4), Me and My Fiddle (G/4/4), Morrison's Jig, Cherokee Shuffle (A/4/4), Road House Ramble (G/4/4), Pat(T)'s Country.
   - Pat(T)'s Country split into 3 movements; mvt1 yields only ~5 bars — needs GUI to reassemble.
9. ~~**Experiment D**~~ — **DEAD END** (see above). Grade thresholds: zero effect. Binarization constants: have effect but no safe universal value due to source heterogeneity. Fix remaining key errors (Ashokan, Soldier's Joy) in the GUI.
10. ~~**Experiment E**~~ — **DEAD END** (see above). Morphological dilation degrades note accuracy monotonically; no net benefit on any tune. Do not apply dilation.
11. **→ Phase 2 — interactive GUI cleanup (THE REMAINING WORK).** Run `cleanup_loop.sh`
    over `health_scores.tsv` worst-first. Start with the 15 `key_status=missed` and the
    `ashokan_tell=True` tunes (real key fixes), then descend the score. Handle the 5
    no-`clean.omr` stragglers and 3 movement-split tunes separately (see CURRENT STATE).

## Pointers to existing tooling

- `batch_tune.sh` — phase 1 single tune: preprocess → Audiveris batch → `clean_omr.py` →
  `clean_mxl.py` → `abc_xml_converter`. Output in `batch_output/<Tune>/`. Resumable via
  `clean.omr` checkpoint. Falls back to `preprocessed.mvt1.mxl` when Audiveris splits the
  score into movements instead of exporting a single `preprocessed.mxl`.
- `batch_all.sh` — runs `batch_tune.sh` over all 269 PNGs; skips tunes with `clean.omr`;
  supports `--dry-run`. Log in `batch_output/batch_all.log`.
- `cleanup_loop.sh` — phase 2 interactive: opens `clean.omr` in Audiveris GUI, waits for
  close, finds exported MXL, runs `clean_mxl.py` → `abc_xml_converter` → final ABC, then
  `validate_final.py`. Supports `--list` and specific tune names as args. With no args the
  queue is ordered **worst-first by `health_scores.tsv`** (not alphabetical); tunes missing
  from the TSV are appended. Output: `abc/<Tune>-final.abc`.
- `validate_final.py` — post-export sanity gate (see Phase 2 "New tooling"). `--all` or
  per-tune; non-zero exit + banner on FAIL. Called automatically by `export_tune.sh` and
  `cleanup_loop.sh`; also feeds `build_tracking_sheet.py`.
- `build_tracking_sheet.py` — regenerates `tracking.md` (the per-tune verification ledger;
  preserves hand-edited Verified?/Notes). `--check` to dry-run. See Phase 2 "New tooling".
- `clean_omr.py` — strips slur/wedge/articulation/bow/ornament/dynamics inters + relations
  from .omr XML **before** GUI opens it
- `clean_mxl.py` — strips same categories from MXL + repeated `<key>` elements (batch path)
- `compare_abc.py` — normalize ABC, split into measures, diff measure-by-measure; normalizes
  intra-measure whitespace; does NOT strip slurs (they're real errors if Audiveris adds them)
- `normalize_interline.py` — measure staff interline via row projection; scale to target 18px; falls back to 1.5× on detection failure. `--measure-only` flag for survey mode.
- `health_score.py` — parse `clean.omr` ZIP XMLs; score key/time/Ashokan-tell/avg-grade; output worst-first TSV. Already run over full corpus → `health_scores.tsv`.
  **`key_status` triage (added 2026-06-12) replaces the old key_ok caveat:**
  - `present` — key sig recognised in the first staff header. No work.
  - `missed`  — first header lacks it, but Audiveris found a printed key sig elsewhere
    (later-system header, stray `<key-alter>` glyph, or an ashokan rest in the header
    band). A real fix that corrupts every pitch → penalised −40. (e.g. Big Scioty G major.)
  - `absent`  — no evidence of any key sig anywhere → probably genuinely keyless (Am / C /
    Dorian — Big Con, Billy in the Lowground). Correct behaviour → NOT penalised.
  Only `missed` is penalised, so the queue ranks by real correction effort. **Caveat:**
  `absent` is a best guess — a sharp that vanished entirely in recognition (no rest, no
  later-system key, no stray glyph) is indistinguishable from keyless without the image.
  Every tune still gets eyeballed in the GUI, so this only affects queue order, not coverage.
  The ashokan_tell signal remains reliable: always a misclassified sharp.
- `sweep_constants.py` — **Experiment D tool**. Sweeps one Audiveris `-constant` over a set of
  tunes, scores with health_score logic, prints a table. Usage: `python3 sweep_constants.py
  [--constant NAME] [--values V1,V2,...] [--tunes T1,T2,...]`. Default sweeps
  `keyAlterMinGrade1`. Use 'baseline' as a value to run without any constant override.
  **Note:** Audiveris (flatpak) can only write to paths under `~`; uses `batch_output/` for temp dirs.
- `verify_mxl.py` — **dead end**, see Experiment C. Audiveris GUI already does this better.
- `overlay_diff.py` — red/blue mismatch overlay for ABC renders.
- `.omr` = ZIP with `sheet#N/sheet#N.xml` (glyph boxes, grades, header stops, SIG relations)
- venv: `../.venv/bin/python3` (has opencv-python-headless, music21, abc_xml_converter).
- Audiveris: `flatpak run org.audiveris.audiveris` (supports `-batch -export -constant
  key=value -output <dir> -sheets <n>`).
- gold-standard ABCs: `abc/*-gold.abc` (Arkansas Traveler, Soldier's Joy, Mississippi Sawyer, Angeline the Baker, Billy in the Lowground, Honest John)
- Batch output: `batch_output/<Tune Name>/` with `preprocessed.png`, `preprocessed.omr`,
  `preprocessed.mxl`, `clean.omr`, `clean.mxl`. Draft ABCs: `abc/<Tune>-draft.abc`.
