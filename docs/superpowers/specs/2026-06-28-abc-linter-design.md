# ABC Notation Linter — Design

**Date:** 2026-06-28
**Status:** Approved (pending spec review)
**Component:** `bin/lint_abc.py`

## Purpose

A standalone command-line tool that scans **verified** ABC files for musical-notation
correctness issues that the existing metadata-focused `bin/validate_abc.py` does not catch.
It complements (does not replace) `validate_abc.py`. The two answer different questions:

- `validate_abc.py` — **fidelity:** does the transcription match the original source?
  This is fundamentally a human judgment (eyeballing the engraved ABC against the scan);
  `validate_abc.py` supports that workflow with metadata/structure checks (key, meter,
  chords, title, truncation).
- `lint_abc.py` (this tool) — **objective correctness:** is the notation internally valid,
  regardless of the source? Catches mistakes the human missed: time signature, beats per
  measure, redundant accidentals, repeat matching. It never references the original scan or
  draft — it only checks that the ABC stands on its own.

## Scope

- **Default target:** all `abc/*-verified.abc` files (the hand-validated finals).
- **CLI surface** mirrors `validate_abc.py`:
  - `python3 bin/lint_abc.py "Tune Name" ["Tune Name 2" ...]` — lint named tunes
    (resolves to `abc/<name>-verified.abc`).
  - `python3 bin/lint_abc.py --all` — lint every `abc/*-verified.abc`.
- Out of scope: drafts and candidates (expected to contain errors), auto-fixing,
  rendering.

## Reused Infrastructure

From `bin/compare_abc.py`, import where directly usable:
- `get_unit(text)` — read `L:` as a `Fraction` (default 1/8).
- `_parse_dur(s)` — parse an ABC duration suffix to a `Fraction` of `L`.
- The `_NOTE_RE` token shape (note = optional accidentals + pitch letter + octave marks
  + optional duration) as the basis for tokenizing.

The linter does its own body extraction (it must keep accidentals, which
`extract_body` preserves, but it must operate **per voice** and **per tune block**, and it
must NOT duration-normalize before beat-summing). Body cleanup strips: chord symbols
`"..."`, decorations `!...!`, grace notes `{...}`, inline headers `[K:...]`,
linebreak `$`, and `%` comments — matching `extract_body`'s stripping, minus the
single-first-voice restriction.

## File / Tune / Voice Model

A `.abc` file may contain multiple **tune blocks** (each begins with `X:`). Each tune block
may contain multiple **voices** (`V:` declarations).

1. **Split into tune blocks** on `X:` lines. Lint every block.
2. Within a block, read header fields: `T:`, `L:`, `M:`, `K:`.
3. **Group body lines by voice id.** A `V:n ...` header sets the current voice; body lines
   accumulate under the active voice id. Repeated declarations of the same id
   (e.g. `V:1 treble` then `V:1`) collapse to one voice. A monophonic tune therefore
   yields exactly one voice.
