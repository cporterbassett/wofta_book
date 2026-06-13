#!/usr/bin/env python3
"""
Pack all PNGs and ABC files in the current directory into a PDF.
- PNG files: embedded as raster (scanned tunes)
- ABC files: converted to vector PDF via LilyPond
- All tunes scaled to usable page width, packed vertically, greedy first-fit
"""
import glob
import io
import os
import re
import shutil
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


def sort_key(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.lower().replace("-", " ")


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


def abc_to_pdf_bytes(abc_path):
    """Convert ABC file to a cropped vector PDF via LilyPond."""
    with tempfile.TemporaryDirectory() as tmpdir:
        abc_name = os.path.basename(abc_path)
        tmp_abc = os.path.join(tmpdir, abc_name)
        shutil.copy(abc_path, tmp_abc)

        base = os.path.splitext(abc_name)[0]
        ly_path = os.path.join(tmpdir, base + ".ly")

        subprocess.run(["abc2ly", tmp_abc, "-o", ly_path],
                       check=True, capture_output=True)

        # Patch: abc2ly omits \paper { indent = 0 }, causing first staff misalignment
        content = open(ly_path).read()
        content = re.sub(
            r"(\\version[^\n]*\n)",
            r"\1\\paper {\n\tindent = 0\n}\n",
            content, count=1,
        )
        open(ly_path, "w").write(content)

        subprocess.run(
            ["lilypond", "--pdf", "-dcrop", ly_path],
            check=True, capture_output=True, cwd=tmpdir,
        )

        cropped = os.path.join(tmpdir, base + ".cropped.pdf")
        with open(cropped, "rb") as f:
            return f.read()


def get_pdf_size(pdf_bytes):
    with Pdf.open(io.BytesIO(pdf_bytes)) as pdf:
        mb = pdf.pages[0].mediabox
        return float(mb[2]) - float(mb[0]), float(mb[3]) - float(mb[1])


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


def render_page(page_items, output_pdf, usable_w, gap):
    """Composite items onto a new letter-size page using pikepdf form XObjects."""
    page_obj = output_pdf.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, PAGE_W, PAGE_H]),
        Resources=Dictionary(XObject=Dictionary()),
        Contents=output_pdf.make_stream(b""),
    ))
    output_pdf.pages.append(pikepdf.Page(page_obj))
    page = output_pdf.pages[-1]

    content = b""
    y = PAGE_H - MARGIN_TOP

    for i, (_, scaled_h, pdf_bytes) in enumerate(page_items):
        with Pdf.open(io.BytesIO(pdf_bytes)) as src:
            src_w = float(src.pages[0].mediabox[2])
            xobj = src.pages[0].as_form_xobject()
            xobj_copy = output_pdf.copy_foreign(xobj)

        xobj_name = f"/Fm{i}"
        page.obj.Resources.XObject[xobj_name] = xobj_copy

        scale = usable_w / src_w
        tx = MARGIN_X
        ty = y - scaled_h
        content += (
            f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm {xobj_name} Do Q\n"
        ).encode()
        y = ty - gap

    page.obj.Contents = output_pdf.make_stream(content)


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"

    HERE = os.path.dirname(os.path.abspath(__file__))
    SCAN_DIR = os.path.join(HERE, "source_images")
    ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")

    # canonical tune set = union of scans and verified ABCs
    scans = {os.path.splitext(os.path.basename(p))[0]: p
             for p in glob.glob(os.path.join(SCAN_DIR, "*.png"))}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(ABC_DIR, "*-verified.abc"))}

    tunes = sorted(set(scans) | set(verified), key=lambda s: sort_key(s))
    all_files = []
    for tune in tunes:
        if tune in verified:
            all_files.append(verified[tune])   # crisp vector engraving
        elif tune in scans:
            all_files.append(scans[tune])       # original scan

    if not all_files:
        print("No tunes found.", file=sys.stderr)
        sys.exit(1)

    n_eng = sum(1 for f in all_files if f.endswith(".abc"))
    n_scan = len(all_files) - n_eng
    print(f"Processing {len(all_files)} tunes ({n_eng} engraved, {n_scan} scanned)...")

    usable_w = PAGE_W - 2 * MARGIN_X
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM

    items = []
    for i, f in enumerate(all_files, 1):
        label = "ABC" if f.endswith(".abc") else "PNG"
        print(f"  [{i}/{len(all_files)}] {label}: {f}")
        if f.endswith(".abc"):
            pdf_bytes = abc_to_pdf_bytes(f)
        else:
            pdf_bytes = png_to_pdf_bytes(f)
        w, h = get_pdf_size(pdf_bytes)
        scale = usable_w / w
        items.append((f, h * scale, pdf_bytes))

    pages = pack_pages(items, GAP_FALLBACK, usable_h)

    print(f"\nPacking {len(items)} tunes onto {len(pages)} pages...")
    output_pdf = Pdf.new()
    for i, page_items in enumerate(pages, 1):
        content_h = sum(h for _, h, _ in page_items)
        gap = GAP_PREFERRED if content_h + (len(page_items) - 1) * GAP_PREFERRED <= usable_h else GAP_FALLBACK
        render_page(page_items, output_pdf, usable_w, gap)
        print(f"  Page {i}/{len(pages)}: {len(page_items)} tune(s) — {', '.join(os.path.basename(f) for f, _, _ in page_items)}")

    print(f"\nWriting {output}...")
    output_pdf.save(output)
    print("Done.")


if __name__ == "__main__":
    main()
