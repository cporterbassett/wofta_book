#!/usr/bin/env python3
"""
Strip noise inters from an Audiveris .omr file before opening in the GUI.

Removes (along with all their SIG relations):
  - slur, wedge                    (CURVES step output)
  - articulation, bow, ornament    (decoration inters)
  - dynamics                       (dynamic marking inters)

This means the user never sees or has to manually delete these spurious
elements in the GUI. If a real slur needs adding back, it takes one
drag in the GUI — much faster than hunting down spurious ones.

Usage:
  python3 clean_omr.py input.omr [output.omr]
  (if output is omitted, overwrites input in place)
"""

import sys
import zipfile
import io
import re
import xml.etree.ElementTree as ET

# Inter element names to strip (XML tag names in sheet#N.xml)
STRIP_INTER_TAGS = {
    'slur', 'wedge',
    'articulation', 'bow', 'ornament',
    'dynamics',
}


def clean_sheet_xml(text):
    """Remove noise inters and all their relations from a sheet XML string."""
    root = ET.fromstring(text)

    # ── 1. Collect IDs of inters to remove ────────────────────────────────────
    remove_ids = set()
    for tag in STRIP_INTER_TAGS:
        for el in root.findall(f'.//{tag}'):
            id_val = el.get('id')
            if id_val:
                remove_ids.add(id_val)

    if not remove_ids:
        return text  # nothing to do

    # ── 2. Remove the inter elements themselves ────────────────────────────────
    for tag in STRIP_INTER_TAGS:
        for parent in root.findall(f'.//{tag}/..'):
            for el in list(parent.findall(tag)):
                if el.get('id') in remove_ids:
                    parent.remove(el)

    # ── 3. Remove relations that reference any removed inter ──────────────────
    for rel_parent in root.findall('.//relation/..'):
        for rel in list(rel_parent.findall('relation')):
            if rel.get('source') in remove_ids or rel.get('target') in remove_ids:
                rel_parent.remove(rel)

    # ── 4. Clean <slurs> text lists (space- or comma-separated IDs) ──────────
    for slurs_el in root.findall('.//slurs'):
        if slurs_el.text:
            ids = re.split(r'[\s,]+', slurs_el.text.strip())
            kept = [i for i in ids if i and i not in remove_ids]
            slurs_el.text = ' '.join(kept) if kept else None

    return ET.tostring(root, encoding='unicode', xml_declaration=False)


def clean_omr(input_path, output_path):
    with zipfile.ZipFile(input_path, 'r') as zin:
        entries = {}
        for name in zin.namelist():
            entries[name] = zin.read(name)

    modified = 0
    for name, data in entries.items():
        if re.match(r'sheet#\d+/sheet#\d+\.xml$', name):
            cleaned = clean_sheet_xml(data.decode('utf-8'))
            # clean_sheet_xml returns the original text (declaration intact) when
            # there's nothing to strip, but ET.tostring(...) emits none. Strip any
            # leading declaration so we always prepend exactly one — otherwise a
            # sheet with no strippable inters ends up with a doubled <?xml ?> PI,
            # which Audiveris rejects ("processing instruction ... not allowed").
            cleaned = re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', cleaned)
            entries[name] = ('<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned).encode('utf-8')
            modified += 1

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())

    print(f"Cleaned {modified} sheet(s): {input_path} -> {output_path}")
    print(f"  Stripped inter types: {', '.join(sorted(STRIP_INTER_TAGS))}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.omr [output.omr]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else inp
    clean_omr(inp, out)