4. **Lint each voice independently.** Beats, accidentals, and repeats are evaluated per
   voice (each voice's measures must each fill the bar). Voices are never concatenated into
   a single stream (that would double measure counts and break beat checks).

### Alt / fragment blocks

A secondary tune block with `M:none` that follows a real tune (e.g. Cherokee Shuffle's
"Alt Measures 12 & 13") is treated as a fragment:
- It **inherits** the previous block's meter for beat-counting.
- It does **not** trigger the missing-time-signature error.

## The Four Checks

All four emit severity **ERROR**. Any ERROR → non-zero exit.

### 1. Missing time signature
Per tune block: `M:` line absent, or value is `none` / `free`. Exception: an inheriting
alt/fragment block (see above) is exempt. One issue per offending block.

### 2. Beat count (smart, anacrusis-aware)
- Compute bar length from `M:` as a `Fraction` of a whole note (`4/4`→1, `6/8`→3/4,
  `2/2`→1, `C`→1, `C|`→1).
- For each measure (per voice), sum note + rest durations: `_parse_dur(suffix) * L`.
- Duration handling:
  - **Tuplets** `(p` (and the explicit `(p:q:r` form): play *p* notes in the time of *q*,
    affecting the next *r* notes. Each affected note's duration is multiplied by `q/p`.
    Defaults follow the ABC standard table (`r` defaults to `p`):

    | `(p` | q (simple meter) | q (compound meter) |
    |------|------------------|--------------------|
    | `(2` | 3 | 3 |
    | `(3` | 2 | 2 |
    | `(4` | 3 | 3 |
    | `(5` | 2 | 3 |
    | `(6` | 2 | 2 |
    | `(7` | 2 | 3 |
    | `(8` | 3 | 3 |
    | `(9` | 2 | 3 |

    "Compound" = meter whose numerator is a multiple of 3 and > 3 (6/8, 9/8, 12/8). The
    explicit `(p:q:r` form overrides the table. Document the table in code.
  - **Broken rhythm** `>` / `<`: redistributes duration between two notes but leaves the
    measure total unchanged — sum is unaffected, so no special handling needed beyond
    tokenizing the `>`/`<` out.
  - **Ties** `-`: no duration effect.
  - **Chords** `[ceg]`: count the chord's duration once (the bracket's, or the inner
    notes' shared duration).
- **Anacrusis:** the **first** and **last** measure of a voice may be short (pickup
  convention — see `[[anacrusis-convention]]`, `[[feedback_meter_anacrusis_numbering]]`).
  Flag first/last only if they **exceed** a full bar. Interior measures must equal the bar
  length exactly.
- **Volta / line-split recombination:** measure fragments produced by `|1`/`|2` voltas or
  by a measure spanning a line break are recombined before summing, reusing the
  `split_measures` barline logic.
- Report: measure number (1-based within the voice), actual total vs. expected, and the
  offending measure text.

### 3. Redundant accidentals
Track accidental state **per measure** (reset at each barline), seeded by the key
signature derived from `K:`.
- Build a key → accidental map for standard `K:` values (majors, minors, and modes:
  `K:Gmaj`, `K:Em`, `K:Ador`, `K:Dmix`, etc.). The map gives the set of letters sharped or
  flatted by the signature.
- For each explicit accidental token on a pitch:
  - **Redundant vs. key:** the accidental matches the key-signature alteration for that
    letter, and no earlier note in the same measure on that exact pitch set a different
    accidental (natural or otherwise) → ERROR. (The F#-in-G-major case.)
  - **Redundant repeat:** the same explicit accidental was already stated on that exact
    pitch earlier in the same measure → ERROR.
  - Out-of-key accidentals (not in the signature) are **not** flagged — legitimate.
- Report: measure number, the offending token, and the reason.

### 4. Unmatched repeats
Scan barline tokens in order (per voice). Maintain repeat depth:
- `|:` → open (+1).
- `:|` → close (−1).
- `::` / `:|:` → close then open (net 0, but errors if it would go negative).
- Tune start is an **implicit open**, so a leading `:|` with no preceding `|:` is valid.
- ERROR if a close would drive depth below the implicit floor, or if depth > 0 at end of
  the voice (an open repeat never closed).
- Report: location (measure number / barline index) and which side is unmatched.

## Output

Colorized, grouped per tune, matching `validate_abc.py` conventions:

```
  FAIL  Tune Name
    [ERROR] Beats: measure 7 has 9/8, expected 8/8 — "A2 B2 d3 A2"
    [ERROR] Accidental: measure 3 redundant ^f (F already sharp in K:G) — "G2 ^f2 e2"
    [ERROR] Repeats: ':|' at measure 16 has no matching '|:'
```

- Per voice, prefix issues with the voice id when a tune has more than one voice.
- Final summary table (tune → PASS/FAIL) and a fail banner listing failing tunes.
- Exit non-zero if any tune has an ERROR; zero otherwise.
- Color only when `stdout.isatty()`.

## Testing (TDD)

`pytest` (repo already has `.pytest_cache`). Tests live in `bin/test_lint_abc.py` (or
`tests/`, matching existing convention — check before writing).

Unit tests with hand-built ABC snippets, one behavior each:
- Beats: known-good 4/4 measure; off-by-one (9/8 in 4/4); 6/8 compound; cut time `C|`;
  triplet measure; broken-rhythm measure; tie across barline; chord measure; valid
  anacrusis pickup (short first + short last); short **interior** measure (must FAIL).
- Accidentals: redundant `^f` in `K:G` (FAIL); `=f` then `^f` in same measure (OK);
  doubled `^c` on same pitch (FAIL); out-of-key `^g` in `K:G` (OK, no flag); accidental
  carrying within a measure then reset at barline.
- Repeats: balanced `|: ... :|` (OK); leading `:|` with no `|:` (OK); `|:` never closed
  (FAIL); `:|` with negative depth (FAIL); `::` shorthand (OK).
- Time signature: missing `M:` (FAIL); `M:none` standalone tune (FAIL); `M:none` alt
  fragment after a real tune (OK, inherits).
- Voices: monophonic tune with repeated `V:1` declaration → one voice, no double count;
  two distinct voices each linted independently.
- Smoke test: run `--all` over every verified file; assert it completes without crashing.

## Non-Goals / YAGNI
- No auto-fix.
- No flagging of legitimate out-of-key accidentals.
- No microtonal / non-standard meters beyond what `M:` parsing supports.
- No integration into `validate_abc.py` for now (separate tool; can be chained later).
