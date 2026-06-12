#!/usr/bin/env python3
"""
Experiment D: Sweep Audiveris -constant values over a source-diverse test set.

For each (constant_value, tune) pair:
  1. Uses the existing preprocessed.png in batch_output/<Tune>/
  2. Runs Audiveris batch with -constant <name>=<value> (or no override for baseline)
  3. Scores the resulting raw .omr with health_score logic (no clean_omr.py — we want
     to see what Audiveris itself detected, not what was stripped)
  4. Prints a comparison table

Usage:
    python3 sweep_constants.py
    python3 sweep_constants.py --constant org.audiveris.omr.glyph.Grades.keyAlterMinGrade1 \\
                               --values 0.2,0.3,0.4,0.45,0.5 \\
                               --tunes "Big Scioty,Arkansas Traveler,Ashokan Farewell"
    python3 sweep_constants.py --constant org.audiveris.omr.image.AdaptiveFilter.halfWindowSize \\
                               --values 8,12,16,20,24

Note: 'baseline' in --values runs Audiveris without any -constant override.
"""

import sys
import os
import argparse
import subprocess
import tempfile
import shutil
import zipfile
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BATCH_DIR = os.path.join(SCRIPT_DIR, "batch_output")
AUDIVERIS = "flatpak run org.audiveris.audiveris"

# Source-diverse sample: mix of key-fail and key-pass tunes, hopefully different typesetters
DEFAULT_TUNES = [
    "Big Scioty",            # key_ok=False, time_ok=False, avg_grade=0.91 — complete failure
    "Miss McCloud's Reel",   # key_ok=False, time_ok=False, avg_grade=0.86 — different source
    "Big Con",               # key_ok=False, time_ok=True,  avg_grade=0.93 — key only fail
    "Billy in the Lowground",# key_ok=False, time_ok=True,  avg_grade=0.92 — key only fail
    "Ashokan Farewell",      # key_ok=True,  ashokan_tell — second sharp barely missed
    "Arkansas Traveler",     # key_ok=True,  no tell — passing control (K:D)
    "Angeline the Baker",    # well-studied, K:D — known reference
]

DEFAULT_CONSTANT = "org.audiveris.omr.glyph.Grades.keyAlterMinGrade1"
DEFAULT_VALUES = ["baseline", "0.5", "0.45", "0.4", "0.35", "0.3"]


def parse_sheet_xml(content: str) -> dict:
    """Parse sheet#1.xml and return health components (same logic as health_score.py)."""
    header_m = re.search(
        r'<header\s+start="(\d+)"\s+stop="(\d+)">(.*?)</header>',
        content, re.DOTALL
    )
    header_stop = int(header_m.group(2)) if header_m else None
    header_body = header_m.group(3) if header_m else ""

    key_ok  = bool(re.search(r'<key\s*>', header_body))
    time_ok = bool(re.search(r'<time\s*>', header_body))

    ashokan_tell = False
    if header_stop is not None:
        for rm in re.finditer(r'<rest\s[^>]*/?>|<rest\s[^>]*>', content):
            after = content[rm.end(): rm.end() + 300]
            bm = re.search(r'<bounds\s+x="(\d+)"', after)
            if bm and int(bm.group(1)) < header_stop:
                ashokan_tell = True
                break

    grades = []
    for line in content.split("\n"):
        ctx_m = re.search(r'\bctx-grade="([0-9.]+)"', line)
        if ctx_m:
            grades.append(float(ctx_m.group(1)))
        else:
            g_m = re.search(r'\bgrade="([0-9.]+)"', line)
            if g_m:
                grades.append(float(g_m.group(1)))
    avg_grade = (sum(grades) / len(grades)) if grades else 0.5

    mc_m = re.search(r'<page\s[^>]*\bmeasure-count="(\d+)"', content)
    measure_count = int(mc_m.group(1)) if mc_m else len(re.findall(r'<measure\s+id=', content))

    return {"key_ok": key_ok, "time_ok": time_ok, "ashokan_tell": ashokan_tell,
            "avg_grade": avg_grade, "measure_count": measure_count}


def score_omr_file(omr_path: str) -> dict | None:
    """Score a raw Audiveris .omr file (ZIP). Returns None on error."""
    try:
        with zipfile.ZipFile(omr_path, "r") as zf:
            names = zf.namelist()
            sheet_file = "sheet#1/sheet#1.xml"
            if sheet_file not in names:
                return None
            content = zf.read(sheet_file).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, OSError):
        return None

    c = parse_sheet_xml(content)
    score = 100
    if not c["key_ok"]:   score -= 40
    if not c["time_ok"]:  score -= 20
    if c["ashokan_tell"]: score -= 30
    score += (c["avg_grade"] - 0.5) * 20
    c["health_score"] = round(score, 2)
    return c


