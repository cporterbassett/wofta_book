#!/usr/bin/env python3
"""
health_score.py — Score Audiveris OMR output files for quality.

Usage:
    python3 health_score.py                         # scan all batch_output/*/clean.omr
    python3 health_score.py path/to/foo.omr ...     # explicit file list

Output: TSV to stdout, sorted worst-first (lowest health_score first).

Health score components (lower = worse):
  - key_status:   Triage of the first-staff key signature into:
                    present — KeySig in first staff header (no work)
                    missed  — first header lacks it, BUT Audiveris found a key
                              sig elsewhere (later system header, stray key-alter
                              glyph, or an ashokan-style rest in the header band).
                              A real, printed key sig that must be fixed → -40.
                    absent  — no evidence of any printed key sig anywhere. The
                              tune is probably genuinely keyless (Am / C / Dorian);
                              this is correct behaviour, so NO penalty.
  - time_ok:      TimeSig present in first staff header?    missing → -20
  - ashokan_tell: Rest glyph inside header x-band?         present → -30
                  (sharp misclassified as quarter-rest = key will be wrong)
  - avg_grade:    Mean ctx-grade across all inters          (avg_grade - 0.5) * 20
  - base:         100

Score range roughly 0–120; lower = more GUI cleanup needed.

The point of the key_status triage: a plain key_ok=False conflates "Audiveris
missed a printed key signature" (a real fix that corrupts every pitch) with
"this tune has no key signature" (nothing to fix). Penalising both equally made
the worst-first queue waste GUI time on tunes that were already correct. Only
`missed` is penalised, so the queue ranks by *real correction effort*.

NOTE: `absent` is a best guess, not a guarantee. If a printed sharp/flat vanished
entirely during recognition (no rest, no later-system key, no stray glyph), it is
indistinguishable from genuinely keyless without looking at the source image.
"""

import sys
import os
import re
import zipfile
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)          # repo root (parent of bin/)
BATCH_DIR = os.path.join(ROOT, "scratch", "batch_output")

TSV_HEADER = "\t".join([
    "tune_name", "health_score", "key_status", "key_ok", "time_ok",
    "ashokan_tell", "avg_grade", "measure_count", "omr_path"
])

# Weights
W_KEY_MISSING   = -40
W_TIME_MISSING  = -20
W_ASHOKAN_TELL  = -30
W_GRADE_SCALE   = 20   # contribution = (avg_grade - 0.5) * W_GRADE_SCALE
BASE_SCORE      = 100


def find_all_omr_files():
    """Return sorted list of clean.omr paths under batch_output/."""
    pattern = os.path.join(BATCH_DIR, "*", "clean.omr")
    return sorted(glob.glob(pattern))


def parse_sheet_xml(content: str) -> dict:
    """
    Parse Audiveris sheet#1.xml content and return a dict of health components.

    XML structure notes:
    - Inters live in <sig><inters>…</inters></sig> with tag names like
      <key …>, <time-pair …>, <rest …>, <barline …>, <head …>, etc.
    - The first staff's header is: <header start="N" stop="M"><clef>…</clef>
      <key>ID</key><time>ID</time></header>
      * <key> child present → key sig recognized
      * <time> child present → time sig recognized
    - "ashokan_tell": a <rest> element whose <bounds x="…"> x < header_stop of
      the first system/staff.  This means Audiveris read a sharp as a rest,
      causing a wrong key.
    - grade attributes: use ctx-grade when present, else grade; average across
      all elements that have a grade attribute.
    - measure-count: from <page … measure-count="N">.
    """

    # ── First staff header ──────────────────────────────────────────────────
    # Match the very first <header start="…" stop="…">…</header> block
    header_m = re.search(
        r'<header\s+start="(\d+)"\s+stop="(\d+)">(.*?)</header>',
        content, re.DOTALL
    )
    header_stop = int(header_m.group(2)) if header_m else None
    header_body = header_m.group(3) if header_m else ""

    key_ok  = bool(re.search(r'<key\s*>', header_body))
    time_ok = bool(re.search(r'<time\s*>', header_body))

    # ── Key signature found in ANY system header (not just the first) ─────────
    # The Ashokan/Big-Scioty pattern: system 1 misses the key sig, but later
    # systems recognise it.  If a <key> child appears in any header, the tune
    # demonstrably HAS a printed key signature.
    key_in_any_header = any(
        re.search(r'<key\s*>', m.group(0))
        for m in re.finditer(r'<header\b.*?</header>', content, re.DOTALL)
    )

    # ── Key-alter glyphs anywhere in the sheet ───────────────────────────────
    # <key-alter> inters are the individual sharp/flat glyphs that make up a key
    # signature.  Their presence (even when not assembled into a header <key>)
    # is direct evidence of a printed key signature.  Plain per-note accidentals
    # are <alter>/<alter-head>, which we deliberately do NOT count here.
    key_alter_present = bool(re.search(r'<key-alter\b', content))

    # ── Ashokan tell ────────────────────────────────────────────────────────
    # Find all <rest …> elements and check whether their bounds x < header_stop.
    # We only care about the first staff (system 1), but since other staves
    # typically have the same header_stop, any matching rest is a problem.
    ashokan_tell = False
    if header_stop is not None:
        for rm in re.finditer(r'<rest\s[^>]*/?>|<rest\s[^>]*>', content):
            # Look for <bounds …> immediately after the rest open tag
            after = content[rm.end(): rm.end() + 300]
            bm = re.search(r'<bounds\s+x="(\d+)"', after)
            if bm and int(bm.group(1)) < header_stop:
                ashokan_tell = True
                break

    # ── Grades ──────────────────────────────────────────────────────────────
    # Prefer ctx-grade when available; fall back to grade.
    # Strategy: collect all ctx-grade values first, then all grade values from
    # elements that lack ctx-grade.
    # Simpler and robust: just collect all ctx-grade attributes, supplemented
    # by grade attributes on elements that have no ctx-grade.
    # Easiest accurate approach: grab every element line's ctx-grade if present
    # else grade; average those.
    grades = []
    # Each inter element is typically on one line with attributes including
    # grade="…" and optionally ctx-grade="…".
    for line in content.split("\n"):
        ctx_m = re.search(r'\bctx-grade="([0-9.]+)"', line)
        if ctx_m:
            grades.append(float(ctx_m.group(1)))
        else:
            g_m = re.search(r'\bgrade="([0-9.]+)"', line)
            if g_m:
                grades.append(float(g_m.group(1)))

    avg_grade = (sum(grades) / len(grades)) if grades else 0.5

    # ── Measure count ───────────────────────────────────────────────────────
    mc_m = re.search(r'<page\s[^>]*\bmeasure-count="(\d+)"', content)
    if mc_m:
        measure_count = int(mc_m.group(1))
    else:
        # fall back: count <measure id=…> elements
        measure_count = len(re.findall(r'<measure\s+id=', content))

    return {
        "key_ok":            key_ok,
        "key_in_any_header": key_in_any_header,
        "key_alter_present": key_alter_present,
        "time_ok":           time_ok,
        "ashokan_tell":      ashokan_tell,
        "avg_grade":         avg_grade,
        "measure_count":     measure_count,
    }


