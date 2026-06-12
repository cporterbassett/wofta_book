# Glyph Cleanup Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `glyph_cleanup_sweep.py` — a script that sweeps morphological dilation kernel sizes over 10 source-diverse WOFTA tunes and reports health scores + note-accuracy scores vs. gold ABCs.

**Architecture:** Single script run with the project venv (`tune_images/.venv/bin/python3`). Imports directly from sibling scripts (`normalize_interline`, `health_score`, `clean_mxl`, `compare_abc`, `abc_xml_converter`). Per-(variant, tune) run: source PNG → `normalize_interline.normalize()` → optional `cv2.dilate` → Audiveris batch in tmpdir → `health_score.score_omr()` → `clean_mxl` + `convert_xml2abc` + measure diff against gold ABC.

**Tech Stack:** Python 3, OpenCV (`cv2`), `abc_xml_converter`, Audiveris (flatpak), pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `notation_pipeline/glyph_cleanup_sweep.py` | **Create** | Main sweep script |
| `notation_pipeline/tests/test_glyph_cleanup_sweep.py` | **Create** | Unit tests |

Existing files imported (not modified):
- `notation_pipeline/normalize_interline.py` — `normalize()`, `apply_unsharp()`
- `notation_pipeline/health_score.py` — `score_omr()`
- `notation_pipeline/clean_mxl.py` — `clean_mxl()`
- `notation_pipeline/compare_abc.py` — `split_measures()`, `extract_body()`, `normalize_for_compare()`

---

## Task 1: Script skeleton — constants, imports, DILATION_VARIANTS

**Files:**
- Create: `notation_pipeline/glyph_cleanup_sweep.py`

- [ ] **Step 1: Create the script skeleton**

```python
#!/usr/bin/env python3
"""
Sweep morphological dilation parameters over a source-diverse tune set.

Pipeline per (variant, tune):
  source PNG → normalize_interline → cv2.dilate (or no-op) → Audiveris
  → health_score + compare_abc (gold tunes only)

Usage:
    python3 glyph_cleanup_sweep.py --operation dilation
    python3 glyph_cleanup_sweep.py --operation dilation --tunes "Arkansas Traveler,Ashokan Farewell"
    python3 glyph_cleanup_sweep.py --operation dilation --timeout 180

Run with: tune_images/.venv/bin/python3 glyph_cleanup_sweep.py --operation dilation
"""

import sys
import os
import argparse
import subprocess
import tempfile
import shutil
import difflib
import time

import cv2
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.dirname(SCRIPT_DIR)
ABC_DIR = os.path.join(SCRIPT_DIR, "abc")
AUDIVERIS = "flatpak run org.audiveris.audiveris"

sys.path.insert(0, SCRIPT_DIR)
from normalize_interline import normalize as _normalize_image, apply_unsharp
from health_score import score_omr
from clean_mxl import clean_mxl
from compare_abc import split_measures, extract_body, normalize_for_compare
from abc_xml_converter import convert_xml2abc

# Gold ABCs: tune name → (gold_abc_path, expected_measure_count)
GOLD_ABCS = {
    "Arkansas Traveler":      (os.path.join(ABC_DIR, "Arkansas Traveler-gold.abc"),      18),
    "Soldier's Joy":          (os.path.join(ABC_DIR, "Soldier's Joy-gold.abc"),          17),
    "Mississippi Sawyer":     (os.path.join(ABC_DIR, "Mississippi Sawyer-gold.abc"),     17),
    "Angeline the Baker":     (os.path.join(ABC_DIR, "Angeline the Baker-gold.abc"),     19),
    "Billy in the Lowground": (os.path.join(ABC_DIR, "Billy in the Lowground-gold.abc"), 16),
    "Honest John":            (os.path.join(ABC_DIR, "Honest John-gold.abc"),            16),
}

DEFAULT_TUNES = [
    "Big Scioty",
    "Miss McCloud's Reel",
    "Big Con",
    "Ashokan Farewell",
    "Arkansas Traveler",
    "Angeline the Baker",
    "Soldier's Joy",
    "Mississippi Sawyer",
    "Billy in the Lowground",
    "Honest John",
]

# Dilation variants: (label, kernel_size) — kernel_size None = baseline (no op)
DILATION_VARIANTS = [
    ("baseline", None),
    ("dilate_k2", 2),
    ("dilate_k3", 3),
    ("dilate_k4", 4),
]


if __name__ == "__main__":
    print("skeleton ok")
```

