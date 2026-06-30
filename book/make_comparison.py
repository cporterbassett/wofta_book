#!/usr/bin/env python3
"""Build the scan-vs-engraving comparison PDF:
  WOFTA_tunes_comparison.pdf — engraved tunes, scan-left / engraving-right,
  portrait-packed. Rows are ordered by CREATION date (oldest at top, newest at
  bottom); see docs/verified_creation_order.md.

Run via bin/build_comparison.sh (activates the venv and opens it in Firefox)."""
import sys

import make_pdf as mp
from make_wofta import load_roster


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes_comparison.pdf"

    scans, verified, allow = load_roster()

    # Only engraved tunes that are on the roster.
    verified_listed = {t: p for t, p in verified.items() if t in allow}
    if not verified_listed:
        print("No engraved tunes found.", file=sys.stderr)
        sys.exit(1)

    print(f"=== Comparison PDF: {len(verified_listed)} engraved tune(s), "
          f"portrait packed, creation order ===")
    mp.make_comparison_pdf(verified_listed, scans, out, sepia=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
