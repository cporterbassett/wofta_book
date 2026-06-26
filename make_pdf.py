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
import re
import subprocess
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


# --- material renderers (kinds) --------------------------------------------

TEXT_W = 540
TEXT_FONT_SIZE = 11
TEXT_LINE_H = 14.5

_CHORD_TOKEN_RE = re.compile(
    r'^[A-G][#b]?(m|M|maj|min|aug|dim|sus[24]?|add)?[0-9]{0,2}$'
)


def _is_chord_line(line):
    """True if the line is chord names, slashes, or a section marker."""
    stripped = line.strip()
    if not stripped:
        return False
    if (stripped.startswith('[') or stripped.startswith('(Chorus')
            or stripped.startswith('Chorus:') or stripped.startswith('Intro:')):
        return True
    no_parens = re.sub(r'\([^)]*\)', '', stripped).strip()
    tokens = no_parens.split()
    return bool(tokens) and all(
        _CHORD_TOKEN_RE.match(t) or t == '/' for t in tokens
    )


def make_text_pdf_bytes(title, key_note, body_lines,
                        font_size=TEXT_FONT_SIZE, line_h=TEXT_LINE_H):
    """Clean Courier page: title, optional key note, then chords/lyrics."""
    n_header = 1 + (1 if key_note else 0) + 1
    h = 24 + n_header * line_h + len(body_lines) * line_h + 16
    pdf = Pdf.new()
    reg = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/Helvetica-Bold")))
    mono = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Courier))
    page_obj = pdf.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, TEXT_W, h]),
        Resources=Dictionary(Font=Dictionary(F1=reg, F2=bold, F3=mono)),
        Contents=pdf.make_stream(b""),
    ))
    pdf.pages.append(pikepdf.Page(page_obj))
    y = h - 22
    content = text_op(title, 16, y, "/F2", 17)
    y -= line_h
    if key_note:
        content += text_op(key_note, 16, y, "/F1", 11)
        y -= line_h
    y -= line_h
    for line in body_lines:
        content += text_op(line, 16, y, "/F3", font_size)
        y -= line_h
    page_obj.Contents = pdf.make_stream(content)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def make_text_pdf_bytes_2col(title, key_note, body_lines,
                             font_size=11, line_h=14.5):
    """Two-column layout with bold Courier for chord lines."""
    mid = len(body_lines) // 2
    blank_indices = [i for i, l in enumerate(body_lines) if not l.strip()]
    split_at = min(blank_indices, key=lambda i: abs(i - mid), default=mid)
    col1 = body_lines[:split_at]
    col2 = body_lines[split_at + 1:]

    col_lines = max(len(col1), len(col2))
    n_header = 1 + (1 if key_note else 0) + 1
    page_w = 612
    margin_x = 18
    col_gap = 18
    col_w = (page_w - 2 * margin_x - col_gap) / 2
    h = 24 + n_header * line_h + col_lines * line_h + 16

    pdf = Pdf.new()
    reg = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    bold_h = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/Helvetica-Bold")))
    mono = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Courier))
    mono_bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/Courier-Bold")))
    page_obj = pdf.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, page_w, h]),
        Resources=Dictionary(Font=Dictionary(F1=reg, F2=bold_h, F3=mono, F4=mono_bold)),
        Contents=pdf.make_stream(b""),
    ))
    pdf.pages.append(pikepdf.Page(page_obj))

    y = h - 22
    content = text_op(title, margin_x, y, "/F2", 17)
    y -= line_h
    if key_note:
        content += text_op(key_note, margin_x, y, "/F1", 11)
        y -= line_h
    y -= line_h

    col2_x = margin_x + col_w + col_gap
    for col_lines_list, x in ((col1, margin_x), (col2, col2_x)):
        cy = y
        for line in col_lines_list:
            font = "/F4" if _is_chord_line(line) else "/F3"
            content += text_op(line, x, cy, font, font_size)
            cy -= line_h

    page_obj.Contents = pdf.make_stream(content)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def crop_pdf_page(pdf_bytes, crop):
    """Replace the first page's MediaBox with crop=(left, bottom, right, top)."""
    l, b, r, t = crop
    with Pdf.open(io.BytesIO(pdf_bytes)) as src:
        src.pages[0].mediabox = Array([l, b, r, t])
        buf = io.BytesIO()
        src.save(buf)
    return buf.getvalue()


