#!/usr/bin/env python3
"""
Build / update tracking.md for the WOFTA ABC transcription project.

Rows = KEEP list from cleanup_keep.sh  ∪  every abc/*-candidate.abc / *-verified.abc tune.
Auto-columns (regenerated every run): Health, key_status, Finalized?,
  Key, Meter, Chords, Title, Measures, Truncation, Verified?.
Human columns (NOT overwritten): "Notes" — parsed back out of
  the existing tracking.md table and re-emitted unchanged.
Verified? is auto-derived from the presence of a -verified.abc file.

Output is a single Markdown file with a summary line and one table.  Markdown
was chosen over XLSX so the tracking state diffs cleanly in git and is readable
in a terminal.  Trade-off: no dropdowns/cell-colour — Verified? is plain text
from a fixed vocabulary (No / Yes / Needs-fix) and status is shown with marks.

Usage:
  python3 build_tracking_sheet.py          # write/update tracking.md
  python3 build_tracking_sheet.py --check  # dry-run; print the file, don't write
"""

import os
import re
import sys
import csv
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))   # bin/ — for sibling imports
ROOT = os.path.dirname(HERE)                         # notation_pipeline/ — for data
ABC_DIR = os.path.join(ROOT, 'abc')
HEALTH_TSV = os.path.join(ROOT, 'health_scores.tsv')

def is_verified(tune_name):
    return os.path.exists(os.path.join(ABC_DIR, f'{tune_name}-verified.abc'))
OUT_PATH = os.path.join(ROOT, 'tracking.md')
KEEP_SH = os.path.join(HERE, 'cleanup_keep.sh')      # sibling script, stays on HERE

sys.path.insert(0, HERE)
from validate_abc import run_validation, discover_all_finals  # noqa: E402

# ── KEEP list extraction ──────────────────────────────────────────────────────

def load_keep_list():
    """Parse KEEP=( ... ) from cleanup_keep.sh and return the ordered list."""
    result = subprocess.run(
        ['awk', r'/^KEEP=\(/,/^\)/', KEEP_SH],
        capture_output=True, text=True
    )
    entries = re.findall(r'"([^"#\n]+)"', result.stdout)
    return [e.strip() for e in entries]


# ── Health score lookup ───────────────────────────────────────────────────────

def load_health_data():
    """Return dict: tune_name → row dict (from health_scores.tsv)."""
    data = {}
    if not os.path.exists(HEALTH_TSV):
        return data
    with open(HEALTH_TSV, newline='') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            data[row['tune_name']] = row
    return data


# ── Tune list assembly ────────────────────────────────────────────────────────

def build_tune_list():
    """KEEP list first (in order), then any extra tunes that have a -candidate.abc or -verified.abc."""
    keep = load_keep_list()
    finals = set(discover_all_finals())
    keep_set = set(keep)
    extras = sorted(t for t in finals if t not in keep_set)
    return keep, keep_set, extras


# ── Markdown table parsing (preserve human columns) ───────────────────────────

HUMAN_COLS = ['Verified?', 'Notes']


def split_md_row(line):
    """Split one Markdown table row into stripped, pipe-unescaped cells."""
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    cells = re.split(r'(?<!\\)\|', line)
    return [c.strip().replace('\\|', '|') for c in cells]


def is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r':?-{2,}:?', c) for c in cells)


def read_existing_human_data():
    """
    Parse the existing tracking.md table, returning the human-editable columns
    keyed by tune name:  tune → {col: value}.
    """
    if not os.path.exists(OUT_PATH):
        return {}

    with open(OUT_PATH) as f:
        lines = f.readlines()

    header = None
    idx = {}
    result = {}
    for line in lines:
        if not line.lstrip().startswith('|'):
            continue
        cells = split_md_row(line)
        if header is None:
            header = cells
            for col in ['Tune'] + HUMAN_COLS:
                if col in header:
                    idx[col] = header.index(col)
            continue
        if is_separator_row(cells):
            continue
        if 'Tune' not in idx or idx['Tune'] >= len(cells):
            continue
        tune = cells[idx['Tune']]
        if not tune:
            continue
        result[tune] = {
            col: (cells[idx[col]] if col in idx and idx[col] < len(cells) else '')
            for col in HUMAN_COLS
        }
    return result


# ── Cell rendering helpers ────────────────────────────────────────────────────

COLUMNS = ['Tune', 'Health', 'key_status', 'Finalized?', 'Key', 'Meter',
           'Chords', 'Title', 'Measures', 'Truncation', 'Verified?', 'Notes']


