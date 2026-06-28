# TODO

## Tune reconciliation backlog

Each of these tunes currently appears **twice** in the WOFTA book: a canonical
entry plus a stray duplicate under a second filename. Fold each pair into a
single tune in a future session. When a stray is removed, also delete its key
from `book/wofta_tunes.txt` (the build will otherwise fail, since every listed
key must match a file).

- **Star Above the Garter** — consolidate the stray into the canonical entry.
  - Canonical: `sources/scans/Star Above the Garter, The.png` +
    `abc/Star Above the Garter, The-draft.abc`
  - Stray: `sources/scans/star-above-the-garter2.png` +
    `abc/star-above-the-garter2-draft.abc`

Note: `Ross's Reel #4` is **not** a duplicate — that is the tune's real name.
