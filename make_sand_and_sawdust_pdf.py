#!/usr/bin/env python3
"""Build "Sand and Sawdust 2026.pdf" — the working set list in printed-sheet
order (not alphabetical). Repeated tunes collapse to first occurrence. Engraved
tunes are shown plain (no sepia). Each tune uses the best material on hand:
verified/candidate ABC, a real source PDF/ODT, or a clean chords/lyrics text page.

Run via: .venv/bin/python3 make_sand_and_sawdust_pdf.py"""
import os
import sys

import make_pdf as mp

HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
REF_DIR = os.path.join(HERE, "notation_pipeline", "reference_sources")
ODT_DIR = HERE
IMG_DIR = os.path.join(HERE, "source_images")

# (display name, kind, path, options)
#   kind: abc | png | pdf | odt | text | text_2col
#   options: {} | {"pages": [0-based ints]} | {"crop": (l,b,r,t)}
#            | {"key_note": str, "font_size": n, "line_h": n}
ENTRIES = [
    ("Arkansas Traveler", "abc", os.path.join(ABC_DIR, "Arkansas Traveler-verified.abc"), {}),
    ("Blackberry Blossom", "abc", os.path.join(ABC_DIR, "Blackberry Blossom-verified.abc"), {}),
    ("Year of Jubilo", "abc", os.path.join(ABC_DIR, "Year of Jubilo-verified.abc"), {}),
    ("Faded Love", "pdf", os.path.join(REF_DIR, "Faded Love D & A.pdf"), {}),
    ("Flop Eared Mule", "abc", os.path.join(ABC_DIR, "Flop Eared Mule-verified.abc"), {}),
    ("Back Home Again in Indiana", "pdf", os.path.join(REF_DIR, "Back Home Again in Indiana.pdf"), {}),
    ("Manitoba Golden Boy", "abc", os.path.join(ABC_DIR, "Manitoba Golden Boy-verified.abc"), {}),
    ("Sleeping Giant Two-Step", "abc", os.path.join(ABC_DIR, "Sleeping Giant Two-Step-verified.abc"), {}),
    ("Old Aunt Jenny (Nightcap On)", "abc", os.path.join(ABC_DIR, "Old Aunt Jenny with Her Nightcap on-verified.abc"), {}),
    ("Gum Tree Canoe", "odt", os.path.join(REF_DIR, "Gumtree Canoe_G.odt"), {"pages": [0]}),
    ("Tombigbee Waltz", "abc", os.path.join(ABC_DIR, "Tombigbee Waltz-verified.abc"), {}),
    ("Red Red Robin", "odt", os.path.join(ODT_DIR, "red red robin.odt"), {}),
    ("Roll in My Sweet Baby's Arms", "text_2col", os.path.join(REF_DIR, "Roll in My Sweet Babys Arms - lyrics chords.txt"), {"key_note": "Key: G"}),
    ("Down in Little Egypt", "abc", os.path.join(ABC_DIR, "Down in Little Egypt-verified.abc"), {}),
    ("Rose in the Mountain", "abc", os.path.join(ABC_DIR, "Rose in the Mountain-verified.abc"), {}),
    ("Rose in the Mountain", "pdf", os.path.join(REF_DIR, "Rose in the Mountain.pdf"), {}),
    ("Sugar Moon", "pdf", os.path.join(REF_DIR, "Sugar Moon.pdf"), {}),
    ("Drunken Sailor", "odt", os.path.join(ODT_DIR, "drunken sailor.odt"), {}),
    ("Roll the Old Chariot Along", "pdf", os.path.join(REF_DIR, "Roll the Old Chariot Along.pdf"), {}),
    ("Red Apple Rag", "abc", os.path.join(ABC_DIR, "Red Apple Rag-verified.abc"), {}),
    ("Snake River Reel", "abc", os.path.join(ABC_DIR, "Snake River Reel-verified.abc"), {}),
    ("Kansas City Kitty", "png", os.path.join(IMG_DIR, "Kansas City Kitty-p1.png"), {}),
    ("Kansas City Kitty", "png", os.path.join(IMG_DIR, "Kansas City Kitty-p2.png"), {}),
    ("Golden Ticket, The", "abc", os.path.join(ABC_DIR, "Golden Ticket, The-verified.abc"), {}),
    ("Me and My Fiddle", "abc", os.path.join(ABC_DIR, "Me and My Fiddle-verified.abc"), {}),
    ("Big Scioty", "abc", os.path.join(ABC_DIR, "Big Scioty-verified.abc"), {}),
    ("Magpie", "abc", os.path.join(ABC_DIR, "Magpie-verified.abc"), {}),
    ("Dill Pickles Rag", "abc", os.path.join(ABC_DIR, "Dill Pickles Rag-verified.abc"), {}),
    ("Golden Slippers", "abc", os.path.join(ABC_DIR, "Golden Slippers-verified.abc"), {}),
    ("Red Wing", "abc", os.path.join(ABC_DIR, "Red Wing-verified.abc"), {}),
    ("Along the Navaho Trail", "pdf", os.path.join(REF_DIR, "Along the Navajo Trail chart.pdf"), {}),
    ("Catfish John", "pdf", os.path.join(REF_DIR, "Catfish John chart.pdf"), {}),
    ("Logger - Pays de Haut, The", "abc", os.path.join(ABC_DIR, "Logger - Pays de Haut, The-verified.abc"), {}),
    ("Roscoe", "abc", os.path.join(ABC_DIR, "Roscoe-verified.abc"), {}),
    ("Summertime", "abc", os.path.join(ABC_DIR, "Summertime-verified.abc"), {}),
    ("Whistling Rufus", "abc", os.path.join(ABC_DIR, "Whistling Rufus-verified.abc"), {}),
    ("Cumberland Gap", "abc", os.path.join(REF_DIR, "Cumberland Gap (lyrics version).abc"), {}),
    ("Camp Meeting on the Fourth of July", "abc", os.path.join(ABC_DIR, "Camp Meeting on the Fourth of July-verified.abc"), {}),
    ("America the Beautiful", "pdf", os.path.join(REF_DIR, "America the Beautiful.pdf"), {}),
    ("You're A Grand Old Flag / Yankee Doodle Dandy", "odt", os.path.join(ODT_DIR, "GrandOldFlagMedley.odt"), {}),
    ("Jefferson and Liberty", "abc", os.path.join(ABC_DIR, "Jefferson and Liberty-verified.abc"), {}),
    ("Pat(T)'s Country", "abc", os.path.join(ABC_DIR, "Pat(T)'s Country-verified.abc"), {}),
    ("Road House Ramble", "abc", os.path.join(ABC_DIR, "Road House Ramble-verified.abc"), {}),
    # --- boxed "A tunes?" on the sheet ---
    ("Uncle Pen", "odt", os.path.join(REF_DIR, "Uncle Pen A.odt"), {}),
    ("Uncle Pen", "odt", os.path.join(ODT_DIR, "Uncle Pen.odt"), {}),
    ("Red Haired Boy", "abc", os.path.join(ABC_DIR, "Red Haired Boy-verified.abc"), {}),
    ("Salt Spring", "abc", os.path.join(ABC_DIR, "Salt Spring-verified.abc"), {}),
    ("Bill Cheatham", "abc", os.path.join(ABC_DIR, "Bill Cheatham-verified.abc"), {}),
    ("Red Bird", "abc", os.path.join(ABC_DIR, "Red Bird-verified.abc"), {}),
    ("Granny Will Your Dog Bite", "abc", os.path.join(ABC_DIR, "Granny Will Your Dog Bite-verified.abc"), {}),
]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Sand and Sawdust 2026.pdf")
    mp.build_book(ENTRIES, output=out, sepia=False, toc_alphabetical=False,
                  toc_title="2026 Sand & Sawdust")
    print("Done.")
