#!/usr/bin/env python3
"""
Merge Audiveris movement-split MXL files into one MusicXML score.

When Audiveris splits a score into movements, batch export writes
clean.mvt1.mxl / clean.mvt2.mxl ... instead of a single clean.mxl. Each is a
standalone single-part score covering one chunk of the tune (e.g. the first pass
of the A part vs. the rest). Picking just one movement silently drops the others
-- the "big chunks missing" bug. This concatenates them, in the given order, into
one MXL: every movement's <measure>s are appended to the first movement's <part>,
renumbered sequentially.

Because each movement restates <divisions>/<key>/<time> in its first measure,
movements with different note-length or meter settings merge correctly -- those
are allowed to change mid-part in MusicXML.

Mirrors clean_mxl.py: reads/writes zipped .mxl over unnamespaced XML.

Usage:
  merge_movements.py output.mxl in1.mxl in2.mxl [in3.mxl ...]
"""

import sys
import io
import zipfile
import xml.etree.ElementTree as ET

# Barline styles that mean "end of piece" -- stripped at the joins so an internal
# movement boundary doesn't render as a final barline mid-tune.
_FINAL_BARSTYLES = {'light-heavy', 'heavy-light', 'final'}


def read_mxl(path):
    """Return (xml_name, root, other_files) for an MXL archive."""
    with zipfile.ZipFile(path, 'r') as z:
        names = z.namelist()
        xml_name = next(n for n in names if n.endswith('.xml') and 'META' not in n)
        root = ET.fromstring(z.read(xml_name))
        other = {n: z.read(n) for n in names if n != xml_name}
    return xml_name, root, other


def first_part(root):
    p = root.find('part')
    if p is None:
        sys.exit("merge_movements: no <part> found in a movement")
    return p


def strip_final_barline(measure):
    for bl in list(measure.findall('barline')):
        if bl.get('location') == 'right' and bl.findtext('bar-style') in _FINAL_BARSTYLES:
            measure.remove(bl)


def mark_system_break(measure):
    pr = measure.find('print')
    if pr is None:
        pr = ET.Element('print')
        measure.insert(0, pr)
    pr.set('new-system', 'yes')


def merge(out_path, in_paths):
    xml_name, base_root, other = read_mxl(in_paths[0])
    base_part = first_part(base_root)

    movements = [base_root] + [read_mxl(p)[1] for p in in_paths[1:]]
    measure_lists = [first_part(r).findall('measure') for r in movements]

    # Rebuild the base part's measures fresh, in movement order.
    for m in list(base_part.findall('measure')):
        base_part.remove(m)

    num = 0
    last = len(measure_lists) - 1
    for i, measures in enumerate(measure_lists):
        if not measures:
            continue
        if i > 0:
            mark_system_break(measures[0])   # keep movements on their own lines
        if i != last:
            strip_final_barline(measures[-1])  # no final barline at an internal join
        for m in measures:
            num += 1
            m.set('number', str(num))
            base_part.append(m)

    body = ET.tostring(base_root, encoding='unicode')
    data = ('<?xml version="1.0" encoding="UTF-8"?>\n' + body).encode('utf-8')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(xml_name, data)
        for name, blob in other.items():
            z.writestr(name, blob)
    with open(out_path, 'wb') as f:
        f.write(buf.getvalue())
    return num


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(f"Usage: {sys.argv[0]} output.mxl in1.mxl [in2.mxl ...]")
    out, ins = sys.argv[1], sys.argv[2:]
    total = merge(out, ins)
    print(f"Merged {len(ins)} movement(s) -> {out}  ({total} measures)")
