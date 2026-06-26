#!/usr/bin/env python3
"""
Build "Sand and Sawdust 2026.pdf" — the working set list, in the exact order
of the printed sheet (/home/porter/Downloads/PXL_20260623_213340768.MP.jpg),
not alphabetical. Repeats on the sheet (Me and My Fiddle, Cumberland Gap,
Sugar Moon) are collapsed to their first occurrence.

For each tune, uses the best material on hand:
  - verified ABC  (engraved, sepia wash)       -- most tunes
  - candidate ABC (engraved, sepia wash)       -- Sugar Moon, Kansas City
    Kitty: not yet verified
  - real ABC notation found at the source      -- Old Aunt Jenny (no chords
    in the source; instrumental)
  - a real chords/lyrics PDF already downloaded -- Red Red Robin (text-only
    page), America the Beautiful, You're A Grand Old Flag/Yankee Doodle Dandy
  - a clean chords+lyrics text page, extracted from the source page (nav/ads/
    boilerplate stripped, just the song) -- everything else still without a
    melody transcription

Run via ./make_sand_and_sawdust_pdf.sh (activates the venv).
"""
import io
import os
import re
import subprocess
import sys
import tempfile

import pikepdf
from pikepdf import Array, Dictionary, Name

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_pdf as mp  # reuse engraving/packing/TOC machinery

HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
REF_DIR = os.path.join(HERE, "notation_pipeline", "reference_sources")
ODT_DIR = HERE  # LibreOffice source files live in the project root

TEXT_W = 540
TEXT_FONT_SIZE = 11
TEXT_LINE_H = 14.5

# Per-tune override (font_size, line_h) for "text" entries that are too long
# to fit at the default size without the bottom getting cut off.
TEXT_FONT_OVERRIDES = {
    "Catfish John": (9, 11.5),
}

# Tunes rendered in 2-column layout with bold chord lines.
TEXT_2COL = {"Roll in My Sweet Baby's Arms"}

# Per-tune MediaBox crop (left, bottom, right, top) in points, applied before
# scaling to usable_w.  Strips the source PDF's internal margins so the content
# fills usable_w at 1:1 scale instead of being shrunk.
PDF_CROP = {
}

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


def make_text_pdf_bytes(title, key_note, body_lines, font_size=TEXT_FONT_SIZE, line_h=TEXT_LINE_H):
    """A clean Courier monospace page: title, optional key note, then the
    chords/lyrics exactly as extracted (chord lines stay aligned over the
    lyric line below them)."""
    n_header = 1 + (1 if key_note else 0) + 1  # title + key + blank
    h = 24 + n_header * line_h + len(body_lines) * line_h + 16
    pdf = pikepdf.Pdf.new()
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
    content = mp.text_op(title, 16, y, "/F2", 17)
    y -= line_h
    if key_note:
        content += mp.text_op(key_note, 16, y, "/F1", 11)
        y -= line_h
    y -= line_h
    for line in body_lines:
        content += mp.text_op(line, 16, y, "/F3", font_size)
        y -= line_h
    page_obj.Contents = pdf.make_stream(content)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def make_text_pdf_bytes_2col(title, key_note, body_lines,
                             font_size=11, line_h=14.5):
    """Two-column layout with bold Courier for chord lines."""
    # Split at the blank line nearest the midpoint.
    mid = len(body_lines) // 2
    blank_indices = [i for i, l in enumerate(body_lines) if not l.strip()]
    split_at = min(blank_indices, key=lambda i: abs(i - mid), default=mid)
    col1 = body_lines[:split_at]
    col2 = body_lines[split_at + 1:]  # skip the blank line itself

    col_lines = max(len(col1), len(col2))
    n_header = 1 + (1 if key_note else 0) + 1
    page_w = 612  # use full letter width for 2-col
    margin_x = 18
    col_gap = 18
    col_w = (page_w - 2 * margin_x - col_gap) / 2
    h = 24 + n_header * line_h + col_lines * line_h + 16

    pdf = pikepdf.Pdf.new()
    reg = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                       BaseFont=Name.Helvetica))
    bold_h = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                          BaseFont=Name("/Helvetica-Bold")))
    mono = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                        BaseFont=Name.Courier))
    mono_bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                             BaseFont=Name("/Courier-Bold")))
    page_obj = pdf.make_indirect(Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, page_w, h]),
        Resources=Dictionary(Font=Dictionary(F1=reg, F2=bold_h,
                                             F3=mono, F4=mono_bold)),
        Contents=pdf.make_stream(b""),
    ))
    pdf.pages.append(pikepdf.Page(page_obj))

    y = h - 22
    content = mp.text_op(title, margin_x, y, "/F2", 17)
    y -= line_h
    if key_note:
        content += mp.text_op(key_note, margin_x, y, "/F1", 11)
        y -= line_h
    y -= line_h

    col2_x = margin_x + col_w + col_gap
    for col_lines_list, x in ((col1, margin_x), (col2, col2_x)):
        cy = y
        for line in col_lines_list:
            font = "/F4" if _is_chord_line(line) else "/F3"
            content += mp.text_op(line, x, cy, font, font_size)
            cy -= line_h

    page_obj.Contents = pdf.make_stream(content)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def crop_pdf_page(pdf_bytes, crop):
    """Return pdf_bytes with the first page's MediaBox replaced by `crop`
    (left, bottom, right, top in points)."""
    l, b, r, t = crop
    with pikepdf.open(io.BytesIO(pdf_bytes)) as src:
        src.pages[0].mediabox = Array([l, b, r, t])
        buf = io.BytesIO()
        src.save(buf)
    return buf.getvalue()


