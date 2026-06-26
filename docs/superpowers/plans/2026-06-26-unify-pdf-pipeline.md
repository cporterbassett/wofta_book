# Unify PDF Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the three tune-book PDF scripts onto one shared engine in `make_pdf.py`, removing the three duplicate build loops, the three content-page renderers, and the `SEPIA` global, while keeping every PDF visually identical.

**Architecture:** `make_pdf.py` becomes a pure engine library (renderer registry + `build_book` + `make_comparison_pdf` + shared machinery). A new `make_wofta.py` holds the WOFTA-specific glob/main logic. `make_sand_and_sawdust_pdf.py` and `make_tin_whistle_pdf.py` shrink to thin config (entry lists + one `build_book` call). Sepia becomes a `build_book` argument, not a mutated global.

**Tech Stack:** Python 3.12 (project `.venv`), `pikepdf`, `img2pdf`, `PIL`, `abcm2ps` + Ghostscript for ABC engraving, headless LibreOffice for ODT, `pdftoppm` (poppler) for verification rasterization.

## Global Constraints

- Always invoke Python through the project venv: `.venv/bin/python3` (never bare `python3`).
- Work from the repo root: `/home/porter/Documents/banjo/WOFTA/tune_images`.
- Generated PDFs are gitignored — never `git add` a `*.pdf`.
- No change to ABC engraving directives, packing geometry, TOC layout, or comparison layout. Output must remain **visually identical** (pixel-identical rasterization); byte-level PDF differences are expected and acceptable.
- The four output PDFs and their producers:
  - `WOFTA_tunes.pdf` + `WOFTA_tunes_comparison.pdf` ← `make_wofta.py`
  - `Sand and Sawdust 2026.pdf` ← `make_sand_and_sawdust_pdf.py`
  - `Tin Whistle.pdf` ← `make_tin_whistle_pdf.py`
- The six material kinds are fixed: `abc`, `png`, `pdf`, `odt`, `text`, `text_2col`. No new kinds.
- Git commits must not mention Claude or co-authorship.
- Verification artifacts live in the scratchpad dir, referred to below as `$SCRATCH`:
  `/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad`

---

### Task 1: Baseline + visual-diff harness

The refactor's "test" is a before/after pixel comparison. This task captures the current (pre-refactor) rendering of all four PDFs as the oracle every later task checks against.

**Files:**
- Create: `$SCRATCH/verify_pdfs.py`
- Create (output): `$SCRATCH/baseline.json`

**Interfaces:**
- Produces: a CLI harness with two modes —
  `verify_pdfs.py capture <out.json>` builds all four PDFs and writes `{pdf_name: [page_sha256, ...]}`;
  `verify_pdfs.py check <baseline.json>` rebuilds all four and exits 0 if every PDF has the same page count and pixel-identical pages, non-zero otherwise, printing a per-PDF `MATCH`/`DIFF` line.

- [ ] **Step 1: Write the harness script**

Create `$SCRATCH/verify_pdfs.py`:

