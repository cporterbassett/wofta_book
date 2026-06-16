#!/usr/bin/env python3
"""
Compare two ABC files by note content, ignoring cosmetic formatting.

Strips: chord symbols, decorations, linebreak markers, measure-number
comments, voice/linebreak headers. Normalizes all note durations to an
L:1/8 basis so files with different L: values are comparable. Splits
on barlines into individual measures, then diffs measure-by-measure.

Usage:
  python3 compare_abc.py gold.abc test.abc
  python3 compare_abc.py gold.abc test.abc --quiet   # score only, no diff
"""

import re
import sys
import difflib
from fractions import Fraction


# ── Duration normalization ────────────────────────────────────────────────────

TARGET_UNIT = Fraction(1, 8)

def get_unit(abc_text):
    """Extract L: field; return as Fraction. Default 1/8."""
    m = re.search(r'^L:(\d+)/(\d+)', abc_text, re.MULTILINE)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    return TARGET_UNIT


def _parse_dur(s):
    """Parse an ABC duration string to a Fraction (relative to L)."""
    if not s:
        return Fraction(1)
    if s.startswith('//'):
        return Fraction(1, 4)
    if s.startswith('/'):
        rest = s[1:]
        return Fraction(1, int(rest)) if rest else Fraction(1, 2)
    if '/' in s:
        n, d = s.split('/', 1)
        return Fraction(int(n), int(d))
    return Fraction(int(s))


def _dur_to_str(f):
    """Convert a Fraction duration (in TARGET_UNIT units) back to ABC string."""
    if f == 1:
        return ''
    if f.denominator == 1:
        return str(f.numerator)
    return f'{f.numerator}/{f.denominator}'


# Matches a note or rest token: optional accidentals + pitch letter +
# optional octave modifiers + optional duration suffix.
_NOTE_RE = re.compile(
    r'([_^=]{0,2}[a-gA-Gz][,\']*)'   # group 1: pitch part
    r'(\d+(?:/\d+)?|/+)?'             # group 2: optional duration
)


def normalize_durations(body, unit):
    """Rewrite every note/rest duration in body to TARGET_UNIT (L:1/8) basis.

    Always runs the substitution (even when unit == TARGET_UNIT) so that
    reducible fractions like 6/2 are canonicalized to 3 before comparison.
    """
    ratio = unit / TARGET_UNIT  # e.g. (1/4)/(1/8) = 2; (1/8)/(1/8) = 1

    def replace(m):
        pitch = m.group(1)
        dur_str = m.group(2) or ''
        src = _parse_dur(dur_str)
        new = src * ratio
        return pitch + _dur_to_str(new)

    return _NOTE_RE.sub(replace, body)


# ── Body extraction ───────────────────────────────────────────────────────────

def extract_body(abc_text):
    """Strip formatting; normalize durations to L:1/8; return note string.

    For multi-voice ABC, only the FIRST voice is returned. Audiveris drafts often
    split a monophonic tune into two voices; concatenating both bodies doubles the
    measure count and trips a false truncation FAIL (e.g. Gil's Schottische draft
    counted 32 for a 16-measure tune; Barlow Knife likewise)."""
    unit = get_unit(abc_text)
    first_voice = None
    current_voice = None
    lines = []
    for line in abc_text.splitlines():
        line = line.strip()
        if not line:
            continue
        vm = re.match(r'^V:\s*(\S+)', line)
        if vm:
            if first_voice is None:
                first_voice = vm.group(1)
            current_voice = vm.group(1)
            continue
        if re.match(r'^[A-Za-z]:', line):
            continue
        if current_voice is not None and current_voice != first_voice:
            continue  # skip secondary-voice body lines
        line = re.sub(r'"[^"]*"', '', line)   # chord symbols
        line = re.sub(r'![^!]*!', '', line)    # decorations
        line = re.sub(r'\{[^}]*\}', '', line)  # grace notes
        line = re.sub(r'\[[A-Z]:[^\]]*\]', '', line)  # inline headers [K:x]
        line = re.sub(r'^w:.*$', '', line)     # lyric/annotation lines
        line = line.replace('$', '')
        line = re.sub(r'%.*$', '', line)
        line = re.sub(r'\s+', ' ', line).strip()
        if line:
            lines.append(line)
    body = ' '.join(lines)
    return normalize_durations(body, unit)


# ── Measure splitting ─────────────────────────────────────────────────────────

# Any barline variant: |, ||, |:, :|, |1, |2, |], :|2, |]2, ], :|:, and the
# `::` shorthand (== :|: , end-repeat + start-repeat). The `::` form has no pipe,
# so it needs its own alternative — without it two measures merge and the count
# comes out one short (e.g. Petronella's `... dA :: F2 ...`).
BARLINE = re.compile(r'\s*(?::*\|+:*[12\]]?|::)\s*')


def split_measures(body):
    parts = BARLINE.split(body)
    return [p.strip() for p in parts if p.strip()]


def normalize_for_compare(measure):
    """Remove notation artifacts that don't affect note content."""
    s = re.sub(r'\s+', '', measure)               # spaces are insignificant in ABC
    return s


# ── Comparison ────────────────────────────────────────────────────────────────

def compare(gold_path, test_path, quiet=False):
    gold_text = open(gold_path).read()
    test_text = open(test_path).read()

    gold_measures = split_measures(extract_body(gold_text))
    test_measures = split_measures(extract_body(test_text))

    gold_norm = [normalize_for_compare(m) for m in gold_measures]
    test_norm = [normalize_for_compare(m) for m in test_measures]

    sm = difflib.SequenceMatcher(None, gold_norm, test_norm, autojunk=False)
    opcodes = sm.get_opcodes()
    matched = sum(g2 - g1 for op, g1, g2, t1, t2 in opcodes if op == 'equal')
    total = len(gold_measures)
    pct = matched / total * 100 if total else 0

    print(f"Measures matched: {matched}/{total} ({pct:.0f}%)")

    if not quiet:
        print()
        for op, g1, g2, t1, t2 in opcodes:
            if op == 'equal':
                for m in gold_measures[g1:g2]:
                    print(f"  OK  {m}")
            elif op == 'replace':
                for m in gold_measures[g1:g2]:
                    print(f"  -- {m}")
                for m in test_measures[t1:t2]:
                    print(f"  ++ {m}")
            elif op == 'delete':
                for m in gold_measures[g1:g2]:
                    print(f"  -- {m}")
            elif op == 'insert':
                for m in test_measures[t1:t2]:
                    print(f"  ++ {m}")


    return matched, total


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    quiet = '--quiet' in sys.argv

    if len(args) != 2:
        print(f"Usage: {sys.argv[0]} gold.abc test.abc [--quiet]")
        sys.exit(1)

    matched, total = compare(args[0], args[1], quiet=quiet)
    sys.exit(0 if matched == total else 1)
