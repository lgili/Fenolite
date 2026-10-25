## ADDED Requirements

### Requirement: Fabrication read-back
`fenolite export ... --readback` SHALL read back the Gerber and Excellon files it wrote, with Fenolite's own readers of the subset that `kicad-cli` writes, and SHALL compare them with the board before the files are kept.
- The outline file MUST close into `1 + n` contours for a board with `n` cut-outs and slots, each matching a ring of the board within the export's resolution.
- Every drill hit and slot MUST match a board hole in position, diameter and plating, and every board hole MUST have its hit.
- Every row of the position file MUST match a footprint's reference, position, rotation and side.
- Every copper layer of the board MUST have its file with a file function; no file of a used layer MUST be empty.
- A mismatch MUST be an `export.readback-*` error: the export writes none of its files (the mutation protocol's all-or-nothing rule).
- The readers MUST refuse any construct outside their subset with `export.readback-unsupported`, never guess.

#### Scenario: A missing slot
- **GIVEN** an authored board with one slot, and a test hook that drops the slot from the Excellon file
- **WHEN** `uv run pytest tests/kicad/exports/test_readback.py -k slot` exports with `--readback`
- **THEN** the exit code is 5, the issues hold one `export.readback-drill` naming the slot, and no file is written

### Requirement: Region renders
`fenolite render BOARD --region X1,Y1,X2,Y2 [--nets] [--open] [--grid LENGTH]` SHALL draw one rectangle of the board with its pads, tracks, vias, slots and filled zones, the pads' net names when `--nets` is given, the open connections as straight lines when `--open` is given, and a grid labelled in board coordinates, under the mutation protocol.
- The render MUST be drawn by Fenolite from the model (SVG, and PNG when the `render` extra is present), so it needs no `kicad-cli`; filled zones MUST be drawn as filled, and the reply MUST say which copper state it used (outline, saved fill, simulated).

#### Scenario: Open connections in a region
- **GIVEN** an authored board with two open connections inside the region
- **WHEN** `fenolite render <board> --region 0mm,0mm,20mm,20mm --nets --open -o views --confirm` runs
- **THEN** the SVG holds two lines of the open-connection class and one label per pad in the region
