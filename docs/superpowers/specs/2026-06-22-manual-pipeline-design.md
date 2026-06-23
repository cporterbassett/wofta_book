# Manual (Claude-free) verify pipeline — design

**Date:** 2026-06-22

## Goal

Provide a version of the `image → Audiveris → verified ABC` per-tune workflow
that runs entirely without Claude, plus a documented one-command way to build
both output PDFs. Today that per-tune flow lives only as a Claude-driven
background task (see `memory/project_verify_workflow.md`); the only genuinely
Claude-specific step is best-effort chord insertion, which a human instead does
directly in EasyABC.

## Deliverables

1. `notation_pipeline/bin/verify_tune.sh "Tune Name"` — standalone orchestration
   script, no Claude.
2. `manual_pipeline.md` (repo root) — copy-pastable launch examples.

No new PDF code: `make_pdf.sh` already builds both PDFs and opens both in
Firefox; the doc just documents it.

## `verify_tune.sh "Tune Name"` flow

Pure orchestration over existing scripts (`export_tune.sh`, `make_compare.sh`,
`render_abc.sh`, `promote_tune.sh`). Linux/Mint-bound (flatpak Audiveris,
wmctrl, easyabc, firefox) — no macOS portability attempted.

1. **Precondition** — require `batch_output/<Tune>/clean.omr`; if missing, print
   the `batch_tune.sh` command to create it and exit non-zero.
2. **Review** — launch Audiveris GUI on `clean.omr`; maximize it via the wmctrl
   poll loop; open the raw scan `source_images/<Tune>.png` in Firefox for
   reference. Block until Audiveris closes (wait on its PID).
3. **Export** — run `export_tune.sh "<Tune>"` (MXL → clean → ABC → render). If
   it exits non-zero (e.g. the movement-split stop that needs `--mvt N`), relay
   its message and abort — nothing half-promoted.
4. **Mechanical fixes (BEFORE EasyABC)** — force canonical `T:<Tune>` using the
   apostrophe-safe env-var Python snippet (pass `$TUNE` via the environment,
   never interpolate into the source). `export_tune.sh` already normalized
   line-breaks to the scan layout. Re-render so the compare reflects the title.
   When EasyABC opens, only musical edits (notes/chords) remain.
5. **Live compare + edit**:
   - Build the initial side-by-side compare with `make_compare.sh <scan>
     <render> <out.png>` (equal-size panels).
   - Write a tiny auto-refreshing HTML page to `/tmp` whose `<img>` reloads
     itself every ~1.5 s with a cache-busting timestamp; open *that* page in
     Firefox (so saves never pile up new tabs).
   - Start a background **mtime watcher** on the candidate ABC (poll ~1 s, no
     `inotifywait` dependency). On each save from EasyABC: re-run
     `render_abc.sh` + `make_compare.sh`, overwriting the same compare PNG. The
     auto-refresh page shows edits within a second or two.
   - Open the candidate ABC in EasyABC (absolute path, foreground).
6. **On EasyABC close** — kill the watcher, do one final compare rebuild.
7. **Promote gate** — prompt `Promote & commit? [y/N]`.
   - `y`: `git add` candidate `&& promote_tune.sh "<Tune>" && git add` verified
     `&& git commit -m "feat: verify <Tune>"` (chained with `&&` so a failure
     aborts the commit).
   - anything else: leave the candidate, print the manual promote command.

## `manual_pipeline.md` (repo root)

Copy-pastable sections:

- **Verify one tune**: `bash notation_pipeline/bin/verify_tune.sh "Tune Name"`
- **Find the next tune to verify**: one-liner listing tunes that have a
  `clean.omr` but no `-verified.abc`, worst-first via `health_scores.tsv`.
- **(If no `clean.omr` yet)**: `bash notation_pipeline/bin/batch_tune.sh "Tune
  Name"` first.
- **Build both PDFs + open in Firefox**: `./make_pdf.sh`.
- **Optional**: refresh the HTML report (`build_report.sh`).

## Out of scope

- No queue/loop in `verify_tune.sh` — one tune at a time by name; the "find
  next" snippet covers discovery.
- No new PDF tooling.
- No automatic chord transcription (the Claude-only step) — done by hand in
  EasyABC.