```python
#!/usr/bin/env python3
"""Build all four tune PDFs and hash each rasterized page, to prove the
pipeline refactor keeps output visually identical. Run with the repo venv."""
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile

REPO = "/home/porter/Documents/banjo/WOFTA/tune_images"
PY = os.path.join(REPO, ".venv", "bin", "python3")

# (script, [output pdfs it produces]) — script invoked with no args uses defaults.
BUILDS = [
    ("make_wofta.py", ["WOFTA_tunes.pdf", "WOFTA_tunes_comparison.pdf"]),
    ("make_sand_and_sawdust_pdf.py", ["Sand and Sawdust 2026.pdf"]),
    ("make_tin_whistle_pdf.py", ["Tin Whistle.pdf"]),
]


def build_all():
    for script, _ in BUILDS:
        path = os.path.join(REPO, script)
        if not os.path.exists(path):
            raise SystemExit(f"missing build script: {script}")
        print(f"  building via {script} ...")
        subprocess.run([PY, path], cwd=REPO, check=True)


def page_hashes(pdf_path):
    """sha256 of each page rasterized at 100 dpi PNG."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "100", "-png", pdf_path,
                        os.path.join(td, "p")], check=True)
        out = []
        for png in sorted(glob.glob(os.path.join(td, "p*.png"))):
            with open(png, "rb") as f:
                out.append(hashlib.sha256(f.read()).hexdigest())
        return out


def snapshot():
    build_all()
    snap = {}
    for _, pdfs in BUILDS:
        for pdf in pdfs:
            snap[pdf] = page_hashes(os.path.join(REPO, pdf))
            print(f"  hashed {pdf}: {len(snap[pdf])} page(s)")
    return snap


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "capture":
        snap = snapshot()
        with open(sys.argv[2], "w") as f:
            json.dump(snap, f, indent=2)
        print(f"baseline written to {sys.argv[2]}")
    elif mode == "check":
        with open(sys.argv[2]) as f:
            baseline = json.load(f)
        current = snapshot()
        ok = True
        for pdf, base_hashes in baseline.items():
            cur = current.get(pdf, [])
            if cur == base_hashes:
                print(f"MATCH  {pdf} ({len(cur)} pages)")
            else:
                ok = False
                if len(cur) != len(base_hashes):
                    print(f"DIFF   {pdf}: {len(base_hashes)} -> {len(cur)} pages")
                else:
                    bad = [i for i, (a, b) in enumerate(zip(base_hashes, cur), 1) if a != b]
                    print(f"DIFF   {pdf}: pages differ -> {bad}")
        sys.exit(0 if ok else 1)
    else:
        raise SystemExit("usage: verify_pdfs.py capture|check <json>")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make the build scripts reachable for the harness**

The harness expects `make_wofta.py` (created in Task 3). For the baseline capture *now*, temporarily symlink it to the current WOFTA script so the baseline reflects today's output:

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
ln -sf make_pdf.py make_wofta.py
```

- [ ] **Step 3: Capture the baseline**

Run:
```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" capture "$SCRATCH/baseline.json"
```
Expected: four `hashed ... N page(s)` lines and `baseline written to ...`. Note the page counts.

- [ ] **Step 4: Remove the temporary symlink**

`make_wofta.py` will be a real file in Task 3; drop the stand-in so it isn't mistaken for the deliverable:

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
rm make_wofta.py
```

- [ ] **Step 5: Commit**

The harness lives in scratchpad (not the repo), so there is nothing to commit yet. Confirm clean:

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git status --short
```
Expected: only the pre-existing modified/untracked files from before this work; no `make_wofta.py`.

---

### Task 2: Add the engine (renderer registry + helpers + `build_book`) to `make_pdf.py`

Additive only — nothing is removed yet, so all three books keep building through their existing code paths. This makes the new API available; later tasks migrate each book onto it, and Task 6 deletes the dead old code.

**Files:**
- Modify: `make_pdf.py` (add new section near the end, before `main()`)

**Interfaces:**
- Consumes: existing `make_pdf` helpers — `PAGE_W`, `PAGE_H`, `MARGIN_X`, `MARGIN_TOP`, `MARGIN_BOTTOM`, `GAP_PREFERRED`, `GAP_FALLBACK`, `SEPIA_RGB`, `abc_to_pdf_bytes`, `png_to_pdf_bytes`, `get_pdf_size`, `pack_pages`, `toc_geometry`, `build_toc_pages`, `make_fonts`, `new_page`, `text_op`.
- Produces:
  - `make_text_pdf_bytes(title, key_note, body_lines, font_size=11, line_h=14.5) -> bytes`
  - `make_text_pdf_bytes_2col(title, key_note, body_lines, font_size=11, line_h=14.5) -> bytes`
  - `odt_to_pdf_bytes(odt_path) -> bytes`
  - `crop_pdf_page(pdf_bytes, crop) -> bytes`
  - `split_pdf_pages(pdf_bytes, only=None) -> list[bytes]`
  - `_is_chord_line(line) -> bool`
  - `RENDERERS: dict[str, callable]` where each callable has signature `(path, options: dict) -> list[tuple[bytes, bool]]` returning `(page_pdf_bytes, is_engraved)` per page.
  - `render_book_page(out, fonts, page_items, usable_w, gap, sepia) -> page_obj` where `page_items` are `(display_name, scaled_h, pdf_bytes, is_engraved)`.
  - `build_book(entries, *, output, sepia=False, toc_alphabetical=False)` where `entries` are `(display_name, kind, path, options)` and `options` is a dict (may be empty).

- [ ] **Step 1: Move the text/odt/crop/split helpers into `make_pdf.py`**

