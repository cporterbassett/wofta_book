#!/usr/bin/env bash
# Shortcut: re-open an existing tune in the live compare + EasyABC workflow,
# skipping Audiveris and re-export. Equivalent to:
#   verify_tune.sh --no-export "Tune Name"
#
# verify_tune picks the file to edit:
#   - if the tune is already verified, it edits the -verified.abc IN PLACE
#     (no candidate is created — your edits land straight in the book);
#   - otherwise it reuses the existing -candidate.abc draft.
#
# Usage:
#   edit_tune.sh "Tune Name"

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${1:?Usage: edit_tune.sh \"Tune Name\"}"

exec bash "${HERE}/verify_tune.sh" --no-export "$@"
