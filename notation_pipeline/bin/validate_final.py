#!/usr/bin/env python3
"""
Validate one or more finalized ABC files against quality checks.

Usage:
  python3 validate_final.py "Tune Name" ["Tune Name 2" ...]
  python3 validate_final.py --all

Checks per abc/<Tune>-final.abc:
  FAIL  Key present & consistent  — K: line exists and non-empty; if health_scores
                                     key_status==missed but key is still C/none, FAIL
  WARN  Meter present             — M: line exists
  WARN  Chords entered            — at least 4 real chord tokens in the body
                                     (text annotations like "^Alt..." are excluded)
  WARN  Title entered             — T: present and not empty/placeholder
  FAIL  Truncation                — final measure-count < draft measure-count  OR  < 16
                                     (anacrusis: short FINAL measure is OK; only count matters)
                                     If gold exists, also compare to gold.

Exit: non-zero if any tune has a FAIL.
"""

import re
import sys
import os
import csv
import glob

# ── Path setup ────────────────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))   # bin/ — for sibling imports
ROOT = os.path.dirname(HERE)                         # notation_pipeline/ — for data
ABC_DIR = os.path.join(ROOT, 'abc')
HEALTH_TSV = os.path.join(ROOT, 'health_scores.tsv')

# ── Import compare_abc measure logic ─────────────────────────────────────────

sys.path.insert(0, HERE)
from compare_abc import split_measures, extract_body

# ── Health-score lookup ───────────────────────────────────────────────────────