- [ ] **Step 2: Make executable and verify it imports cleanly**

```bash
chmod +x notation_pipeline/glyph_cleanup_sweep.py
tune_images/.venv/bin/python3 notation_pipeline/glyph_cleanup_sweep.py --operation dilation
```

Expected output: `skeleton ok`

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py
git commit -m "feat: add glyph_cleanup_sweep.py skeleton with constants"
```

---

## Task 2: `apply_dilation()` — elliptical morphological dilation

**Files:**
- Modify: `notation_pipeline/glyph_cleanup_sweep.py`
- Create: `notation_pipeline/tests/test_glyph_cleanup_sweep.py`

- [ ] **Step 1: Write the failing test**

`notation_pipeline/tests/test_glyph_cleanup_sweep.py`:

```python
import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from glyph_cleanup_sweep import apply_dilation


def _thin_line_image():
    """3-pixel-wide vertical dark line on white background, 30×30."""
    img = np.full((30, 30, 3), 255, dtype=np.uint8)
    img[:, 13:16, :] = 0  # 3-px dark column
    return img


def test_apply_dilation_increases_dark_pixels():
    img = _thin_line_image()
    dark_before = np.sum(img == 0)
    result = apply_dilation(img, kernel_size=3)
    dark_after = np.sum(result == 0)
    assert dark_after > dark_before, "dilation should add dark pixels"


def test_apply_dilation_kernel2_smaller_than_kernel4():
    img = _thin_line_image()
    r2 = apply_dilation(img, kernel_size=2)
    r4 = apply_dilation(img, kernel_size=4)
    assert np.sum(r4 == 0) > np.sum(r2 == 0), "larger kernel → more dark pixels"


def test_apply_dilation_returns_same_shape():
    img = _thin_line_image()
    result = apply_dilation(img, kernel_size=3)
    assert result.shape == img.shape
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: `ImportError` or `AttributeError` — `apply_dilation` not yet defined.

- [ ] **Step 3: Implement `apply_dilation()` in glyph_cleanup_sweep.py**

Add after the `from abc_xml_converter import convert_xml2abc` line:

```python
def apply_dilation(img_bgr: np.ndarray, kernel_size: int) -> np.ndarray:
    """Morphological dilation with an elliptical kernel, 1 iteration.

    Elliptical kernel chosen because sharp strokes are diagonal —
    rectangular kernels would square off curves.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
    )
    return cv2.dilate(img_bgr, kernel, iterations=1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py notation_pipeline/tests/test_glyph_cleanup_sweep.py
git commit -m "feat: implement apply_dilation() with tests"
```

---

## Task 3: `score_abc_accuracy()` — measure-level diff against gold ABC

**Files:**
- Modify: `notation_pipeline/glyph_cleanup_sweep.py`
- Modify: `notation_pipeline/tests/test_glyph_cleanup_sweep.py`

- [ ] **Step 1: Write the failing tests**

Append to `notation_pipeline/tests/test_glyph_cleanup_sweep.py`:

