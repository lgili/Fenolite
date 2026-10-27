## Why

Item 5 of the consolidation list the maintainer ordered on 2026-10-26, and task 12.1 of c0175. `fenolite
export` hands the user the files `kicad-cli` wrote and trusts them. A fabricator builds what those files say,
not what the board says: a hole missing from a drill file, an outline that does not close, or a part placed
on the wrong side is found when the boards come back. Fenolite can read the files back and compare them
with the board before writing them.

## What Changes

- `fenolite.exports.readback`: Fenolite's own readers of the Gerber, Excellon and position files in the
  subset `kicad-cli` writes. They refuse anything else (`export.readback-unsupported`).
- The comparisons:
  - the outline closes into one contour per ring of the board;
  - every hit and slot matches a hole in position, diameter and plating, and every hole has one;
  - every position row matches its footprint;
  - every copper layer has a non-empty file.
- `fenolite export --readback` runs them on the files of the run before anything is planned; a mismatch is
  an `export.readback-*` error, so nothing is written.
- `docs/formats/kicad/drill.md` (new) and `gerber.md` record the subset, observed on `kicad-cli` 10.0.7;
  `H-K-READBACK-SUBSET`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `manufacturing-exports`: ADDED "Fabrication read-back" and "Read-back readers" (from c0175).

## Non-goals

- Reading IPC-D-356, IPC-2581, ODB++ or STEP back.
- A rendering of the read files; c0175's "Region renders" stays there.
- Requiring a position row for every footprint: KiCad leaves some out on purpose (`exclude_from_pos_files`),
  so only the rows are checked.

## Evidence level required

`KICAD-VERIFIED` for the subset on 10.0.x (local `kicad-cli` 10.0.7); the `kicad-9` job settles 9.0.

## Impact

- `src/fenolite/exports/readback.py`, `codes.py`, `src/fenolite/cli/cmd_export.py`, `explain.toml`, tests
  (`tests/unit/exports/test_readback_readers.py`, `tests/kicad/export/test_readback.py`,
  `tests/_readbackbench.py`), `docs/exports.md`, `docs/cli-contract.md`, `docs/formats/kicad/`, the guide's
  `fabrication` page, `CHANGELOG.md`.