def score_omr(omr_path: str) -> dict | None:
    """
    Open an .omr file (ZIP), parse the sheet XML, compute health score.
    Returns a result dict or None on error.
    """
    tune_name = os.path.basename(os.path.dirname(omr_path))

    try:
        with zipfile.ZipFile(omr_path, "r") as zf:
            names = zf.namelist()
            sheet_file = "sheet#1/sheet#1.xml"
            if sheet_file not in names:
                print(f"WARNING: {omr_path}: no sheet#1/sheet#1.xml", file=sys.stderr)
                return None
            content = zf.read(sheet_file).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, OSError) as e:
        print(f"WARNING: {omr_path}: {e}", file=sys.stderr)
        return None

    c = parse_sheet_xml(content)

    # ── Key-signature triage ─────────────────────────────────────────────────
    #   present — recognised in the first staff header (nothing to fix)
    #   missed  — not in the first header, but there is evidence of a printed key
    #             sig elsewhere (later-system header, a stray key-alter glyph, or
    #             an ashokan rest inside the header band) → a real fix
    #   absent  — no evidence of any key sig → probably genuinely keyless (correct)
    if c["key_ok"]:
        key_status = "present"
    elif c["key_in_any_header"] or c["key_alter_present"] or c["ashokan_tell"]:
        key_status = "missed"
    else:
        key_status = "absent"

    # Compute score
    score = BASE_SCORE
    if key_status == "missed":
        score += W_KEY_MISSING
    if not c["time_ok"]:
        score += W_TIME_MISSING
    if c["ashokan_tell"]:
        score += W_ASHOKAN_TELL
    score += (c["avg_grade"] - 0.5) * W_GRADE_SCALE

    return {
        "tune_name":     tune_name,
        "health_score":  round(score, 2),
        "key_status":    key_status,
        "key_ok":        c["key_ok"],
        "time_ok":       c["time_ok"],
        "ashokan_tell":  c["ashokan_tell"],
        "avg_grade":     round(c["avg_grade"], 4),
        "measure_count": c["measure_count"],
        "omr_path":      os.path.abspath(omr_path),
    }


def main():
    if len(sys.argv) > 1:
        omr_paths = sys.argv[1:]
    else:
        omr_paths = find_all_omr_files()
        if not omr_paths:
            print(f"No clean.omr files found under {BATCH_DIR}", file=sys.stderr)
            sys.exit(1)

    results = []
    for path in omr_paths:
        r = score_omr(path)
        if r is not None:
            results.append(r)

    # Sort worst-first (lowest score first)
    results.sort(key=lambda r: r["health_score"])

    print(TSV_HEADER)
    for r in results:
        print("\t".join([
            r["tune_name"],
            str(r["health_score"]),
            r["key_status"],
            str(r["key_ok"]),
            str(r["time_ok"]),
            str(r["ashokan_tell"]),
            str(r["avg_grade"]),
            str(r["measure_count"]),
            r["omr_path"],
        ]))


if __name__ == "__main__":
    main()