def split_pdf_pages(pdf_bytes, only=None):
    """Return list of single-page pdf bytes. `only`, if given, is a list of
    0-based page indices to keep (default: all pages)."""
    out = []
    with pikepdf.open(io.BytesIO(pdf_bytes)) as src:
        indices = only if only is not None else range(len(src.pages))
        for i in indices:
            single = pikepdf.Pdf.new()
            single.pages.append(src.pages[i])
            buf = io.BytesIO()
            single.save(buf)
            out.append(buf.getvalue())
    return out


# (display name, kind, path-or-key, extra)
#   kind: "abc"  -> path is an .abc file (engraved, sepia)
#         "pdf"  -> path is a real source pdf; extra (if given) is the list
#                   of 0-based page indices to keep, else all pages
#         "odt"  -> path is a LibreOffice ODT; converted to PDF at build time;
#                   extra (if given) is the list of 0-based page indices to keep
#         "text" -> path is a clean chords/lyrics .txt file; extra is the
#                   key note shown under the title (or None)
ENTRIES = [
    ("Arkansas Traveler", "abc", os.path.join(ABC_DIR, "Arkansas Traveler-verified.abc"), None),
    ("Blackberry Blossom", "abc", os.path.join(ABC_DIR, "Blackberry Blossom-verified.abc"), None),
    ("Year of Jubilo", "abc", os.path.join(ABC_DIR, "Year of Jubilo-verified.abc"), None),
    # ("Faded Love", "text", os.path.join(REF_DIR, "Faded Love - lyrics chords.txt"),
    #  "Key: D (transposed up from source key of G)"),  # kept for future use
    ("Faded Love", "pdf", os.path.join(REF_DIR, "Faded Love D & A.pdf"), None),
    ("Flop Eared Mule", "abc", os.path.join(ABC_DIR, "Flop Eared Mule-verified.abc"), None),
    # ("Back Home Again in Indiana", "text", os.path.join(REF_DIR, "Back Home Again in Indiana - lyrics chords.txt"),
    #  "Key: G"),  # kept for future use
    ("Back Home Again in Indiana", "pdf", os.path.join(REF_DIR, "Back Home Again in Indiana.pdf"), None),
    ("Manitoba Golden Boy", "abc", os.path.join(ABC_DIR, "Manitoba Golden Boy-verified.abc"), None),
    ("Sleeping Giant Two-Step", "abc", os.path.join(ABC_DIR, "Sleeping Giant Two-Step-verified.abc"), None),
    ("Old Aunt Jenny (Nightcap On)", "abc", os.path.join(ABC_DIR, "Old Aunt Jenny with Her Nightcap on-verified.abc"), None),
    # ("Gum Tree Canoe", "text", os.path.join(REF_DIR, "Gum Tree Canoe - lyrics chords.txt"),
    #  "Key: G, transposed up from source key of D (paired with Tombigbee Waltz on the "
    #  "sheet, listed there as \"Guntree Canoe\")"),  # kept for future use
    ("Gum Tree Canoe", "odt", os.path.join(REF_DIR, "Gumtree Canoe_G.odt"), [0]),
    ("Tombigbee Waltz", "abc", os.path.join(ABC_DIR, "Tombigbee Waltz-verified.abc"), None),
    ("Red Red Robin", "odt", os.path.join(ODT_DIR, "red red robin.odt"), None),
    ("Roll in My Sweet Baby's Arms", "text", os.path.join(REF_DIR, "Roll in My Sweet Babys Arms - lyrics chords.txt"), "Key: G"),
    ("Down in Little Egypt", "abc", os.path.join(ABC_DIR, "Down in Little Egypt-verified.abc"), None),
    ("Rose in the Mountain", "abc", os.path.join(ABC_DIR, "Rose in the Mountain-verified.abc"), None),
    ("Rose in the Mountain", "pdf", os.path.join(REF_DIR, "Rose in the Mountain.pdf"), None),
    ("Sugar Moon", "pdf", os.path.join(REF_DIR, "Sugar Moon.pdf"), None),
    ("Drunken Sailor", "odt", os.path.join(ODT_DIR, "drunken sailor.odt"), None),
    ("Roll the Old Chariot Along", "pdf", os.path.join(REF_DIR, "Roll the Old Chariot Along.pdf"), None),
    ("Red Apple Rag", "abc", os.path.join(ABC_DIR, "Red Apple Rag-verified.abc"), None),
    ("Snake River Reel", "abc", os.path.join(ABC_DIR, "Snake River Reel-verified.abc"), None),
    ("Kansas City Kitty", "png", os.path.join(HERE, "source_images", "Kansas City Kitty-p1.png"), None),
    ("Kansas City Kitty", "png", os.path.join(HERE, "source_images", "Kansas City Kitty-p2.png"), None),
    ("Golden Ticket, The", "abc", os.path.join(ABC_DIR, "Golden Ticket, The-verified.abc"), None),
    ("Me and My Fiddle", "abc", os.path.join(ABC_DIR, "Me and My Fiddle-verified.abc"), None),
    ("Big Scioty", "abc", os.path.join(ABC_DIR, "Big Scioty-verified.abc"), None),
    ("Magpie", "abc", os.path.join(ABC_DIR, "Magpie-verified.abc"), None),
    ("Dill Pickles Rag", "abc", os.path.join(ABC_DIR, "Dill Pickles Rag-verified.abc"), None),
    ("Golden Slippers", "abc", os.path.join(ABC_DIR, "Golden Slippers-verified.abc"), None),
    ("Red Wing", "abc", os.path.join(ABC_DIR, "Red Wing-verified.abc"), None),
    ("Along the Navaho Trail", "pdf", os.path.join(REF_DIR, "Along the Navajo Trail chart.pdf"), None),
    ("Catfish John", "pdf", os.path.join(REF_DIR, "Catfish John chart.pdf"), None),
    ("Logger - Pays de Haut, The", "abc", os.path.join(ABC_DIR, "Logger - Pays de Haut, The-verified.abc"), None),
    ("Roscoe", "abc", os.path.join(ABC_DIR, "Roscoe-verified.abc"), None),
    ("Summertime", "abc", os.path.join(ABC_DIR, "Summertime-verified.abc"), None),
    ("Whistling Rufus", "abc", os.path.join(ABC_DIR, "Whistling Rufus-verified.abc"), None),
    ("Cumberland Gap", "abc", os.path.join(REF_DIR, "Cumberland Gap (lyrics version).abc"), None),
    ("Camp Meeting on the Fourth of July", "abc", os.path.join(ABC_DIR, "Camp Meeting on the Fourth of July-verified.abc"), None),
    ("America the Beautiful", "pdf", os.path.join(REF_DIR, "America the Beautiful.pdf"), None),
    ("You're A Grand Old Flag / Yankee Doodle Dandy", "odt",
     os.path.join(ODT_DIR, "GrandOldFlagMedley.odt"), None),
    ("Jefferson and Liberty", "abc", os.path.join(ABC_DIR, "Jefferson and Liberty-verified.abc"), None),
    ("Pat(T)'s Country", "abc", os.path.join(ABC_DIR, "Pat(T)'s Country-verified.abc"), None),
    ("Road House Ramble", "abc", os.path.join(ABC_DIR, "Road House Ramble-verified.abc"), None),
    # --- boxed "A tunes?" on the sheet ---
    ("Uncle Pen", "odt", os.path.join(REF_DIR, "Uncle Pen A.odt"), None),
    ("Uncle Pen", "odt", os.path.join(ODT_DIR, "Uncle Pen.odt"), None),
    ("Red Haired Boy", "abc", os.path.join(ABC_DIR, "Red Haired Boy-verified.abc"), None),
    ("Salt Spring", "abc", os.path.join(ABC_DIR, "Salt Spring-verified.abc"), None),
    ("Bill Cheatham", "abc", os.path.join(ABC_DIR, "Bill Cheatham-verified.abc"), None),
    ("Red Bird", "abc", os.path.join(ABC_DIR, "Red Bird-verified.abc"), None),
    ("Granny Will Your Dog Bite", "abc", os.path.join(ABC_DIR, "Granny Will Your Dog Bite-verified.abc"), None),
]


