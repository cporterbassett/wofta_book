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
    line = re.sub(r'"(?:\\.|[^"\\])*"', '', line)  # chord symbols / annotations (handles \" escapes)
    line = re.sub(r'![^!]*!', '', line)          # decorations
    line = re.sub(r'\[[A-Za-z]:[^\]]*\]', '', line)  # inline headers [K:...]
    line = line.replace('$', '')                 # linebreak marker
    line = re.sub(r'%.*$', '', line)             # trailing comment
    return line.strip()


def parse_tune_blocks(text):
    """Split a file into TuneBlocks (one per X:), grouping body lines by voice id."""
    blocks = []
    cur = None
    voice = None
    in_textblock = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('X:'):
            cur = TuneBlock()
            blocks.append(cur)
            voice = None
            continue
        if cur is None:
            continue
        if line.startswith('%%begintext'):
            in_textblock = True
            continue
        if line.startswith('%%endtext'):
            in_textblock = False
            continue
        if in_textblock:
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
        if c == '{':                       # grace-note group: no metric duration
            j = measure.find('}', i)
            i = j + 1 if j != -1 else i + 1
            continue
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
    """Interior measures must equal barlen; first/last may be short (pickup). A short
    interior measure is also allowed when it pairs with an adjacent measure to total
    exactly one bar (section-boundary pickup / measure split across a line break)."""
    measures = split_measures(body)
    durs = [measure_duration(m, unit, compound) for m in measures]
    n = len(measures)
    last = n - 1
    issues = []
    for idx, m in enumerate(measures):
        dur = durs[idx]
        if dur == barlen:
            continue
        if idx == 0 or idx == last:
            if dur > barlen:
                issues.append(Issue('beats', voice, idx + 1,
                    f'measure {idx + 1} has {dur} (> bar {barlen}); too long for a pickup', m))
            continue
        if dur < barlen and (
            (idx + 1 < n and dur + durs[idx + 1] == barlen) or
            (idx - 1 >= 0 and dur + durs[idx - 1] == barlen)
        ):
            continue  # pickup / split-measure pair sums to a full bar
        issues.append(Issue('beats', voice, idx + 1,
            f'measure {idx + 1} has {dur}, expected {barlen}', m))
    return issues


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


# ── Repeats ───────────────────────────────────────────────────────────────────

_BARTOK = re.compile(r':*\|+:*|::')


def check_repeats(voice, body):
    """Flag explicit |: opens that are never closed. A :| at depth 0 is a valid
    section/da-capo repeat (back to the last section start or the tune start)."""
    issues = []
    depth = 0
    for mt in _BARTOK.finditer(body):
        tok = mt.group(0)
        if tok.startswith(':') and depth > 0:   # close consumes an open repeat
            depth -= 1
        if tok.endswith(':'):                    # open
            depth += 1
    if depth > 0:
        issues.append(Issue('repeat', voice, None,
            f"{depth} unclosed '|:' (no matching ':|')"))
    return issues


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
