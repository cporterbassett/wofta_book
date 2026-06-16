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
from collections import Counter

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

    # Strip <lyric> elements. Audiveris OCRs prose printed on the page (e.g. the
    # instructional paragraph on Dill Pickles Rag) as note lyrics, which become
    # garbled `w:` lines that break ABC rendering. These tunes have no real lyrics.
    for note in root.iter('note'):
        for lyric in [c for c in note if _tag(c) == 'lyric']:
            note.remove(lyric)

    # Remove now-empty <notations> elements
    for note in root.iter('note'):
        empty = [c for c in note if _tag(c) == 'notations' and len(c) == 0]
        for c in empty:
            note.remove(c)

    # Strip <direction> elements (dynamics, wedges, words, etc.)
    for measure in root.iter('measure'):
        for direction in list(measure.findall('direction')):
            measure.remove(direction)

    # Collapse to a single voice. These are monophonic fiddle/banjo tunes, so any
    # secondary voice Audiveris detects is an OMR artifact (a few stray notes/rests
    # that the user does not want). Keep the dominant voice per part and drop the
    # rest, along with the <backup>/<forward> cursor moves that only existed to
    # interleave the extra voice.
    for part in root.iter('part'):
        counts = Counter()
        for note in part.iter('note'):
            v = note.find('voice')
            if v is not None and v.text:
                counts[v.text] += 1
        if len(counts) <= 1:
            continue
        keep = counts.most_common(1)[0][0]
        for measure in part.iter('measure'):
            for note in list(measure.findall('note')):
                v = note.find('voice')
                if v is not None and v.text and v.text != keep:
                    measure.remove(note)
            for mover in list(measure.findall('backup')) + list(measure.findall('forward')):
                measure.remove(mover)

    # Keep <key> and <clef> only in the first measure of each part. Audiveris
    # restates the clef at a system break (e.g. Pink Eye Lament's measure 9, the
    # start of line 2); abc_xml_converter emits that as a bogus inline `[K:treble]`
    # which downstream tools read as a KEY change, resetting accidentals and
    # mangling the rest of the tune. These are single-clef monophonic tunes, so any
    # later clef is a redundant restatement and safe to drop.
    for part in root.iter('part'):
        first_measure = True
        for measure in part.iter('measure'):
            if not first_measure:
                attrs = measure.find('attributes')
                if attrs is not None:
                    for stale in list(attrs.findall('key')) + list(attrs.findall('clef')):
                        attrs.remove(stale)
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
