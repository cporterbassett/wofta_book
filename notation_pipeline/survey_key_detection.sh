#!/usr/bin/env bash
# Survey key and meter detection at original DPI (no preprocessing) across WOFTA tunes.
# Runs Audiveris on each image, extracts key/meter from measure 1 of MXL output.
# Usage: bash survey_key_detection.sh [output_file.tsv]
#
# Output: TSV with columns: tune, fifths, mode, beats, beat-type

set -uo pipefail

IMAGES_DIR="/home/porter/Documents/banjo/WOFTA/tune_images"
WORKDIR="${IMAGES_DIR}/notation_pipeline"
SURVEY_DIR="${WORKDIR}/tmp_pipeline/survey"
OUTPUT="${1:-${WORKDIR}/survey_results.tsv}"

mkdir -p "$SURVEY_DIR"

# Map fifths → key name
fifths_to_key() {
    local fifths="$1" mode="${2:-major}"
    case "$fifths" in
        -7) echo "Cb" ;; -6) echo "Gb" ;; -5) echo "Db" ;;
        -4) echo "Ab" ;; -3) echo "Eb" ;; -2) echo "Bb" ;;
        -1) echo "F"  ;; 0)  echo "C"  ;; 1)  echo "G"  ;;
        2)  echo "D"  ;; 3)  echo "A"  ;; 4)  echo "E"  ;;
        5)  echo "B"  ;; 6)  echo "F#" ;; 7)  echo "C#" ;;
        *) echo "?" ;;
    esac
}

# Extract key and meter from first key/time elements in MXL
extract_from_mxl() {
    local mxl="$1"
    python3 - "$mxl" << 'PYEOF'
import sys, zipfile, xml.etree.ElementTree as ET

mxl_path = sys.argv[1]
try:
    with zipfile.ZipFile(mxl_path) as z:
        for n in z.namelist():
            if not n.startswith('META') and n.endswith('.xml'):
                data = z.read(n)
                break
    root = ET.fromstring(data)
except Exception as e:
    print(f"ERROR\t?\t?\t?\t{e}")
    sys.exit(1)

fifths = None
mode = 'major'
beats = None
beat_type = None

for part in root.iter('part'):
    for measure in part.iter('measure'):
        attrs = measure.find('attributes')
        if attrs is None:
            continue
        key_elem = attrs.find('key')
        if key_elem is not None and fifths is None:
            f = key_elem.findtext('fifths')
            m = key_elem.findtext('mode')
            if f is not None:
                fifths = f
                if m:
                    mode = m
        time_elem = attrs.find('time')
        if time_elem is not None and beats is None:
            beats = time_elem.findtext('beats')
            beat_type = time_elem.findtext('beat-type')
        if fifths is not None and beats is not None:
            break
    if fifths is not None and beats is not None:
        break

print(f"{fifths or 'none'}\t{mode}\t{beats or '?'}\t{beat_type or '?'}")
PYEOF
}

echo -e "tune\tfifths\tmode\tbeats\tbeat_type\tkey_name" > "$OUTPUT"

TUNES=(
    "Bill Cheatham"
    "Billy in the Lowground"
    "Booth Shot Lincoln"
    "Calliope House"
    "Cherokee Shuffle"
    "Cluck Old Hen"
    "Devil's Dream"
    "Fisher's Hornpipe"
    "Flop Eared Mule"
    "Forked Deer"
    "June Apple"
    "Liberty"
    "Lost Indian"
    "Mississippi Sawyer"
    "Morrison's Jig"
    "Old Joe Clark"
    "Red Haired Boy"
    "Salt Creek"
    "Soldier's Joy"
    "Turkey in the Straw"
)

TOTAL=${#TUNES[@]}
echo "Surveying $TOTAL tunes at original DPI..." >&2

for i in "${!TUNES[@]}"; do
    TUNE="${TUNES[$i]}"
    SRC="${IMAGES_DIR}/${TUNE}.png"
    TUNE_DIR="${SURVEY_DIR}/${TUNE}"
    MXL_DIR="${TUNE_DIR}/mxl"

    echo "[$(( i + 1 ))/$TOTAL] $TUNE" >&2

    if [[ ! -f "$SRC" ]]; then
        echo -e "${TUNE}\tMISSING\t-\t-\t-\t-" >> "$OUTPUT"
        echo "  MISSING image" >&2
        continue
    fi

    mkdir -p "$MXL_DIR"

    # Run Audiveris at original DPI
    flatpak run org.audiveris.audiveris -batch -export -output "$MXL_DIR" "$SRC" \
        > "${TUNE_DIR}/audiveris.log" 2>&1 || true

    MXL=$(find "$MXL_DIR" -name "*.mxl" | head -1)
    if [[ -z "$MXL" ]]; then
        echo -e "${TUNE}\tNO_MXL\t-\t-\t-\t-" >> "$OUTPUT"
        echo "  No MXL produced" >&2
        continue
    fi

    # Extract key and meter
    RESULT=$(extract_from_mxl "$MXL")
    FIFTHS=$(echo "$RESULT" | cut -f1)
    MODE=$(echo "$RESULT" | cut -f2)
    BEATS=$(echo "$RESULT" | cut -f3)
    BEAT_TYPE=$(echo "$RESULT" | cut -f4)

    if [[ "$FIFTHS" =~ ^-?[0-9]+$ ]]; then
        KEY_NAME=$(fifths_to_key "$FIFTHS" "$MODE")
    else
        KEY_NAME="?"
    fi

    echo -e "${TUNE}\t${FIFTHS}\t${MODE}\t${BEATS}\t${BEAT_TYPE}\t${KEY_NAME}" >> "$OUTPUT"
    echo "  Key: ${KEY_NAME} (fifths=${FIFTHS}, mode=${MODE})  Meter: ${BEATS}/${BEAT_TYPE}" >&2
done

echo "" >&2
echo "Done. Results in: $OUTPUT" >&2
cat "$OUTPUT"
