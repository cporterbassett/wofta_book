#!/usr/bin/env python3
"""
Compose multiple tune images (PNG or PDF) onto a single letter-size PDF page.

Usage:
    python3 compose_page.py output.pdf tune1.png tune2.pdf ...
"""
import sys
import io
import pikepdf
from pikepdf import Pdf, Dictionary, Array, Name
from PIL import Image
import img2pdf

PAGE_W = 612   # letter, points
PAGE_H = 792
MARGIN_X = 36  # 0.5 inch sides
MARGIN_TOP = 36
MARGIN_BOTTOM = 36
GAP = 20       # between tunes
PNG_DPI = 150  # assumed DPI for PNGs with no metadata


def png_to_tmp_pdf(png_path):
    """Convert a PNG to a single-page PDF bytes, respecting DPI."""
    with Image.open(png_path) as img:
        dpi = img.info.get("dpi")
        if dpi:
            dpi = dpi[0]
        else:
            dpi = PNG_DPI
        layout = img2pdf.get_layout_fun(
            (img2pdf.in_to_pt(img.size[0] / dpi), img2pdf.in_to_pt(img.size[1] / dpi))
        )
    with open(png_path, "rb") as f:
        return img2pdf.convert(f.read(), layout_fun=layout)


def get_pdf_size(pdf_or_bytes):
    """Return (width, height) in points from a PDF file path or bytes."""
    if isinstance(pdf_or_bytes, (str, bytes)):
        if isinstance(pdf_or_bytes, bytes):
            pdf = Pdf.open(io.BytesIO(pdf_or_bytes))
        else:
            pdf = Pdf.open(pdf_or_bytes)
        with pdf:
            mb = pdf.pages[0].mediabox
            return float(mb[2]) - float(mb[0]), float(mb[3]) - float(mb[1])


def compose(sources, output_path):
    """
    sources: list of file paths (.png or .pdf)
    Scales each to usable page width, stacks top to bottom.
    """
    usable_w = PAGE_W - 2 * MARGIN_X

    # Convert PNGs to PDF bytes; collect (pdf_bytes_or_path, w, h)
    items = []
    for src in sources:
        if src.lower().endswith(".png"):
            pdf_bytes = png_to_tmp_pdf(src)
            w, h = get_pdf_size(pdf_bytes)
            items.append((pdf_bytes, w, h))
        else:
            w, h = get_pdf_size(src)
            items.append((src, w, h))

    # Calculate scaled heights
    scaled = []
    for (src, w, h) in items:
        scale = usable_w / w
        scaled.append((src, w, h, scale, h * scale))

    total_h = sum(sh for *_, sh in scaled) + GAP * (len(scaled) - 1)
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
    if total_h > usable_h:
        print(f"Warning: content height {total_h:.0f}pt exceeds usable {usable_h:.0f}pt", file=sys.stderr)

    # Build output PDF
    output = Pdf.new()
    page_obj = output.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, PAGE_W, PAGE_H]),
        Resources=Dictionary(XObject=Dictionary()),
        Contents=output.make_stream(b""),
    ))
    output.pages.append(pikepdf.Page(page_obj))
    page = output.pages[0]

    content = b""
    y = PAGE_H - MARGIN_TOP  # current top y, working downward

    for i, (src, src_w, src_h, scale, actual_h) in enumerate(scaled):
        if isinstance(src, bytes):
            pdf = Pdf.open(io.BytesIO(src))
        else:
            pdf = Pdf.open(src)

        with pdf:
            xobj = pdf.pages[0].as_form_xobject()
            xobj_copy = output.copy_foreign(xobj)

        xobj_name = f"/Fm{i}"
        page.obj.Resources.XObject[xobj_name] = xobj_copy

        tx = MARGIN_X
        ty = y - actual_h
        content += f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm {xobj_name} Do Q\n".encode()
        y = ty - GAP

    page.obj.Contents = output.make_stream(content)
    output.save(output_path)
    print(f"Written: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} output.pdf tune1.png/pdf tune2.png/pdf ...", file=sys.stderr)
        sys.exit(1)
    compose(sys.argv[2:], sys.argv[1])
