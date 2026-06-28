#!/usr/bin/env python3
"""Build the two WOFTA tune PDFs:
  1. WOFTA_tunes.pdf            — every tune, engraved (verified ABC) preferred
     over scan; engraved tunes get a sepia wash; alphabetical TOC.
  2. WOFTA_tunes_comparison.pdf — engraved tunes, scan-left / engraving-right.

Run via ./make_pdf.sh (activates the venv and opens both in Firefox)."""
import glob
import os
import sys

import make_pdf as mp


def main():
    main_out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"
    comp_out = os.path.splitext(main_out)[0] + "_comparison.pdf"

    here = os.path.dirname(os.path.abspath(__file__))
    scan_dir = os.path.join(here, "source_images")
    abc_dir = os.path.join(here, "notation_pipeline", "abc")

    scans = {mp.stem_of(p): p for p in glob.glob(os.path.join(scan_dir, "*.png"))}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(abc_dir, "*-verified.abc"))}

    tunes = sorted(set(scans) | set(verified),
                   key=lambda s: s.lower().replace("-", " "))
    if not tunes:
        print("No tunes found.", file=sys.stderr)
        sys.exit(1)

    entries = []
    for t in tunes:
        if t in verified:
            entries.append((t, "abc", verified[t], {}))
        else:
            entries.append((t, "png", scans[t], {}))

    n_eng = sum(1 for _, kind, _, _ in entries if kind == "abc")
    print(f"=== Book PDF: {len(entries)} tunes "
          f"({n_eng} engraved, {len(entries) - n_eng} scanned) ===")
    mp.build_book(entries, output=main_out, sepia=True, toc_alphabetical=True,
                  toc_title="WOFTA Chapter 5 2026 Book")

    print(f"\n=== Comparison PDF: {len(verified)} engraved tune(s), portrait packed ===")
    mp.make_comparison_pdf(verified, scans, comp_out, sepia=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