These currently live in `make_sand_and_sawdust_pdf.py`. Add them to `make_pdf.py` just after the `embed_form` function (around line 223), adapting the two text builders to call local helpers (drop the `mp.` prefix). Add `import re` to the import block at the top of `make_pdf.py`.

```python
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
```

- [ ] **Step 2: Add the renderer registry**

Append after the helpers from Step 1:

```python
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
```

Note: the text renderers need the display name as the page title, so `build_book` injects `display_name` into `options` before calling (Step 4).

- [ ] **Step 3: Add the unified content-page renderer**

Append:

```python
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
```

- [ ] **Step 4: Add `build_book`**

Append:

```python
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

    _, _, _, _, n_toc_pages = toc_geometry(len(items))
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
```

- [ ] **Step 5: Verify the module imports and all books still build identically**

`make_pdf.py` still has its old `main()`, `render_content_page`, and `SEPIA` global, so the three books are unchanged. Confirm the additions don't break import or output:

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
.venv/bin/python3 -c "import make_pdf; print('ok', bool(make_pdf.RENDERERS), bool(make_pdf.build_book))"
ln -sf make_pdf.py make_wofta.py   # harness still needs the WOFTA producer
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
rm make_wofta.py
```
Expected: `ok True True`, then four `MATCH` lines and exit 0.

- [ ] **Step 6: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add make_pdf.py
git commit -m "feat: add renderer registry, build_book engine to make_pdf"
```

---

### Task 3: Create `make_wofta.py`; point `make_pdf.sh` at it

Lift the WOFTA-specific glob/main logic out of `make_pdf.py` into its own thin script that uses `build_book`. `make_pdf.py`'s old `main()` stays for now (removed in Task 6) so nothing breaks mid-flight.

**Files:**
- Create: `make_wofta.py`
- Modify: `make_pdf.sh` (line invoking `make_pdf.py`)

**Interfaces:**
- Consumes: `make_pdf.build_book`, `make_pdf.make_comparison_pdf`, `make_pdf.stem_of`.
- Produces: `make_wofta.py` CLI — `make_wofta.py [main_out.pdf]` writes `main_out` (default `WOFTA_tunes.pdf`) and `<stem>_comparison.pdf`.

- [ ] **Step 1: Write `make_wofta.py`**

```python
#!/usr/bin/env python3
"""Build the two WOFTA tune PDFs:
  1. WOFTA_tunes.pdf            — every tune, engraved (verified ABC) preferred
     over scan; engraved tunes get a sepia wash; alphabetical TOC.
  2. WOFTA_tunes_comparison.pdf — engraved tunes, scan-left / engraving-right.

Run via ./make_pdf.sh (activates the venv and opens both in Firefox)."""
import glob
import os
import sys

import make_pdf as mp


def main():
    main_out = sys.argv[1] if len(sys.argv) > 1 else "WOFTA_tunes.pdf"
    comp_out = os.path.splitext(main_out)[0] + "_comparison.pdf"

    here = os.path.dirname(os.path.abspath(__file__))
    scan_dir = os.path.join(here, "source_images")
    abc_dir = os.path.join(here, "notation_pipeline", "abc")

    scans = {mp.stem_of(p): p for p in glob.glob(os.path.join(scan_dir, "*.png"))}
    verified = {os.path.basename(p)[:-len("-verified.abc")]: p
                for p in glob.glob(os.path.join(abc_dir, "*-verified.abc"))}

    tunes = sorted(set(scans) | set(verified),
                   key=lambda s: s.lower().replace("-", " "))
    if not tunes:
        print("No tunes found.", file=sys.stderr)
        sys.exit(1)

    entries = []
    for t in tunes:
        if t in verified:
            entries.append((t, "abc", verified[t], {}))
        else:
            entries.append((t, "png", scans[t], {}))

    n_eng = sum(1 for _, kind, _, _ in entries if kind == "abc")
    print(f"=== Book PDF: {len(entries)} tunes "
          f"({n_eng} engraved, {len(entries) - n_eng} scanned) ===")
    mp.build_book(entries, output=main_out, sepia=True, toc_alphabetical=True)

    print(f"\n=== Comparison PDF: {len(verified)} engraved tune(s), portrait packed ===")
    mp.make_comparison_pdf(verified, scans, comp_out)

    print("\nDone.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
chmod +x make_wofta.py
```

- [ ] **Step 3: Point `make_pdf.sh` at the new script**

