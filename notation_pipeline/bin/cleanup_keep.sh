#!/usr/bin/env bash
# Phase 2 cleanup over the CONFIRMED KEEP subset only.
#
# Porter is still waiting on the final keep/add list, so we are NOT cleaning the
# whole corpus yet — only tunes already known to be in the final book. This
# wrapper feeds that subset to cleanup_loop.sh, ordered WORST-FIRST by
# health_score (hardest GUI work front-loaded).
#
# Usage:
#   bash cleanup_keep.sh            # run the GUI loop over the keep subset
#   bash cleanup_keep.sh --list     # just list the queue + done/pending status
#
# Edit KEEP below as the keep list firms up.
#
# Name notes:
#   - "Temperance Reel"  == Teetotaller's Reel (same tune, book titles it Temperance).
#   - "Liberty"          is the standalone tune (NOT "Jefferson and Liberty").
#   - "Red Haired Boy"   OMR is truncated (9 of ~16 measures) — add missing bars in GUI.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Worst-first by health_score (low = more GUI effort).
KEEP=(
  "Needle Case"                                          # 68  missed key sig — real fix
  "Cherokee Shuffle"                                     # 78
  "Red Haired Boy"                                       # 88  TRUNCATED 9/~16 bars
  "Temperance Reel"                                      # 89  (Teetotaller's Reel)
  "Girl I Left Behind Me, The"                           # 107
  "Old Joe Clark"                                        # 108
  "Golden Slippers"                                      # 108
  "Nail That Catfish to the Tree"                        # 108
  "Angeline the Baker"                                   # 108
  "Shove That Pig's Foot a Little Further in the Fire"   # 108
  "Seneca Square Dance"                                  # 108
  "Maggots in the Sheephide"                             # 108
  "Red Wing"                                             # 108
  "Over the Waterfall"                                   # 108
  "Chinese Breakdown"                                    # 108
  "Soldier's Joy"                                        # 108
  "Eighth of January"                                    # 108
  "St. Anne's Reel"                                      # 108
  "Magpie"                                               # 108
  "Mississippi Sawyer"                                   # 108
  "Year of Jubilo"                                       # 108
  "Sadie at the Back Door"                               # 108
  "Arkansas Traveler"                                    # 108
  "Kesh Jig"                                             # 108
  "Porter's Reel"                                        # 108
  "Liberty"                                              # 108
  "Whiskey Before Breakfast"                             # 108
  "Hey Polka"                                            # 108
  "June Apple"                                           # 108
  "Salt Creek"                                           # 108
  "Swinging on a Gate"                                   # 109

  # --- Added 2026-06-15 (second keep batch) ---
  "Big Scioty"
  "Ashokan Farewell"
  "Dill Pickles Rag"
  "Drowsy Maggie"
  "Frosty Morning"
  "Galopede"
  "Gil's Schottische"
  "Give the Fiddler a Dram"
  "Grasshopper Sittin' on a Sweet Potato Vine"
  "Hollow Poplar"
  "Ice on the Road"
  "Jimmy Allen"
  "Kerry Mills' Barn Dance"                              # NO clean.omr yet — needs OMR before it can be verified
  "Mairi's Wedding"
  "Manitoba Golden Boy"
  "March of St. Timothy"
  "Mason's Apron"
  "Peacock Rag"
  "Petronella"
  "Pig Ankle Rag"
  "Pink Eye Lament"
  "Possum Up a Gum Stump"
  "Red Bird"
  "Rights of Man"
  "Road to Lisdoonvarna, The"
  "Salt Spring"
  "Spotted Pony"
  "Swallowtail Jig"
  "Wind That Shakes the Barley"
)

exec bash "${HERE}/cleanup_loop.sh" "$@" "${KEEP[@]}"