```python
from glyph_cleanup_sweep import score_abc_accuracy

GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "abc")


def test_score_abc_accuracy_self_match():
    gold = os.path.join(GOLD_DIR, "Arkansas Traveler-gold.abc")
    matched, total = score_abc_accuracy(gold, gold)
    assert matched == total
    assert total == 18


def test_score_abc_accuracy_self_match_soldiers_joy():
    gold = os.path.join(GOLD_DIR, "Soldier's Joy-gold.abc")
    matched, total = score_abc_accuracy(gold, gold)
    assert matched == total
    assert total == 17
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: `ImportError` — `score_abc_accuracy` not yet defined.

- [ ] **Step 3: Implement `score_abc_accuracy()`**

Add to `glyph_cleanup_sweep.py` after `apply_dilation()`:

```python
def score_abc_accuracy(gold_path: str, test_path: str) -> tuple[int, int]:
    """Diff test ABC against gold at the measure level.

    Returns (matched_measures, total_gold_measures).
    Uses compare_abc's normalization (strips chords, decorations, grace notes;
    normalizes durations to L:1/8) so cosmetic differences don't count as errors.
    """
    gold_text = open(gold_path).read()
    test_text = open(test_path).read()
    gold_measures = split_measures(extract_body(gold_text))
    test_measures = split_measures(extract_body(test_text))
    gold_norm = [normalize_for_compare(m) for m in gold_measures]
    test_norm = [normalize_for_compare(m) for m in test_measures]
    sm = difflib.SequenceMatcher(None, gold_norm, test_norm, autojunk=False)
    matched = sum(g2 - g1 for op, g1, g2, t1, t2 in sm.get_opcodes() if op == "equal")
    return matched, len(gold_measures)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py notation_pipeline/tests/test_glyph_cleanup_sweep.py
git commit -m "feat: implement score_abc_accuracy() with tests"
```

---

## Task 4: `normalize_tune()` and `mxl_to_abc()` — pipeline helpers

**Files:**
- Modify: `notation_pipeline/glyph_cleanup_sweep.py`
- Modify: `notation_pipeline/tests/test_glyph_cleanup_sweep.py`

- [ ] **Step 1: Write failing tests**

Append to `notation_pipeline/tests/test_glyph_cleanup_sweep.py`:

```python
import tempfile, shutil
from glyph_cleanup_sweep import normalize_tune, mxl_to_abc

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
BATCH_DIR = os.path.join(os.path.dirname(__file__), "..", "batch_output")


def test_normalize_tune_produces_png():
    src = os.path.join(IMAGES_DIR, "Arkansas Traveler.png")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.png")
        normalize_tune(src, out)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0


def test_mxl_to_abc_produces_abc():
    # Use Arkansas Traveler's existing clean.mxl from batch_output
    mxl_src = os.path.join(BATCH_DIR, "Arkansas Traveler", "clean.mxl")
    if not os.path.isfile(mxl_src):
        pytest.skip("batch_output/Arkansas Traveler/clean.mxl not present")
    with tempfile.TemporaryDirectory() as d:
        mxl_copy = os.path.join(d, "test.mxl")
        shutil.copy2(mxl_src, mxl_copy)
        abc_out = os.path.join(d, "test.abc")
        success = mxl_to_abc(mxl_copy, abc_out)
        assert success
        assert os.path.isfile(abc_out)
        assert open(abc_out).read().strip() != ""
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: `ImportError` — `normalize_tune`, `mxl_to_abc` not yet defined.

- [ ] **Step 3: Implement `normalize_tune()` and `mxl_to_abc()`**

Add to `glyph_cleanup_sweep.py` after `score_abc_accuracy()`:

```python
def normalize_tune(src_png: str, out_png: str, target: float = 18.0) -> None:
    """Run interline normalization with fixed-1.5× fallback.

    Mirrors the logic in batch_tune.sh Step 1.
    """
    try:
        _normalize_image(src_png, out_png, target)
    except RuntimeError:
        # Staff detection failed (e.g. Hey Polka, Forester's Hornpipe).
        # Fall back to fixed 1.5× resize with unsharp mask.
        img = cv2.imread(src_png)
        sharpened = apply_unsharp(img)
        h, w = img.shape[:2]
        resized = cv2.resize(
            sharpened, (int(w * 1.5), int(h * 1.5)),
            interpolation=cv2.INTER_LANCZOS4
        )
        cv2.imwrite(out_png, resized)


def mxl_to_abc(mxl_path: str, abc_path: str) -> bool:
    """Clean MXL and convert to ABC. Returns True on success.

    Modifies mxl_path in-place (clean_mxl overwrites), then writes ABC
    to abc_path via abc_xml_converter.
    """
    try:
        clean_mxl(mxl_path, mxl_path)
        abc_text = convert_xml2abc(file_to_convert=mxl_path, output_directory="")
        if not abc_text or not abc_text.strip():
            return False
        open(abc_path, "w").write(abc_text)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py notation_pipeline/tests/test_glyph_cleanup_sweep.py
git commit -m "feat: implement normalize_tune() and mxl_to_abc() helpers with tests"
```