def render_content_page(out, fonts, page_items, usable_w, gap):
    """Like make_pdf.render_content_page, but sepia is driven by an explicit
    is_engraved flag per item instead of a `.abc` filename suffix, since our
    items are keyed by display name, not file path."""
    page_obj = mp.new_page(out, mp.PAGE_W, mp.PAGE_H, fonts)
    content = b""
    y = mp.PAGE_H - mp.MARGIN_TOP
    for i, (name, scaled_h, pdf_bytes, is_engraved) in enumerate(page_items):
        with pikepdf.open(io.BytesIO(pdf_bytes)) as src:
            src_w = float(src.pages[0].mediabox[2])
            xobj = out.copy_foreign(src.pages[0].as_form_xobject())
        xobj_name = f"/Fm{i}"
        page_obj.Resources.XObject[xobj_name] = xobj
        scale = usable_w / src_w
        tx = mp.MARGIN_X
        ty = y - scaled_h
        if mp.SEPIA and is_engraved:
            r, g, b = mp.SEPIA_RGB
            content += (f"q {r:.4f} {g:.4f} {b:.4f} rg "
                        f"{tx:.2f} {ty:.2f} {usable_w:.2f} {scaled_h:.2f} re f Q\n").encode()
        content += (f"q {scale:.6f} 0 0 {scale:.6f} {tx:.2f} {ty:.2f} cm "
                    f"{xobj_name} Do Q\n").encode()
        y = ty - gap
    page_obj.Contents = out.make_stream(content)
    return page_obj


