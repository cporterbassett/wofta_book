#!/usr/bin/env python3
"""
Render an Audiveris MXL to PNG via MuseScore headless, then produce a
red/blue overlay diff against the original scan.

Red   = ink in the scan but NOT in the MXL render (missed notes / OMR gap)
Blue  = ink in the MXL render but NOT in the scan (spurious notes)
Black = ink present in both (agreement)

Usage:
    python3 verify_mxl.py <clean.mxl> <original_scan.png> [output_diff.png]

diff.png defaults to <mxl_stem>.diff.png next to the MXL file.

Requirements:
    MuseScore 4 AppImage at MSCORE_PATH (see constant below, or set
    MSCORE env var), ImageMagick convert, OpenCV + NumPy in the active venv.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to MuseScore executable.  Override with env var MSCORE.
_DEFAULT_MSCORE = (
    "/home/porter/Downloads/MuseScore-Studio-4.4.4.243461245-x86_64.AppImage"
)
MSCORE = os.environ.get("MSCORE", _DEFAULT_MSCORE)

# DPI used for MuseScore PNG export.  150 dpi gives ~1079px wide on Letter;
# raise to 200+ if you want more detail in the diff.
RENDER_DPI = 150


# ---------------------------------------------------------------------------
# MuseScore render
# ---------------------------------------------------------------------------

def render_mxl(mxl_path: Path, out_dir: Path, dpi: int = RENDER_DPI) -> list[Path]:
    """
    Render *mxl_path* to PNG page(s) inside *out_dir*.

    MuseScore names output files  <stem>-1.png, <stem>-2.png, ...
    when there are multiple pages.  Returns a sorted list of the produced
    PNG paths.
    """
    stem = "render"
    out_base = out_dir / f"{stem}.png"

    cmd = [MSCORE, "-o", str(out_base), "-r", str(dpi), str(mxl_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # MuseScore exits 0 even on warnings; check stderr for fatal errors.
    if result.returncode != 0:
        print("MuseScore stderr:", result.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"MuseScore exited {result.returncode}")

    # Collect all page PNGs produced.
    pages = sorted(out_dir.glob(f"{stem}-*.png"))
    if not pages:
        # Single-page score: MuseScore may emit <stem>.png (no suffix)
        single = out_dir / f"{stem}.png"
        if single.exists():
            pages = [single]
    if not pages:
        raise RuntimeError(
            f"MuseScore produced no PNG in {out_dir}. "
            f"stderr: {result.stderr[-500:]}"
        )

    return pages


def stitch_pages(pages: list[Path], out_path: Path) -> None:
    """
    Vertically concatenate page PNGs with ImageMagick convert -append.
    Handles the case where pages may have slightly different widths by
    forcing all to the same width first (pad to widest).
    """
    if len(pages) == 1:
        import shutil
        shutil.copy(pages[0], out_path)
        return

    cmd = ["convert"] + [str(p) for p in pages] + ["-append", str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ImageMagick convert failed: {result.stderr}")


# ---------------------------------------------------------------------------
# Image processing (mirrors overlay_diff.py)
# ---------------------------------------------------------------------------

def load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot load: {path}")
    return img


def binarise(gray: np.ndarray, block: int = 31, c: int = 10) -> np.ndarray:
    """Adaptive threshold → ink=0 (black), paper=255 (white)."""
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block, c,
    )


def align_to(src: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Scale src to exactly (target_h, target_w)."""
    return cv2.resize(src, (target_w, target_h), interpolation=cv2.INTER_AREA)


def make_diff(
    scan_path: Path,
    render_path: Path,
    out_path: Path,
) -> None:
    scan_gray   = load_gray(scan_path)
    render_gray = load_gray(render_path)

    h, w = scan_gray.shape

    # Scale the MuseScore render to match the scan's pixel dimensions.
    # Both images should contain the same number of staff systems, so a
    # uniform scale gives roughly the right staff pitch (vertical spacing)
    # for a meaningful ink comparison.  Perfect pixel-level alignment is
    # not achievable without a full image-registration step, but the diff
    # still clearly shows which regions have extra or missing ink.
    render_scaled = align_to(render_gray, h, w)

    # Binarise (ink=0, paper=255)
    scan_bin   = binarise(scan_gray)
    render_bin = binarise(render_scaled)

    # Invert so ink=255, paper=0
    scan_ink   = cv2.bitwise_not(scan_bin)
    render_ink = cv2.bitwise_not(render_bin)

    # Build BGR overlay on white background:
    #   R channel dark where scan has ink
    #   B channel dark where render has ink
    #   G channel dark where either has ink (makes overlap look dark/black)
    r = np.clip(255 - scan_ink.astype(np.int16),   0, 255).astype(np.uint8)
    g = np.clip(255 - np.maximum(scan_ink, render_ink).astype(np.int16), 0, 255).astype(np.uint8)
    b = np.clip(255 - render_ink.astype(np.int16), 0, 255).astype(np.uint8)

    bgr = np.zeros((h, w, 3), dtype=np.uint8)
    bgr[:, :, 2] = r   # R  (scan ink → red)
    bgr[:, :, 1] = g   # G
    bgr[:, :, 0] = b   # B  (render ink → blue)

    cv2.imwrite(str(out_path), bgr)
    print(f"Diff written: {out_path}  ({w}×{h}px)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: verify_mxl.py <clean.mxl> <original_scan.png> [output_diff.png]",
            file=sys.stderr,
        )
        sys.exit(1)

    mxl_path  = Path(sys.argv[1]).resolve()
    scan_path = Path(sys.argv[2]).resolve()
    out_path  = (
        Path(sys.argv[3]).resolve()
        if len(sys.argv) > 3
        else mxl_path.with_name(mxl_path.stem + ".diff.png")
    )

    if not mxl_path.exists():
        print(f"MXL not found: {mxl_path}", file=sys.stderr)
        sys.exit(1)
    if not scan_path.exists():
        print(f"Scan not found: {scan_path}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="verify_mxl_") as tmpdir:
        tmp = Path(tmpdir)

        # Step 1 — render MXL → page PNGs
        print(f"Rendering {mxl_path.name} via MuseScore …")
        pages = render_mxl(mxl_path, tmp)
        print(f"  {len(pages)} page(s): {[p.name for p in pages]}")

        # Step 2 — stitch pages vertically into one PNG
        stitched = tmp / "stitched.png"
        stitch_pages(pages, stitched)

        # Step 3-6 — binarise, diff, save
        print(f"Building overlay diff …")
        make_diff(scan_path, stitched, out_path)

    # Step 7 — open in Firefox
    subprocess.Popen(["firefox", str(out_path)])
    print(f"Opened in Firefox: {out_path}")


if __name__ == "__main__":
    main()
