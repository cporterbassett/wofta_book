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


def apply_dilation(img_bgr: np.ndarray, kernel_size: int) -> np.ndarray:
    """Thicken dark music notation strokes via morphological erosion.

    Erosion shrinks the white background, expanding dark regions. Elliptical
    kernel chosen because sharp strokes are diagonal — rectangular kernels
    would square off curves.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
    )
    return cv2.erode(img_bgr, kernel, iterations=1)


def score_abc_accuracy(gold_path: str, test_path: str) -> tuple[int, int]:
    """Diff test ABC against gold at the measure level.

    Returns (matched_measures, total_gold_measures).
    Uses compare_abc's normalization (strips chords, decorations, grace notes;
    normalizes durations to L:1/8) so cosmetic differences don't count as errors.
    """
    with open(gold_path) as f:
        gold_text = f.read()
    with open(test_path) as f:
        test_text = f.read()
    gold_measures = split_measures(extract_body(gold_text))
    test_measures = split_measures(extract_body(test_text))
    gold_norm = [normalize_for_compare(m) for m in gold_measures]
    test_norm = [normalize_for_compare(m) for m in test_measures]
    sm = difflib.SequenceMatcher(None, gold_norm, test_norm, autojunk=False)
    matched = sum(g2 - g1 for op, g1, g2, t1, t2 in sm.get_opcodes() if op == "equal")
    return matched, len(gold_measures)


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
        if img is None:
            raise FileNotFoundError(f"Cannot read source image: {src_png}")
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
        # Temporarily clear sys.argv to prevent convert_xml2abc from parsing pytest flags
        original_argv = sys.argv
        sys.argv = [sys.argv[0]]
        try:
            abc_text = convert_xml2abc(file_to_convert=mxl_path, output_directory="")
        finally:
            sys.argv = original_argv
        if not abc_text or not abc_text.strip():
            return False
        with open(abc_path, "w") as f:
            f.write(abc_text)
        return True
    except Exception:
        return False


# Gold ABCs: tune name → (gold_abc_path, expected_measure_count)
GOLD_ABCS = {
    "Arkansas Traveler":      (os.path.join(ABC_DIR, "Arkansas Traveler-gold.abc"),      18),
    "Soldier's Joy":          (os.path.join(ABC_DIR, "Soldier's Joy-gold.abc"),          18),
    "Mississippi Sawyer":     (os.path.join(ABC_DIR, "Mississippi Sawyer-gold.abc"),     18),
    "Angeline the Baker":     (os.path.join(ABC_DIR, "Angeline the Baker-gold.abc"),     19),
    "Billy in the Lowground": (os.path.join(ABC_DIR, "Billy in the Lowground-gold.abc"), 17),
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
