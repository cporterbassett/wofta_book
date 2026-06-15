#!/usr/bin/env python3
"""
Pack all PNGs and ABC files in the current directory into a PDF.
- PNG files: embedded as raster (scanned tunes)
- ABC files: converted to vector PDF via abcm2ps (EPS) + Ghostscript
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

# --- Temporary sepia tint on engraved (ABC-rendered) tunes ----------------
# Gives the crisp vector engravings a slight warm background so they're easy to
# tell apart from the scans. Affects ONLY engraved tunes (PDF + comparison HTML);
# scans are left untouched. Turn off with `SEPIA=0 ./make_pdf.sh` or flip the
# default below to "0".
SEPIA = os.environ.get("SEPIA", "1") != "0"
SEPIA_HEX = "#f8efd9"                      # slight sepia / cream
SEPIA_RGB = (0.973, 0.937, 0.851)          # same colour, 0..1 for PostScript


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


# Same directives render_abc.sh injects, so a tune's PDF engraving matches its
# comparison-report render: line-start measure numbers, bold chords + volta numbers.
ABC_DIRECTIVES = (
    "%%measurenb 0\n"
    "%%measurefont Times-Italic 9\n"
    "%%titlefont Times-Bold 24\n"
    "%%gchordfont Helvetica-Bold 12\n"
    "%%repeatfont Helvetica-Bold 9\n"
)

# For HTML SVG: zero margins so notation fills the full declared width (no
# whitespace strips on either side), matching the content-crop we do for PDF.
ABC_DIRECTIVES_HTML = ABC_DIRECTIVES + (
    "%%leftmargin 0\n"
    "%%rightmargin 0\n"
    "%%topmargin 0\n"
    "%%botmargin 0\n"
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
        with open(tmp_abc, "w") as out, open(abc_path) as src:
            out.write(ABC_DIRECTIVES)
            out.write(src.read())

        # Don't use check=True: abcm2ps exits non-zero on cosmetic warnings
        # (e.g. "Line too much shrunk") while still emitting valid EPS. Only a
        # missing EPS is a real failure.
        subprocess.run(
            ["abcm2ps", "-E", "-s", "1.0", "-O", "out", "tune.abc"],
            capture_output=True, cwd=tmpdir,
        )
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

    for i, (fname, scaled_h, pdf_bytes) in enumerate(page_items):
        with Pdf.open(io.BytesIO(pdf_bytes)) as src:
            src_w = float(src.pages[0].mediabox[2])
            xobj = src.pages[0].as_form_xobject()
            xobj_copy = output_pdf.copy_foreign(xobj)

        xobj_name = f"/Fm{i}"
        page.obj.Resources.XObject[xobj_name] = xobj_copy

        scale = usable_w / src_w
        tx = MARGIN_X
        ty = y - scaled_h
        # Slight sepia wash behind engraved (ABC) tunes only — drawn first so the
        # notes paint on top. Scanned PNGs get no tint.
        if SEPIA and fname.endswith(".abc"):
            r, g, b = SEPIA_RGB
            content += (
                f"q {r:.4f} {g:.4f} {b:.4f} rg "
                f"{tx:.2f} {ty:.2f} {usable_w:.2f} {scaled_h:.2f} re f Q\n"
            ).encode()
        content += (
            f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm {xobj_name} Do Q\n"
        ).encode()
        y = ty - gap

    page.obj.Contents = output_pdf.make_stream(content)


def abc_to_svg_str(abc_path):
    """Render an ABC file to inline SVG string via abcm2ps -g.

    Uses zero margins so notation fills the full declared page width (no empty
    strips on either side). Adds a viewBox and sets width=100% so the SVG
    scales to fit its HTML container rather than overflowing at fixed px size.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_abc = os.path.join(tmpdir, "tune.abc")
        with open(tmp_abc, "w") as out, open(abc_path) as src:
            out.write(ABC_DIRECTIVES_HTML)
            out.write(src.read())
        # See abc_to_pdf_bytes: tolerate non-zero exit (cosmetic warnings) as
        # long as an SVG is produced.
        subprocess.run(
            ["abcm2ps", "-g", "-s", "1.0", "-O", "out", "tune.abc"],
            capture_output=True, cwd=tmpdir,
        )
        svg_files = sorted(glob.glob(os.path.join(tmpdir, "out*.svg")))
        if not svg_files:
            raise RuntimeError(f"abcm2ps produced no SVG for {abc_path}")
        with open(svg_files[0]) as f:
            raw = f.read()
    idx = raw.index("<svg")
    svg = raw[idx:]
    # Replace fixed "width=Xpx height=Ypx" with a viewBox + scalable width
    # so the browser can resize the SVG to fit its container.
    m = re.search(r'width="([\d.]+)px"\s+height="([\d.]+)px"', svg)
    if m:
        w, h = m.group(1), m.group(2)
        svg = svg[:m.start()] + f'width="100%" viewBox="0 0 {w} {h}"' + svg[m.end():]
    return svg


def make_html(verified, scans, html_path):
    """Write side-by-side comparison HTML for all verified tunes."""
    tunes = sorted(verified.keys(), key=sort_key)
    html_dir = os.path.dirname(os.path.abspath(html_path))

    rows = []
    for tune in tunes:
        svg = abc_to_svg_str(verified[tune])
        scan_path = scans.get(tune)
        if scan_path:
            rel = os.path.relpath(scan_path, html_dir)
            scan_html = f'<img src="{rel}" alt="Original scan">'
        else:
            scan_html = "<em>No scan</em>"
        rows.append(f"""
  <section>
    <h2>{tune}</h2>
    <div class="comparison">
      <div class="panel engraved"><h3>Engraved (ABC)</h3>{svg}</div>
      <div class="panel"><h3>Original Scan</h3>{scan_html}</div>
    </div>
  </section>""")

    # Only the engraved panel gets the slight sepia background (scans stay white).
    sepia_css = (f".panel.engraved svg {{ background: {SEPIA_HEX}; }}"
                 if SEPIA else "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>WOFTA Verified Tunes ({len(tunes)})</title>
  <style>
    body {{ font-family: sans-serif; max-width: 1600px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
    h1 {{ color: #333; }}
    section {{ background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,.1); }}
    h2 {{ margin-top: 0; color: #444; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
    .comparison {{ display: flex; gap: 20px; }}
    .panel {{ flex: 1; min-width: 0; }}
    .panel h3 {{ font-size: .9em; color: #666; margin-bottom: 8px; }}
    .panel svg {{ max-width: 100%; height: auto; display: block; }}
    .panel img {{ max-width: 100%; height: auto; display: block; border: 1px solid #ddd; }}
    {sepia_css}
  </style>
</head>
<body>
  <h1>WOFTA Verified Tunes ({len(tunes)})</h1>
{''.join(rows)}
</body>
</html>"""

    with open(html_path, "w") as f:
        f.write(html)
    print(f"HTML comparison written to {html_path}")


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

    html_output = os.path.splitext(os.path.abspath(output))[0] + "_verified.html"
    print(f"\nBuilding HTML comparison for {len(verified)} verified tune(s)...")
    make_html(verified, scans, html_output)

    print("Done.")


if __name__ == "__main__":
    main()
