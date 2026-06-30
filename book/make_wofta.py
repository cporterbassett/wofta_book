#!/usr/bin/env python3
"""Build the main WOFTA tune PDF:
  WOFTA_tunes.pdf — every tune, engraved (verified ABC) preferred over scan;
  engraved tunes get a sepia wash; alphabetical TOC.

The scan-vs-engraving comparison PDF is built separately, on demand, via
bin/build_comparison.sh (book/make_comparison.py).

Run via bin/build_wofta.sh (activates the venv and opens the book in Firefox)."""
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


def load_roster():
    """Return (scans, verified, allow) validated against disk.

    scans:    {tune -> scan png path} (top-level + verified/ subdir)
    verified: {tune -> verified ABC path}
    allow:    set of roster keys from wofta_tunes.txt
    """
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

    return scans, verified, allow


def main():
    main_out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"

    scans, verified, allow = load_roster()

    # Keep only listed tunes; files on disk that aren't listed are ignored.
    tunes = sorted((t for t in set(scans) | set(verified) if t in allow),
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

    print("\nDone.")


if __name__ == "__main__":
    main()
