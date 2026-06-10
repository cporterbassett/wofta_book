#!/usr/bin/env python3
"""
Pack all PNGs in the current directory into a PDF.
- All images are scaled to the same width (widest image), maintaining aspect ratio.
- Images are stacked vertically per page; as many as fit without shrinking are packed together.
- Per page: use MARGIN=80/GAP=40 if it fits, otherwise MARGIN=40/GAP=20.
"""
import glob
import io
import sys
from PIL import Image
import img2pdf

MARGIN_PREFERRED = 80
MARGIN_FALLBACK  = 40
GAP_PREFERRED    = 40
GAP_FALLBACK     = 20


def load_and_scale(files, target_width):
    """Return list of (fname, scaled_height, original_width)."""
    result = []
    for f in files:
        with Image.open(f) as img:
            w, h = img.size
            new_h = round(h * target_width / w)
            result.append((f, new_h, w))
    return result


def pack_pages(images, gap, height_limit):
    """Greedy first-fit packing, preserving input order."""
    pages, current, current_h = [], [], 0
    for item in images:
        h = item[1]
        g = gap if current else 0
        if current and current_h + g + h > height_limit:
            pages.append(current)
            current, current_h = [item], h
        else:
            current.append(item)
            current_h += g + h
    if current:
        pages.append(current)
    return pages


def render_page(page_items, target_width, page_w, page_h, margin, gap):
    """Composite images onto a white canvas and return PNG bytes."""
    canvas = Image.new("RGB", (page_w, page_h), "white")
    y = margin
    for i, (fname, scaled_h, orig_w) in enumerate(page_items):
        with Image.open(fname) as img:
            if orig_w != target_width:
                img = img.resize((target_width, scaled_h), Image.LANCZOS)
            x = (page_w - target_width) // 2
            canvas.paste(img, (x, y))
        y += scaled_h + (gap if i < len(page_items) - 1 else 0)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "../WOFTA_tunes.pdf"

    files = sorted(glob.glob("*.png"))
    if not files:
        print("No PNG files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {len(files)} images...")
    # Target width = widest image (only upscale narrow ones, never shrink)
    raw_sizes = {}
    for f in files:
        with Image.open(f) as img:
            raw_sizes[f] = img.size
    target_width = max(w for w, h in raw_sizes.values())

    images = load_and_scale(files, target_width)
    max_scaled_h = max(h for _, h, _ in images)

    # Pack using the smaller gap for maximum density
    pages = pack_pages(images, GAP_FALLBACK, max_scaled_h)

    # Fixed page canvas (based on preferred/largest values)
    page_w = target_width + 2 * MARGIN_PREFERRED
    page_h = max_scaled_h + 2 * MARGIN_PREFERRED

    preferred_count = fallback_count = 0
    page_bytes = []
    for i, page_items in enumerate(pages, 1):
        content_h = sum(h for _, h, _ in page_items)
        gaps_preferred = (len(page_items) - 1) * GAP_PREFERRED
        if content_h + gaps_preferred <= max_scaled_h:
            margin, gap = MARGIN_PREFERRED, GAP_PREFERRED
            preferred_count += 1
        else:
            margin, gap = MARGIN_FALLBACK, GAP_FALLBACK
            fallback_count += 1
        print(f"  Page {i}/{len(pages)}: {len(page_items)} image(s), "
              f"margin={margin} gap={gap}", end="\r")
        page_bytes.append(render_page(page_items, target_width, page_w, page_h, margin, gap))

    print()
    print(f"Pages: {len(pages)} total  "
          f"({preferred_count} with margin={MARGIN_PREFERRED}/gap={GAP_PREFERRED}, "
          f"{fallback_count} with margin={MARGIN_FALLBACK}/gap={GAP_FALLBACK})")
    print(f"Writing {output}...")
    with open(output, "wb") as f:
        f.write(img2pdf.convert(page_bytes))
    print("Done.")


if __name__ == "__main__":
    main()