---

## Task 5: `run_audiveris()` and `run_one()` — per-run pipeline

**Files:**
- Modify: `notation_pipeline/glyph_cleanup_sweep.py`

No unit tests for `run_audiveris()` (requires Audiveris process) or `run_one()` (integration — tested end-to-end in Task 6).

- [ ] **Step 1: Implement `run_audiveris()` and `run_one()`**

Add to `glyph_cleanup_sweep.py` after `mxl_to_abc()`:

```python
def run_audiveris(png_path: str, output_dir: str, timeout: int = 120) -> str | None:
    """Run Audiveris batch. Returns path to the .omr file or None on failure."""
    cmd = AUDIVERIS.split() + ["-batch", "-export", "-output", output_dir, png_path]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    for fname in os.listdir(output_dir):
        if fname.endswith(".omr"):
            return os.path.join(output_dir, fname)
    return None


def run_one(tune: str, label: str, kernel_size: int | None,
            timeout: int) -> dict:
    """Run the full pipeline for one (tune, variant) pair.

    Returns a result dict with keys:
      health_score, key_ok, time_ok, ashokan_tell, avg_grade (from score_omr)
      abc_matched, abc_total  (only if tune has a gold ABC and MXL succeeded)
      error  (string, only on failure)
    """
    src_png = os.path.join(IMAGES_DIR, f"{tune}.png")
    if not os.path.isfile(src_png):
        return {"error": f"source PNG not found: {src_png}"}

    gold_abc_path, _ = GOLD_ABCS.get(tune, (None, None))

    tmpdir = tempfile.mkdtemp(prefix="glyph_sweep_")
    try:
        # Step 1: normalize interline (with 1.5× fallback)
        norm_png = os.path.join(tmpdir, "normalized.png")
        normalize_tune(src_png, norm_png)

        # Step 2: apply dilation (no-op for baseline)
        if kernel_size is not None:
            img = cv2.imread(norm_png)
            cv2.imwrite(norm_png, apply_dilation(img, kernel_size))

        # Step 3: Audiveris
        omr_path = run_audiveris(norm_png, tmpdir, timeout=timeout)
        if omr_path is None:
            return {"error": "audiveris_no_omr"}

        # Step 4: health score
        result = score_omr(omr_path)
        if result is None:
            return {"error": "score_omr_failed"}

        # Step 5: note accuracy (gold tunes only)
        if gold_abc_path:
            mxl_candidates = [
                f for f in os.listdir(tmpdir)
                if f.endswith(".mxl")
            ]
            if mxl_candidates:
                mxl_path = os.path.join(tmpdir, mxl_candidates[0])
                abc_path = os.path.join(tmpdir, "test.abc")
                if mxl_to_abc(mxl_path, abc_path):
                    matched, total = score_abc_accuracy(gold_abc_path, abc_path)
                    result["abc_matched"] = matched
                    result["abc_total"] = total

        return result

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

- [ ] **Step 2: Quick syntax check**

```bash
.venv/bin/python3 -c "import notation_pipeline.glyph_cleanup_sweep" 2>/dev/null || \
.venv/bin/python3 notation_pipeline/glyph_cleanup_sweep.py 2>&1 | head -5
```

Expected: `skeleton ok` (main guard still prints this).

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py
git commit -m "feat: implement run_audiveris() and run_one() pipeline"
```

