#!/usr/bin/env python3
"""Compose a side-by-side current-vs-new comparison PDF, one tune per LANDSCAPE page.

Layout per page:
  - tune title (top, centered)
  - two columns: OLD (left) vs NEW (right), each cropped + scaled to its column
  - a difference-description text band across the bottom

Usage: compose_diff.py <work_dir> <out.pdf> <map.txt> <left_label> <descriptions.json> [band_header]
  work_dir holds <tune>-cur.png (left) and <tune>-new.png (right)
  map.txt  is pipe-delimited "tune|pdf" lines (first field = tune key)
  band_header (optional) overrides the bottom description-band heading.
"""
import sys, os, io, json
from PIL import Image, ImageDraw, ImageFont
import img2pdf

WORK, OUT, MAP, LEFT_LABEL, DESCJSON = sys.argv[1:6]
BAND_HEADER = sys.argv[6] if len(sys.argv) > 6 else "Change applied (left = your updated engraving):"

DPI = 200
PAGE_W, PAGE_H = 2200, 1700          # landscape letter @ 200dpi
MARGIN = 50
GUTTER = 40
COL_W = (PAGE_W - 2 * MARGIN - GUTTER) // 2
TITLE_H = 70
LABEL_H = 44
TEXT_BAND_H = 360                    # bottom description band
PANEL_TOP = MARGIN + TITLE_H + LABEL_H + 6
PANEL_MAXH = PAGE_H - PANEL_TOP - TEXT_BAND_H - MARGIN

def font(sz, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans%s.ttf"):
        p = p % ("-Bold" if bold else "")
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def content_crop(im, pad=18):
    """Crop to the dense notation block, ignoring faint specks / lone © glyphs.

    A row/column counts as content only if its ink (dark) pixel count exceeds a
    fraction of the image dimension, so isolated marks and copyright glyphs don't
    defeat the crop the way a raw bounding box does."""
    g = im.convert("L")
    px = g.load()
    w, h = g.size
    # Downsample columns for speed: count dark pixels per row/col via point ops.
    bw = g.point(lambda v: 255 if v < 160 else 0)
    # row sums
    import numpy as np
    a = np.asarray(bw, dtype=np.uint8) // 255
    rows = a.sum(axis=1)
    cols = a.sum(axis=0)
    rT = max(8, int(0.025 * w))      # a row needs >=2.5% of width in ink
    cT = max(8, int(0.025 * h))
    rmask = np.where(rows > rT)[0]
    cmask = np.where(cols > cT)[0]
    if len(rmask) == 0 or len(cmask) == 0:
        return im
    t, b = rmask[0], rmask[-1]
    l, r = cmask[0], cmask[-1]
    l = max(0, l - pad); t = max(0, t - pad)
    r = min(w, r + pad); b = min(h, b + pad)
    return im.crop((l, t, r, b))

def fit(im, maxw, maxh):
    im = content_crop(im)
    scale = min(maxw / im.width, maxh / im.height)
    if scale < 1 or scale > 1:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    return im

def wrap(d, text, fnt, maxw):
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=fnt) <= maxw:
            line = trial
        else:
            if line: out.append(line)
            line = word
    if line: out.append(line)
    return out

desc = json.load(open(DESCJSON))
tunes = [l.split("|", 1)[0].strip() for l in open(MAP)
         if l.strip() and not l.lstrip().startswith("#")]

pages = []
for tune in tunes:
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(page)
    # title
    tf = font(58, bold=True)
    d.text(((PAGE_W - d.textlength(tune, font=tf)) / 2, MARGIN), tune, fill="black", font=tf)
    # column labels
    lf = font(30, bold=True)
    cols = [(MARGIN, LEFT_LABEL, (224, 238, 255)),
            (MARGIN + COL_W + GUTTER, "NEW 2026 PDF", (255, 240, 224))]
    yL = MARGIN + TITLE_H
    for x, label, tint in cols:
        d.rectangle([x, yL, x + COL_W, yL + LABEL_H], fill=tint)
        d.text((x + 8, yL + 7), label, fill=(40, 40, 40), font=lf)
    # images
    for (x, label, tint), suffix in zip(cols, ("cur", "new")):
        path = os.path.join(WORK, f"{tune}-{suffix}.png")
        if os.path.exists(path):
            im = fit(Image.open(path).convert("RGB"), COL_W, PANEL_MAXH)
            page.paste(im, (x + (COL_W - im.width) // 2, PANEL_TOP))
        else:
            d.text((x + 8, PANEL_TOP), "(missing)", fill="red", font=font(30))
    # description band
    by = PAGE_H - TEXT_BAND_H - MARGIN + 10
    d.line([(MARGIN, by - 10), (PAGE_W - MARGIN, by - 10)], fill=(180, 180, 180), width=2)
    hf = font(30, bold=True)
    d.text((MARGIN, by), BAND_HEADER, fill=(0, 0, 0), font=hf)
    by += 44
    bf = font(28)
    for line in wrap(d, desc.get(tune, ""), bf, PAGE_W - 2 * MARGIN):
        d.text((MARGIN, by), line, fill=(20, 20, 20), font=bf)
        by += 36
    pages.append(page)

bufs = []
for p in pages:
    b = io.BytesIO(); p.save(b, format="PNG"); bufs.append(b.getvalue())
layout = img2pdf.get_layout_fun((img2pdf.in_to_pt(PAGE_W / DPI), img2pdf.in_to_pt(PAGE_H / DPI)))
with open(OUT, "wb") as f:
    f.write(img2pdf.convert(bufs, layout_fun=layout))
print(f"wrote {OUT} ({len(pages)} pages)")
