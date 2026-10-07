## Why

A contract manufacturer gets, beside Gerber and drill files, a fabrication drawing (outline and size, drill table and map, stack-up, notes) and assembly drawings (parts and references per side). Fenolite makes neither: a drawing sheet is a frame and a title block (c0012). The review of 2026-10-05 (`docs/roadmap.md`, Gaps to a complex board) found no owner.

Measured on `kicad-cli` 10.0.6 and 9.0.9 (design, Context):

- A board `table` and a `gr_text_box` written into a copy of a board load and plot, variables resolved. A cell wraps its text but keeps its row height.
- At the default scale a plot puts an item where the board puts it; 9.0.9 has no other scale for PDF or SVG.
- `pcb export drill --generate-map --generate-report` writes drill maps, one symbol and legend line per tool, and a report of holes per tool.
- Do-not-populate parts can be crossed out or hidden on fabrication layers.

## What Changes

- **Two export kinds**: `fenolite export … --fab-drawing --assembly-drawing [--drawing-spec FILE]`.
- **Plot copies, no drawing code.** Fenolite writes tables, notes, dimensions and missing designators as board items into a copy, and `kicad-cli pcb export pdf` draws them with the frame and title block. The user's board never changes.
- **Fabrication drawing**: a PDF page with the outline, its overall dimensions, board, stack-up (c0101), drill and impedance (c0105) tables and numbered notes; KiCad's drill maps and report beside it. Drill counts are checked against the report on every run.
- **Assembly drawings**: a top page and a mirrored bottom page of the fabrication layers, do-not-populate parts crossed out, values hidden, designators added where a footprint shows none.
- **Layout**: the board stays where it is, at 1:1; blocks go where the sheet and the board leave room, on the smallest of A4 to A0 that holds them.
- **Spec file** `fenolite.drawing-spec.v0` (TOML): paper, sheet, tables, notes, assembly options.
- Manifest kinds `fab-drawing` and `assembly-drawing`; seven `drawing.*` codes.

Size: 8 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `manufacturing-exports`: ADDED "Drawing specification files", "Drawing tables and notes", "Drawing page layout", "Drawing plot copies", "Fabrication drawing kind", "Assembly drawing kind".
- `cli-contract`: ADDED "Drawing options of the export command".
- `kicad-oracle`: ADDED "Drawing facts are probed".

## Non-goals

- Drawing items in the user's board: nowhere in v0.2c; derived tables go stale after `route`.
- DSL calls: nowhere in v0.2c; one spec file serves built and KiCad-made boards.
- Panel drawings: c0118. Hole positions and datums: the user's dimensions on `Dwgs.User` (c0103) are plotted.
- Scales other than 1:1 and one multi-page PDF: nowhere; 9.0.9 has no `--scale` and writes multi-page output elsewhere. DXF plots: c0116.
- Default notes, tolerances, classes, materials, finishes: nowhere; the user gives every value (c0047).
- A bill of materials on the drawing: c0064 owns the BOM file.
- Sheet numbers per page: nowhere, KiCad prints 1/1 on board plots.

**Limits.** Landscape A4 to A0 when chosen; a board outside every page fails; a glyph bound sizes tables, wider than needed; assembly notes on the top page only; drill maps carry no frame; each page is its own PDF.

## Evidence level required

- New rows `H-K-DRAW-ITEMS`, `-TEXT`, `-PAGE`, `-SHEET`, `-DRILL`, `-ASSEMBLY`, `-REPEAT`, `-LAYER`, settled on 9.0.9 and 10.0.6 before merge; `exports.drawings.EVIDENCE` stays `INFERRED` until the first three hold.
- Spec reading, tables, layout, copies: mechanical, unit scenarios.

## Impact

- New: `exports/drawing_spec.py`, `drawing_tables.py`, `drawing_layout.py`, `drawings.py`; `backends/kicad/drawing.py`; `docs/drawings.md`.
- Changed: `backends/base.py`, `backends/kicad/cli.py`, `exports/plan.py`, `exports/codes.py`, `cli/cmd_export.py`, export docs.
- Depends on c0101 and c0116; uses c0105, c0112 and c0103 when archived.
