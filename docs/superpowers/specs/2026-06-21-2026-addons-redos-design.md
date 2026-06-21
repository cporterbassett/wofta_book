# 2026 Add-ons & Redos — Integration Design

**Date:** 2026-06-21
**Source:** `/home/porter/Documents/banjo/WOFTA/2026/2026 add-ons & redos copy/` (58 PDFs)

## Goal

Incorporate 58 new tune PDFs into the WOFTA corpus, ultimately as verified ABC
engravings (full OMR → GUI cleanup → verified pipeline). The PDFs are
heterogeneous: some are clean Finale/MuseScore engravings, some are handwritten/
marked-up raw scans.

## Categorization (verified by name-match against the corpus)

- **11 already-verified** (a `-verified.abc` already exists): Chinquapin, Clinch
  Mountain Backstep, Crooked Stovepipe, Florida Blues, Frosty Morning, Magpie,
  Old Joe Clark, Porter's Reel, Sally Ann, Starry Night for a Ramble, Wind That
  Shakes the Barley.
- **23 replace** (a `source_images/*.png` scan exists, no verified ABC): Acorn
  Hill Breakdown, Clearwater Stomp, Cricket On a Hearth, Far From Home, Fisher's
  Hornpipe, Gypsy Waltz, Laura Susan, Lost Indian, MacArthur Road, Me and My
  Fiddle, Miss McCloud's Reel, Monkey in the Dogcart, Moonlight, Morrison's Jig,
  None of Your Business, Red River Cart Polka, Road House Ramble, Ross's Reel #4,
  Salmon Tails Up the Water, Stone's Rag, Waverly Two-Step, Woodchopper's Reel,
  Red Apple Rag.
- **24 new** (no existing version): Black Jack Grove, Blueberry Jig, Camp Meeting
  on the Fourth of July, Cock o' the North, Crested Hens, Dogs in the Dishes,
  Ebenezer, Far Away, Harvest Home, Haste to the Wedding, Hector the Hero,
  Lamplighter's Hornpipe, Miller's Reel, Romeo's Last Chance, Roscoe, Silver
  Spear, Snake River Reel, South Missouri, Squirrel Hunters, Texas Gales, Cuckoo's
  Nest (The), Golden Ticket (The), Mackadavie (The), Whistling Rufus.

(Note: "Red Apple Rag" has neither a scan nor verified ABC in the corpus snapshot
but is treated as add/replace; confirm during prep. It is listed under replace
above pending check — if no scan exists it is simply a new tune.)

## Deliverables (in order; pause for review after each)

### 1. Verified diff report
`notation_pipeline/reports/2026_verified_diff.pdf` + written notes.
Per verified tune: left = current `-verified.abc` rendered via `render_abc.sh`
(same path `make_pdf.py` uses); right = new PDF rasterized. One tune per page.
Written measure-level notes on musical differences (notes, measures, chords,
repeats, structure). **No corpus files touched.**

### 2. Replace diff report
`notation_pipeline/reports/2026_replace_diff.pdf` + written notes.
Same format; left = existing `source_images/<Tune>.png` scan. **No files touched.**

### 3. Prep + draft the 24 new tunes
- PDF → cleaned PNG (light cleanup for clean engravings, full `raw_image_prep.md`
  process for scans) → `source_images/<Canonical>.png`.
- Canonical naming: title-case, real apostrophes, strip key/version suffixes,
  leading "The" → ", The". Name list confirmed with user before writing files.
- Phase-1 batch OMR → `abc/<Tune>-draft.abc`, queued for Phase-2 cleanup.

## Out of scope this session

- Actually swapping/redoing the 11 verified and 23 replace tunes — those wait on
  the user's per-tune decisions after reading the diff reports.
- Phase-2 GUI cleanup / promotion to verified — the user's manual one-tune loop.
