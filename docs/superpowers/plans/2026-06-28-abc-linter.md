# ABC Notation Linter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `bin/lint_abc.py`, a standalone CLI that scans verified ABC files for objective notation errors (missing time signature, wrong beat counts, redundant accidentals, unmatched repeats).

**Architecture:** A single module in `bin/` (following the `validate_abc.py` / `compare_abc.py` one-file-per-tool pattern). It parses each file into tune blocks → voices, runs four independent check functions per voice, and prints a colorized per-tune report with a non-zero exit on any ERROR. It reuses `compare_abc.py`'s `split_measures` and `_parse_dur` helpers. It never reads the original scan or draft — it only checks the ABC's internal validity.

**Tech Stack:** Python 3.12, `fractions.Fraction`, `re`, `dataclasses`; pytest 9.0.3 (in `.venv`).

## Global Constraints

- Target files: `abc/*-verified.abc` only (default `--all`). Named-tune args resolve to `abc/<name>-verified.abc`.
- All four checks emit severity `ERROR`. Any ERROR → process exit code 1; otherwise 0.
- Color output only when `sys.stdout.isatty()`.
- Run tests with: `.venv/bin/python -m pytest bin/test_lint_abc.py -v` (from repo root `/home/porter/Documents/banjo/WOFTA/tune_images`).
- Reuse, do not duplicate, `compare_abc.split_measures` and `compare_abc._parse_dur`.
- Per voice: lint each distinct voice independently; repeated `V:1` declarations collapse to one voice. Prefix issues with the voice id only when a tune block has more than one voice.
- Alt/fragment block: a tune block with `M:none`/absent meter that follows a real tune inherits the previous block's bar length and is exempt from the missing-time-signature check.
- Anacrusis: the first and last measure of a voice may be short; flag them only if they exceed a full bar. Interior measures must equal the bar length exactly.

---

### Task 1: Module scaffold, data model, and parsing

**Files:**
- Create: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: `compare_abc.split_measures(body) -> list[str]`, `compare_abc._parse_dur(s) -> Fraction`.
- Produces:
  - `Issue` dataclass: `Issue(check: str, voice: str, measure: int|None, message: str, measure_text: str = '', level: str = 'ERROR')`
  - `TuneBlock` dataclass: fields `title: str`, `unit: Fraction`, `meter: str`, `key: str`, `voices: dict[str,str]`, `voice_order: list[str]`
  - `clean_body_line(line: str) -> str`
  - `parse_tune_blocks(text: str) -> list[TuneBlock]`

- [ ] **Step 1: Write the failing test**

Create `bin/test_lint_abc.py`:

```python
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # bin/
import lint_abc


SINGLE = """X:1
T:Test Tune
L:1/8
M:4/4
K:G
V:1 treble
V:1
 G2 A2 B2 c2 | d4 d4 |
"""

MULTI_X = """X:1
T:Main
L:1/8
M:4/4
K:A
A2 A2 A2 A2 |
X:2
T:
M:none
K:A
f2 fg a2 b2 |
"""


def test_parse_single_block_collapses_repeated_voice():
    blocks = lint_abc.parse_tune_blocks(SINGLE)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.title == "Test Tune"
    assert b.unit == Fraction(1, 8)
    assert b.meter == "4/4"
    assert b.key == "G"
    assert b.voice_order == ["1"]              # V:1 treble + V:1 collapse to one
    assert "G2 A2 B2 c2" in b.voices["1"]


def test_parse_two_x_blocks():
    blocks = lint_abc.parse_tune_blocks(MULTI_X)
    assert len(blocks) == 2
    assert blocks[1].meter == "none"


def test_clean_body_line_strips_decorations_keeps_accidentals():
    line = '"D" (F2[Fd]2) ^f2 !trill!e2 {ag}d2 $'
    out = lint_abc.clean_body_line(line)
    assert '"' not in out and '!' not in out and '{' not in out and '$' not in out
    assert '^f2' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lint_abc'`.

