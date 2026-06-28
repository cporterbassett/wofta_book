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


# ── Beat counting ─────────────────────────────────────────────────────────────

# (p notes in the time of q. (simple_q, compound_q); r (affected count) defaults to p.
_TUPLET_Q = {2: (3, 3), 3: (2, 2), 4: (3, 3), 5: (2, 3),
             6: (2, 2), 7: (2, 3), 8: (3, 3), 9: (2, 3)}

_PITCH = re.compile(r"[_^=]{0,2}[A-Ga-gxz][,']*")
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
        if c == '[':                       # chord (real chords open with a note/accidental)
            j = measure.find(']', i)
            if i + 1 >= n or measure[i + 1] not in "_^=ABCDEFGabcdefg" or j == -1:
                i += 1                      # stray '[' (e.g. volta annotation residue) — skip
                continue
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
