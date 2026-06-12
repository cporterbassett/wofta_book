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