- [ ] **Step 3: Write minimal implementation**

Create `bin/lint_abc.py`:

```python
#!/usr/bin/env python3
"""
Lint finalized ABC files for objective notation errors.

Unlike validate_abc.py (which supports the human "does it match the source?"
fidelity check), this tool answers "is the notation internally valid?" — it never
references the original scan or draft.

Checks (all ERROR; any ERROR -> exit 1):
  - Missing time signature  (M: absent / none / free), except inheriting alt fragments
  - Beat count              (each interior measure must fill the bar; pickup edges may be short)
  - Redundant accidentals   (matches key sig with no prior cancel; or repeated in measure)
  - Unmatched repeats       (|: never closed, or :| with no open and no implicit-start credit)

Usage:
  python3 lint_abc.py "Tune Name" ["Tune Name 2" ...]
  python3 lint_abc.py --all
"""

import os
import re
import sys
import glob
from dataclasses import dataclass, field
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))   # bin/
ROOT = os.path.dirname(HERE)
ABC_DIR = os.path.join(ROOT, 'abc')

sys.path.insert(0, HERE)
from compare_abc import split_measures, _parse_dur


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    check: str            # 'meter' | 'beats' | 'accidental' | 'repeat'
    voice: str            # voice id, or '' when the block has a single voice
    measure: 'int | None'
    message: str
    measure_text: str = ''
    level: str = 'ERROR'


@dataclass
class TuneBlock:
    title: str = ''
    unit: Fraction = Fraction(1, 8)
    meter: str = ''
    key: str = ''
    voices: dict = field(default_factory=dict)        # voice_id -> joined body str
    voice_order: list = field(default_factory=list)


# ── Parsing ───────────────────────────────────────────────────────────────────

def clean_body_line(line):
    """Strip non-pitch notation, keep accidentals. Mirrors extract_body's cleanup."""
    line = re.sub(r'"[^"]*"', '', line)          # chord symbols / annotations
    line = re.sub(r'![^!]*!', '', line)          # decorations
    line = re.sub(r'\{[^}]*\}', '', line)        # grace notes
    line = re.sub(r'\[[A-Za-z]:[^\]]*\]', '', line)  # inline headers [K:...]
    line = line.replace('$', '')                 # linebreak marker
    line = re.sub(r'%.*$', '', line)             # trailing comment
    return line.strip()


def parse_tune_blocks(text):
    """Split a file into TuneBlocks (one per X:), grouping body lines by voice id."""
    blocks = []
    cur = None
    voice = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('X:'):
            cur = TuneBlock()
            blocks.append(cur)
            voice = None
            continue
        if cur is None:
            continue
        if not line or line.startswith('%'):
            continue
        fm = re.match(r'([A-Za-z]):\s*(.*)$', line)
        if fm and fm.group(1) != 'X':
            f, val = fm.group(1), fm.group(2).strip()
            if f == 'T' and not cur.title:
                cur.title = val
            elif f == 'L':
                mm = re.match(r'(\d+)/(\d+)', val)
                if mm:
                    cur.unit = Fraction(int(mm.group(1)), int(mm.group(2)))
            elif f == 'M':
                cur.meter = val
            elif f == 'K':
                cur.key = val
            elif f == 'V':
                vid = val.split()[0] if val.split() else '1'
                voice = vid
                if vid not in cur.voices:
                    cur.voices[vid] = ''
                    cur.voice_order.append(vid)
            continue  # all other info fields ignored
        body = clean_body_line(line)
        if not body:
            continue
        if voice is None:
            voice = '1'
            if '1' not in cur.voices:
                cur.voices['1'] = ''
                cur.voice_order.append('1')
        cur.voices[voice] = (cur.voices[voice] + ' ' + body).strip()
    return blocks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
chmod +x bin/lint_abc.py
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: lint_abc scaffold with tune-block/voice parsing"
```