def odt_to_pdf_bytes(odt_path):
    """Convert a LibreOffice ODT to PDF bytes using headless LibreOffice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, odt_path],
            check=True, capture_output=True,
        )
        stem = os.path.splitext(os.path.basename(odt_path))[0]
        pdf_path = os.path.join(tmpdir, stem + ".pdf")
        with open(pdf_path, "rb") as f:
            return f.read()


def build(output):
    mp.SEPIA = False  # this book shows engraved tunes plain, not sepia-washed
    usable_w = mp.PAGE_W - 2 * mp.MARGIN_X
    usable_h = mp.PAGE_H - mp.MARGIN_TOP - mp.MARGIN_BOTTOM

    # items: (display_name, scaled_h, pdf_bytes, is_engraved)
    items = []
    for i, (name, kind, path, extra) in enumerate(ENTRIES, 1):
        print(f"  [{i}/{len(ENTRIES)}] {kind}: {name}")
        if kind == "abc":
            pdf_bytes = mp.abc_to_pdf_bytes(path)
            w, h = mp.get_pdf_size(pdf_bytes)
            items.append((name, h * (usable_w / w), pdf_bytes, True))
        elif kind in ("pdf", "odt"):
            if kind == "odt":
                raw = odt_to_pdf_bytes(path)
            else:
                with open(path, "rb") as f:
                    raw = f.read()
            for page_bytes in split_pdf_pages(raw, only=extra):
                if name in PDF_CROP:
                    page_bytes = crop_pdf_page(page_bytes, PDF_CROP[name])
                w, h = mp.get_pdf_size(page_bytes)
                items.append((name, h * (usable_w / w), page_bytes, False))
        elif kind == "png":
            pdf_bytes = mp.png_to_pdf_bytes(path)
            w, h = mp.get_pdf_size(pdf_bytes)
            items.append((name, h * (usable_w / w), pdf_bytes, False))
        elif kind == "text":
            with open(path) as f:
                body_lines = f.read().splitlines()
            if name in TEXT_2COL:
                pdf_bytes = make_text_pdf_bytes_2col(name, extra, body_lines)
            else:
                font_size, line_h = TEXT_FONT_OVERRIDES.get(name, (TEXT_FONT_SIZE, TEXT_LINE_H))
                pdf_bytes = make_text_pdf_bytes(name, extra, body_lines, font_size, line_h)
            w, h = mp.get_pdf_size(pdf_bytes)
            items.append((name, h * (usable_w / w), pdf_bytes, False))
        else:
            raise ValueError(kind)

    pages = mp.pack_pages(
        [(n, h, b) for n, h, b, _ in items], mp.GAP_FALLBACK, usable_h)
    # pack_pages only groups by height, so re-attach is_engraved by walking
    # items in lockstep (pack_pages preserves item order/identity via height+bytes).
    flat_items = iter(items)
    pages_full = []
    for page in pages:
        page_full = []
        for _ in page:
            page_full.append(next(flat_items))
        pages_full.append(page_full)
    pages = pages_full
    _, _, _, _, n_toc_pages = mp.toc_geometry(len(ENTRIES))

    print(f"\nPacking {len(items)} item(s) for {len(ENTRIES)} tunes onto "
          f"{len(pages)} content pages (+{n_toc_pages} TOC page(s))...")

    out = pikepdf.Pdf.new()
    fonts = mp.make_fonts(out)

    # first content page each tune's name appears on
    tune_dest = {}
    for ci, page_items in enumerate(pages, 1):
        content_h = sum(h for _, h, _, _ in page_items)
        gap = (mp.GAP_PREFERRED
               if content_h + (len(page_items) - 1) * mp.GAP_PREFERRED <= usable_h
               else mp.GAP_FALLBACK)
        page_obj = render_content_page(out, fonts, page_items, usable_w, gap)
        printed = n_toc_pages + ci
        for fname, _, _, _ in page_items:
            if fname not in tune_dest:
                tune_dest[fname] = (printed, page_obj)

    # TOC in set-list order (not alphabetical) -- first occurrence per tune name
    seen = set()
    entries = []
    for name, _, _, _ in items:
        if name in seen:
            continue
        seen.add(name)
        entries.append((name, tune_dest[name][0], tune_dest[name][1]))
    mp.build_toc_pages(out, fonts, entries, n_toc_pages)

    print(f"Writing {output}...")
    out.save(output)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Sand and Sawdust 2026.pdf")
    build(out)
    print("Done.")
