#!/usr/bin/env python3
"""Split PDF sheet music pages into individual tune images.

Detection strategy: a tune boundary is a whitespace gap followed by content
whose horizontal spread is narrow (title text, not a full-width staff line),
AND a full-width staff line appears 50-400 rows later (the music that follows
the title). This correctly rejects "Fiddle" labels (staff line appears within
~20 rows) and lyric lines at page bottom (no staff line follows at all).
"""

import sys
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

DPI = 200
DARK_THRESHOLD = 180       # pixels below this are considered dark ink
WHITE_ROW_FRAC = 0.01      # row is "whitespace" when < this fraction is dark
MIN_GAP_ROWS = 12          # minimum whitespace run to examine as a potential boundary
TITLE_SPREAD_MAX = 0.65    # post-gap content narrower than this → could be a title
STAFF_SPAN_MIN = 0.58      # a staff-line row spans at least this fraction of page width
STAFF_COVER_MIN = 0.15     # and has at least this dark-pixel coverage
STAFF_DIST_MIN = 70        # title must be at least this many rows before first staff line
STAFF_DIST_MAX = 400       # but music must start within this many rows (no orphaned titles)
MIN_TUNE_ROWS = 60         # a detected tune region must be at least this tall
MARGIN_PX = 15             # padding pixels added above/below each crop


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

def _gap_runs(is_white: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    """Return (start, end) of each whitespace run of at least min_len rows."""
    runs: list[tuple[int, int]] = []
    in_gap = False
    gs = 0
    for i, w in enumerate(is_white):
        if w and not in_gap:
            in_gap = True; gs = i
        elif not w and in_gap:
            in_gap = False
            if i - gs >= min_len:
                runs.append((gs, i))
    if in_gap and len(is_white) - gs >= min_len:
        runs.append((gs, len(is_white)))
    return runs


def _first_staff_row(dark: np.ndarray, start: int, page_width: int,
                     max_search: int = 500) -> int | None:
    """Return row index of first staff-line-like row at or after `start`."""
    end = min(start + max_search, dark.shape[0])
    for r in range(start, end):
        cols = np.where(dark[r])[0]
        if len(cols) == 0:
            continue
        span = (cols[-1] - cols[0]) / page_width
        cover = len(cols) / page_width
        if span >= STAFF_SPAN_MIN and cover >= STAFF_COVER_MIN:
            return r
    return None


def _post_gap_spread(dark: np.ndarray, is_white: np.ndarray,
                     gap_end: int, page_width: int,
                     n_rows: int = 10) -> float | None:
    """Median horizontal spread of the first n_rows of content after gap_end."""
    content: list[int] = []
    for r in range(gap_end, min(gap_end + 100, dark.shape[0])):
        if not is_white[r]:
            content.append(r)
        if len(content) >= n_rows:
            break
    if not content:
        return None
    spreads: list[float] = []
    for r in content:
        cols = np.where(dark[r])[0]
        if len(cols) > 3:
            spreads.append((cols[-1] - cols[0]) / page_width)
    return float(np.median(spreads)) if spreads else None


def find_tune_regions(image_path: Path) -> list[tuple[int, int]]:
    """Return (top, bottom) pixel pairs for each tune detected on the page."""
    arr = np.array(Image.open(image_path).convert("L"))
    dark = arr < DARK_THRESHOLD
    page_width = arr.shape[1]
    page_height = arr.shape[0]

    dark_count = dark.sum(axis=1)
    is_white = dark_count < (page_width * WHITE_ROW_FRAC)

    gaps = _gap_runs(is_white, MIN_GAP_ROWS)

    tune_boundary_rows: list[int] = []   # row where each tune starts (incl. top margin)

    for g_start, g_end in gaps:
        spread = _post_gap_spread(dark, is_white, g_end, page_width)
        if spread is None:
            continue  # nothing after this gap (bottom of page)
        if spread >= TITLE_SPREAD_MAX:
            continue  # wide content = chord symbols or staff line, not a title

        # Narrow content after gap — could be a title. Check distance to first staff line.
        first_staff = _first_staff_row(dark, g_end, page_width, max_search=STAFF_DIST_MAX + 50)
        if first_staff is None:
            continue  # no staff line follows (orphaned text at bottom)

        dist = first_staff - g_end
        if STAFF_DIST_MIN <= dist <= STAFF_DIST_MAX:
            tune_boundary_rows.append(g_start)

    if not tune_boundary_rows:
        # No boundaries found — whole page is one tune
        content = np.where(~is_white)[0]
        if len(content) == 0:
            return []
        return [(int(content[0]), int(content[-1]))]

    # Build regions: each boundary → next boundary (or page end)
    tune_regions: list[tuple[int, int]] = []
    for i, brow in enumerate(tune_boundary_rows):
        region_end = tune_boundary_rows[i + 1] if i + 1 < len(tune_boundary_rows) else page_height
        content_in_range = np.where(~is_white[brow:region_end])[0] + brow
        if len(content_in_range) == 0:
            continue
        top = int(content_in_range[0])
        bottom = int(content_in_range[-1])
        if bottom - top >= MIN_TUNE_ROWS:
            tune_regions.append((top, bottom))

    return tune_regions


# ---------------------------------------------------------------------------
# Splitting and output
# ---------------------------------------------------------------------------

def render_pdf_pages(pdf_path: Path, output_dir: str) -> list[Path]:
    prefix = str(Path(output_dir) / "page")
    result = subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-png", str(pdf_path), prefix],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr}")
    return sorted(Path(output_dir).glob("page-*.png"))


