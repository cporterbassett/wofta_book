# Glyph Cleanup Preprocessing — Sweep Design
_2026-06-12_

## Goal

Determine whether morphological dilation (thickening thin sharp strokes) improves
Audiveris recognition quality across the WOFTA corpus. This is Experiment A's "Still to do"
item from `next_steps.md`: measure glyph cleanup independently of scaling.

Despeckle (xerox noise removal) was scoped out: morphological opening and median blur
both operate at the same scale as augmentation dots (~2–3px at 18px interline), risking
false removal of dotted-note dots. Despeckling is deferred to a separate experiment with
explicit dot protection.

## Script

`notation_pipeline/glyph_cleanup_sweep.py`

### Invocation

```
python3 glyph_cleanup_sweep.py --operation dilation
python3 glyph_cleanup_sweep.py --operation dilation --tunes "Arkansas Traveler,Ashokan Farewell"
python3 glyph_cleanup_sweep.py --operation dilation --timeout 180
```

`--operation` currently only accepts `dilation`; reserved for future `despeckle` when that
experiment is designed.

## Pipeline per run

For each (variant, tune) pair:

1. Load source PNG from `tune_images/<Tune>.png`
2. Run `normalize_interline.normalize()` → normalized PNG in tmpdir (fallback to 1.5× on detection failure)
3. Apply glyph cleanup op to the normalized PNG (no-op for baseline)
4. Run Audiveris batch → tmpdir
5. Parse raw `.omr` with health_score logic → key/time/ashokan/health
6. If tune has a gold ABC: run `clean_mxl.py` → `abc_xml_converter` → `compare_abc.py` → note accuracy score
7. Clean up tmpdir

No writes to `batch_output/`.

## Dilation variants

Elliptical kernel, 1 iteration, `cv2.dilate`. Elliptical chosen because sharp strokes are
diagonal — rectangular kernels would square off curves.

| Variant     | Kernel |
|-------------|--------|
| baseline    | none   |
| dilate_k2   | 2×2    |
| dilate_k3   | 3×3    |
| dilate_k4   | 4×4    |

## Tune set

10 tunes total. All 10 get health scoring; the 6 with gold ABCs also get note-accuracy scoring.

**Health + note accuracy (gold ABCs in `abc/`):**
- Arkansas Traveler (`Arkansas Traveler-gold.abc`) — 18 measures, K:D
- Soldier's Joy (`Soldier's Joy-gold.abc`) — 17 measures, K:D (pickup)
- Mississippi Sawyer (`Mississippi Sawyer-gold.abc`) — 17 measures, K:D (pickup)
- Angeline the Baker (`Angeline the Baker-gold.abc`) — 19 measures, K:D
- Billy in the Lowground (`Billy in the Lowground-gold.abc`) — 16 measures, K:C (key_ok=False at baseline — useful regression check)
- Honest John (`Honest John-gold.abc`) — 16 measures, K:G/D jig; source PNG at `old_images/Honest John.png` (symlinked to `tune_images/Honest John.png`)

**Health only (no gold ABC):**
- Big Scioty — key_ok=False, time_ok=False (worst-case control)
- Miss McCloud's Reel — key_ok=False, time_ok=False (different source)
- Big Con — key_ok=False only
- Ashokan Farewell — ashokan_tell (second sharp misclassified)

## Output tables

### Table 1 — Health scores (all 10 tunes)

```
variant      Big Scioty           Arkansas Traveler  ...
baseline     ..T  h=88            KT.  h=108
dilate_k2    ..T  h=88            KT.  h=109
dilate_k3    ..T  h=89            KT.  h=108
dilate_k4    K.T  h=96            KT.  h=107
```

Legend: K=key_ok T=time_ok A=ashokan_tell h=health_score

### Table 2 — Note accuracy (gold-standard tunes only)

```
variant      Ark.Traveler  Soldier's Joy  Miss.Sawyer  Angeline  Billy  Honest John
baseline     17/18 (94%)   12/17 (71%)    14/17 (82%)  ?/19      ?/16   ?/16
dilate_k2    ?/18          ?/17           ?/17         ?/19      ?/16   ?/16
```

Baseline row for Arkansas Traveler, Soldier's Joy, Mississippi Sawyer is filled in from
prior known results as a sanity check; if the sweep's baseline differs, the pipeline has
regressed. Baseline for Angeline, Billy, Honest John will be established by the sweep.

## Success criteria

A variant is "promising" if it improves at least one failing tune's health score (key or
ashokan_tell) **without degrading any passing tune**, AND does not reduce note accuracy on
any gold-standard tune. If any kernel size passes, the best one gets integrated into
`normalize_interline.py` as a post-scale step (or as an opt-in flag in `batch_tune.sh`).

If no variant improves anything, dilation is ruled out and the "glyph cleanup" item in
`next_steps.md` is closed.

## Follow-on

If dilation shows promise: integrate the winning kernel size into `batch_tune.sh`
(as the default post-normalize step, or as a `--glyph-cleanup` flag).

Despeckle experiment: design separately with connected-component size filtering
(remove only components with area < 4px²) to avoid removing augmentation dots.
