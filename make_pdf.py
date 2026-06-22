#!/usr/bin/env python3
"""
Build the two standard WOFTA tune PDFs from the union of scans + verified ABCs.

  1. WOFTA_tunes.pdf            — every tune, prefer the engraved (verified ABC)
                                  rendering over the scan. Engraved tunes get a
                                  sepia wash. Starts with a clickable table of
                                  contents. Letter portrait, tunes packed
                                  vertically (greedy first-fit).
  2. WOFTA_tunes_comparison.pdf — every engraved tune as a portrait row, original
                                  scan on the left, engraving (sepia) on the right,
                                  multiple tunes packed per page.

PNG scans are embedded as raster; ABC files are converted to cropped vector PDFs
via abcm2ps (EPS) + Ghostscript.
"""
import glob
import io
import math
import os
import subprocess
import sys
import tempfile

import img2pdf
import pikepdf
from pikepdf import Array, Dictionary, Name, Pdf
from PIL import Image

PAGE_W = 612
PAGE_H = 792
MARGIN_X = 36
MARGIN_TOP = 36
MARGIN_BOTTOM = 36
GAP_PREFERRED = 28
GAP_FALLBACK = 14
PNG_DPI = 150

# Sepia tint behind engraved (ABC-rendered) tunes, so the crisp vector
# engravings read warm and are easy to tell apart from the scans. Affects ONLY
# engraved tunes; scans are left untouched. Turn off with `SEPIA=0 ./make_pdf.sh`.
SEPIA = os.environ.get("SEPIA", "1") != "0"
SEPIA_RGB = (0.973, 0.937, 0.851)          # #f8efd9 — slight cream


