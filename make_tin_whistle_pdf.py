#!/usr/bin/env python3
"""Build "Tin Whistle.pdf" — tin whistle repertoire, engraved (plain, no sepia).
Run via: .venv/bin/python3 make_tin_whistle_pdf.py"""
import os
import sys

import make_pdf as mp

HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
IMG_DIR = os.path.join(HERE, "source_images")

# (display name, kind, path, options)
ENTRIES = [
    ("Red Haired Boy", "abc", os.path.join(ABC_DIR, "Red Haired Boy-verified.abc"), {}),
    ("Far Away", "png", os.path.join(IMG_DIR, "Far Away.png"), {}),
    ("Little Donald in the Pigpen", "png", os.path.join(IMG_DIR, "Little Donald in the Pigpen.png"), {}),
    ("Eighth of January", "abc", os.path.join(ABC_DIR, "Eighth of January-verified.abc"), {}),
    ("Hey Polka", "abc", os.path.join(ABC_DIR, "Hey Polka-verified.abc"), {}),
    ("Arkansas Traveler", "abc", os.path.join(ABC_DIR, "Arkansas Traveler-verified.abc"), {}),
    ("Chinese Breakdown", "abc", os.path.join(ABC_DIR, "Chinese Breakdown-verified.abc"), {}),
    ("Angeline the Baker", "abc", os.path.join(ABC_DIR, "Angeline the Baker-verified.abc"), {}),
    ("Whiskey Before Breakfast", "abc", os.path.join(ABC_DIR, "Whiskey Before Breakfast-verified.abc"), {}),
    ("Liberty", "abc", os.path.join(ABC_DIR, "Liberty-verified.abc"), {}),
    ("The Boys of Blue Hill", "abc", os.path.join(ABC_DIR, "Boys of Blue Hill, The-verified.abc"), {}),
    ("Drowsy Maggie", "abc", os.path.join(ABC_DIR, "Drowsy Maggie-verified.abc"), {}),
    ("Kesh Jig", "abc", os.path.join(ABC_DIR, "Kesh Jig-verified.abc"), {}),
    ("Road to Lisdoonvarna", "abc", os.path.join(ABC_DIR, "Road to Lisdoonvarna, The-verified.abc"), {}),
    ("Red Wing", "abc", os.path.join(ABC_DIR, "Red Wing-verified.abc"), {}),
]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Tin Whistle.pdf")
    mp.build_book(ENTRIES, output=out, sepia=False, toc_alphabetical=False)
    print("Done.")