def split_pdf_pages(pdf_bytes, only=None):
    """Return list of single-page pdf bytes; `only` = 0-based indices to keep."""
    out = []
    with Pdf.open(io.BytesIO(pdf_bytes)) as src:
        indices = only if only is not None else range(len(src.pages))
        for i in indices:
            single = Pdf.new()
            single.pages.append(src.pages[i])
            buf = io.BytesIO()
            single.save(buf)
            out.append(buf.getvalue())
    return out


def odt_to_pdf_bytes(odt_path):
    """Convert a LibreOffice ODT to PDF bytes using headless LibreOffice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, odt_path],
            check=True, capture_output=True,
        )
        stem = os.path.splitext(os.path.basename(odt_path))[0]
        with open(os.path.join(tmpdir, stem + ".pdf"), "rb") as f:
            return f.read()


def _render_abc(path, options):
    return [(abc_to_pdf_bytes(path), True)]


def _render_png(path, options):
    return [(png_to_pdf_bytes(path), False)]


def _render_pdf(path, options):
    with open(path, "rb") as f:
        raw = f.read()
    pages = split_pdf_pages(raw, only=options.get("pages"))
    crop = options.get("crop")
    if crop:
        pages = [crop_pdf_page(p, crop) for p in pages]
    return [(p, False) for p in pages]


def _render_odt(path, options):
    raw = odt_to_pdf_bytes(path)
    pages = split_pdf_pages(raw, only=options.get("pages"))
    crop = options.get("crop")
    if crop:
        pages = [crop_pdf_page(p, crop) for p in pages]
    return [(p, False) for p in pages]


def _render_text(path, options):
    with open(path) as f:
        body_lines = f.read().splitlines()
    pdf_bytes = make_text_pdf_bytes(
        options["display_name"], options.get("key_note"), body_lines,
        options.get("font_size", TEXT_FONT_SIZE),
        options.get("line_h", TEXT_LINE_H),
    )
    return [(pdf_bytes, False)]


def _render_text_2col(path, options):
    with open(path) as f:
        body_lines = f.read().splitlines()
    pdf_bytes = make_text_pdf_bytes_2col(
        options["display_name"], options.get("key_note"), body_lines,
        options.get("font_size", 11), options.get("line_h", 14.5),
    )
    return [(pdf_bytes, False)]


RENDERERS = {
    "abc": _render_abc,
    "png": _render_png,
    "pdf": _render_pdf,
    "odt": _render_odt,
    "text": _render_text,
    "text_2col": _render_text_2col,
}


def render_book_page(out, fonts, page_items, usable_w, gap, sepia):
    """Composite packed items onto one letter page. page_items entries are
    (display_name, scaled_h, pdf_bytes, is_engraved). A sepia wash is drawn
    behind an item only when sepia and the item is engraved."""
    page_obj = new_page(out, PAGE_W, PAGE_H, fonts)
    content = b""
    y = PAGE_H - MARGIN_TOP
    for i, (name, scaled_h, pdf_bytes, is_engraved) in enumerate(page_items):
        with Pdf.open(io.BytesIO(pdf_bytes)) as src:
            src_w = float(src.pages[0].mediabox[2])
            xobj = out.copy_foreign(src.pages[0].as_form_xobject())
        xobj_name = f"/Fm{i}"
        page_obj.Resources.XObject[xobj_name] = xobj
        scale = usable_w / src_w
        tx = MARGIN_X
        ty = y - scaled_h
        if sepia and is_engraved:
            r, g, b = SEPIA_RGB
            content += (f"q {r:.4f} {g:.4f} {b:.4f} rg "
                        f"{tx:.2f} {ty:.2f} {usable_w:.2f} {scaled_h:.2f} re f Q\n").encode()
        content += (f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm "
                    f"{xobj_name} Do Q\n").encode()
        y = ty - gap
    page_obj.Contents = out.make_stream(content)
    return page_obj


def build_book(entries, *, output, sepia=False, toc_alphabetical=False):
    """Build a packed tune book from entries = (display_name, kind, path, options).
    sepia washes engraved items; toc_alphabetical sorts the TOC (else set-list
    order). Multi-page sources and duplicate names collapse to first occurrence
    in the TOC."""
    usable_w = PAGE_W - 2 * MARGIN_X
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM

    items = []  # (display_name, scaled_h, pdf_bytes, is_engraved)
    for i, (name, kind, path, options) in enumerate(entries, 1):
        print(f"  [{i}/{len(entries)}] {kind}: {name}")
        opts = dict(options or {})
        opts["display_name"] = name
        for pdf_bytes, is_engraved in RENDERERS[kind](path, opts):
            w, h = get_pdf_size(pdf_bytes)
            items.append((name, h * (usable_w / w), pdf_bytes, is_engraved))

    pages_h = pack_pages([(n, h, b) for n, h, b, _ in items],
                         GAP_FALLBACK, usable_h)
    # pack_pages preserves order; re-attach is_engraved by walking items in lockstep.
    flat = iter(items)
    pages = [[next(flat) for _ in page] for page in pages_h]

    n_unique_names = len({name for name, _, _, _ in items})
    _, _, _, _, n_toc_pages = toc_geometry(n_unique_names)
    print(f"\nPacking {len(items)} item(s) onto {len(pages)} content pages "
          f"(+{n_toc_pages} TOC page(s))...")

    out = Pdf.new()
    fonts = make_fonts(out)

    tune_dest = {}  # display_name -> (printed_pageno, page_obj), first occurrence
    for ci, page_items in enumerate(pages, 1):
        content_h = sum(h for _, h, _, _ in page_items)
        gap = (GAP_PREFERRED
               if content_h + (len(page_items) - 1) * GAP_PREFERRED <= usable_h
               else GAP_FALLBACK)
        page_obj = render_book_page(out, fonts, page_items, usable_w, gap, sepia)
        printed = n_toc_pages + ci
        for name, _, _, _ in page_items:
            if name not in tune_dest:
                tune_dest[name] = (printed, page_obj)

    if toc_alphabetical:
        order = sorted(tune_dest, key=lambda s: s.lower().replace("-", " "))
    else:
        order, seen = [], set()
        for name, _, _, _ in items:
            if name not in seen:
                seen.add(name)
                order.append(name)
    entries_toc = [(name, tune_dest[name][0], tune_dest[name][1]) for name in order]
    build_toc_pages(out, fonts, entries_toc, n_toc_pages)

    print(f"Writing {output}...")
    out.save(output)


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


# --- PDF 2: portrait side-by-side comparison, packed -----------------------

COMP_TITLE_H = 28      # space above each pair: tune name + panel captions
COMP_PANEL_GAP = 18    # horizontal gap between the scan + engraving columns
COMP_BLOCK_GAP = 24    # vertical gap between consecutive tune rows


def render_comparison_page(out, fonts, page_blocks, panel_w, left_x, right_x, sepia):
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
                              sepia=sepia)
        y = top - block_h - COMP_BLOCK_GAP
    page_obj.Contents = out.make_stream(content)
    return page_obj


def make_comparison_pdf(verified, scans, output, sepia=True):
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
                                          panel_w, left_x, right_x, sepia)
        printed = n_toc_pages + ci
        for block in page_blocks:
            tune_dest[block[0]] = (printed, page_obj)

    entries = [(name, tune_dest[name][0], tune_dest[name][1])
               for name in sorted(tune_dest, key=lambda s: s.lower().replace("-", " "))]
    build_toc_pages(out, fonts, entries, n_toc_pages)

    print(f"Writing {output} ({len(pages)} content + {n_toc_pages} TOC pages)...")
    out.save(output)