---

### Task 2: Meter parsing and missing-time-signature check

**Files:**
- Modify: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: `TuneBlock`.
- Produces:
  - `meter_to_barlen(meter: str) -> Fraction | None`  (whole-note length of one bar; None if absent/none/free)
  - `is_compound(meter: str) -> bool`
  - `check_time_signature(block: TuneBlock, barlen: Fraction | None) -> list[Issue]`

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
def test_meter_to_barlen():
    assert lint_abc.meter_to_barlen("4/4") == Fraction(1)
    assert lint_abc.meter_to_barlen("6/8") == Fraction(3, 4)
    assert lint_abc.meter_to_barlen("2/2") == Fraction(1)
    assert lint_abc.meter_to_barlen("C") == Fraction(1)
    assert lint_abc.meter_to_barlen("C|") == Fraction(1)
    assert lint_abc.meter_to_barlen("none") is None
    assert lint_abc.meter_to_barlen("") is None


def test_is_compound():
    assert lint_abc.is_compound("6/8") is True
    assert lint_abc.is_compound("9/8") is True
    assert lint_abc.is_compound("4/4") is False
    assert lint_abc.is_compound("3/4") is False     # 3 is not > 3
    assert lint_abc.is_compound("C") is False


def test_check_time_signature():
    b = lint_abc.TuneBlock(meter="")
    assert len(lint_abc.check_time_signature(b, None)) == 1
    # When a barlen was supplied (real or inherited), no missing-meter error:
    assert lint_abc.check_time_signature(b, Fraction(1)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "meter or compound or time_signature" -v`
Expected: FAIL with `AttributeError: module 'lint_abc' has no attribute 'meter_to_barlen'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bin/lint_abc.py`:

```python
# ── Meter ─────────────────────────────────────────────────────────────────────

def meter_to_barlen(meter):
    """One bar's length as a Fraction of a whole note. None if no usable meter."""
    m = (meter or '').strip()
    if not m or m.lower() in ('none', 'free'):
        return None
    if m in ('C', 'c', 'C|', 'c|'):     # common (4/4) and cut (2/2) both == 1 whole
        return Fraction(1)
    mm = re.match(r'(\d+)\s*/\s*(\d+)', m)
    if mm:
        return Fraction(int(mm.group(1)), int(mm.group(2)))
    return None


def is_compound(meter):
    """True for 6/8, 9/8, 12/8 ... (numerator a multiple of 3 and > 3)."""
    mm = re.match(r'(\d+)\s*/\s*(\d+)', (meter or '').strip())
    if not mm:
        return False
    num = int(mm.group(1))
    return num % 3 == 0 and num > 3


def check_time_signature(block, barlen):
    """ERROR if this block has no usable meter and none was inherited."""
    if barlen is None:
        return [Issue('meter', '', None, 'no time signature (M:) present')]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "meter or compound or time_signature" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: meter parsing and missing-time-signature check"
```

---

### Task 3: Beat-count check (durations, tuplets, chords, anacrusis)

**Files:**
- Modify: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: `compare_abc._parse_dur`, `compare_abc.split_measures`.
- Produces:
  - `measure_duration(measure: str, unit: Fraction, compound: bool) -> Fraction`
  - `check_beats(voice: str, body: str, unit: Fraction, barlen: Fraction, compound: bool) -> list[Issue]`

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
U8 = Fraction(1, 8)


def test_measure_duration_simple():
    # 8 eighth-notes in 4/4 == 1 whole note
    assert lint_abc.measure_duration("G2 A2 B2 c2", U8, False) == Fraction(1)
    assert lint_abc.measure_duration("d4 d4", U8, False) == Fraction(1)


def test_measure_duration_chord_counts_once():
    # [EA]2 [ce]2 [ce]2 [Ae][Be]  in L:1/16 -> (2+2+2+1+1)/16 = 8/16 = 1/2
    assert lint_abc.measure_duration("[EA]2[ce]2 [ce]2[Ae][Be]", Fraction(1, 16), False) == Fraction(1, 2)


def test_measure_duration_triplet():
    # (3abc in L:1/8 simple meter: 3 eighths in time of 2 -> 2/8 = 1/4
    assert lint_abc.measure_duration("(3abc", U8, False) == Fraction(1, 4)


def test_measure_duration_broken_rhythm_unchanged():
    # a>b == a3/2 + b1/2 ; same total as a b
    assert lint_abc.measure_duration("a>b", U8, False) == lint_abc.measure_duration("a b", U8, False)


def test_check_beats_flags_interior_only():
    # measure 2 (interior) is short -> 1 issue; pickup edges ignored
    body = "dB | A2 B2 | A2 B2 d3 A | A3"   # m1 short(edge ok), m2 short(FAIL), m3 full, m4 short(edge ok)
    issues = lint_abc.check_beats("", body, U8, Fraction(1), False)
    assert len(issues) == 1
    assert issues[0].measure == 2


def test_check_beats_too_long_pickup_flagged():
    body = "A2 B2 d3 A2 | A2 B2 d3 A"    # m1 edge but 9/8 > 8/8 -> FAIL
    issues = lint_abc.check_beats("", body, U8, Fraction(1), False)
    assert any(i.measure == 1 for i in issues)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "duration or beats" -v`
Expected: FAIL with `AttributeError: ... 'measure_duration'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bin/lint_abc.py`:

```python
# ── Beat counting ─────────────────────────────────────────────────────────────

# (p notes in the time of q. (simple_q, compound_q); r (affected count) defaults to p.
_TUPLET_Q = {2: (3, 3), 3: (2, 2), 4: (3, 3), 5: (2, 3),
             6: (2, 2), 7: (2, 3), 8: (3, 3), 9: (2, 3)}

_PITCH = re.compile(r"[_^=]{0,2}[A-Ga-gz][,']*")
_DURSUFFIX = re.compile(r"(?:\d+)?(?:/+)?(?:\d+)?")


def _suffix_dur(text, pos, unit):
    """Read a duration suffix at text[pos:]; return (Fraction-of-whole, new_pos)."""
    m = _DURSUFFIX.match(text, pos)
    s = m.group(0)
    return _parse_dur(s) * unit, m.end()


def measure_duration(measure, unit, compound):
    """Total sounded duration of a measure, as a Fraction of a whole note.

    Chords count once; tuplets scale the affected notes; broken rhythm and ties
    are duration-neutral; slurs/spaces are ignored.
    """
    total = Fraction(0)
    i, n = 0, len(measure)
    tuplet_remaining = 0
    tuplet_ratio = Fraction(1)
    while i < n:
        c = measure[i]
        if c == '(' and i + 1 < n and measure[i + 1].isdigit():
            tm = re.match(r'\((\d+)(?::(\d*))?(?::(\d*))?', measure[i:])
            p = int(tm.group(1))
            q = int(tm.group(2)) if tm.group(2) else None
            r = int(tm.group(3)) if tm.group(3) else None
            if q is None:
                qs, qc = _TUPLET_Q.get(p, (2, 3))
                q = qc if compound else qs
            tuplet_remaining = r if r is not None else p
            tuplet_ratio = Fraction(q, p)
            i += tm.end()
            continue
        if c == '[':                       # chord
            j = measure.find(']', i)
            if j == -1:
                break
            dval, after = _suffix_dur(measure, j + 1, unit)
            if measure[j + 1:after] == '':  # no suffix after ] -> use first inner note
                inner = _PITCH.match(measure, i + 1)
                if inner:
                    dval, _ = _suffix_dur(measure, inner.end(), unit)
            if tuplet_remaining > 0:
                dval *= tuplet_ratio
                tuplet_remaining -= 1
            total += dval
            i = after
            continue
        pm = _PITCH.match(measure, i)
        if pm:
            dval, after = _suffix_dur(measure, pm.end(), unit)
            if tuplet_remaining > 0:
                dval *= tuplet_ratio
                tuplet_remaining -= 1
            total += dval
            i = after
            continue
        i += 1                              # spaces, slurs (), > < - etc.
    return total


def check_beats(voice, body, unit, barlen, compound):
    """Interior measures must equal barlen; first/last may be short (pickup)."""
    issues = []
    measures = split_measures(body)
    last = len(measures) - 1
    for idx, m in enumerate(measures):
        dur = measure_duration(m, unit, compound)
        if idx == 0 or idx == last:
            if dur > barlen:
                issues.append(Issue('beats', voice, idx + 1,
                    f'measure {idx + 1} has {dur} (> bar {barlen}); too long for a pickup', m))
        elif dur != barlen:
            issues.append(Issue('beats', voice, idx + 1,
                f'measure {idx + 1} has {dur}, expected {barlen}', m))
    return issues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "duration or beats" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: beat-count check with tuplet/chord/anacrusis handling"
```

---

### Task 4: Redundant-accidentals check

**Files:**
- Modify: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: `compare_abc.split_measures`.
- Produces:
  - `key_accidentals(key: str) -> dict[str,str]`  (letter -> '#' or 'b' for the signature)
  - `check_accidentals(voice: str, body: str, key_map: dict[str,str]) -> list[Issue]`

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
def test_key_accidentals():
    assert lint_abc.key_accidentals("G") == {"F": "#"}
    assert lint_abc.key_accidentals("D") == {"F": "#", "C": "#"}
    assert lint_abc.key_accidentals("F") == {"B": "b"}
    assert lint_abc.key_accidentals("Em") == {"F": "#"}        # E minor == 1 sharp
    assert lint_abc.key_accidentals("Ador") == {"F": "#"}  # A dorian == G major == 1 sharp
    assert lint_abc.key_accidentals("C") == {}


def test_accidental_redundant_vs_key():
    km = lint_abc.key_accidentals("G")
    issues = lint_abc.check_accidentals("", "G2 ^f2 e2", km)   # F already sharp in G
    assert len(issues) == 1 and "redundant" in issues[0].message.lower()


def test_accidental_natural_then_sharp_is_ok():
    km = lint_abc.key_accidentals("G")
    assert lint_abc.check_accidentals("", "=f2 ^f2", km) == []  # natural cancels, ^f restores


def test_accidental_out_of_key_not_flagged():
    km = lint_abc.key_accidentals("G")
    assert lint_abc.check_accidentals("", "^g2 a2", km) == []   # G# not in key -> legit


def test_accidental_repeated_in_measure():
    km = lint_abc.key_accidentals("C")
    issues = lint_abc.check_accidentals("", "^c2 ^c2", km)      # 2nd ^c redundant
    assert len(issues) == 1


def test_accidental_resets_each_measure():
    km = lint_abc.key_accidentals("C")
    # ^c in m1, ^c in m2 -> each is the first in its measure, neither repeated
    assert lint_abc.check_accidentals("", "^c2 d2 | ^c2 d2", km) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "key_accidentals or accidental" -v`
Expected: FAIL with `AttributeError: ... 'key_accidentals'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bin/lint_abc.py`:

```python
# ── Accidentals ───────────────────────────────────────────────────────────────

_SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
_FLAT_ORDER  = ['B', 'E', 'A', 'D', 'G', 'C', 'F']
_FIFTHS = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
           'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7}


def _mode_offset(mode):
    m = mode.strip().lower()
    if m.startswith('maj') or m.startswith('ion') or m == '':
        return 0
    if m.startswith('dor'):
        return -2
    if m.startswith('phr'):
        return -4
    if m.startswith('lyd'):
        return 1
    if m.startswith('mix'):
        return -1
    if m.startswith('loc'):
        return -5
    if m.startswith('aeo') or m.startswith('min') or m.startswith('m'):
        return -3
    return 0


def key_accidentals(key):
    """Map each altered letter to '#' or 'b' for the key signature of K:<key>."""
    km = re.match(r"\s*([A-Ga-g][#b]?)\s*(.*)", key or '')
    if not km:
        return {}
    tonic = km.group(1)[0].upper() + km.group(1)[1:]
    fifths = _FIFTHS.get(tonic)
    if fifths is None:
        return {}
    fifths += _mode_offset(km.group(2))
    out = {}
    if fifths > 0:
        for letter in _SHARP_ORDER[:fifths]:
            out[letter] = '#'
    elif fifths < 0:
        for letter in _FLAT_ORDER[:-fifths]:
            out[letter] = 'b'
    return out


_ACC_SYM = {'^': '#', '^^': '##', '_': 'b', '__': 'bb', '=': '='}
_ACCNOTE = re.compile(r"([_^=]{1,2})([A-Ga-g])([,']*)")


def _octave(letter, marks):
    o = 0 if letter.isupper() else 1
    return o + marks.count("'") - marks.count(",")


def check_accidentals(voice, body, key_map):
    """Flag accidentals that match the key sig (with no prior cancel) or repeat in-measure."""
    issues = []
    for idx, measure in enumerate(split_measures(body)):
        seen = {}   # (LETTER, octave) -> symbol
        for mt in _ACCNOTE.finditer(measure):
            acc, raw_letter, marks = mt.group(1), mt.group(2), mt.group(3)
            letter = raw_letter.upper()
            pitch = (letter, _octave(raw_letter, marks))
            sym = _ACC_SYM.get(acc, acc)
            if seen.get(pitch) == sym:
                issues.append(Issue('accidental', voice, idx + 1,
                    f'redundant repeated {acc}{raw_letter} in measure {idx + 1}', measure))
            elif pitch not in seen and key_map.get(letter) == sym:
                issues.append(Issue('accidental', voice, idx + 1,
                    f'redundant {acc}{raw_letter} ({letter} already {sym} in key) '
                    f'in measure {idx + 1}', measure))
            seen[pitch] = sym
    return issues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "key_accidentals or accidental" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: redundant-accidentals check with key-signature map"
```

---

### Task 5: Unmatched-repeats check

**Files:**
- Modify: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Produces: `check_repeats(voice: str, body: str) -> list[Issue]`

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
def test_repeats_balanced_ok():
    assert lint_abc.check_repeats("", "|: a b :| |: c d :|") == []


def test_repeats_leading_close_ok():
    # ":|" with no "|:" repeats from the start -> valid (implicit credit)
    assert lint_abc.check_repeats("", "a b :| c d") == []


def test_repeats_unclosed_open_fails():
    issues = lint_abc.check_repeats("", "|: a b | c d")
    assert len(issues) == 1 and "unclosed" in issues[0].message.lower()


def test_repeats_extra_close_fails():
    # implicit credit used by first :| ; second :| is unmatched
    issues = lint_abc.check_repeats("", "a :| b :| c")
    assert len(issues) == 1


def test_repeats_double_colon_shorthand_ok():
    assert lint_abc.check_repeats("", "|: a b :: c d :|") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "repeats" -v`
Expected: FAIL with `AttributeError: ... 'check_repeats'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bin/lint_abc.py`:

```python
# ── Repeats ───────────────────────────────────────────────────────────────────

_BARTOK = re.compile(r':*\|+:*|::')


def check_repeats(voice, body):
    """Match |: / :| pairs. Tune start is one implicit open ('|:') credit."""
    issues = []
    depth = 0
    implicit = 1
    for mt in _BARTOK.finditer(body):
        tok = mt.group(0)
        closes = tok.startswith(':')
        opens = tok.endswith(':')
        if closes:
            if depth > 0:
                depth -= 1
            elif implicit > 0:
                implicit -= 1
            else:
                issues.append(Issue('repeat', voice, None,
                    "':|' with no matching '|:'"))
        if opens:
            depth += 1
    if depth > 0:
        issues.append(Issue('repeat', voice, None,
            f"{depth} unclosed '|:' (no matching ':|')"))
    return issues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "repeats" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: unmatched-repeats check"
```

---

### Task 6: Orchestration, reporting, and CLI

**Files:**
- Modify: `bin/lint_abc.py`
- Test: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: all check functions, `meter_to_barlen`, `is_compound`, `parse_tune_blocks`.
- Produces:
  - `lint_block(block: TuneBlock, inherited: tuple|None) -> tuple[list[Issue], tuple|None]`
  - `lint_file(path: str) -> list[Issue]`
  - `resolve_path(name: str) -> str`
  - `discover_all() -> list[str]`
  - `main(argv: list[str]) -> int`

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
def _write(tmp_path, text):
    p = tmp_path / "T.abc"
    p.write_text(text)
    return str(p)


def test_lint_file_clean(tmp_path):
    path = _write(tmp_path, SINGLE)
    assert lint_abc.lint_file(path) == []


def test_lint_file_alt_block_inherits_meter(tmp_path):
    # 2nd block has M:none but inherits 4/4; its full bar passes, no missing-meter error
    path = _write(tmp_path, MULTI_X)
    issues = lint_abc.lint_file(path)
    assert [i for i in issues if i.check == 'meter'] == []


def test_lint_file_catches_bad_beats(tmp_path):
    bad = "X:1\nL:1/8\nM:4/4\nK:G\nG2 A2 B2 | d4 d4 |\n"  # interior m1 short
    path = _write(tmp_path, bad)
    issues = lint_abc.lint_file(path)
    assert any(i.check == 'beats' for i in issues)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -k "lint_file" -v`
Expected: FAIL with `AttributeError: ... 'lint_file'`.

- [ ] **Step 3: Write minimal implementation**

Append to `bin/lint_abc.py`:

```python
# ── Orchestration ─────────────────────────────────────────────────────────────

def lint_block(block, inherited):
    """Lint one tune block. Returns (issues, new_inherited)."""
    issues = []
    real_barlen = meter_to_barlen(block.meter)
    if real_barlen is not None:
        barlen, compound = real_barlen, is_compound(block.meter)
        new_inherited = (barlen, compound)
    elif inherited is not None:
        barlen, compound = inherited           # alt/fragment inherits; exempt from meter check
        new_inherited = inherited
    else:
        issues += check_time_signature(block, None)
        barlen, compound, new_inherited = None, False, inherited

    key_map = key_accidentals(block.key)
    multi = len(block.voice_order) > 1
    for vid in block.voice_order:
        body = block.voices[vid]
        vlabel = vid if multi else ''
        if barlen is not None:
            issues += check_beats(vlabel, body, block.unit, barlen, compound)
        issues += check_accidentals(vlabel, body, key_map)
        issues += check_repeats(vlabel, body)
    return issues, new_inherited


def lint_file(path):
    text = open(path).read()
    inherited = None
    issues = []
    for block in parse_tune_blocks(text):
        block_issues, inherited = lint_block(block, inherited)
        issues += block_issues
    return issues


# ── Path resolution ───────────────────────────────────────────────────────────

def resolve_path(name):
    if os.path.isfile(name):
        return name
    return os.path.join(ABC_DIR, f'{name}-verified.abc')


def discover_all():
    return sorted(glob.glob(os.path.join(ABC_DIR, '*-verified.abc')))


# ── Reporting / CLI ───────────────────────────────────────────────────────────

COLORS = {'PASS': '\033[32m', 'FAIL': '\033[31m', 'RESET': '\033[0m'}


def _c(level, text, use_color):
    return f"{COLORS.get(level, '')}{text}{COLORS['RESET']}" if use_color else text


def _tune_name(path):
    base = os.path.basename(path)
    return re.sub(r'-verified\.abc$', '', base)


def main(argv):
    use_color = sys.stdout.isatty()
    args = [a for a in argv if not a.startswith('--')]
    if '--all' in argv:
        paths = discover_all()
    elif args:
        paths = [resolve_path(a) for a in args]
    else:
        print('Usage: lint_abc.py "Tune Name" [...]  OR  lint_abc.py --all')
        return 1

    failing = []
    for path in paths:
        name = _tune_name(path)
        if not os.path.isfile(path):
            print(_c('FAIL', f'  FAIL  {name}', use_color))
            print(f'    [ERROR] file not found: {path}')
            failing.append(name)
            continue
        issues = lint_file(path)
        if not issues:
            print(_c('PASS', f'  PASS  {name}', use_color))
            continue
        failing.append(name)
        print(_c('FAIL', f'  FAIL  {name}', use_color))
        for i in issues:
            vp = f'(V:{i.voice}) ' if i.voice else ''
            tail = f' — "{i.measure_text}"' if i.measure_text else ''
            print(f'    {_c("FAIL", "[" + i.level + "]", use_color)} '
                  f'{i.check}: {vp}{i.message}{tail}')

    print()
    print(f'  {len(paths) - len(failing)} clean, {len(failing)} with issues '
          f'(of {len(paths)} checked)')
    return 1 if failing else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -v`
Expected: all passed (full suite).

- [ ] **Step 5: Commit**

```bash
git add bin/lint_abc.py bin/test_lint_abc.py
git commit -m "feat: lint_abc orchestration, reporting, and CLI"
```

---

### Task 7: Smoke test over verified corpus and first real run

**Files:**
- Modify: `bin/test_lint_abc.py`

**Interfaces:**
- Consumes: `lint_abc.discover_all`, `lint_abc.lint_file`.

- [ ] **Step 1: Write the failing test**

Append to `bin/test_lint_abc.py`:

```python
def test_smoke_all_verified_runs_without_crashing():
    paths = lint_abc.discover_all()
    assert paths, "expected verified ABC files in abc/"
    for p in paths:
        lint_abc.lint_file(p)   # must not raise
```

- [ ] **Step 2: Run test to verify it passes (it should already pass)**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py::test_smoke_all_verified_runs_without_crashing -v`
Expected: PASS (no crash). If it raises on a real file, fix the parser/check that choked before continuing.

- [ ] **Step 3: Run the linter for real and eyeball results**

Run: `.venv/bin/python bin/lint_abc.py --all`
Expected: a per-tune PASS/FAIL report ending with the summary line. Spot-check 2-3 reported issues by opening the named ABC file to confirm they are real (not false positives). Note any systematic false positive — if found, it indicates a check bug to fix and re-commit before finishing.

- [ ] **Step 4: Run the full suite once more**

Run: `.venv/bin/python -m pytest bin/test_lint_abc.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add bin/test_lint_abc.py
git commit -m "test: smoke-test lint_abc over the verified corpus"
```

---

## Self-Review Notes

- **Spec coverage:** missing-time-signature → Task 2/6; beats (tuplets/broken/ties/chords/anacrusis/voltas via `split_measures`) → Task 3; redundant accidentals (key-redundant + repeat-in-measure, octave-aware, out-of-key exempt) → Task 4; unmatched repeats (implicit-start credit) → Task 5; per-block + per-voice + alt-fragment inheritance → Task 6; verified-only CLI (`--all` / named) → Task 6; smoke over corpus → Task 7.
- **Severity:** every Issue defaults `level='ERROR'`; `main` returns 1 when any issue exists. Matches "all four = ERROR".
- **Reuse:** `split_measures` and `_parse_dur` imported from `compare_abc`, not reimplemented.
- **Type consistency:** `Issue` and `TuneBlock` signatures, `meter_to_barlen`/`is_compound`/`check_*` names and argument orders are consistent across Tasks 1–6.