---

## Task 6: `main()` — argument parsing, sweep loop, result tables

**Files:**
- Modify: `notation_pipeline/glyph_cleanup_sweep.py`

- [ ] **Step 1: Replace the `if __name__ == "__main__"` block with `main()`**

Replace the entire `if __name__ == "__main__": print("skeleton ok")` block with:

```python
def _fmt_health(r: dict) -> str:
    if "error" in r:
        return f"ERR({r['error'][:8]})"
    k = "K" if r.get("key_ok") else "."
    t = "T" if r.get("time_ok") else "."
    a = "A" if r.get("ashokan_tell") else "."
    h = r.get("health_score", 0)
    return f"{k}{t}{a}  h={h:.0f}"


def _fmt_abc(r: dict) -> str:
    if "abc_matched" not in r:
        return "—"
    m, total = r["abc_matched"], r["abc_total"]
    pct = m / total * 100 if total else 0
    return f"{m}/{total} ({pct:.0f}%)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--operation", choices=["dilation"], default="dilation",
                        help="Glyph cleanup operation to sweep (default: dilation)")
    parser.add_argument("--tunes", default=",".join(DEFAULT_TUNES),
                        help="Comma-separated tune names")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Audiveris timeout per run in seconds (default: 120)")
    args = parser.parse_args()

    tunes = [t.strip() for t in args.tunes.split(",")]

    # Validate tune source PNGs exist
    valid_tunes = []
    for tune in tunes:
        png = os.path.join(IMAGES_DIR, f"{tune}.png")
        if not os.path.isfile(png):
            print(f"WARNING: skipping {tune!r} — no source PNG at {png}", file=sys.stderr)
        else:
            valid_tunes.append(tune)
    if not valid_tunes:
        print("ERROR: no valid tunes", file=sys.stderr)
        sys.exit(1)

    variants = DILATION_VARIANTS  # only dilation for now
    total = len(variants) * len(valid_tunes)
    print(f"Glyph cleanup sweep: --operation {args.operation}")
    print(f"  Tunes   : {valid_tunes}")
    print(f"  Variants: {[v for v, _ in variants]}")
    print(f"  Runs    : {total}")
    print()

    results: dict[tuple[str, str], dict] = {}

    run_num = 0
    for label, kernel_size in variants:
        for tune in valid_tunes:
            run_num += 1
            print(f"[{run_num:2d}/{total}]  {label:12s}  {tune}", flush=True)
            t0 = time.time()
            r = run_one(tune, label, kernel_size, args.timeout)
            elapsed = time.time() - t0
            results[(label, tune)] = r
            print(f"          → {_fmt_health(r)}  abc={_fmt_abc(r)}  ({elapsed:.0f}s)")

    # ── Table 1: Health scores ────────────────────────────────────────────────
    col_w = 20
    val_w = 12
    abbrevs = [t[:col_w - 1] for t in valid_tunes]

    print()
    print("=" * 70)
    print("HEALTH SCORES")
    print("=" * 70)
    header = f"{'variant':{val_w}}" + "".join(f"{a:{col_w}}" for a in abbrevs)
    print(header)
    print("-" * len(header))
    for label, _ in variants:
        row = f"{label:{val_w}}"
        for tune in valid_tunes:
            r = results.get((label, tune), {})
            row += f"{_fmt_health(r):{col_w}}"
        print(row)
    print()
    print("Legend: K=key_ok T=time_ok A=ashokan_tell h=health_score")

    # ── Table 2: Note accuracy (gold tunes only) ──────────────────────────────
    gold_tunes = [t for t in valid_tunes if t in GOLD_ABCS]
    if gold_tunes:
        abbrevs_g = [t[:col_w - 1] for t in gold_tunes]
        print()
        print("=" * 70)
        print("NOTE ACCURACY (gold tunes)")
        print("=" * 70)
        header_g = f"{'variant':{val_w}}" + "".join(f"{a:{col_w}}" for a in abbrevs_g)
        print(header_g)
        print("-" * len(header_g))
        for label, _ in variants:
            row = f"{label:{val_w}}"
            for tune in gold_tunes:
                r = results.get((label, tune), {})
                row += f"{_fmt_abc(r):{col_w}}"
            print(row)

    # ── Regression check ──────────────────────────────────────────────────────
    print()
    print("Regressions (passing at baseline that broke):")
    baseline_results = {tune: results.get(("baseline", tune), {}) for tune in valid_tunes}
    for tune in valid_tunes:
        b = baseline_results[tune]
        if "error" in b or not b.get("key_ok"):
            continue
        broke = [label for label, _ in variants if label != "baseline"
                 and not results.get((label, tune), {}).get("key_ok")]
        if broke:
            print(f"  {tune}: key broke at {broke}")
        else:
            print(f"  {tune}: no regressions")

    print()
    print("Key recovery (failing at baseline that improved):")
    for tune in valid_tunes:
        b = baseline_results[tune]
        if "error" in b or b.get("key_ok"):
            continue
        fixed = [label for label, _ in variants if label != "baseline"
                 and results.get((label, tune), {}).get("key_ok")]
        if fixed:
            print(f"  {tune}: key recovered at {fixed}")
        else:
            print(f"  {tune}: still failing at all variants")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify arg parsing and --help**

```bash
.venv/bin/python3 notation_pipeline/glyph_cleanup_sweep.py --help
```

Expected: usage message listing `--operation`, `--tunes`, `--timeout`.

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py
git commit -m "feat: implement main() with sweep loop and result tables"
```

