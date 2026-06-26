# Unify the three PDF pipelines onto one engine

**Date:** 2026-06-26
**Status:** Approved, ready for implementation plan

## Problem

There are three scripts that each build a tune-book PDF:

- `make_pdf.py` — WOFTA book (`WOFTA_tunes.pdf`) + side-by-side comparison
  (`WOFTA_tunes_comparison.pdf`). Auto-discovers tunes by glob.
- `make_sand_and_sawdust_pdf.py` — "Sand and Sawdust 2026.pdf", explicit
  set-list order, mixed material (abc/png/pdf/odt/text/text-2col).
- `make_tin_whistle_pdf.py` — "Tin Whistle.pdf", explicit list (abc/png).

The latter two already `import make_pdf as mp` and reuse its helpers, so an
engine already exists — but the duplication the user flagged is real:

- **Three near-identical `build()` loops** (convert each entry → scale → pack →
  render content pages → build TOC).
- **Three copies of the content-page renderer**: `make_pdf.render_content_page`,
  `make_sand_and_sawdust_pdf.render_content_page` (sepia by explicit flag), and
  the tin-whistle inline loop (no sepia). They differ only in how sepia is decided.
- **Per-kind dispatch split across files**: the `abc`/`png`/`odt`/`pdf`/`text`/
  `text_2col` renderers and their helpers (`make_text_pdf_bytes`,
  `make_text_pdf_bytes_2col`, `odt_to_pdf_bytes`, `crop_pdf_page`,
  `split_pdf_pages`) live only in the S&S script, unavailable to the others.
- **`SEPIA` is a module global** that S&S and tin-whistle mutate as a side effect
  (`mp.SEPIA = False`) — fragile and order-dependent.

## Goal

Refactor **and** unify behavior (user choice): one consistent code path for all
three books, removing the duplicate loops, the three content-page renderers, and
the `SEPIA` global. Minor cosmetic changes are acceptable only if they fall out
of the unification; the three PDFs should remain visually identical (see
Verification).

## Design

### Module layout

`make_pdf.py` becomes a **pure engine library** — no book-specific `main()`.
All three books are peers that import it.

- **`make_pdf.py`** (engine): renderer registry; the text/2col/odt/pdf/crop/split
  helpers (moved up from the S&S script); `build_book(...)`;
  `make_comparison_pdf(...)`; and the shared packing/TOC/font machinery
  (`pack_pages`, `toc_geometry`, `build_toc_pages`, `make_fonts`, `new_page`,
  `text_op`, `embed_form`, `abc_to_pdf_bytes`, `png_to_pdf_bytes`,
  `get_pdf_size`). The `SEPIA` module global is removed.
- **`make_wofta.py`** (new): the old `make_pdf.py:main()` lifted out. Imports
  `make_pdf`, globs `source_images/*.png` and
  `notation_pipeline/abc/*-verified.abc`, builds entries, calls
  `build_book(..., sepia=True, toc_alphabetical=True)` → `WOFTA_tunes.pdf`, then
  `make_comparison_pdf(...)` → `WOFTA_tunes_comparison.pdf`.
- **`make_sand_and_sawdust_pdf.py`**: thin config — the `ENTRIES` list + one
  `build_book(..., sepia=False, toc_alphabetical=False)` call.
- **`make_tin_whistle_pdf.py`**: thin config — the `ENTRIES` list + one
  `build_book(..., sepia=False)` call (default `toc_alphabetical=False`).
- **`make_pdf.sh`**: updated to run `make_wofta.py` instead of `make_pdf.py`
  (the comparison-output path logic and `firefox` opens are unchanged).

### Entry format & renderer registry

Every book describes its content as a list of entries with one shape:

```python
(display_name, kind, path, options)
```

`kind` dispatches into a **renderer registry** — a dict mapping `kind` → function.
Each renderer takes `(path, options)` and returns a list of
`(pdf_bytes, is_engraved)` (a list because `pdf`/`odt` sources can contribute
multiple pages):

| kind        | renderer            | is_engraved | options used                          |
|-------------|---------------------|-------------|---------------------------------------|
| `abc`       | `render_abc`        | True        | —                                     |
| `png`       | `render_png`        | False       | —                                     |
| `pdf`       | `render_pdf`        | False       | `pages` (0-based indices), `crop`     |
| `odt`       | `render_odt`        | False       | `pages`, `crop` (convert then split)  |
| `text`      | `render_text`       | False       | `key_note`, `font_size`, `line_h`     |
| `text_2col` | `render_text_2col`  | False       | `key_note`, `font_size`, `line_h`     |

`is_engraved` is intrinsic to the renderer (it is the old `.abc`-suffix check,
made explicit). Sepia is then `sepia and is_engraved` at render time.

The S&S side-tables (`TEXT_FONT_OVERRIDES`, `TEXT_2COL`, `PDF_CROP`) fold into
per-entry `options`, so a tune's quirks sit next to the tune. (`text_2col`
becomes its own `kind` rather than a name-membership lookup.)

### `build_book` behavior

```python
def build_book(entries, *, output, sepia=False, toc_alphabetical=False):
```

The single loop that replaces all three `build()` functions:

1. For each entry, look up the renderer by `kind`, call `(path, options)` →
   list of `(pdf_bytes, is_engraved)`. For each returned page compute scaled
   height vs. `usable_w`. Collect a flat list
   `items = [(display_name, scaled_h, pdf_bytes, is_engraved), ...]`.
2. `pack_pages(items_by_height, GAP_FALLBACK, usable_h)` — greedy first-fit,
   unchanged. (Keep the existing per-page gap upgrade to `GAP_PREFERRED` when a
   page's content still fits.)
3. Render each content page with the **single** content-page renderer: draw the
   sepia wash when `sepia and is_engraved`. Replaces all three renderers.
4. TOC: destinations keyed by **first occurrence** of each `display_name`
   (multi-page/duplicate tunes collapse to their first page — current behavior).
   `toc_alphabetical=True` → sorted order (WOFTA); `False` → set-list/insertion
   order (S&S, tin-whistle).

`make_comparison_pdf` stays a separate function (its side-by-side layout is
unique) but keeps using the shared `abc_to_pdf_bytes` / `png_to_pdf_bytes` /
`embed_form` / TOC helpers.

### Behavior reconciliations

- **Tin Whistle**: loses its bespoke inline render loop; output identical.
- **Sand & Sawdust**: its custom `render_content_page` is replaced by the shared
  one with the same sepia-by-flag logic; output identical. `mp.SEPIA = False`
  side effect replaced by `sepia=False` argument.
- **WOFTA**: `main()` moves to `make_wofta.py`; book + comparison output identical.

## Verification

No automated tests exist. Verify by before/after comparison using the `.venv`
python:

1. **Before** (current `master`): build all three books (and WOFTA comparison).
   Record page count and per-page raster hashes via `pdftoppm`.
2. **After** (refactor): rebuild all four PDFs.
3. **Compare**: identical page count per PDF and pixel-identical pages
   (rasterize + diff). Byte-level differences are expected (PDF object ordering);
   any **visual** diff is a regression to fix before claiming done.

## Out of scope

- No change to ABC engraving directives, packing geometry, TOC layout, or the
  comparison layout.
- No new book types or material kinds beyond the six already in use.
- No unrelated refactoring of the notation pipeline.