def md_escape(s):
    """Make a value safe inside a Markdown table cell."""
    return str(s).replace('\r', ' ').replace('\n', ' ').replace('|', '\\|')


def mark(val, finalized):
    """✓ / ✗ for a boolean check; blank when the tune isn't finalized yet."""
    if not finalized:
        return ''
    return '✓' if val else '✗'


# ── Main builder ──────────────────────────────────────────────────────────────

def build():
    dry_run = '--check' in sys.argv

    keep_list, keep_set, extras = build_tune_list()
    all_tunes = keep_list + extras
    finals_set = set(discover_all_finals())
    health_data = load_health_data()
    existing_human = read_existing_human_data()

    finalized = [t for t in all_tunes if t in finals_set]
    sys.stderr.write(f'Running validation on {len(finalized)} finalized tune(s)...\n')

    # Run the validator quietly; we only want the structured summaries.
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        summaries, _, _ = run_validation(finalized, use_color=False)
    finally:
        sys.stdout = old_stdout

    rows = []
    for tune in all_tunes:
        hs_row = health_data.get(tune, {})
        finalized_flag = tune in finals_set

        if finalized_flag and tune in summaries:
            val_summary, extracted = summaries[tune]
            key_ok    = mark(extracted.get('key_ok'), True)
            meter_ok  = mark(extracted.get('meter_ok'), True)
            chords_ok = mark(extracted.get('chords_ok'), True)
            title_ok  = mark(extracted.get('title_ok'), True)
            measures  = extracted.get('measure_count', '')
            trunc     = '❌ FAIL' if extracted.get('truncation_fail') else ''
        else:
            val_summary = None
            key_ok = meter_ok = chords_ok = title_ok = ''
            measures = ''
            trunc = ''

        human = existing_human.get(tune, {})
        verified = 'Yes' if is_verified(tune) else 'No'
        notes = (human.get('Notes') or '').strip()

        rows.append({
            'Tune':       tune,
            'Health':     hs_row.get('health_score', ''),
            'key_status': hs_row.get('key_status', ''),
            'Finalized?': '✅' if finalized_flag else '',
            'Key':        key_ok,
            'Meter':      meter_ok,
            'Chords':     chords_ok,
            'Title':      title_ok,
            'Measures':   measures,
            'Truncation': trunc,
            'Verified?':  verified,
            'Notes':      notes,
            '_val':       val_summary,
        })

    # ── Summary line ──────────────────────────────────────────────────────────
    total      = len(rows)
    n_final    = sum(1 for r in rows if r['Finalized?'])
    n_pass     = sum(1 for r in rows if r['_val'] == 'PASS')
    n_warn     = sum(1 for r in rows if r['_val'] == 'WARN')
    n_fail     = sum(1 for r in rows if r['_val'] == 'FAIL')
    n_verified = sum(1 for r in rows if r['Verified?'] == 'Yes')
    remaining  = total - n_final

    # ── Render Markdown ───────────────────────────────────────────────────────
    out = []
    out.append('# WOFTA Transcription Tracking')
    out.append('')
    out.append('_Auto-generated by `build_tracking_sheet.py`. The auto columns are '
               'overwritten on every run; the **Notes** column is preserved; '
               '**Verified?** is auto-derived from the presence of a `-verified.abc`._')
    out.append('_`Verified?` vocabulary: `No` / `Yes` / `Needs-fix`. '
               'Marks: ✓ pass · ✗ fail · ✅ finalized · ❌ truncated._')
    out.append('')
    out.append(f'**Summary:** {total} tunes · {n_final} finalized · '
               f'{n_pass} PASS · {n_warn} WARN · {n_fail} FAIL · '
               f'{n_verified} verified · {remaining} remaining')
    out.append('')
    out.append('| ' + ' | '.join(COLUMNS) + ' |')
    out.append('|' + '|'.join('---' for _ in COLUMNS) + '|')
    for r in rows:
        out.append('| ' + ' | '.join(md_escape(r.get(c, '')) for c in COLUMNS) + ' |')
    out.append('')
    text = '\n'.join(out)

    if dry_run:
        print(text)
        return

    with open(OUT_PATH, 'w') as f:
        f.write(text)
    print(f'Written: {OUT_PATH}')
    print(f'  {total} tunes  ({n_final} finalized, {n_pass} PASS, '
          f'{n_warn} WARN, {n_fail} FAIL, {n_verified} verified)')


if __name__ == '__main__':
    build()
