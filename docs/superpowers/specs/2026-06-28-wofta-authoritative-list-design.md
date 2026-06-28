# WOFTA Authoritative Tune List — Design

Date: 2026-06-28

## Problem

`book/make_wofta.py` has no roster of what belongs in the WOFTA Chapter 5 book.
It builds membership purely by globbing the filesystem:

- top-level scans: `sources/scans/*.png`
- verified ABCs: `abc/*-verified.abc`

(plus `sources/scans/verified/*.png` for the comparison PDF only). The display
key for each entry is the file stem — `os.path.splitext(basename)` — with the
verified-ABC stem being `<name>` from `<name>-verified.abc`.

Because membership is implicit, anything sourced for a *different* book leaks in.
In particular, tunes sourced for the **Sand & Sawdust 2026** working set
(captured 2026-06-23, see `transcribe/reports/sand_and_sawdust_2026.md`) that
happen to land as a scan or a verified ABC silently appear in the WOFTA book.

## What counts as "came in for Sand & Sawdust and wasn't there before"

Determined by **git history diff** (the method chosen during brainstorming),
cutoff = **2026-06-23** (the date the S&S set list was captured):

For each current WOFTA tune, find the earliest date *any* of its
WOFTA-contributing files entered the repo — its top-level scan, its verified
ABC, **or** its scan now sitting in `sources/scans/verified/` (a tune's scan
moves there when it is verified). Renames are followed (`git log --follow`) so
the reorg of 2026-06-27 does not reset dates. A tune is "new for S&S" iff that
earliest date is on/after the cutoff.

This per-*tune* (not per-file) metric is essential: many 2026-06-23 commits
merely *verified* tunes that already had scans in WOFTA (e.g. Logger, Whistling
Rufus, Roscoe). Their scans predate the cutoff, so they correctly stay.

### Result — 8 tunes / 10 membership keys to exclude

All 8 trace to the S&S report; no unrelated tunes were caught.

| Source path that leaked it | Tunes |
|---|---|
| WOTFAhandouts scan (`sources/scans/*.png`) | Kansas City Kitty (keys `Kansas City Kitty`, `Kansas City Kitty-p1`, `Kansas City Kitty-p2`), Roll the Old Chariot Along, Sugar Moon, Red Red Robin, Cumberland Gap |
| Verified ABC (`abc/*-verified.abc`) | Rose in the Mountain, Summertime, Old Aunt Jenny with Her Nightcap on |

Other S&S tunes (Gum Tree Canoe, Grand Old Flag / Yankee Doodle, Faded Love,
Back Home Again in Indiana, Drunken Sailor, Along the Navajo Trail, Catfish
John, Roll in My Sweet Baby's Arms, Uncle Pen, America the Beautiful) are
sourced only as `odt/` / `text/` / `pdf/` — formats the WOFTA book never reads —
so they were never in the WOFTA book and need no action.

Counts: current build produces **292** membership keys; after removing the 10
above, **282** remain.

## Components

### 1. `book/wofta_tunes.txt` — the allow-list

- The **282 authoritative membership keys**, one per line, sorted
  case-insensitively (matching `make_wofta`'s sort:
  `key=lambda s: s.lower().replace("-", " ")`).
- Keys are the **exact stems** `make_wofta` computes — *not* normalized.
  This protects real tune names that end in a digit but are not page numbers:
  `Morrison's Jig 2`, `Ross's Reel #4`, `seneca-square-dance 2`,
  `star-above-the-garter2`. A normalizing list would mangle these
  (`Ross's Reel #4` → `Ross's Reel #`) or collide them with a sibling
  (`Morrison's Jig 2` → `Morrison's Jig`), silently dropping a tune.
- `#`-comment header records: purpose, derivation (git diff, cutoff
  2026-06-23), and the 8 excluded tunes. Lines starting with `#` and blank
  lines are ignored by the loader.
- The known duplicate strays (`Morrison's Jig 2`, `seneca-square-dance 2`,
  `star-above-the-garter2`) **stay on the list for now** — they are real
  current book entries; reconciling them is deferred (see `TODO.md`).

### 2. `book/make_wofta.py` — filter by the list

- Load `book/wofta_tunes.txt` into a set (ignoring `#`/blank lines).
- Build entries from the glob exactly as today, then **keep only entries whose
  key is in the set**. A globbed file whose key is *not* on the list is
  **silently skipped** — no warning. (The list is the sole source of truth for
  what's in; extra files on disk are simply not in the book.)
- **Before building, validate the list against disk: every list key must match
  a current file** (a top-level scan stem or a verified-ABC stem). If any list
  key has no matching file, **exit with an error** naming the offending keys.
  This keeps the roster from drifting out of sync.
- Both the main book and the comparison PDF use the filtered set.

### 3. `TODO.md` (repo root) — tune reconciliation backlog

Records duplicates to fold together in a future session (not this one). Each
tune currently appears twice in the book:

- **Morrison's Jig** — canonical `Morrison's Jig.png` + `Morrison's Jig-draft.abc`;
  stray `Morrison's Jig 2.png` + `Morrison's Jig 2-draft.abc`; also
  `sources/pdfs/add-ons-2026/Morrison's Jig fixed.pdf`. One tune, two scans.
- **Seneca Square Dance** — canonical is **verified**:
  `sources/scans/verified/Seneca Square Dance.png` +
  `abc/Seneca Square Dance-verified.abc`; stray `seneca-square-dance 2.png` +
  `seneca-square-dance 2-draft.abc`.
- **Star Above the Garter** — canonical `Star Above the Garter, The.png` +
  `Star Above the Garter, The-draft.abc`; stray `star-above-the-garter2.png` +
  `star-above-the-garter2-draft.abc`.

Each entry notes that removing the stray will also require deleting its key from
`book/wofta_tunes.txt`. `Ross's Reel #4` is **not** a duplicate — that is the
tune's real name; no action.

## Out of scope

- The Sand & Sawdust and Tin Whistle builds (already curated via explicit
  `ENTRIES` lists in their scripts).
- The multi-page "`Tune-p1`/`-p2` becomes separate entries" quirk (only ever
  affected Kansas City Kitty, which is excluded).
- Actually reconciling the three duplicate tunes (deferred to `TODO.md`).

## Acceptance

- `book/wofta_tunes.txt` exists with 282 keys; none of the 10 excluded keys
  present; the four digit-ending real names present and intact.
- `make_wofta.py` builds the main + comparison PDFs containing exactly the
  listed tunes; the 8 S&S tunes are absent.
- Removing a line from the list and rebuilding drops that tune silently;
  adding a list key with no matching file makes the build exit with an error
  naming it.
- `TODO.md` exists at repo root with the three reconciliation entries.
