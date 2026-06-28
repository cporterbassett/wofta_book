# Sand and Sawdust 2026

Working list (separate from the full corpus). Source: photo of the printed set list
(`/home/porter/Downloads/PXL_20260623_213340768.MP.jpg`), captured 2026-06-23.

Status legend: ✅ verified · 🟡 has OMR draft (verify-eligible) · 🔴 not in corpus (needs source)

Note: the printed sheet repeats Me and My Fiddle, Cumberland Gap, and Sugar Moon; listed once each here.

## ✅ Already verified (28)
- Arkansas Traveler — D
- Blackberry Blossom — G
- Year of Jubilo — D
- Flop Eared Mule — D/A
- Manitoba Golden Boy — D *(paired w/ Sleeping Giant)*
- Sleeping Giant Two-Step — D
- Big Scioty — G
- Magpie — G
- Dill Pickles Rag — G
- Golden Slippers — G
- Red Wing — G
- Jefferson and Liberty — am
- Red Haired Boy — A *(A-tunes box)*
- Salt Spring — A *(A-tunes box)*
- Red Bird — A *(A-tunes box)*
- Roscoe — G *(verified 2026-06-23, commit f1bb6c2a)*
- Tombigbee Waltz — G *(paired w/ Guntree Canoe, which is missing)*
- Down in Little Egypt — C
- Red Apple Rag — G
- Snake River Reel — D
- Golden Ticket, The — G
- Me and My Fiddle — G/D
- Logger - Pays de Haut, The — D *("The logger")*
- Whistling Rufus — G *("Whistlin' Rufus")*
- Camp Meeting on the Fourth of July — D
- Road House Ramble — G *("Roadhouse Ramble")* *(verified 2026-06-24, commit 10cb3491)*
- Bill Cheatham — A *(A-tunes box)*
- Granny Will Your Dog Bite — A *(A-tunes box)* *(verified 2026-06-24, commit 26d268db)*

## 🟡 Has OMR draft — verify-eligible now (1)
- [ ] Pat(T)'s Country — D

## 🟡 Sourced from WOTFAhandouts_April2025.pdf — draft created, verify-eligible (3)
Source: `/home/porter/Documents/banjo/WOFTA/WOTFAhandouts_April2025.pdf` (no text layer; 56 pp; scanned 2026-06-23).
Prepped 2026-06-23: PDF page → 200dpi gray → trim → `source_images/<Tune>.png` → `batch_tune.sh` → `-draft.abc`.
These are song lead sheets (lyrics + guitar-chord boxes), so OMR is rough — expect heavier Phase-2 cleanup.
- [ ] Kansas City Kitty — C *(PDF pp. 17–18 stacked; OMR split into movements, only mvt1 captured — re-OMR likely)*
- [ ] Roll the Old Chariot Along — dm *(PDF p. 32; OMR read Key=F/4-4, ~18 bars; handwritten verses below staff ignored)*
- [ ] Sugar Moon — C *(PDF p. 46; OMR came out keyless/meterless — candidate exists, resume at stage 3)*

## 🟡 Rose in the Mountain / Summertime — now sourced, see notation_pipeline/abc/ drafts
(no longer in the unsourced list below; Rose in the Mountain has a draft+verified ABC, Summertime is verified)

## 🔴 Reference chord/lyric sources downloaded 2026-06-24 — no melody-ABC yet (13)
Raw downloaded pages live in `notation_pipeline/reference_sources/<Tune>.html|.pdf`, but the book
(`Sand and Sawdust 2026.pdf`) embeds *cleaned* content only, with nav/ads/boilerplate stripped:
- `<Tune> - lyrics chords.txt` (Courier, chords aligned over lyrics) for most — Faded Love, Back
  Home Again in Indiana, Gum Tree Canoe, Roll in My Sweet Baby's Arms, Drunken Sailor, Along the
  Navajo Trail, Catfish John, Uncle Pen
- `Old Aunt Jenny.abc` — real ABC notation found on tunearch.org (Traditional Tune Archive),
  engraved like the verified tunes; no chords in that source (instrumental reel)
- `Cumberland Gap (lyrics version).abc` — 2026-06-24 Porter supplied a new scan
  (`source_images/Cumberland Gap.png`, key C, "Kentucky arr. Trinka", w/ 3 extra verses) of a
  DIFFERENT "Cumberland Gap" than the famous bluegrass fiddle tune — this one has real notation
  + chords + lyrics. Audiveris OMR mis-read several pitches/rhythms (cross-checked against
  pixel-measured notehead positions and the raw clean.mxl, which was far more reliable than the
  lossy mxl→abc draft conversion); hand-corrected from that MusicXML data, not just the OMR draft.
- `Red Red Robin - lyrics chords.txt` — 2026-06-24 Porter supplied a cleaner scan
  (`source_images/Red Red Robin.png`, key C already, chords by Misc Traditional) replacing the
  earlier PDF-page-3 extraction; transcribed by hand, no nav/ad cruft to strip this time
No OMR possible — these are vocal songs, melody must come from ear/transcription. Chords are
already transposed to target key (2026-06-24) in the cleaned `.txt`/`.abc` files below; the raw
`.html`/`.pdf` downloads are left in their original source key for reference. Next step: build
ABC drafts (melody + chords + lyrics) by hand/transcription.
- [ ] Faded Love — D *(transposed from source G — `Faded Love - lyrics chords.txt`)*
- [ ] Back Home Again in Indiana — G *(already in G — `Back Home Again in Indiana - lyrics chords.txt`)*
- [ ] Old Aunt Jenny / Nightcap On — G *(already in G, real ABC notation, instrumental — `Old Aunt Jenny.abc`)*
- [ ] Guntree Canoe — G *(real title is "Gum Tree Canoe"; transposed from source D — `Gum Tree Canoe - lyrics chords.txt`; paired w/ Tombigbee Waltz)*
- [ ] Red Red Robin — C *(already in C — `Red Red Robin - lyrics chords.txt`)*
- [ ] Roll in My Sweet Baby's Arms — G *(already in G, capo 2 — `Roll in My Sweet Babys Arms - lyrics chords.txt`)*
- [ ] Drunken Sailor — em *(transposed from source Dm — `Drunken Sailor - lyrics chords.txt`)*
- [ ] Along the Navaho Trail — D *(transposed from source G — `Along the Navajo Trail - lyrics chords.txt`)*
- [ ] Catfish John — E *(transposed from source D — `Catfish John - lyrics chords.txt`)*
- [ ] Cumberland Gap — C *(different song than the famous bluegrass tune; real notation+chords+lyrics — `Cumberland Gap (lyrics version).abc`)*
- [ ] America the Beautiful — G *(already in G — `America the Beautiful Alt.pdf`)*
- [ ] You're A Grand Old Flag / Yankee Doodle Dandy — C *(transposed from source G — `Grand Old Flag Yankee Doodle - chords.txt`)*
- [ ] Uncle Pen — A *(already in A, no capo — `Uncle Pen - lyrics chords.txt`)*