In `make_pdf.sh`, change the invocation line:

```bash
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/make_pdf.py" "$MAIN_OUTPUT"
```
to:
```bash
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/make_wofta.py" "$MAIN_OUTPUT"
```

- [ ] **Step 4: Verify WOFTA output unchanged**

`make_wofta.py` is now a real file, so the harness uses it directly (no symlink):

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
```
Expected: four `MATCH` lines (including both WOFTA PDFs) and exit 0.

- [ ] **Step 5: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add make_wofta.py make_pdf.sh
git commit -m "feat: split WOFTA book into make_wofta.py using build_book"
```

---

### Task 4: Shrink `make_tin_whistle_pdf.py` to thin config

Replace its bespoke build loop with a single `build_book` call.

**Files:**
- Modify: `make_tin_whistle_pdf.py` (full rewrite of everything below `ENTRIES`)

**Interfaces:**
- Consumes: `make_pdf.build_book`.
- Produces: same CLI — `make_tin_whistle_pdf.py [out.pdf]` (default `Tin Whistle.pdf`).

- [ ] **Step 1: Rewrite the script**

Keep the `ENTRIES` data but give each entry the 4-tuple shape `(name, kind, path, options)`, and replace `build()` + `__main__` with a `build_book` call:

```python
#!/usr/bin/env python3
"""Build "Tin Whistle.pdf" — tin whistle repertoire, engraved (plain, no sepia).
Run via: .venv/bin/python3 make_tin_whistle_pdf.py"""
import os
import sys

import make_pdf as mp

HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
IMG_DIR = os.path.join(HERE, "source_images")

# (display name, kind, path, options)
ENTRIES = [
    ("Red Haired Boy", "abc", os.path.join(ABC_DIR, "Red Haired Boy-verified.abc"), {}),
    ("Far Away", "png", os.path.join(IMG_DIR, "Far Away.png"), {}),
    ("Little Donald in the Pigpen", "png", os.path.join(IMG_DIR, "Little Donald in the Pigpen.png"), {}),
    ("Eighth of January", "abc", os.path.join(ABC_DIR, "Eighth of January-verified.abc"), {}),
    ("Hey Polka", "abc", os.path.join(ABC_DIR, "Hey Polka-verified.abc"), {}),
    ("Arkansas Traveler", "abc", os.path.join(ABC_DIR, "Arkansas Traveler-verified.abc"), {}),
    ("Chinese Breakdown", "abc", os.path.join(ABC_DIR, "Chinese Breakdown-verified.abc"), {}),
    ("Angeline the Baker", "abc", os.path.join(ABC_DIR, "Angeline the Baker-verified.abc"), {}),
    ("Whiskey Before Breakfast", "abc", os.path.join(ABC_DIR, "Whiskey Before Breakfast-verified.abc"), {}),
    ("Liberty", "abc", os.path.join(ABC_DIR, "Liberty-verified.abc"), {}),
    ("The Boys of Blue Hill", "abc", os.path.join(ABC_DIR, "Boys of Blue Hill, The-verified.abc"), {}),
    ("Drowsy Maggie", "abc", os.path.join(ABC_DIR, "Drowsy Maggie-verified.abc"), {}),
    ("Kesh Jig", "abc", os.path.join(ABC_DIR, "Kesh Jig-verified.abc"), {}),
    ("Road to Lisdoonvarna", "abc", os.path.join(ABC_DIR, "Road to Lisdoonvarna, The-verified.abc"), {}),
    ("Red Wing", "abc", os.path.join(ABC_DIR, "Red Wing-verified.abc"), {}),
]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Tin Whistle.pdf")
    mp.build_book(ENTRIES, output=out, sepia=False, toc_alphabetical=False)
    print("Done.")
```

- [ ] **Step 2: Verify Tin Whistle output unchanged**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
```
Expected: four `MATCH` lines and exit 0.

- [ ] **Step 3: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add make_tin_whistle_pdf.py
git commit -m "refactor: tin whistle book as thin build_book config"
```

---

### Task 5: Shrink `make_sand_and_sawdust_pdf.py` to thin config

Replace its build loop, local `render_content_page`, and the side-tables (`TEXT_FONT_OVERRIDES`, `TEXT_2COL`, `PDF_CROP`) with a single `build_book` call, folding per-tune quirks into each entry's `options`. The text/odt/crop/split helpers it used now live in `make_pdf.py` (Task 2), so its local copies are deleted.

