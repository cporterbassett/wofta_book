#!/usr/bin/env bash
# Shortcut: open an existing candidate ABC in the live compare + EasyABC workflow,
# skipping Audiveris and re-export. Equivalent to:
#   verify_tune.sh --no-export "Tune Name"
#
# If no candidate ABC exists but a verified ABC does, copies the verified file to
# candidate so it can be re-edited.
#
# Usage:
#   edit_tune.sh "Tune Name"

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${HERE}/.." && pwd)"

TUNE="${1:?Usage: edit_tune.sh \"Tune Name\"}"
CAND="${PIPELINE_DIR}/abc/${TUNE}-candidate.abc"
VERIFIED="${PIPELINE_DIR}/abc/${TUNE}-verified.abc"

if [[ ! -f "$CAND" && -f "$VERIFIED" ]]; then
    echo "No candidate found; copying verified → candidate for re-edit."
    cp "$VERIFIED" "$CAND"
fi

exec bash "${HERE}/verify_tune.sh" --no-export "$@"
