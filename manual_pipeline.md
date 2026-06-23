# Manual pipeline (no Claude)

Copy-pastable commands for running the `image → Audiveris → verified ABC`
workflow and building the output PDFs entirely by hand. Run everything from the
repo root: `cd ~/Documents/banjo/WOFTA/tune_images`.

---

## Verify one tune

Opens Audiveris on the cleaned OMR (maximized) + the raw scan in Firefox,
exports to a candidate ABC, fixes the title, then opens a **live** side-by-side
compare (source vs. engraved) plus EasyABC. Saving in EasyABC refreshes the
compare automatically — no need to close it. On close it asks whether to promote
+ commit.

**Next tune, no name needed** — auto-picks the worst-first tune that has a
`clean.omr` and isn't verified yet:

```bash
bash notation_pipeline/bin/verify_tune.sh
```

**A specific tune** — pass its name:

```bash
bash notation_pipeline/bin/verify_tune.sh "Soldier's Joy"
```

What you do while it runs:

1. **Audiveris** opens — correct the OMR, then **close the window**.
2. The script exports + titles the candidate, then opens **EasyABC** and a
   **compare** tab in Firefox.
3. In EasyABC: fix notes, add chords. **Save** to see the compare update.
   **Close** EasyABC when done.
4. Answer **`y`** at `Promote & commit?` to publish it into the book, or anything
   else to leave it as a candidate.

> If a tune has no cleaned OMR yet the script will tell you to run phase-1 first
> (see below).

### Movement split

Sometimes Audiveris splits a score into movements and the export step stops with
`⚠ MOVEMENT SPLIT`, listing one ABC per movement (e.g.
`abc/<Tune>-clean.mvt1.abc`, `…mvt2.abc`). Inspect those, then re-run picking the
movement — this **skips the Audiveris re-open** (your OMR edits are already saved):

```bash
bash notation_pipeline/bin/verify_tune.sh "Tune Name" --mvt 1
```

mvt1 is usually the main tune. If the movements are actually two halves of one
tune (e.g. A part / B part), pick `--mvt 1`, then in EasyABC paste the other
half's notes from its `…-clean.mvt2.abc` file.

### Skip a tune

Blocked on a tune (open questions, etc.)? Park it — auto-pick steps over parked
tunes on every future no-name run until you un-park it.

```bash
bash notation_pipeline/bin/verify_tune.sh --skip            # park the current auto-pick, run the next
bash notation_pipeline/bin/verify_tune.sh --skip "Tune Name"  # park a named tune, run the next
```

Parked tunes are listed one-per-line in `notation_pipeline/verify_skip.txt`.

- **Park without running the next** — just append to the file:
  ```bash
  echo "Drunken Cat" >> notation_pipeline/verify_skip.txt
  ```
- **Un-park** (ready to tackle it again) — remove its line:
  ```bash
  vi notation_pipeline/verify_skip.txt
  ```

---

## Find the next tune to verify

Tunes that have a cleaned OMR but are **not yet verified**, worst-first
(hardest GUI work first):

```bash
tail -n +2 notation_pipeline/health_scores.tsv | cut -f1 \
  | grep -vxFf <(ls notation_pipeline/abc/*-verified.abc 2>/dev/null \
      | sed 's|.*/abc/||; s|-verified\.abc$||') \
  | head -20
```

(`health_scores.tsv` is already sorted worst-first; `grep -v` drops the tunes
that already have a `-verified.abc`, keeping that order.)

---

## Phase 1 — create the cleaned OMR (only if missing)

If `verify_tune.sh` says there's no `clean.omr`, run the OMR step first
(preprocess → Audiveris → cleaned OMR + draft ABC), then verify:

```bash
bash notation_pipeline/bin/batch_tune.sh "Tune Name"
bash notation_pipeline/bin/verify_tune.sh "Tune Name"
```

---

## Build both PDFs and open them in Firefox

`make_pdf.sh` builds the full book (engraved preferred, sepia, with a clickable
table of contents) **and** the scan-vs-engraved comparison PDF, then opens both
in Firefox:

```bash
./make_pdf.sh
```

Outputs:

- `WOFTA_tunes.pdf` — the full book
- `WOFTA_tunes_comparison.pdf` — every engraved tune, scan left / engraving right

Write them somewhere else by passing a path (the comparison name is derived
from it):

```bash
./make_pdf.sh /tmp/WOFTA_tunes.pdf      # also writes /tmp/WOFTA_tunes_comparison.pdf
```

---

## Optional — refresh the HTML report

A single scrollable page of every finalized tune (scan above its engraving):

```bash
bash notation_pipeline/bin/build_report.sh
firefox notation_pipeline/reports/finalized_report.html &
```
