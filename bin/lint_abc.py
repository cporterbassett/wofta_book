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
