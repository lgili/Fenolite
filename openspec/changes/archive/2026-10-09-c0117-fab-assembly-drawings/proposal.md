## Why

A contract manufacturer gets, beside Gerber and drill files, a fabrication drawing (outline and size, drill table and map, stack-up, notes) and assembly drawings (parts and references per side). Fenolite makes neither: a drawing sheet is a frame and a title block (c0012). The complex-board review of 2026-10-05 found no owner; on `origin/dev` at `9aba2dff` there is still none (no kind plots `F.Fab`, `Dwgs.User` or a drill map as a deliverable). Milestone v0.4 (written as "v0.2c" before the renaming of 2026-10-07).

Measured on `kicad-cli` 10.0.6 and 9.0.9 (design, Context):

- A board `table` and a `gr_text_box` written into a copy of a board load and plot, variables resolved. A cell wraps its text but keeps its row height.
- At the default scale a plot puts an item where the board puts it; 9.0.9 has no other scale for PDF or SVG.
- `pcb export drill --generate-map --generate-report` writes drill maps, one symbol and legend line per tool, and a report of holes per tool.
- Do-not-populate parts can be crossed out or hidden on fabrication layers.

## What Changes

- **Two export kinds**: `fenolite export … --fab-drawing --assembly-drawing [--drawing-spec FILE]`.
- **Plot copies, no drawing code.** Fenolite writes tables, notes, dimensions and missing designators as board items into a copy, and `kicad-cli pcb export pdf` draws them with the frame and title block. The user's board never changes.
- **Fabrication drawing**: a PDF page with the outline, its overall dimensions, board, stack-up (c0101) and drill tables and numbered notes (the impedance table and the via-protection row are added by c0105 and c0112, which land later); KiCad's drill maps and report beside it. Drill counts are checked against the report on every run.
- **Assembly drawings**: a top page and a mirrored bottom page of the fabrication layers, do-not-populate parts crossed out, values hidden, designators added where a footprint shows none.
- **Layout**: the board stays where it is, at 1:1; blocks go where the sheet and the board leave room, on the smallest of A4 to A0 that holds them.
- **Spec file** `fenolite.drawing-spec.v0` (TOML): paper, sheet, tables, notes, assembly options.
- Manifest kinds `fab-drawing` and `assembly-drawing`, derived kinds of "Artefact states"; seven `drawing.*` codes.

Size: 8 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `manufacturing-exports`: ADDED "Drawing specification files", "Drawing tables and notes", "Drawing page layout", "Drawing plot copies", "Fabrication drawing kind", "Assembly drawing kind", "Drawing kinds in the manifest"; MODIFIED "Artefact states" (two derived kinds; c0116 modifies it first).
- `cli-contract`: ADDED "Drawing options of the export command".
- `kicad-oracle`: ADDED "Drawing facts are probed".

## Non-goals

- Drawing items in the user's board: nowhere in v0.4; derived tables go stale after `route`.
- DSL calls: nowhere in v0.4; one spec file serves built and KiCad-made boards.
- Drawings of an Altium board: nowhere. The drawings are plotted by `kicad-cli` from a KiCad board, and `export` refuses any other path (exit 2, `FEN-2001`); an Altium build has its output job (c0087, c0138), which is Altium's own way to drawings.
- The impedance table and the via-protection row on the drawing: c0105 and c0112, each with a MODIFIED delta of "Drawing tables and notes" when it lands; this change keeps the table name `impedance` valid and empty.
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

## Prerequisites

- `0.3.0` is released from `dev` (c0084 archived, so "Export command" holds `--altium-rul`).
- c0101 on `dev`: the stack-up table reads `dielectric_kind`, `color`, `impedance_controlled` and `Stackup.thickness()`.
- c0116 on `dev`: `run_kind(…, layers=…)`, the `/CreationDate` prefix, `result.repeat`, and its text of "Artefact states", on which this change's delta is regenerated (order c0116, c0117, c0118, c0105).
- Not prerequisites, because they land later by the order of the review: c0103 (its emitter replaces this change's dimension node when it lands), c0105 and c0112 (they add their block and row), c0077 (references on catalog footprints; Decision 12 adds them meanwhile), c0080 (the guide line of task 8.2).
- c0096, c0097 and c0099: nothing here touches them. Waiting for this change: c0119 stage 5.
