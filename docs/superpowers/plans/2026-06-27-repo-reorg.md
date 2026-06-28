# Repo Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the `tune_images` repo into clear domains (`abc/`, `bin/`, `transcribe/`, `book/`, `sources/`), purge ~1.2 G of dead image churn from git history, preserve each tune's oldest raw scan + latest version, and fold in the sibling `../2026` published-PDF set.

**Architecture:** A destructive-but-backed-up sequence. First *rescue* each tune's oldest historical blob (the raw scans live inside soon-to-be-purged `new_book/`/`old_book/` history) to an out-of-repo temp. Then rewrite history with `git-filter-repo` to drop dead directories and root-level binaries. Then restructure the working tree with `git mv`, drop the rescued originals into place, import `../2026`, repoint all hardcoded paths, rewrite `.gitignore`, and verify the three book builders still produce PDFs.

**Tech Stack:** git, `git-filter-repo` (pip), Python 3 (the repo's `.venv`), bash. No new runtime dependencies.

## Global Constraints

- Work on branch `repo-reorg` (already created; spec already committed there). Never operate on `master` directly.
- The repo has **no remote** and a **single worktree** — history rewrite is safe, but it is irreversible without the backup, so the Task 1 backup is mandatory before Task 3.
- Configs must work on both Linux Mint and macOS (the user runs both). Any PATH mechanism must be cross-platform.
- Never commit `.venv/` (6.5 G), `__pycache__/`, OMR scratch (`batch_output/`, most of `reports/`), or generated book PDFs.
- Preserve, per tune: the **oldest** committed version (raw scan) and the **latest** working-tree version. Discard intermediate churn.
- `git mv` (not `mv`) for all relocations so history follows the files.
- In commit messages, never credit Claude / AI authorship.

---

## Task 1: Safety backup + tooling

**Files:**
- Create: `../tune_images_BACKUP_2026-06-27.tar` (out of repo)
- Modify: none

**Interfaces:**
- Produces: a full repo tarball (including `.git`) and a working `git-filter-repo` binary on PATH.

- [ ] **Step 1: Confirm branch and clean tracked state**

Run:
```bash
cd /home/porter/Documents/banjo/WOFTA/tune_images
git branch --show-current        # expect: repo-reorg
git status --porcelain | grep -v '^??' || echo "tracked tree clean"
```
Expected: branch is `repo-reorg`; no modified/staged tracked files (untracked `??` entries like the loose `.odt` files and `--help` are fine).

- [ ] **Step 2: Make the full backup (includes `.git`, excludes the huge venv)**

Run:
```bash
tar --exclude='./.venv' -cf ../tune_images_BACKUP_2026-06-27.tar -C . .
ls -lh ../tune_images_BACKUP_2026-06-27.tar
```
Expected: a tarball roughly 1.5–1.8 G (≈1.2 G `.git` + ~0.4 G files). This is the rollback point.

- [ ] **Step 3: Install git-filter-repo into the venv**

Run:
```bash
.venv/bin/pip install git-filter-repo
.venv/bin/git-filter-repo --version
```
Expected: prints a version (e.g. `git filter-repo 2.x`).

- [ ] **Step 4: Record the starting `.git` size for later comparison**

Run:
```bash
du -sh .git
```
Expected: ~1.2 G. Note this number — Task 3 verifies it drops.

No commit (nothing changed in the repo).

---

## Task 2: Rescue each tune's oldest raw scan

**Files:**
- Create: `/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/originals_rescue/` (out-of-repo temp holding ~290 PNGs)
- Modify: none

**Interfaces:**
- Produces: `originals_rescue/<TuneName>.png` for every current scan — the oldest committed blob (or the current file if the scan was never committed). Task 6 copies these into `sources/scans/originals/`.

Why out-of-repo: `git-filter-repo` (Task 3) wants a clean tree and rewrites the object DB; staging these now would either be purged or block the rewrite. Keep them aside, copy in afterward.

- [ ] **Step 1: Write the rescue script**

Create `/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/rescue_originals.sh`:
```bash
#!/usr/bin/env bash
# Extract the OLDEST committed version of each current scan (following renames),
# which reaches back into new_book/old_book history (the raw scans).
set -euo pipefail
cd /home/porter/Documents/banjo/WOFTA/tune_images
OUT="/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/originals_rescue"
rm -rf "$OUT"; mkdir -p "$OUT"
missing=0
# Both scan tiers; -z handles spaces in names.
git ls-files -z 'source_images/*.png' 'source_images/verified/*.png' \
 | while IFS= read -r -d '' p; do
    name="$(basename "$p")"
    # git log is newest-first; the LAST :raw line (END) is the oldest commit,
    # whose new-blob ($4) is the original content for this path.
    blob="$(git log --follow --format='%H' --raw -- "$p" 2>/dev/null \
            | awk '/^:/{b=$4} END{print b}')"
    if [ -n "${blob:-}" ] && git cat-file -e "$blob" 2>/dev/null; then
        git cat-file blob "$blob" > "$OUT/$name"
    else
        # Never committed (working-tree-only scan): keep the current file as its own original.
        cp "$p" "$OUT/$name"
        echo "WARN no history, used current: $name" >&2
    fi
done
echo "rescued: $(find "$OUT" -name '*.png' | wc -l)"
```

- [ ] **Step 2: Run it**

Run:
```bash
chmod +x /tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/rescue_originals.sh
/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/rescue_originals.sh
```
Expected: `rescued: 290` (±a few). Any `WARN no history` lines are acceptable and list scans that were never committed.

- [ ] **Step 3: Verify count matches the tracked scan count**

Run:
```bash
OUT=/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/originals_rescue
echo "tracked scans: $(git ls-files 'source_images/*.png' 'source_images/verified/*.png' | wc -l)"
echo "rescued:       $(find "$OUT" -name '*.png' | wc -l)"
du -sh "$OUT"
```
Expected: the two counts match; size is a few hundred MB (raw scans are ~1 MB each). **Do not proceed to Task 3 unless the counts match.**

- [ ] **Step 4: Sanity-check one rescued original looks like a raw scan**

Run:
```bash
OUT=/tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/originals_rescue
identify -format '%f %wx%h\n' "$OUT/Amelia.png"
```
Expected: prints dimensions; typically larger/full-page vs. the trimmed current scan — confirms we pulled the original, not the latest.

No commit (temp is out of repo).

---

## Task 3: Purge dead history

**Files:**
- Modify: git history (all commits)

**Interfaces:**
- Produces: a rewritten history with dead directories and root-level binaries removed; `.git` shrunk from ~1.2 G to well under 100 M.

Purged paths (all confirmed absent from the current tree): `new_book/` (56 M), `old_book/` (46 M), `notation_pipeline/web_images/`, `notation_pipeline/diffs/`, `notation_pipeline/renders/`, and every root-level `*.png`/`*.jpg`/`*.pdf` (104 M of old committed binaries; current root PDFs are already gitignored and untracked, so none are lost).

- [ ] **Step 1: Dry-run the purge analysis to eyeball what gets dropped**

Run:
```bash
git ls-files 'new_book/*' 'old_book/*' 'notation_pipeline/web_images/*' \
             'notation_pipeline/diffs/*' 'notation_pipeline/renders/*' | head
echo "current-tree files under purge dirs (should be EMPTY): $(git ls-files 'new_book/*' 'old_book/*' | wc -l)"
echo "current tracked ROOT binaries the regex would hit (should be NONE):"
git ls-files | grep -E '^[^/]+\.(png|jpe?g|pdf)$' || echo "NONE — regex purge is safe"
```
Expected: `0` current-tree files under the purge directories, and `NONE` for root binaries — confirms purging touches nothing still in use. **If either check is non-empty, stop and revise the purge args before running filter-repo.**

- [ ] **Step 2: Run git-filter-repo**

Run:
```bash
.venv/bin/git-filter-repo --force --invert-paths \
  --path new_book/ \
  --path old_book/ \
  --path notation_pipeline/web_images/ \
  --path notation_pipeline/diffs/ \
  --path notation_pipeline/renders/ \
  --path-regex '^[^/]+\.(png|jpe?g|pdf)$'
```
Expected: filter-repo runs, prints "Parsed N commits ... Repacking ... Completed successfully". It rewrites `repo-reorg` and `master` and repacks automatically.

- [ ] **Step 3: Verify the working tree is intact and history shrank**

Run:
```bash
du -sh .git
git log --oneline -3
ls make_pdf.py make_wofta.py && ls source_images | head -2
git ls-files | wc -l
```
Expected: `.git` is now well under 100 M (down from ~1.2 G); recent commits including the spec commit are still present; `make_*.py` and `source_images/` still exist in the working tree; tracked file count dropped.

- [ ] **Step 4: Confirm the spec commit survived**

Run:
```bash
git log --oneline -- docs/superpowers/specs/2026-06-27-repo-reorg-design.md
```
Expected: the "docs: add repo reorganization design spec" commit is listed.

No manual commit (filter-repo committed the rewrite).

---

## Task 4: New skeleton — promote `abc/` and `bin/`

**Files:**
- Create: `abc/`, `bin/`, `transcribe/`, `book/`, `sources/`, `sources/scans/`, `sources/pdfs/`, `sources/odt/`, `sources/text/`
- Modify (move): `notation_pipeline/abc/` → `abc/`; `notation_pipeline/bin/*` → `bin/`

**Interfaces:**
- Produces: top-level `abc/` (the crown-jewel transcriptions) and top-level `bin/` (scripts). Later tasks point code at `abc/` and add `bin/` to PATH.

- [ ] **Step 1: Create the directory skeleton**

Run:
```bash
mkdir -p bin transcribe book sources/scans sources/pdfs sources/odt sources/text
```

- [ ] **Step 2: Move ABC to top level**

Run:
```bash
git mv notation_pipeline/abc abc
ls abc/*.abc | wc -l
```
Expected: the ABC files now live in `abc/`; count is non-zero.

- [ ] **Step 3: Move the scripts to top-level `bin/`**

Run:
```bash
git mv notation_pipeline/bin/* bin/
rmdir notation_pipeline/bin 2>/dev/null || true
ls bin/*.sh bin/*.py | wc -l
```
Expected: ~22 scripts now in `bin/`.

- [ ] **Step 4: Commit**

Run:
```bash
git add -A
git commit -m "refactor: promote abc/ and bin/ to top level"
```

---

## Task 5: Relocate pipeline → `transcribe/` and build code → `book/`

**Files:**
- Modify (move): remaining `notation_pipeline/*` → `transcribe/`; `make_pdf.py`, `make_wofta.py`, `make_tin_whistle_pdf.py`, `make_sand_and_sawdust_pdf.py` → `book/`
- Modify: `make_pdf.sh` (path to `make_wofta.py`)

**Interfaces:**
- Consumes: nothing from prior tasks beyond the skeleton.
- Produces: `book/make_pdf.py` (engine, imported as `make_pdf`/`mp` by the others), `book/make_wofta.py`, `book/make_tin_whistle_pdf.py`, `book/make_sand_and_sawdust_pdf.py`. All four import each other by module name and resolve because they share `book/`.

- [ ] **Step 1: Move the remaining pipeline contents**

Run:
```bash
git mv notation_pipeline/docs transcribe/docs 2>/dev/null || true
for x in reference_sources reports tmp_pipeline health_scores.tsv tracking.md \
         verify_queue.txt verify_skip.txt README.md .gitignore; do
  [ -e "notation_pipeline/$x" ] && git mv "notation_pipeline/$x" "transcribe/$x" || true
done
ls notation_pipeline 2>/dev/null && echo "REMAINING ABOVE" || echo "notation_pipeline emptied"
```
Expected: leftover tracked pipeline files move under `transcribe/`. (Untracked `batch_output/`/`renders/` may still sit in `notation_pipeline/` — handled in Task 8's gitignore + a later physical move; ignore for now.)

- [ ] **Step 2: Move the four build scripts into `book/`**

Run:
```bash
git mv make_pdf.py make_wofta.py make_tin_whistle_pdf.py make_sand_and_sawdust_pdf.py book/
ls book/
```
Expected: all four `.py` files now in `book/`.

- [ ] **Step 3: Repoint `make_pdf.sh` at the moved entry script**

In `make_pdf.sh`, change line 9:
```bash
# OLD:
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/make_wofta.py" "$MAIN_OUTPUT"
# NEW:
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/book/make_wofta.py" "$MAIN_OUTPUT"
```

- [ ] **Step 4: Commit**

Run:
```bash
git add -A
git commit -m "refactor: split pipeline into transcribe/ and build code into book/"
```

---

## Task 6: Move scans into `sources/scans/` and drop in rescued originals

**Files:**
- Modify (move): `source_images/*` → `sources/scans/`
- Create: `sources/scans/originals/*.png` (from the Task 2 rescue temp)

**Interfaces:**
- Produces: `sources/scans/{*.png, verified/, originals/}` — the three-tier scan home the build code (fixed in Task 7) will read.

- [ ] **Step 1: Move the existing two scan tiers**

Run:
```bash
git mv source_images/verified sources/scans/verified
git mv source_images/*.png sources/scans/
rmdir source_images 2>/dev/null || true
echo "latest: $(ls sources/scans/*.png | wc -l)  verified: $(ls sources/scans/verified/*.png | wc -l)"
```
Expected: `latest: 170  verified: 120`.

- [ ] **Step 2: Copy in the rescued originals**

Run:
```bash
mkdir -p sources/scans/originals
cp /tmp/claude-1000/-home-porter-Documents-banjo-WOFTA-tune-images/26b45e9c-517b-49a5-b3e6-04e1c7a94a20/scratchpad/originals_rescue/*.png sources/scans/originals/
ls sources/scans/originals/*.png | wc -l
```
Expected: ~290 originals.

- [ ] **Step 3: Commit**

Run:
```bash
git add -A
git commit -m "refactor: move scans to sources/scans/ with originals tier"
```

---

## Task 7: Unify source PDFs/ODT/text + import ../2026 + repoint build paths

**Files:**
- Modify (move): loose root `*.odt` → `sources/odt/`; `transcribe/reference_sources/*.{pdf,odt,txt}` → `sources/{pdfs,odt,text}/`
- Create: `sources/pdfs/` content from `../2026`, `sources/pdfs/add-ons-2026/`, `sources/pdfs/MANIFEST.md`
- Modify: `book/make_wofta.py`, `book/make_tin_whistle_pdf.py`, `book/make_sand_and_sawdust_pdf.py`

**Interfaces:**
- Consumes: `sources/scans/` from Task 6.
- Produces: every build script's path constants resolve under the repo root regardless of the scripts now living in `book/`.

- [ ] **Step 1: Move loose root ODT and split reference_sources by format**

Run:
```bash
git add *.odt 2>/dev/null || true            # they were untracked; track then move
git mv *.odt sources/odt/ 2>/dev/null || true
for f in transcribe/reference_sources/*.pdf; do [ -e "$f" ] && git mv "$f" sources/pdfs/; done
for f in transcribe/reference_sources/*.odt; do [ -e "$f" ] && git mv "$f" sources/odt/; done
for f in transcribe/reference_sources/*.txt; do [ -e "$f" ] && git mv "$f" sources/text/; done
rmdir transcribe/reference_sources 2>/dev/null || true
ls sources/odt sources/text | head
```
Expected: ODT files (including `red red robin.odt`, `Gumtree Canoe_G.odt`) under `sources/odt/`; lyric `.txt` under `sources/text/`.

- [ ] **Step 2: Import the ../2026 published PDFs**

Run:
```bash
cp ../2026/*.pdf sources/pdfs/
mkdir -p sources/pdfs/add-ons-2026
cp "../2026/2026 add-ons & redos copy/"*.pdf sources/pdfs/add-ons-2026/
echo "pdfs: $(ls sources/pdfs/*.pdf | wc -l)  add-ons: $(ls sources/pdfs/add-ons-2026/*.pdf | wc -l)"
```
Expected: ~216 top-level PDFs (2026 set merged with the former reference_sources PDFs) and 58 add-ons.

- [ ] **Step 3: Generate the PDF manifest**

Run:
```bash
{ echo "# sources/pdfs manifest"; echo; echo "Imported from ../2026 on 2026-06-27."; echo;
  echo "## Top level"; ls sources/pdfs/*.pdf | xargs -n1 basename | sed 's/^/- /';
  echo; echo "## add-ons-2026"; ls sources/pdfs/add-ons-2026/*.pdf | xargs -n1 basename | sed 's/^/- /'; } \
  > sources/pdfs/MANIFEST.md
head sources/pdfs/MANIFEST.md
```
Expected: a readable manifest listing every imported PDF.

- [ ] **Step 4: Repoint `make_wofta.py`**

In `book/make_wofta.py`:
```python
# L19 OLD:  here = os.path.dirname(os.path.abspath(__file__))
# L19 NEW:  here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# L20 OLD:  scan_dir = os.path.join(here, "source_images")
# L20 NEW:  scan_dir = os.path.join(here, "sources", "scans")
# L21 OLD:  abc_dir = os.path.join(here, "notation_pipeline", "abc")
# L21 NEW:  abc_dir = os.path.join(here, "abc")
```

- [ ] **Step 5: Repoint `make_tin_whistle_pdf.py`**

In `book/make_tin_whistle_pdf.py`:
```python
# L9  OLD:  HERE = os.path.dirname(os.path.abspath(__file__))
# L9  NEW:  HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# L10 OLD:  ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
# L10 NEW:  ABC_DIR = os.path.join(HERE, "abc")
# L11 OLD:  IMG_DIR = os.path.join(HERE, "source_images")
# L11 NEW:  IMG_DIR = os.path.join(HERE, "sources", "scans")
```

- [ ] **Step 6: Repoint `make_sand_and_sawdust_pdf.py` constants**

In `book/make_sand_and_sawdust_pdf.py`, replace the constants block (lines 13–17):
```python
# OLD:
HERE = os.path.dirname(os.path.abspath(__file__))
ABC_DIR = os.path.join(HERE, "notation_pipeline", "abc")
REF_DIR = os.path.join(HERE, "notation_pipeline", "reference_sources")
ODT_DIR = HERE
IMG_DIR = os.path.join(HERE, "source_images")
# NEW:
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABC_DIR = os.path.join(HERE, "abc")
PDF_DIR = os.path.join(HERE, "sources", "pdfs")
ODT_DIR = os.path.join(HERE, "sources", "odt")
TXT_DIR = os.path.join(HERE, "sources", "text")
IMG_DIR = os.path.join(HERE, "sources", "scans")
```

- [ ] **Step 7: Repoint the per-entry `REF_DIR` references by extension**

`REF_DIR` no longer exists; each entry must point at the format-specific dir. Run:
```bash
cd book
sed -i -E 's/os\.path\.join\(REF_DIR, ("[^"]+\.pdf")\)/os.path.join(PDF_DIR, \1)/g' make_sand_and_sawdust_pdf.py
sed -i -E 's/os\.path\.join\(REF_DIR, ("[^"]+\.odt")\)/os.path.join(ODT_DIR, \1)/g' make_sand_and_sawdust_pdf.py
sed -i -E 's/os\.path\.join\(REF_DIR, ("[^"]+\.txt")\)/os.path.join(TXT_DIR, \1)/g' make_sand_and_sawdust_pdf.py
grep -n 'REF_DIR' make_sand_and_sawdust_pdf.py || echo "no REF_DIR references remain"
cd ..
```
Expected: `no REF_DIR references remain`. (The pre-existing `ODT_DIR` entry for `red red robin.odt` now correctly resolves to `sources/odt/`.)

- [ ] **Step 8: Commit**

Run:
```bash
git add -A
git commit -m "refactor: unify tune sources under sources/, import 2026 PDFs, repoint build paths"
```

---

## Task 8: Fix pipeline-script paths, rewrite `.gitignore`, relocate scratch

**Files:**
- Modify: scripts in `bin/` that hardcode `source_images` / `notation_pipeline`
- Modify: `.gitignore`
- Modify (move): untracked `notation_pipeline/batch_output`, `notation_pipeline/reports` (untracked parts) → `scratch/`

**Interfaces:**
- Produces: scripts that resolve paths under the new layout; a `.gitignore` that ignores all regenerable scratch and outputs; `scratch/` as the single ignored OMR work area.

- [ ] **Step 1: Survey the path references that still point at the old layout**

Run:
```bash
grep -rnE 'source_images|notation_pipeline|\.\./\.\.' bin/ | wc -l
grep -rlE 'source_images|notation_pipeline' bin/
```
Expected: a list of scripts needing updates. Review it before editing.

- [ ] **Step 2: Apply the common path substitutions in `bin/`**

The scripts assumed they lived in `notation_pipeline/bin/` (two levels deep) and that scans were at `source_images/`. They now live in `bin/` (one level deep). Run:
```bash
# scans moved
grep -rlZ 'source_images' bin/ | xargs -0 sed -i 's#source_images#sources/scans#g'
# abc + pipeline references
grep -rlZ 'notation_pipeline/abc' bin/ | xargs -0 sed -i 's#notation_pipeline/abc#abc#g'
grep -rlZ 'notation_pipeline/reference_sources' bin/ | xargs -0 sed -i 's#notation_pipeline/reference_sources#sources/pdfs#g'
grep -rlZ 'notation_pipeline' bin/ | xargs -0 sed -i 's#notation_pipeline/##g; s#notation_pipeline#.#g'
# "two levels up to repo root" assumption (bin/ is now one level up)
grep -rlZ 'cd "\$(dirname "\$0")/../.."' bin/ | xargs -0 sed -i 's#dirname "\$0")/../..#dirname "$0")/..#g'
```
Then manually inspect the scripts flagged in Step 1 for any remaining `../..` or pipeline-relative idioms and fix to be relative to repo root (`bin/`'s parent). Verify:
```bash
grep -rnE 'source_images|notation_pipeline|/\.\./\.\.' bin/ || echo "no stale path refs remain"
```
Expected: `no stale path refs remain`.

- [ ] **Step 3: Relocate untracked OMR scratch into `scratch/`**

Run:
```bash
mkdir -p scratch
[ -d notation_pipeline/batch_output ] && mv notation_pipeline/batch_output scratch/batch_output || true
[ -d notation_pipeline/renders ] && mv notation_pipeline/renders scratch/renders || true
# reports: keep tracked code, move untracked outputs
[ -d notation_pipeline/reports ] && mv notation_pipeline/reports scratch/reports_scratch 2>/dev/null || true
rmdir notation_pipeline 2>/dev/null || true
ls scratch/
```
Expected: scratch dirs relocated; `notation_pipeline/` gone.

- [ ] **Step 4: Write the new `.gitignore`**

Replace `.gitignore` with:
```gitignore
.venv/

# Regenerable scratch & generated output
scratch/
output/

# OMR intermediates (in case any land outside scratch/)
*.cropped.png

# LilyPond / engraving intermediates
*.ly
*.midi
*.eps
*.svg

# Generated book PDFs anywhere in the tree (sources/pdfs/ is force-added below)
/*.pdf

# Python bytecode
__pycache__/

# Editor / runtime crash logs
neovide_backtraces.log
```
Then force-track the source PDFs (which `*.pdf`-style rules must not catch — note the rule above is root-anchored `/*.pdf`, so `sources/pdfs/**` stays tracked):
```bash
git check-ignore sources/pdfs/Amelia\ \[WB1\].pdf && echo "WRONGLY IGNORED" || echo "source PDFs tracked OK"
```
Expected: `source PDFs tracked OK`.

- [ ] **Step 5: Drop the stray root file and generated PDFs from tracking**

Run:
```bash
git rm --cached --ignore-unmatch -- --help 2>/dev/null || true
rm -f -- ./--help 2>/dev/null || true
git status --porcelain | grep -E '\.pdf$' || echo "no tracked root PDFs"
```
Expected: the stray `--help` PDF and generated root PDFs are no longer tracked.

- [ ] **Step 6: Commit**

Run:
```bash
git add -A
git commit -m "refactor: repoint bin/ scripts, add scratch/, rewrite .gitignore"
```

---

## Task 9: Verify the three books build + final review

**Files:**
- Create: `output/` (generated, ignored)
- Modify: none (verification only)

**Interfaces:**
- Consumes: everything from Tasks 4–8.
- Produces: three rebuilt PDFs proving the new layout works end to end.

- [ ] **Step 1: Build the WOFTA book**

Run:
```bash
mkdir -p output
.venv/bin/python3 book/make_wofta.py output/WOFTA_tunes.pdf
ls -lh output/WOFTA_tunes.pdf
```
Expected: a multi-MB PDF is produced with no path/file-not-found errors.

- [ ] **Step 2: Build the Tin Whistle book**

Run:
```bash
.venv/bin/python3 book/make_tin_whistle_pdf.py output/Tin\ Whistle.pdf
ls -lh output/Tin\ Whistle.pdf
```
Expected: PDF produced; the `png`-kind entries (e.g. `Far Away.png`) resolve from `sources/scans/`.

- [ ] **Step 3: Build the Sand & Sawdust book**

Run:
```bash
.venv/bin/python3 book/make_sand_and_sawdust_pdf.py output/Sand\ and\ Sawdust\ 2026.pdf
ls -lh output/Sand\ and\ Sawdust\ 2026.pdf
```
Expected: PDF produced; `pdf`/`odt`/`text` entries resolve from `sources/pdfs`, `sources/odt`, `sources/text`.

- [ ] **Step 4: Confirm `output/` is ignored, not staged**

Run:
```bash
git status --porcelain output/ || echo "output/ correctly ignored"
```
Expected: nothing staged under `output/`.

- [ ] **Step 5: Final tree + size review**

Run:
```bash
git ls-files | sed -E 's#/.*##' | sort | uniq -c | sort -rn
du -sh .git
du -sh --exclude=.venv .
```
Expected: top-level tracked dirs are `abc bin book sources transcribe docs` (+ root files); `.git` is small; total (minus venv) ~400 M.

- [ ] **Step 6: Update `README.md` to describe the new layout**

Edit `README.md` so its directory overview matches: `abc/`, `bin/` (on PATH), `transcribe/`, `book/`, `sources/{scans,pdfs,odt,text}/`, `output/` (ignored), `scratch/` (ignored). Then:
```bash
git add README.md
git commit -m "docs: document the reorganized repo layout"
```

- [ ] **Step 7: Merge to master**

Once all three books build and the tree looks right:
```bash
git checkout master
git merge --ff-only repo-reorg
```
Expected: fast-forward merge; `master` now holds the reorganized repo.

- [ ] **Step 8: Keep the backup until satisfied**

Leave `../tune_images_BACKUP_2026-06-27.tar` in place until the user confirms everything works on both machines, then it can be deleted.

---

## Notes for the implementer

- **PATH for `bin/`** (deferred convenience, not blocking): add a cross-platform line to the user's shell profile or a repo `.envrc` (direnv), e.g. `export PATH="$PWD/bin:$PATH"`. Confirm with the user how they want `bin/` on PATH on both Mint and macOS before editing any dotfiles (their CLAUDE.md requires yadm-tracked config edits + commit/push).
- **If anything goes wrong before Task 9 merges:** `cd ..; rm -rf tune_images && mkdir tune_images && tar -xf tune_images_BACKUP_2026-06-27.tar -C tune_images` restores the pre-rewrite state (then re-create the venv or restore it separately).
- The `bin/` script path-fixing in Task 8 is the least mechanical part; budget time to run a couple of representative scripts (e.g. `bin/render_abc.sh`, `bin/verify_tune.sh --help`) and fix stragglers the bulk `sed` missed.