def split_page(image_path: Path, regions: list[tuple[int, int]],
               output_dir: Path, counter: int) -> list[str]:
    """Save crops, return list of output filenames written."""
    img = Image.open(image_path)
    width, height = img.size
    written: list[str] = []
    for top, bottom in regions:
        crop = img.crop((0, max(0, top - MARGIN_PX), width, min(height, bottom + MARGIN_PX)))
        name = f"tune_{counter:03d}.png"
        crop.save(output_dir / name)
        print(f"    {name}  ({bottom - top} px tall)")
        written.append(name)
        counter += 1
    return written


def generate_html(output_dir: Path, pdf_name: str,
                  page_records: list[tuple[str, list[str]]]) -> None:
    """Write index.html into output_dir showing all tunes grouped by page."""
    rows = []
    for page_label, filenames in page_records:
        rows.append(f'<tr class="page-header"><td colspan="2">— {page_label} —</td></tr>')
        for fname in filenames:
            rows.append(
                f'<tr><td class="label">{fname}</td>'
                f'<td><img src="{fname}" alt="{fname}"></td></tr>'
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{pdf_name} — tune splits</title>
<style>
  body {{ font-family: sans-serif; background: #f4f4f4; margin: 0; padding: 1em; }}
  h1 {{ font-size: 1.1em; color: #333; }}
  table {{ border-collapse: collapse; width: 100%; }}
  tr.page-header td {{
    background: #2c5f8a; color: #fff; font-weight: bold;
    padding: 6px 10px; font-size: 0.9em; letter-spacing: 0.05em;
  }}
  td.label {{
    vertical-align: top; padding: 8px 12px 8px 4px;
    font-size: 0.8em; color: #555; white-space: nowrap; width: 1%;
  }}
  td img {{ max-width: 900px; display: block; border: 1px solid #ccc;
             background: #fff; margin: 4px 0; }}
  tr:hover td img {{ border-color: #2c5f8a; }}
</style>
</head>
<body>
<h1>{pdf_name} — {sum(len(f) for _, f in page_records)} tunes extracted</h1>
<table>
{''.join(rows)}
</table>
</body>
</html>
"""
    out = output_dir / "index.html"
    out.write_text(html)
    print(f"  → viewer: {out}")


def process_pdf(pdf_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{pdf_path.name}")
    page_records: list[tuple[str, list[str]]] = []
    counter = 1
    with tempfile.TemporaryDirectory() as tmpdir:
        pages = render_pdf_pages(pdf_path, tmpdir)
        for page_path in pages:
            page_num = page_path.stem.split("-")[-1]
            regions = find_tune_regions(page_path)
            if not regions:
                print(f"  page {page_num}: (blank/skipped)")
                continue
            print(f"  page {page_num}: {len(regions)} tune(s)")
            written = split_page(page_path, regions, output_dir, counter)
            counter += len(written)
            page_records.append((f"PDF page {page_num}  ({len(written)} tune(s))", written))
    print(f"  → {counter - 1} total tunes extracted to {output_dir}/")
    generate_html(output_dir, pdf_path.name, page_records)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: split_tunes.py <file.pdf> [output_dir]  [file2.pdf ...]")
        sys.exit(1)

    pdfs = [Path(a) for a in args if a.endswith(".pdf")]
    non_pdfs = [a for a in args if not a.endswith(".pdf")]

    for pdf in pdfs:
        if not pdf.exists():
            print(f"Not found: {pdf}", file=sys.stderr)
            continue
        if len(pdfs) == 1 and non_pdfs:
            out = Path(non_pdfs[0])
        else:
            out = pdf.parent / (pdf.stem + "_tunes")
        process_pdf(pdf, out)


if __name__ == "__main__":
    main()
