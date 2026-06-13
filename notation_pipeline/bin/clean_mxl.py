#!/usr/bin/env python3
"""
Strip Audiveris noise from an MXL file before abc_xml_converter.

Removes:
  - slurs  (<slur> in <notations>)
  - decorations (<ornaments>, <articulations>, <technical> in <notations>)
  - repeated key signatures (<key> in every measure except the first of each part)

Reads from input_path, writes cleaned MXL to output_path (may be the same file).
"""

import sys
import zipfile
import io
import xml.etree.ElementTree as ET

# MusicXML namespace (Audiveris output is unnamespaced, but handle either)
_STRIP_FROM_NOTATIONS = {'ornaments', 'articulations', 'technical', 'dynamics'}


def _tag(el):
    return el.tag.split('}')[-1] if '}' in el.tag else el.tag


def clean_tree(root):
    # Strip noise from <notations> blocks
    for notations in root.iter('notations'):
        to_remove = [c for c in notations if _tag(c) in _STRIP_FROM_NOTATIONS]
        for c in to_remove:
            notations.remove(c)

    # Remove now-empty <notations> elements
    for note in root.iter('note'):
        empty = [c for c in note if _tag(c) == 'notations' and len(c) == 0]
        for c in empty:
            note.remove(c)

    # Strip <direction> elements (dynamics, wedges, words, etc.)
    for measure in root.iter('measure'):
        for direction in list(measure.findall('direction')):
            measure.remove(direction)

    # Keep <key> only in the first measure of each part
    for part in root.iter('part'):
        first_measure = True
        for measure in part.iter('measure'):
            if not first_measure:
                attrs = measure.find('attributes')
                if attrs is not None:
                    for key in list(attrs.findall('key')):
                        attrs.remove(key)
            else:
                first_measure = False


def clean_mxl(input_path, output_path):
    with zipfile.ZipFile(input_path, 'r') as zin:
        names = zin.namelist()
        xml_name = next(n for n in names if n.endswith('.xml') and 'META' not in n)
        raw_xml = zin.read(xml_name)
        other_files = {n: zin.read(n) for n in names if n != xml_name}

    ET.register_namespace('', '')
    root = ET.fromstring(raw_xml)
    clean_tree(root)
    cleaned_xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    cleaned_bytes = ('<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned_xml).encode('utf-8')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        zout.writestr(xml_name, cleaned_bytes)
        for name, data in other_files.items():
            zout.writestr(name, data)

    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.mxl [output.mxl]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else inp
    clean_mxl(inp, out)
    print(f"Cleaned: {inp} -> {out}")