**Files:**
- Modify: `make_sand_and_sawdust_pdf.py` (full rewrite)

**Interfaces:**
- Consumes: `make_pdf.build_book`.
- Produces: same CLI — `make_sand_and_sawdust_pdf.py [out.pdf]` (default `Sand and Sawdust 2026.pdf`).

- [ ] **Step 1: Rewrite the script**

The entry conversions from the current `ENTRIES`:
- `("name", "text", path, key_note)` → `("name", "text", path, {"key_note": key_note})`, plus `"font_size"/"line_h"` from `TEXT_FONT_OVERRIDES` (only `Catfish John`: `9, 11.5` — but note Catfish John is now a `pdf` entry, so no text override is actually needed; the only remaining `text` entry is "Roll in My Sweet Baby's Arms", which is in `TEXT_2COL`).
- `"Roll in My Sweet Baby's Arms"` was in `TEXT_2COL` → kind becomes `text_2col`.
- `pdf`/`odt` entries with a page list (4th field was the `only` indices) → `{"pages": [...]}`. Only `Gum Tree Canoe` has `[0]`.
- `PDF_CROP` is currently empty, so no `crop` options.

```python
#!/usr/bin/env python3
"""Build "Sand and Sawdust 2026.pdf" — the working set list in printed-sheet
order (not alphabetical). Repeated tunes collapse to first occurrence. Engraved
tunes are shown plain (no sepia). Each tune uses the best material on hand:
verified/candidate ABC, a real source PDF/ODT, or a clean chords/lyrics text page.

Run via: .venv/bin/python3 make_sand_and_sawdust_pdf.py"""
import os
import sys

import make_pdf as mp

HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
REF_DIR = os.path.join(HERE, "notation_pipeline", "reference_sources")
ODT_DIR = HERE
IMG_DIR = os.path.join(HERE, "source_images")

# (display name, kind, path, options)
#   kind: abc | png | pdf | odt | text | text_2col
#   options: {} | {"pages": [0-based ints]} | {"crop": (l,b,r,t)}
#            | {"key_note": str, "font_size": n, "line_h": n}
ENTRIES = [
    ("Arkansas Traveler", "abc", os.path.join(ABC_DIR, "Arkansas Traveler-verified.abc"), {}),
    ("Blackberry Blossom", "abc", os.path.join(ABC_DIR, "Blackberry Blossom-verified.abc"), {}),
    ("Year of Jubilo", "abc", os.path.join(ABC_DIR, "Year of Jubilo-verified.abc"), {}),
    ("Faded Love", "pdf", os.path.join(REF_DIR, "Faded Love D & A.pdf"), {}),
    ("Flop Eared Mule", "abc", os.path.join(ABC_DIR, "Flop Eared Mule-verified.abc"), {}),
    ("Back Home Again in Indiana", "pdf", os.path.join(REF_DIR, "Back Home Again in Indiana.pdf"), {}),
    ("Manitoba Golden Boy", "abc", os.path.join(ABC_DIR, "Manitoba Golden Boy-verified.abc"), {}),
    ("Sleeping Giant Two-Step", "abc", os.path.join(ABC_DIR, "Sleeping Giant Two-Step-verified.abc"), {}),
    ("Old Aunt Jenny (Nightcap On)", "abc", os.path.join(ABC_DIR, "Old Aunt Jenny with Her Nightcap on-verified.abc"), {}),
    ("Gum Tree Canoe", "odt", os.path.join(REF_DIR, "Gumtree Canoe_G.odt"), {"pages": [0]}),
    ("Tombigbee Waltz", "abc", os.path.join(ABC_DIR, "Tombigbee Waltz-verified.abc"), {}),
    ("Red Red Robin", "odt", os.path.join(ODT_DIR, "red red robin.odt"), {}),
    ("Roll in My Sweet Baby's Arms", "text_2col", os.path.join(REF_DIR, "Roll in My Sweet Babys Arms - lyrics chords.txt"), {"key_note": "Key: G"}),
    ("Down in Little Egypt", "abc", os.path.join(ABC_DIR, "Down in Little Egypt-verified.abc"), {}),
    ("Rose in the Mountain", "abc", os.path.join(ABC_DIR, "Rose in the Mountain-verified.abc"), {}),
    ("Rose in the Mountain", "pdf", os.path.join(REF_DIR, "Rose in the Mountain.pdf"), {}),
    ("Sugar Moon", "pdf", os.path.join(REF_DIR, "Sugar Moon.pdf"), {}),
    ("Drunken Sailor", "odt", os.path.join(ODT_DIR, "drunken sailor.odt"), {}),
    ("Roll the Old Chariot Along", "pdf", os.path.join(REF_DIR, "Roll the Old Chariot Along.pdf"), {}),
    ("Red Apple Rag", "abc", os.path.join(ABC_DIR, "Red Apple Rag-verified.abc"), {}),
    ("Snake River Reel", "abc", os.path.join(ABC_DIR, "Snake River Reel-verified.abc"), {}),
    ("Kansas City Kitty", "png", os.path.join(IMG_DIR, "Kansas City Kitty-p1.png"), {}),
    ("Kansas City Kitty", "png", os.path.join(IMG_DIR, "Kansas City Kitty-p2.png"), {}),
    ("Golden Ticket, The", "abc", os.path.join(ABC_DIR, "Golden Ticket, The-verified.abc"), {}),
    ("Me and My Fiddle", "abc", os.path.join(ABC_DIR, "Me and My Fiddle-verified.abc"), {}),
    ("Big Scioty", "abc", os.path.join(ABC_DIR, "Big Scioty-verified.abc"), {}),
    ("Magpie", "abc", os.path.join(ABC_DIR, "Magpie-verified.abc"), {}),
    ("Dill Pickles Rag", "abc", os.path.join(ABC_DIR, "Dill Pickles Rag-verified.abc"), {}),
    ("Golden Slippers", "abc", os.path.join(ABC_DIR, "Golden Slippers-verified.abc"), {}),
    ("Red Wing", "abc", os.path.join(ABC_DIR, "Red Wing-verified.abc"), {}),
    ("Along the Navaho Trail", "pdf", os.path.join(REF_DIR, "Along the Navajo Trail chart.pdf"), {}),
    ("Catfish John", "pdf", os.path.join(REF_DIR, "Catfish John chart.pdf"), {}),
    ("Logger - Pays de Haut, The", "abc", os.path.join(ABC_DIR, "Logger - Pays de Haut, The-verified.abc"), {}),
    ("Roscoe", "abc", os.path.join(ABC_DIR, "Roscoe-verified.abc"), {}),
    ("Summertime", "abc", os.path.join(ABC_DIR, "Summertime-verified.abc"), {}),
    ("Whistling Rufus", "abc", os.path.join(ABC_DIR, "Whistling Rufus-verified.abc"), {}),
    ("Cumberland Gap", "abc", os.path.join(REF_DIR, "Cumberland Gap (lyrics version).abc"), {}),
    ("Camp Meeting on the Fourth of July", "abc", os.path.join(ABC_DIR, "Camp Meeting on the Fourth of July-verified.abc"), {}),
    ("America the Beautiful", "pdf", os.path.join(REF_DIR, "America the Beautiful.pdf"), {}),
    ("You're A Grand Old Flag / Yankee Doodle Dandy", "odt", os.path.join(ODT_DIR, "GrandOldFlagMedley.odt"), {}),
    ("Jefferson and Liberty", "abc", os.path.join(ABC_DIR, "Jefferson and Liberty-verified.abc"), {}),
    ("Pat(T)'s Country", "abc", os.path.join(ABC_DIR, "Pat(T)'s Country-verified.abc"), {}),
    ("Road House Ramble", "abc", os.path.join(ABC_DIR, "Road House Ramble-verified.abc"), {}),
    # --- boxed "A tunes?" on the sheet ---
    ("Uncle Pen", "odt", os.path.join(REF_DIR, "Uncle Pen A.odt"), {}),
    ("Uncle Pen", "odt", os.path.join(ODT_DIR, "Uncle Pen.odt"), {}),
    ("Red Haired Boy", "abc", os.path.join(ABC_DIR, "Red Haired Boy-verified.abc"), {}),
    ("Salt Spring", "abc", os.path.join(ABC_DIR, "Salt Spring-verified.abc"), {}),
    ("Bill Cheatham", "abc", os.path.join(ABC_DIR, "Bill Cheatham-verified.abc"), {}),
    ("Red Bird", "abc", os.path.join(ABC_DIR, "Red Bird-verified.abc"), {}),
    ("Granny Will Your Dog Bite", "abc", os.path.join(ABC_DIR, "Granny Will Your Dog Bite-verified.abc"), {}),
]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Sand and Sawdust 2026.pdf")
    mp.build_book(ENTRIES, output=out, sepia=False, toc_alphabetical=False)
    print("Done.")
```

