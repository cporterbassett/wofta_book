# Notation Pipeline — Attempt Log

**Date:** 2026-06-10  
**Goal:** Replace 277 messy scanned/xeroxed PNG images with clean programmatically-rendered notation.  
**Conclusion:** Abandoned. See bottom for why and what to do instead.

---

## The Idea

Music notation is fully deterministic — if you know the notes, key, meter, and chord symbols, the image is completely specified. Rather than cleaning up pixels, generate clean PNGs from scratch using:

1. **ABC notation** — plain-text music format widely used for folk/traditional tunes
2. **abcm2ps** — renders ABC to PostScript → PNG via Ghostscript
3. Comparison overlay to catch transcription errors

---

## Tools Built

### `transcribe.py`
Sends a scan to Claude via `claude -p` (subscription auth, no API key needed) and receives ABC notation back. Uses `Popen` streaming to avoid a pipe-buffer deadlock that caused `subprocess.run(capture_output=True)` to hang indefinitely when the model generated thousands of thinking-token JSON events.

### `render_abc.sh`
Calls `abcm2ps` → Ghostscript → PNG. Stitches multi-page output with ImageMagick if the tune spans more than one page.

### `overlay_diff.py`
Loads the original scan (red channel) and clean render (blue channel), binarises both with adaptive thresholding, and composites them. Matching ink appears dark/black; red = only in original; blue = only in render. Intended for catching transcription errors.

### `process_tune.sh`
Orchestrates all three steps for one tune. Skips transcription if `.abc` already exists.

### `fetch_abc.py`
Searches thesession.org's JSON API for a tune by name and downloads the ABC. Falls back to a `.nomatch` marker file so re-runs skip already-tried tunes.

---

## Approaches Tried

### 1. `claude -p --effort low` (subprocess)

**Result: Failed — hallucinated notes.**

With `--effort low`, Claude completes in ~30 seconds but does not actually read the noteheads. It generates a plausible-sounding fiddle tune in the correct key with correct chord symbols and structure — but the notes are invented. Compared to the original, measure 2 of Booth Shot Lincoln should be `F#, A, B, A, A, A`; the low-effort output had `D, F#, D, A, F#, D, A`.

### 2. `claude -p` default effort (subprocess)

**Result: Failed — pipe deadlock / timeout.**

Default effort generates ~5,000–8,000 thinking tokens before producing output. The original implementation used `subprocess.run(capture_output=True)` which deadlocks when the stdout pipe buffer fills with hundreds of JSON thinking-token events. Fixed by switching to `Popen` + line-by-line streaming.

With the fix, the model completes in ~140 seconds. Quality was still poor: measure 2 of Booth Shot Lincoln came back as `A, C#, D, F#, E, E` rather than the correct `F#, A, B, A, A, A`.

**Root cause:** The `claude -p` subprocess fires up a fresh Claude Code session. The model can see the image and correctly identifies key, time signature, chord symbols, and gross structure — but does not read individual noteheads accurately enough for this task. This may be because the images are small (note heads are ~10–15px) and degraded by xerox artifacts.

### 3. oemer (Optical Music Recognition)

**Result: Partial — pitch roughly right, rhythm unreliable.**

`oemer` is a Python OMR tool using neural networks trained on music notation. Installed via `pip install oemer` in `.venv`. Runs on CPU (no CUDA available).

- Key signature: correctly detected (A major, 3 sharps)
- Note pitches: approximately correct range (A4–A5, consistent with A major fiddle tune)
- Rhythm values: unreliable — output contained random mixture of 32nd, 16th, quarter, half notes
- Also detected phantom low notes (A2, G#2) from non-note image elements

Produces MusicXML. Conversion to ABC via `music21` failed (wrote object repr instead of ABC). `xml2abc` was not available on PyPI; Wim Vree's canonical converter URL returned 404.

### 4. thesession.org ABC lookup

**Result: Wrong key, no chords, wrong measures.**

thesession.org has a JSON API (`/tunes/search`, `/tunes/{id}`). Search matched well-known tunes by name (5/5 on test batch: Arkansas Traveler, Angeline the Baker, Blackberry Blossom, Billy in the Lowground, Booth Shot Lincoln).

Problems with the downloaded ABC:
- **Key:** Community transcriptions are in whatever key the contributor used. The book's specific key is not preserved.
- **Chords:** Virtually no folk tune ABC files on thesession.org include chord symbols. The book has chord symbols throughout.
- **Arrangement:** Even for the same tune, the number of measures, repeat structure, and endings differ between versions.

Correcting all three per tune would require significant manual review — comparable to partial manual transcription.

### 5. Direct in-session transcription (Claude Code reading images)

**Result: Better than subprocess, but slow and still error-prone.**

Claude Code can read cropped system images at 2× scale and identify notes with reasonable accuracy. Tested on Booth Shot Lincoln system 1 with user verification measure by measure.

Workflow:
1. Crop each system to a 2× scale PNG
2. Claude reads note names; user confirms/corrects
3. Build ABC incrementally

This produced correct note names for verified measures, but:
- Requires user to know the tune or verify every note
- ~5–10 minutes per system × 7 systems × 277 tunes = not feasible at scale
- User does not know ABC notation and does not know most of the tunes

---

## Why It Was Abandoned

The fundamental blocker is the **verification problem**: any automated transcription (Claude, oemer, online lookup) produces output that needs to be checked against the original. Checking requires either:
- Knowing the tune well enough to spot wrong notes by ear/eye, or
- Reading notation carefully against the scan note-by-note

The user knows neither ABC notation nor most of the 277 tunes. Without a verifier, the pipeline produces clean-looking but potentially wrong notation — which is worse than a messy-but-correct scan.

---

## If You Want to Revisit This Later

The infrastructure is all here:

```bash
cd notation_pipeline/

# Render an ABC file you've already verified:
bash render_abc.sh abc/SomeTune.abc renders/SomeTune.render.png

# Compare with original:
source ../.venv/bin/activate
python3 overlay_diff.py ../SomeTune.png renders/SomeTune.render.png diffs/SomeTune.diff.png
firefox diffs/SomeTune.diff.png &

# Search thesession.org for a tune:
python3 fetch_abc.py "Tune Name"
```

Prerequisites: `abcm2ps`, `ghostscript`, `imagemagick` (system); `opencv-python-headless`, `anthropic`, `music21`, `oemer` (in `../.venv`).

The most realistic path forward would be finding a collaborator who knows the tunes and can do correction passes on oemer or online-ABC output — even 10 tunes per session would make a dent.
