#!/usr/bin/env bash
# Run Phase-1 OMR (batch_tune.sh) over the 44 Deliverable-2+3 tunes.
# Logs one line per tune to run_omr_44.log; full per-tune output appended too.
set -uo pipefail
cd /home/porter/Documents/banjo/WOFTA/tune_images
source .venv/bin/activate

LOG="notation_pipeline/reports/2026_diff_work/run_omr_44.log"
: > "$LOG"

# 20 replace (re-OMR on swapped new scans) + 24 new canonical names
tunes=(
  "Acorn Hill Breakdown" "Clearwater Stomp" "Cricket On a Hearth" "Far From Home"
  "Fisher's Hornpipe" "Gypsy Waltz" "Laura Susan" "Lost Indian" "MacArthur Road"
  "Miss McCloud's Reel" "Monkey in the Dogcart" "Moonlight" "Morrison's Jig"
  "None of Your Business" "Red Apple Rag" "Red River Cart Polka"
  "Salmon Tails Up the Water" "Stone's Rag" "Waverly Two-Step" "Woodchopper's Reel"
  "Black Jack Grove" "Blueberry Jig" "Camp Meeting on the Fourth of July"
  "Cock o' the North" "Crested Hens" "Dogs in the Dishes" "Ebenezer" "Far Away"
  "Harvest Home" "Haste to the Wedding" "Hector the Hero" "Lamplighter's Hornpipe"
  "Miller's Reel" "Romeo's Last Chance" "Roscoe" "Silver Spear" "Snake River Reel"
  "South Missouri" "Squirrel Hunters" "Golden Ticket, The" "Texas Gales"
  "Cuckoo's Nest, The" "Mackadavie, The" "Whistling Rufus"
)

total=${#tunes[@]}
i=0; ok=0; fail=0
echo "[$(date +%H:%M:%S)] starting OMR on $total tunes" | tee -a "$LOG"
for t in "${tunes[@]}"; do
  i=$((i+1))
  start=$(date +%s)
  if bash notation_pipeline/bin/batch_tune.sh "$t" >> "$LOG" 2>&1; then
    res=OK; ok=$((ok+1))
  else
    res=FAIL; fail=$((fail+1))
  fi
  dur=$(( $(date +%s) - start ))
  printf "[%s] %2d/%2d  %-7s (%3ds)  %s\n" "$(date +%H:%M:%S)" "$i" "$total" "$res" "$dur" "$t" | tee -a "$LOG"
done
echo "[$(date +%H:%M:%S)] DONE  ok=$ok fail=$fail / $total" | tee -a "$LOG"