- [ ] **Step 2: Verify Sand & Sawdust output unchanged**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
```
Expected: four `MATCH` lines and exit 0.

> If `Sand and Sawdust 2026.pdf` shows `DIFF`, the most likely cause is the
> `text`/`text_2col` title: the old code passed the display name as `title` and
> the `key_note` as the line under it. Confirm `_render_text`/`_render_text_2col`
> pass `options["display_name"]` as the title and `options["key_note"]` as the
> subtitle (Task 2, Step 2). Re-run after fixing.

- [ ] **Step 3: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add make_sand_and_sawdust_pdf.py
git commit -m "refactor: sand & sawdust book as thin build_book config"
```

---

### Task 6: Remove dead code from `make_pdf.py`

All three books now use `build_book`; the old WOFTA-specific `main()`, the old `render_content_page`, and the `SEPIA` global are dead. Remove them so `make_pdf.py` is a pure engine.

**Files:**
- Modify: `make_pdf.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `make_pdf.py` with no `main()`, no `__main__` block, no module-level `SEPIA`, no old `render_content_page`/`make_main_pdf`.

- [ ] **Step 1: Delete the old book-builder code**

Remove from `make_pdf.py`:
- the `SEPIA = os.environ.get(...)` line and its comment block (keep `SEPIA_RGB`).
- `render_content_page` (the old `.abc`-suffix sepia version) — superseded by `render_book_page`.
- `pack_pages` is still used by `build_book` — KEEP it.
- `make_main_pdf` — superseded by `build_book`.
- `main()` and the `if __name__ == "__main__": main()` block — moved to `make_wofta.py`.

`make_comparison_pdf` references `embed_form(..., sepia=SEPIA)`. Change its signature to `make_comparison_pdf(verified, scans, output, sepia=True)` and use the parameter; update the call in `make_wofta.py` to `mp.make_comparison_pdf(verified, scans, comp_out, sepia=True)`. The `render_comparison_page` helper takes `sepia` through the same path — thread the parameter down (it currently reads the global via `embed_form(..., sepia=SEPIA)`).

- [ ] **Step 2: Verify nothing references the removed names**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
grep -rn --include=*.py -E "\bSEPIA\b|make_main_pdf|\.render_content_page|mp\.SEPIA" . | grep -v SEPIA_RGB | grep -v .venv
```
Expected: no output (every reference to the removed globals/functions is gone).

