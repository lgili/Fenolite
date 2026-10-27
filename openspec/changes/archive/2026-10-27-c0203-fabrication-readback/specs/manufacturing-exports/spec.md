## ADDED Requirements

### Requirement: Fabrication read-back
`fenolite export --readback` SHALL compare the Gerber, drill and position files of the run with the board before planning a write.
- The outline MUST close into one contour per ring of the board.
- Every hit and slot MUST match a hole in position, diameter and plating, and every hole MUST have one.
- Every position row MUST match its footprint; every copper layer MUST have a non-empty file.
- A mismatch MUST be an `export.readback-*` error, and nothing is written.

#### Scenario: A missing slot
- **GIVEN** the authored bench of `tests/_readbackbench.py` with one non-plated slot, and a test seam that drops the slot from the drill file that the read-back sees
- **WHEN** `uv run pytest tests/kicad/export/test_readback.py -k slot` exports with `--gerbers --drill --readback --confirm`
- **THEN** the exit code is 5, the issues hold one `export.readback-drill` naming `H1`, and no file is written

### Requirement: Read-back readers
`fenolite.exports.readback` SHALL read the subset of Gerber, Excellon and position files that `kicad-cli` writes, recorded in `docs/formats/kicad/gerber.md` and `docs/formats/kicad/drill.md`, and SHALL refuse any other construct with `Unsupported` (`export.readback-unsupported`), never guessing.

#### Scenario: Readers on authored texts
- **WHEN** `uv run pytest tests/unit/exports/test_readback_readers.py` reads an outline of a rectangle and a stadium, a drill file with a hit and a slot, and texts with another format, inches, step and repeat or a zero-suppressed coordinate
- **THEN** the outline gives two closed contours with the stadium's box 12 mm to 18 mm, the drill file its hit and slot, and every other text raises `Unsupported`
