## Why

Package 9 of change c0175 ("File safety"), placed first by the maintainer on 2026-10-26 in the consolidation
list ("vamos fazer nessa ordem"). Fenolite edits files that someone else owns. A board open in KiCad is
overwritten by its next save, a project in a synced folder may be only a placeholder, and a copied project
still points at its old folder. A write that lands on such a file loses work, and nothing warns today.

## What Changes

- `fenolite snapshot PATH --out DIR`: a copy of a design file with its companions, or of a project folder,
  accepted only when every file has the same SHA-256 before and after all were read. `DIR/snapshot.json`
  lists the hashes.
- `fenolite publish SRC --to DST --receipt RECEIPT`: puts the copy back, replacing only the files whose
  hash is still the one the receipt recorded (`safety.changed-since-receipt` otherwise, nothing written;
  `--skip-changed` writes the others).
- Every writing command warns `safety.open-session` for a planned file with KiCad's lock file beside it.
  `fenolite doctor --sessions PATH` lists lock files and online-only files.
- Files that a sync client keeps only online are recognised by their documented attributes and stop
  `snapshot`, `publish` and `refs` with the new error `FEN-3007` (exit 3, retryable).
- `fenolite refs PATH [--repoint OLD=NEW]`: the paths a project's documents hold, and their rewrite in KiCad
  documents.
- Package `fenolite.safety`, nine issue codes, four public sources (S-0828 to S-0831), three hypotheses.

## Capabilities

### New Capabilities

- `file-safety`: "Stable snapshot", "Publish guarded by receipts", "Open sessions", "Online-only files" and
  "Project references".

### Modified Capabilities

None. c0175 keeps "Gated and three-way differences" of `file-safety` and its task 4.6.

## Non-goals

- `diff --allow` and `--three-way` (c0175, task 4.6).
- Lock files of tools without a public source for their name (Altium Designer among them).
- Partial publish without `--skip-changed`: a command writes all its files or none beside an error.

## Evidence level required

`INFERRED`: `kicad-cli` opens no editor, so the lock file is read from KiCad's developer documentation
(`H-K-PRO-LOCK`, pending a session of the maintainer); the copy and the receipt rule are proved on authored
projects (`H-G-SNAPSHOT-STABLE`, `H-G-PROJECT-REFS`).

## Impact

- `src/fenolite/safety/`, `src/fenolite/cli/cmd_snapshot.py`, `cmd_publish.py`, `cmd_refs.py`, `cmd_doctor.py`,
  `main.py` (the dispatcher's warning), `errors.py` (`FEN-3007`), `explain.toml`, `tests/unit/safety/`,
  `docs/file-safety.md`, `docs/cli-contract.md`, `docs/formats/kicad/project.md`, the agent guide's `files`
  and `recovery` pages, `CHANGELOG.md`.