def load_health_scores():
    """Return dict: tune_name → row dict from health_scores.tsv."""
    scores = {}
    if not os.path.exists(HEALTH_TSV):
        return scores
    with open(HEALTH_TSV, newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            scores[row['tune_name']] = row
    return scores


# ── Measure counting ──────────────────────────────────────────────────────────

def count_measures(path):
    """Return number of measures in an ABC file, or None if file missing."""
    if not os.path.exists(path):
        return None
    text = open(path).read()
    return len(split_measures(extract_body(text)))


# ── Per-tune validation ───────────────────────────────────────────────────────

PLACEHOLDER_TITLES = {'title', 'ddle', '', 'none'}

def validate_tune(tune_name, health_scores):
    """
    Returns a list of (level, check_name, message) tuples.
    level is 'PASS', 'WARN', or 'FAIL'.
    Also returns a dict of extracted values for the tracking sheet.
    """
    results = []
    extracted = {}

    final_path = os.path.join(ABC_DIR, f'{tune_name}-final.abc')
    draft_path = os.path.join(ABC_DIR, f'{tune_name}-draft.abc')
    gold_path  = os.path.join(ABC_DIR, f'{tune_name}-gold.abc')

    if not os.path.exists(final_path):
        results.append(('FAIL', 'File exists', f'abc/{tune_name}-final.abc not found'))
        return results, extracted

    text = open(final_path).read()

    # ── Key present & consistent ──────────────────────────────────────────────
    key_match = re.search(r'^K:\s*(.*)', text, re.MULTILINE)
    key_val = key_match.group(1).strip() if key_match else ''
    extracted['key'] = key_val

    key_lower = key_val.lower()
    key_is_empty = not key_val or key_lower == 'none'
    key_is_c_or_none = key_lower in ('c', 'cmaj', 'none', '') or not key_val

    if key_is_empty:
        results.append(('FAIL', 'Key present', f'K: is missing or empty (got: {repr(key_val)})'))
        extracted['key_ok'] = False
    else:
        # Check health_scores key_status: if missed and key is still C/none, real fix was skipped
        hs = health_scores.get(tune_name)
        if hs and hs.get('key_status') == 'missed' and key_is_c_or_none:
            results.append(('FAIL', 'Key consistent',
                f'key_status=missed in health_scores but final key is still "{key_val}" '
                f'(the real key fix was skipped)'))
            extracted['key_ok'] = False
        else:
            results.append(('PASS', 'Key present', f'K:{key_val}'))
            extracted['key_ok'] = True

    # ── Meter present ─────────────────────────────────────────────────────────
    meter_match = re.search(r'^M:\s*(.*)', text, re.MULTILINE)
    meter_val = meter_match.group(1).strip() if meter_match else ''
    extracted['meter'] = meter_val
    if not meter_val or meter_val.lower() in ('none', 'free'):
        results.append(('WARN', 'Meter present', f'M: is missing or "none" (got: {repr(meter_val)})'))
        extracted['meter_ok'] = False
    else:
        results.append(('PASS', 'Meter present', f'M:{meter_val}'))
        extracted['meter_ok'] = True

    # ── Chords entered ────────────────────────────────────────────────────────
    # Count only real chords; exclude ABC text annotations ("^...", "_...", etc.).
    CHORD_MIN = 4
    quoted = re.findall(r'"([^"]*)"', text)
    chord_count = sum(1 for q in quoted if q[:1] not in '^_<>@')
    extracted['chord_count'] = chord_count
    if chord_count < CHORD_MIN:
        results.append(('WARN', 'Chords entered',
            f'only {chord_count} chord(s) — expected >= {CHORD_MIN} (likely incomplete)'))
        extracted['chords_ok'] = False
    else:
        results.append(('PASS', 'Chords entered', f'{chord_count} chord(s)'))
        extracted['chords_ok'] = True

    # ── Title entered ─────────────────────────────────────────────────────────
    title_match = re.search(r'^T:\s*(.*)', text, re.MULTILINE)
    title_val = title_match.group(1).strip() if title_match else ''
    extracted['title'] = title_val
    if not title_val or title_val.lower() in PLACEHOLDER_TITLES:
        results.append(('WARN', 'Title entered', f'T: is missing or placeholder (got: {repr(title_val)})'))
        extracted['title_ok'] = False
    else:
        results.append(('PASS', 'Title entered', f'T:{title_val}'))
        extracted['title_ok'] = True

    # ── Truncation check ──────────────────────────────────────────────────────
    final_count = count_measures(final_path)
    draft_count = count_measures(draft_path)
    gold_count  = count_measures(gold_path)
    extracted['measure_count'] = final_count

    FLOOR = 16

    trunc_fail = False
    trunc_msgs = []

    if final_count < FLOOR:
        trunc_fail = True
        trunc_msgs.append(f'final has only {final_count} measures (floor={FLOOR})')

    if draft_count is not None:
        # Only compare if draft has a real key and meter (skip obviously-wrong drafts)
        draft_text = open(draft_path).read()
        draft_key_m = re.search(r'^K:\s*(.*)', draft_text, re.MULTILINE)
        draft_key = draft_key_m.group(1).strip().lower() if draft_key_m else ''
        draft_meter_m = re.search(r'^M:\s*(.*)', draft_text, re.MULTILINE)
        draft_meter = draft_meter_m.group(1).strip().lower() if draft_meter_m else ''

        if draft_key in ('none', '') or draft_meter in ('none', ''):
            # Draft itself had wrong/missing key or meter — comparison unreliable
            trunc_msgs.append(
                f'(draft has K:{draft_key}/M:{draft_meter} — draft vs final comparison skipped)')
        elif final_count < draft_count:
            trunc_fail = True
            trunc_msgs.append(
                f'final={final_count} measures < draft={draft_count} measures')
        else:
            trunc_msgs.append(f'final={final_count} >= draft={draft_count}')
    else:
        trunc_msgs.append(f'(no draft found, floor check only: {final_count}>={FLOOR})')

    if gold_count is not None:
        if final_count < gold_count:
            trunc_fail = True
            trunc_msgs.append(f'final={final_count} < gold={gold_count} measures')
        else:
            trunc_msgs.append(f'final={final_count} >= gold={gold_count}')

    level = 'FAIL' if trunc_fail else 'PASS'
    extracted['truncation_fail'] = trunc_fail
    results.append((level, 'Truncation', '; '.join(trunc_msgs)))

    return results, extracted


# ── Formatting helpers ────────────────────────────────────────────────────────

COLORS = {
    'PASS': '\033[32m',  # green
    'WARN': '\033[33m',  # yellow
    'FAIL': '\033[31m',  # red
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
}

def colorize(level, text):
    c = COLORS.get(level, '')
    return f"{c}{text}{COLORS['RESET']}"


def print_results(tune_name, results, extracted, use_color=True):
    any_fail = any(r[0] == 'FAIL' for r in results)
    any_warn = any(r[0] == 'WARN' for r in results)

    summary = 'FAIL' if any_fail else ('WARN' if any_warn else 'PASS')

    if use_color:
        header = colorize(summary, f'  {summary}')
    else:
        header = f'  {summary}'
    print(f'{header}  {tune_name}')

    for level, check, msg in results:
        if use_color:
            lbl = colorize(level, f'    [{level}]')
        else:
            lbl = f'    [{level}]'
        print(f'{lbl} {check}: {msg}')

    return summary


def print_fail_banner(failing_tunes, use_color=True):
    line = '!' * 60
    msg = f'\n{line}\n  VALIDATION FAILED — {len(failing_tunes)} tune(s) with FAIL:\n'
    for t in failing_tunes:
        msg += f'    • {t}\n'
    msg += f'{line}\n'
    if use_color:
        print(colorize('FAIL', msg))
    else:
        print(msg)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_validation(tune_names, use_color=True):
    """
    Validate the given tune names.  Returns (summaries_dict, any_fail_bool).
    summaries_dict: tune_name → ('PASS'|'WARN'|'FAIL', extracted_dict)
    """
    health_scores = load_health_scores()
    summaries = {}
    failing = []

    for tune_name in tune_names:
        results, extracted = validate_tune(tune_name, health_scores)
        summary = print_results(tune_name, results, extracted, use_color=use_color)
        summaries[tune_name] = (summary, extracted)
        if summary == 'FAIL':
            failing.append(tune_name)

    return summaries, bool(failing), failing


def discover_all_finals():
    """Return sorted list of tune names that have a -final.abc."""
    paths = glob.glob(os.path.join(ABC_DIR, '*-final.abc'))
    names = []
    for p in paths:
        base = os.path.basename(p)
        name = re.sub(r'-final\.abc$', '', base)
        names.append(name)
    return sorted(names)


if __name__ == '__main__':
    args = sys.argv[1:]
    use_color = sys.stdout.isatty()

    if not args:
        print('Usage: validate_final.py "Tune Name" [...]  OR  validate_final.py --all')
        sys.exit(1)

    if '--all' in args:
        tune_names = discover_all_finals()
        if not tune_names:
            print('No *-final.abc files found.')
            sys.exit(0)
    else:
        tune_names = [a for a in args if not a.startswith('--')]

    print(f'Validating {len(tune_names)} tune(s)...\n')
    summaries, any_fail, failing = run_validation(tune_names, use_color=use_color)

    print()
    # Summary table
    col_w = max(len(t) for t in tune_names) + 2
    print(f"  {'Tune':<{col_w}}  {'Result'}")
    print(f"  {'-'*col_w}  ------")
    for tune, (summary, _) in summaries.items():
        if use_color:
            s = colorize(summary, summary)
        else:
            s = summary
        print(f"  {tune:<{col_w}}  {s}")

    if any_fail:
        print_fail_banner(failing, use_color=use_color)
        sys.exit(1)
    else:
        print('\nAll checks passed (or warnings only).\n')
        sys.exit(0)