---

## Task 7: End-to-end smoke test on one tune

Run the sweep on a single fast tune to verify the full pipeline works before the 40-run full sweep.

- [ ] **Step 1: Run baseline-only on Arkansas Traveler**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 notation_pipeline/glyph_cleanup_sweep.py \
    --operation dilation \
    --tunes "Arkansas Traveler"
```

Expected: health score `KT.  h=~108`, abc accuracy `17/18 (94%)` or close. The pipeline should complete in ~2 min for 4 variants × 1 tune.

- [ ] **Step 2: Verify all tests still pass**

```bash
.venv/bin/python3 -m pytest notation_pipeline/tests/test_glyph_cleanup_sweep.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add notation_pipeline/glyph_cleanup_sweep.py notation_pipeline/tests/test_glyph_cleanup_sweep.py
git commit -m "feat: glyph_cleanup_sweep.py complete — smoke tested on Arkansas Traveler"
```

---

## Task 8: Full sweep run

- [ ] **Step 1: Run the full 10-tune, 4-variant sweep**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 notation_pipeline/glyph_cleanup_sweep.py \
    --operation dilation \
    --timeout 150 \
    2>&1 | tee notation_pipeline/dilation_sweep_results.txt
```

Expected: ~40 Audiveris runs, ~60–80 min total. Output saved to `dilation_sweep_results.txt`.

- [ ] **Step 2: Verify baseline note accuracy matches prior known values**

From the output, check the baseline row of the note accuracy table:
- Arkansas Traveler: should be `17/18 (94%)`
- Soldier's Joy: should be `12/17 (71%)`
- Mississippi Sawyer: should be `14/17 (82%)`

If any of these differ by more than 1 measure, the pipeline has a bug — re-examine `mxl_to_abc()` or `score_abc_accuracy()`.

- [ ] **Step 3: Record results and update next_steps.md**

Add a new "Experiment E — Glyph Cleanup (Dilation)" section to `next_steps.md` with the actual results table. Mark as DONE if dilation showed no improvement, or as "promising — integrate kernel N" if it did.

- [ ] **Step 4: Commit results**

```bash
git add notation_pipeline/dilation_sweep_results.txt notation_pipeline/next_steps.md
git commit -m "data: glyph dilation sweep results"
```
