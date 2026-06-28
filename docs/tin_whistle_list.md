# Tin Whistle Repertoire

A curated list of 10 tin whistle tunes, maintained as both a simple text list and an automatically-generated PDF.

## The List

1. Red Haired Boy
2. Little Donald in the Pigpen
3. Eighth of January
4. Hey Polka
5. Arkansas Traveler
6. Chinese Breakdown
7. Angeline the Baker
8. Whiskey Before Breakfast
9. Liberty
10. Kesh Jig

## Files

- **`tin_whistle_list.txt`** — The source list (plain text, easy to edit)
- **`make_tin_whistle_pdf.py`** — Script to generate the PDF from ABC notation files
- **`Tin Whistle.pdf`** — The generated PDF (7 pages: 1 TOC + 6 content pages)

## Regenerating the PDF

After editing `tin_whistle_list.txt`, update the `ENTRIES` list in `make_tin_whistle_pdf.py` and run:

```bash
source .venv/bin/activate
python3 make_tin_whistle_pdf.py
```

This will regenerate `Tin Whistle.pdf` with any new or updated tune notations from the `notation_pipeline/abc/` directory.

## Notes

- All tunes use verified ABC notation except *Little Donald in the Pigpen*, which uses the draft version
- The PDF uses plain engraved notation (no sepia wash)
- Tunes are packed efficiently across pages with consistent spacing
