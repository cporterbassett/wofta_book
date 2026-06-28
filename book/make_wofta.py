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

# Authoritative roster: only tunes whose membership key appears here go in the
# book. See book/wofta_tunes.txt for the format and how the list was derived.
LIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "wofta_tunes.txt")


def load_allowlist(path):
    with open(path) as f:
        return {line.strip() for line in f
                if line.strip() and not line.startswith("#")}


def main():
    main_out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"
    comp_out = os.path.splitext(main_out)[0] + "_comparison.pdf"

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scan_dir = os.path.join(here, "sources", "scans")
    abc_dir = os.path.join(here, "abc")

    # Top-level scans are the unverified tunes; verified tunes' scans live in
    # scans/verified/. Include both so the comparison PDF can show every
    # engraved tune beside its original scan (top-level wins on the rare overlap).
    scan_paths = (glob.glob(os.path.join(scan_dir, "verified", "*.png"))
                  + glob.glob(os.path.join(scan_dir, "*.png")))
    scans = {mp.stem_of(p): p for p in scan_paths}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(abc_dir, "*-verified.abc"))}

    allow = load_allowlist(LIST_PATH)

    # Validate the roster against disk: every listed key must match a current
    # file (a top-level scan stem or a verified-ABC stem). A key with no file
    # means the list has drifted out of sync — fail loudly.
    on_disk = set(scans) | set(verified)
    missing = sorted(allow - on_disk)
    if missing:
        print("ERROR: wofta_tunes.txt lists tunes with no matching file:",
              file=sys.stderr)
        for k in missing:
            print(f"  {k}", file=sys.stderr)
        sys.exit(1)

    # Keep only listed tunes; files on disk that aren't listed are ignored.
    tunes = sorted((t for t in on_disk if t in allow),
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

    # Comparison PDF: only engraved tunes that are on the roster.
    verified_listed = {t: p for t, p in verified.items() if t in allow}
    print(f"\n=== Comparison PDF: {len(verified_listed)} engraved tune(s), portrait packed ===")
    mp.make_comparison_pdf(verified_listed, scans, comp_out, sepia=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