def run_audiveris(png_path: str, output_dir: str, constant: str | None, value: str | None,
                  timeout: int = 120) -> str | None:
    """Run Audiveris batch. Returns path to the .omr file, or None on failure."""
    cmd = AUDIVERIS.split() + ["-batch", "-export", "-output", output_dir]
    if constant and value:
        cmd += ["-constant", f"{constant}={value}"]
    cmd.append(png_path)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None

    omr_candidates = []
    for fname in os.listdir(output_dir):
        if fname.endswith(".omr"):
            omr_candidates.append(os.path.join(output_dir, fname))
    return omr_candidates[0] if omr_candidates else None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--constant", default=DEFAULT_CONSTANT,
                        help=f"Audiveris constant to sweep (default: {DEFAULT_CONSTANT})")
    parser.add_argument("--values", default=",".join(DEFAULT_VALUES),
                        help="Comma-separated values to try; use 'baseline' for no override")
    parser.add_argument("--tunes", default=",".join(DEFAULT_TUNES),
                        help="Comma-separated tune names (must exist in batch_output/)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Audiveris timeout per run in seconds (default: 120)")
    args = parser.parse_args()

    constant = args.constant
    values = [v.strip() for v in args.values.split(",")]
    tunes = [t.strip() for t in args.tunes.split(",")]

    # Validate tunes
    valid_tunes = []
    for tune in tunes:
        png = os.path.join(BATCH_DIR, tune, "preprocessed.png")
        if not os.path.isfile(png):
            print(f"WARNING: skipping {tune!r} — no preprocessed.png found", file=sys.stderr)
        else:
            valid_tunes.append(tune)
    if not valid_tunes:
        print("ERROR: no valid tunes to process", file=sys.stderr)
        sys.exit(1)

    short_name = constant.split(".")[-1]
    total = len(values) * len(valid_tunes)
    print(f"Experiment D: sweeping {short_name}")
    print(f"  Constant : {constant}")
    print(f"  Values   : {values}")
    print(f"  Tunes    : {valid_tunes}")
    print(f"  Runs     : {total}")
    print()

    # Results: dict[(value, tune)] = score_dict or None
    results = {}

    run_num = 0
    for value in values:
        for tune in valid_tunes:
            run_num += 1
            png = os.path.join(BATCH_DIR, tune, "preprocessed.png")
            label = "baseline" if value == "baseline" else f"{short_name}={value}"
            print(f"[{run_num:2d}/{total}] {label:35s}  {tune}", flush=True)

            tmpdir = tempfile.mkdtemp(prefix="sweep_exp_d_", dir=BATCH_DIR)
            try:
                t0 = time.time()
                cv = None if value == "baseline" else value
                omr_path = run_audiveris(png, tmpdir, constant if cv else None, cv,
                                         timeout=args.timeout)
                elapsed = time.time() - t0

                if omr_path:
                    score = score_omr_file(omr_path)
                    results[(value, tune)] = score
                    if score:
                        k = "Y" if score["key_ok"] else "N"
                        t = "Y" if score["time_ok"] else "N"
                        a = "A" if score["ashokan_tell"] else "."
                        h = score["health_score"]
                        print(f"         → key={k} time={t} ashokan={a}  health={h:6.1f}  ({elapsed:.0f}s)")
                    else:
                        results[(value, tune)] = None
                        print(f"         → score_omr failed  ({elapsed:.0f}s)")
                else:
                    results[(value, tune)] = None
                    print(f"         → Audiveris produced no .omr  ({elapsed:.0f}s)")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Summary table ──────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(f"SUMMARY — {short_name} sweep")
    print("=" * 70)

    # Column header: tune names (abbreviated)
    abbrevs = [t[:18] for t in valid_tunes]
    col_w = 20
    val_w = 10

    header = f"{'value':{val_w}}" + "".join(f"{a:{col_w}}" for a in abbrevs)
    print(header)
    print("-" * len(header))

    for value in values:
        row = f"{value:{val_w}}"
        for tune in valid_tunes:
            r = results.get((value, tune))
            if r is None:
                cell = "ERR"
            else:
                k = "K" if r["key_ok"] else "."
                t = "T" if r["time_ok"] else "."
                a = "A" if r["ashokan_tell"] else "."
                h = f"{r['health_score']:.0f}"
                cell = f"{k}{t}{a}  h={h}"
            row += f"{cell:{col_w}}"
        print(row)

    print()
    print("Legend: K=key_ok T=time_ok A=ashokan_tell h=health_score")

    # ── Key detection improvement summary ─────────────────────────────────────
    print()
    print("Key detection improvement (tunes where key was FAILING at baseline):")
    for tune in valid_tunes:
        baseline = results.get(("baseline", tune))
        if baseline is None or baseline["key_ok"]:
            continue  # skip tunes already passing at baseline
        improvements = []
        for value in values:
            if value == "baseline":
                continue
            r = results.get((value, tune))
            if r and r["key_ok"]:
                improvements.append(value)
        if improvements:
            print(f"  {tune}: key fixed at values {improvements}")
        else:
            print(f"  {tune}: key still failing at all tested values")

    print()
    print("False-positive check (tunes passing at baseline that BROKE):")
    for tune in valid_tunes:
        baseline = results.get(("baseline", tune))
        if baseline is None or not baseline["key_ok"]:
            continue  # only check tunes that were passing
        regressions = []
        for value in values:
            if value == "baseline":
                continue
            r = results.get((value, tune))
            if r and not r["key_ok"]:
                regressions.append(value)
        if regressions:
            print(f"  {tune}: key BROKE at values {regressions}")
        else:
            print(f"  {tune}: no regressions")


if __name__ == "__main__":
    main()
