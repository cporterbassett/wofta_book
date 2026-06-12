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