- [ ] **Step 3: Verify all four PDFs still identical**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
```
Expected: four `MATCH` lines and exit 0.

- [ ] **Step 4: Commit**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add make_pdf.py make_wofta.py
git commit -m "refactor: make make_pdf.py a pure engine, drop SEPIA global and old main"
```

---

### Task 7: Final smoke test + docs touch-up

**Files:**
- Modify: `README.md` (if it documents the build scripts)

- [ ] **Step 1: Full clean rebuild via the wrapper**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
SCRATCH="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/e677f4cb-244c-4fe1-a8dc-44a90d9555c7/scratchpad"
.venv/bin/python3 "$SCRATCH/verify_pdfs.py" check "$SCRATCH/baseline.json"
```
Expected: four `MATCH` lines and exit 0.

- [ ] **Step 2: Update README if it names `make_pdf.py` as the WOFTA entry point**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
grep -n "make_pdf" README.md || echo "no README reference"
```
If it references `make_pdf.py` as the script to run for the WOFTA book, change it to `make_wofta.py` (or `./make_pdf.sh`). If no reference, skip.

- [ ] **Step 3: Commit any doc change**

```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git add README.md && git commit -m "docs: point WOFTA build at make_wofta.py" || echo "nothing to commit"
```

---

## Notes for the implementer

- The verify harness rebuilds **all four** PDFs every `check`; ABC engraving + LibreOffice conversion makes a full run take a couple minutes. That's expected.
- `pdftoppm` at 100 dpi is the equality oracle. If a real visual change is intended later, re-capture the baseline; for this refactor, any `DIFF` is a regression.
- Do not `git add` PDFs (gitignored) or the scratchpad harness.