def sort_key(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.lower().replace("-", " ")


def stem_of(path):
    return os.path.splitext(os.path.basename(path))[0]


def pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_op(text, x, y, font, size):
    """A BT..ET text-drawing operator as bytes (latin-1, lossy for odd glyphs)."""
    esc = pdf_escape(text).encode("latin-1", "replace")
    return (f"BT {font} {size} Tf {x:.2f} {y:.2f} Td (".encode()
            + esc + b") Tj ET\n")


def png_to_pdf_bytes(png_path):
    with Image.open(png_path) as img:
        dpi_info = img.info.get("dpi")
        dpi = dpi_info[0] if dpi_info else PNG_DPI
        layout = img2pdf.get_layout_fun((
            img2pdf.in_to_pt(img.size[0] / dpi),
            img2pdf.in_to_pt(img.size[1] / dpi),
        ))
    with open(png_path, "rb") as f:
        return img2pdf.convert(f.read(), layout_fun=layout)


# Same directives render_abc.sh injects, so a tune's PDF engraving matches its
# comparison render: line-start measure numbers, bold chords + volta numbers.
ABC_DIRECTIVES = (
    "%%measurenb 0\n"
    "%%contbarnb 1\n"  # count 1st/2nd endings as separate measures (match the WOFTA scans)
    "%%measurefont Times-Italic 9\n"
    "%%titlefont Times-Bold 24\n"
    "%%gchordfont Helvetica-Bold 12\n"
    "%%repeatfont Helvetica-Bold 9\n"
)


def abc_to_pdf_bytes(abc_path):
    """Convert an ABC file to a content-cropped vector PDF via abcm2ps (EPS) + Ghostscript.

    abcm2ps declares the full page as its EPS BoundingBox even though the
    notation only occupies the centre (margins ~50pt each side). We use
    gs -sDEVICE=bbox to find the actual drawn extents, then re-render with
    those exact dimensions so the resulting PDF contains only the notation —
    no empty margin strips — and scales correctly alongside the scanned PNGs.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_abc = os.path.join(tmpdir, "tune.abc")
        with open(abc_path) as src:
            abc_src = src.read()

        def render(extra=""):
            with open(tmp_abc, "w") as out:
                out.write(extra)
                out.write(ABC_DIRECTIVES)
                out.write(abc_src)
            # Don't use check=True: abcm2ps exits non-zero on cosmetic warnings
            # (e.g. "Line too much shrunk") while still emitting valid EPS. Only a
            # missing EPS is a real failure.
            return subprocess.run(
                ["abcm2ps", "-E", "-s", "1.0", "-O", "out", "tune.abc"],
                capture_output=True, cwd=tmpdir,
            )

        result = render()

        # -E (EPS) mode uses a narrow default staff width and auto-wraps any line
        # that doesn't fit, ignoring the tune's `$` line breaks — so dense tunes
        # (e.g. Dill Pickles Rag) render with the wrong, early breaks in the PDF.
        # When abcm2ps reports an overfull/shrunk line, re-render with a wide page
        # so every `$`-delimited line fits on one staff and the intended breaks
        # are kept. Only the few densest tunes trigger this; the rest are
        # unchanged. (Tunes with their own embedded %%pagewidth keep it.)
        stderr = result.stderr.decode("utf-8", "replace").lower()
        if "overfull" in stderr or "shrunk" in stderr:
            for stale in glob.glob(os.path.join(tmpdir, "out*.eps")):
                os.remove(stale)
            render("%%pagewidth 1000pt\n")

        eps_files = sorted(glob.glob(os.path.join(tmpdir, "out*.eps")))
        if not eps_files:
            raise RuntimeError(f"abcm2ps produced no EPS for {abc_path}")

        # Find actual drawn content extents (declared BoundingBox = full page).
        bbox_result = subprocess.run(
            ["gs", "-dBATCH", "-dNOPAUSE", "-dQUIET", "-sDEVICE=bbox", eps_files[0]],
            capture_output=True, text=True,
        )
        llx = lly = 0.0
        urx, ury = 612.0, 792.0
        for line in bbox_result.stderr.splitlines():
            if line.startswith("%%HiResBoundingBox:"):
                parts = line.split()[1:]
                llx, lly, urx, ury = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
                break
        w, h = urx - llx, ury - lly

        pdf_path = os.path.join(tmpdir, "out.pdf")
        subprocess.run(
            ["gs", "-dBATCH", "-dNOPAUSE", "-dQUIET",
             "-sDEVICE=pdfwrite",
             f"-dDEVICEWIDTHPOINTS={w:.3f}",
             f"-dDEVICEHEIGHTPOINTS={h:.3f}",
             "-o", pdf_path,
             "-c", f"<</PageSize [{w:.3f} {h:.3f}] /PageOffset [{-llx:.3f} {-lly:.3f}]>> setpagedevice",
             "-f", eps_files[0]],
            check=True, capture_output=True,
        )
        with open(pdf_path, "rb") as f:
            return f.read()


def get_pdf_size(pdf_bytes):
    with Pdf.open(io.BytesIO(pdf_bytes)) as pdf:
        mb = pdf.pages[0].mediabox
        return float(mb[2]) - float(mb[0]), float(mb[3]) - float(mb[1])


# --- Fonts shared across generated text pages ------------------------------

def make_fonts(out):
    """Return (regular, bold) indirect Helvetica font objects for `out`."""
    reg = out.make_indirect(Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    bold = out.make_indirect(Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/Helvetica-Bold")))
    return reg, bold


def new_page(out, width, height, fonts):
    """Create + append a blank page with F1 (regular) / F2 (bold) fonts."""
    reg, bold = fonts
    page_obj = out.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, width, height]),
        Resources=Dictionary(
            XObject=Dictionary(),
            Font=Dictionary(F1=reg, F2=bold),
        ),
        Contents=out.make_stream(b""),
    ))
    out.pages.append(pikepdf.Page(page_obj))
    return page_obj


def embed_form(out, page_obj, pdf_bytes, name, box, sepia=False):
    """Place a single-page PDF as a form XObject fit (aspect-preserving) into
    `box` = (x, y, w, h), centred horizontally and top-aligned. Returns the
    content-stream bytes to draw it (and an optional sepia wash behind it)."""
    bx, by, bw, bh = box
    with Pdf.open(io.BytesIO(pdf_bytes)) as src:
        mb = src.pages[0].mediabox
        src_w = float(mb[2]) - float(mb[0])
        src_h = float(mb[3]) - float(mb[1])
        xobj = out.copy_foreign(src.pages[0].as_form_xobject())
    page_obj.Resources.XObject[name] = xobj

    scale = min(bw / src_w, bh / src_h)
    draw_w, draw_h = src_w * scale, src_h * scale
    tx = bx + (bw - draw_w) / 2
    ty = by + bh - draw_h          # top-aligned within the box

    content = b""
    if sepia:
        r, g, b = SEPIA_RGB
        content += (f"q {r:.4f} {g:.4f} {b:.4f} rg "
                    f"{tx:.2f} {ty:.2f} {draw_w:.2f} {draw_h:.2f} re f Q\n").encode()
    content += (f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm "
                f"{name} Do Q\n").encode()
    return content


# --- PDF 1: full book with table of contents -------------------------------

def pack_pages(items, gap, usable_h):
    """Greedy first-fit packing. items: list of (fname, scaled_h, pdf_bytes)"""
    pages, current, current_h = [], [], 0
    for item in items:
        h = item[1]
        g = gap if current else 0
        if current and current_h + g + h > usable_h:
            pages.append(current)
            current, current_h = [item], h
        else:
            current.append(item)
            current_h += g + h
    if current:
        pages.append(current)
    return pages


def render_content_page(out, fonts, page_items, usable_w, gap):
    """Composite packed tunes onto a new letter page. Returns the page object."""
    page_obj = new_page(out, PAGE_W, PAGE_H, fonts)
    content = b""
    y = PAGE_H - MARGIN_TOP
    for i, (fname, scaled_h, pdf_bytes) in enumerate(page_items):
        with Pdf.open(io.BytesIO(pdf_bytes)) as src:
            src_w = float(src.pages[0].mediabox[2])
            xobj = out.copy_foreign(src.pages[0].as_form_xobject())
        xobj_name = f"/Fm{i}"
        page_obj.Resources.XObject[xobj_name] = xobj
        scale = usable_w / src_w
        tx = MARGIN_X
        ty = y - scaled_h
        if SEPIA and fname.endswith(".abc"):
            r, g, b = SEPIA_RGB
            content += (f"q {r:.4f} {g:.4f} {b:.4f} rg "
                        f"{tx:.2f} {ty:.2f} {usable_w:.2f} {scaled_h:.2f} re f Q\n").encode()
        content += (f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm "
                    f"{xobj_name} Do Q\n").encode()
        y = ty - gap
    page_obj.Contents = out.make_stream(content)
    return page_obj


TOC_TITLE_H = 44
TOC_LINE_H = 14
TOC_FONT = 10
TOC_COL_GAP = 24


def toc_geometry(n_entries):
    usable_w = PAGE_W - 2 * MARGIN_X
    col_w = (usable_w - TOC_COL_GAP) / 2
    top_y = PAGE_H - MARGIN_TOP - TOC_TITLE_H
    lines_per_col = int((top_y - MARGIN_BOTTOM) / TOC_LINE_H)
    entries_per_page = lines_per_col * 2
    n_pages = max(1, math.ceil(n_entries / entries_per_page))
    return col_w, top_y, lines_per_col, entries_per_page, n_pages


def build_toc_pages(out, fonts, entries, n_toc_pages):
    """entries: list of (name, printed_pageno, dest_page_obj) in display order.
    Builds the TOC pages, inserts them at the front of the document."""
    col_w, top_y, lines_per_col, entries_per_page, _ = toc_geometry(len(entries))
    col_x = [MARGIN_X, MARGIN_X + col_w + TOC_COL_GAP]
    num_w = 34  # reserved right strip for the page number
    name_max_w = col_w - num_w - 6

    toc_page_objs = []
    for p in range(n_toc_pages):
        page_obj = new_page(out, PAGE_W, PAGE_H, fonts)
        content = text_op("Contents", MARGIN_X, PAGE_H - MARGIN_TOP - 22, "/F2", 20)
        annots = []
        chunk = entries[p * entries_per_page:(p + 1) * entries_per_page]
        for j, (name, pageno, dest) in enumerate(chunk):
            col = j // lines_per_col
            row = j % lines_per_col
            x = col_x[col]
            y = top_y - row * TOC_LINE_H
            # Truncate long names to keep the page-number column clear.
            disp = name
            while len(disp) > 1 and _approx_w(disp, TOC_FONT) > name_max_w:
                disp = disp[:-1]
            if disp != name:
                disp = disp[:-1] + "…"
            content += text_op(disp, x, y, "/F1", TOC_FONT)
            num = str(pageno)
            nx = x + col_w - _approx_w(num, TOC_FONT)
            content += text_op(num, nx, y, "/F1", TOC_FONT)
            # Clickable jump to the tune's page.
            annots.append(out.make_indirect(Dictionary(
                Type=Name.Annot, Subtype=Name.Link,
                Rect=Array([x, y - 3, x + col_w, y + TOC_FONT]),
                Border=Array([0, 0, 0]),
                A=Dictionary(S=Name.GoTo, D=Array([dest, Name.Fit])),
            )))
        page_obj.Contents = out.make_stream(content)
        if annots:
            page_obj.Annots = Array(annots)
        toc_page_objs.append(page_obj)

    # Move the freshly-appended TOC pages to the front, preserving order.
    for idx, tp in enumerate(toc_page_objs):
        out.pages.remove(pikepdf.Page(tp))
        out.pages.insert(idx, pikepdf.Page(tp))
    return toc_page_objs


# Approximate Helvetica advance widths (per 1pt em) for the common ASCII range.
def _approx_w(text, size):
    return sum(0.50 if c in "iIl.,;:'|!" else
               0.78 if c in "mwMW" else 0.556 for c in text) * size


def make_main_pdf(pairs, output):
    """pairs: list of (tune_name, file_path) already in display order."""
    usable_w = PAGE_W - 2 * MARGIN_X
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
    name_of = {path: name for name, path in pairs}

    items = []
    for i, (name, f) in enumerate(pairs, 1):
        label = "ABC" if f.endswith(".abc") else "PNG"
        print(f"  [{i}/{len(pairs)}] {label}: {name}")
        pdf_bytes = abc_to_pdf_bytes(f) if f.endswith(".abc") else png_to_pdf_bytes(f)
        w, h = get_pdf_size(pdf_bytes)
        items.append((f, h * (usable_w / w), pdf_bytes))

    pages = pack_pages(items, GAP_FALLBACK, usable_h)
    _, _, _, _, n_toc_pages = toc_geometry(len(items))

    print(f"\nPacking {len(items)} tunes onto {len(pages)} content pages "
          f"(+{n_toc_pages} TOC page(s))...")
    out = Pdf.new()
    fonts = make_fonts(out)

    tune_dest = {}   # tune name -> (printed_pageno, page_obj)
    for ci, page_items in enumerate(pages, 1):
        content_h = sum(h for _, h, _ in page_items)
        gap = (GAP_PREFERRED
               if content_h + (len(page_items) - 1) * GAP_PREFERRED <= usable_h
               else GAP_FALLBACK)
        page_obj = render_content_page(out, fonts, page_items, usable_w, gap)
        printed = n_toc_pages + ci
        for fname, _, _ in page_items:
            tune_dest[name_of[fname]] = (printed, page_obj)

    entries = [(name, tune_dest[name][0], tune_dest[name][1])
               for name in sorted(tune_dest, key=lambda s: s.lower().replace("-", " "))]
    build_toc_pages(out, fonts, entries, n_toc_pages)

    print(f"Writing {output}...")
    out.save(output)


# --- PDF 2: portrait side-by-side comparison, packed -----------------------

COMP_TITLE_H = 28      # space above each pair: tune name + panel captions
COMP_PANEL_GAP = 18    # horizontal gap between the scan + engraving columns
COMP_BLOCK_GAP = 24    # vertical gap between consecutive tune rows


def render_comparison_page(out, fonts, page_blocks, panel_w, left_x, right_x):
    """One portrait page of stacked tune rows: scan left, engraving right."""
    page_obj = new_page(out, PAGE_W, PAGE_H, fonts)
    content = b""
    y = PAGE_H - MARGIN_TOP
    for idx, (tune, block_h, eng_bytes, scan_bytes, panels_h) in enumerate(page_blocks):
        top = y
        content += text_op(tune, MARGIN_X, top - 13, "/F2", 13)
        content += text_op("Original", left_x, top - COMP_TITLE_H + 3, "/F1", 8)
        content += text_op("Engraved", right_x, top - COMP_TITLE_H + 3, "/F1", 8)
        panel_bottom = top - COMP_TITLE_H - panels_h
        left_box = (left_x, panel_bottom, panel_w, panels_h)
        right_box = (right_x, panel_bottom, panel_w, panels_h)
        if scan_bytes is not None:
            content += embed_form(out, page_obj, scan_bytes, f"/S{idx}", left_box)
        else:
            content += text_op("(no scan)", left_x, panel_bottom + panels_h / 2,
                               "/F1", 10)
        content += embed_form(out, page_obj, eng_bytes, f"/E{idx}", right_box,
                              sepia=SEPIA)
        y = top - block_h - COMP_BLOCK_GAP
    page_obj.Contents = out.make_stream(content)
    return page_obj


def make_comparison_pdf(verified, scans, output):
    tunes = sorted(verified, key=lambda s: s.lower().replace("-", " "))
    usable_w = PAGE_W - 2 * MARGIN_X
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
    panel_w = (usable_w - COMP_PANEL_GAP) / 2
    left_x = MARGIN_X
    right_x = MARGIN_X + panel_w + COMP_PANEL_GAP
    cap_h = usable_h - COMP_TITLE_H

    blocks = []
    for i, tune in enumerate(tunes, 1):
        print(f"  [{i}/{len(tunes)}] compare: {tune}")
        eng_bytes = abc_to_pdf_bytes(verified[tune])
        ew, eh = get_pdf_size(eng_bytes)
        scan = scans.get(tune)
        if scan:
            scan_bytes = png_to_pdf_bytes(scan)
            sw, sh = get_pdf_size(scan_bytes)
            scan_h = sh * (panel_w / sw)
        else:
            scan_bytes, scan_h = None, 0
        eng_h = eh * (panel_w / ew)
        # Each column fills the half-width; row height = the taller of the two,
        # capped so a single tall tune still fits one page.
        panels_h = min(max(scan_h, eng_h), cap_h)
        block_h = COMP_TITLE_H + panels_h
        blocks.append((tune, block_h, eng_bytes, scan_bytes, panels_h))

    # Greedy first-fit: as many tune rows per page as fit.
    items = [(b, b[1]) for b in blocks]   # (block, height)
    pages, current, cur_h = [], [], 0
    for block, h in items:
        g = COMP_BLOCK_GAP if current else 0
        if current and cur_h + g + h > usable_h:
            pages.append(current)
            current, cur_h = [block], h
        else:
            current.append(block)
            cur_h += g + h
    if current:
        pages.append(current)

    out = Pdf.new()
    fonts = make_fonts(out)
    _, _, _, _, n_toc_pages = toc_geometry(len(tunes))

    tune_dest = {}   # tune name -> (printed_pageno, page_obj)
    for ci, page_blocks in enumerate(pages, 1):
        page_obj = render_comparison_page(out, fonts, page_blocks,
                                          panel_w, left_x, right_x)
        printed = n_toc_pages + ci
        for block in page_blocks:
            tune_dest[block[0]] = (printed, page_obj)

    entries = [(name, tune_dest[name][0], tune_dest[name][1])
               for name in sorted(tune_dest, key=lambda s: s.lower().replace("-", " "))]
    build_toc_pages(out, fonts, entries, n_toc_pages)

    print(f"Writing {output} ({len(pages)} content + {n_toc_pages} TOC pages)...")
    out.save(output)


# --- entry point -----------------------------------------------------------

def main():
    main_out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"
    comp_out = os.path.splitext(main_out)[0] + "_comparison.pdf"

    HERE = os.path.dirname(os.path.abspath(__file__))
    SCAN_DIR = os.path.join(HERE, "source_images")
    ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")

    scans = {stem_of(p): p for p in glob.glob(os.path.join(SCAN_DIR, "*.png"))}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(ABC_DIR, "*-verified.abc"))}

    tunes = sorted(set(scans) | set(verified), key=lambda s: s.lower().replace("-", " "))
    pairs = [(t, verified[t] if t in verified else scans[t]) for t in tunes]
    if not pairs:
        print("No tunes found.", file=sys.stderr)
        sys.exit(1)

    n_eng = sum(1 for _, f in pairs if f.endswith(".abc"))
    print(f"=== Book PDF: {len(pairs)} tunes "
          f"({n_eng} engraved, {len(pairs) - n_eng} scanned) ===")
    make_main_pdf(pairs, main_out)

    print(f"\n=== Comparison PDF: {len(verified)} engraved tune(s), portrait packed ===")
    make_comparison_pdf(verified, scans, comp_out)

    print("\nDone.")


if __name__ == "__main__":
    main()
