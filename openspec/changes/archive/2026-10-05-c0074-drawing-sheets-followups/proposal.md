## Why

The model carries a drawing sheet and a title block, and the project writer sets the board's drawing sheet key (c0012). A script cannot reach either: a built project always has KiCad's default frame and an empty title block. The plan gives v0.2b the "import of the user's `.kicad_wks`".

c0068 moved four follow-ups to v0.2b (its design, Decision 13). Three remain after c0071 took the rule kinds:

- **Export presets.** Exports run with fixed options. A fab that wants Protel extensions or another drill format needs hand edits.
- **Outline snapping and footprint edge items.** `board_outline` chains edges exactly and ignores edge items inside footprints. Three of the 21 demo boards stay open, although KiCad accepts all of them.
- **Stitching that avoids keep-outs and the board edge.** Stitch vias ignore rule areas and the edge, so a fence can put vias where DRC then fails.

Probes of 2026-10-05, on 9.0.9 and 10.0.6:

- `schematic.page_layout_descr_file`, relative or `${KIPRJMOD}/…`, gives the frame that `sch export svg` draws on the root and the child sheets. The board key does not reach the schematic.
- KiCad chains an outline across gaps up to 9.999 µm and reports `invalid_outline` from 10.001 µm. At exactly 10 µm, 10.0.6 closes and 9.0.9 does not.
- The export options that a preset needs exist on both majors; `--variant`, `--generate-tenting` and `--check-zones` exist only on 10.

## What Changes

- **Drawing sheet and title block in the DSL**: `d.drawing_sheet(path, paper=…)` takes a user's `.kicad_wks` or a `*.sheet.toml`; `d.title_block(title=…, revision=…, date=…, company=…, comments=…, variables=…)`.
- **In the build**: the sheet is read, checked and written for the target as `<name>.kicad_wks`. The project names it for the board and, when a schematic is written, for the schematic too.
- **Export presets**: `fenolite export --preset FILE`, a TOML file of the user's with options per kind (Gerber layers and extensions, drill format, units and origin, placement format and side). Each option maps to a `kicad-cli` flag present on both majors. Without a preset, the commands are unchanged.
- **Outline**: endpoints closer than 10 µm are joined, and edge items inside footprints are chained with the board's, so all 21 demo outlines close, as KiCad says.
- **Stitching**: candidates inside a rule area that forbids vias, or closer to the board edge than the edge clearance in force, are dropped.

Size: 11.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-dsl`: ADDED "Drawing sheet and title block in the DSL", "Drawing sheets in a build".
- `kicad-file-backend`: MODIFIED "Projects carry the drawing sheet and text variables", "Board outline as rings".
- `manufacturing-exports`: ADDED "Export presets".
- `cli-contract`: MODIFIED "Export command".
- `manual-copper`: MODIFIED "Stitching vias".
- `kicad-oracle`: ADDED "Follow-up facts are probed".

## Non-goals

- No preset of any fab or assembly house ships with Fenolite; presets are the user's files.
- No `template import` command for `.kicad_wks`: c0046 adds that command for Altium templates, and a KiCad source can join it there.
- No zone avoidance in stitching: it needs zone fills at build time (c0068).
- No per-command result schemas (v1.0) and no `inspect` of project and rules files (unscheduled).

## Evidence level required

- New rows `H-K-PRO-WKS-SCH`, `H-K-OUTLINE-CHAIN`, `H-K-OUTLINE-FPEDGE`, `H-K-EXPORT-OPTIONS` and `H-K-STITCH-AVOID`, settled by probes on both majors.
- `H-G-EDGE-EXACT` is refuted by the 10 µm chaining and recorded as such; `H-G-PLACE-OUTLINE` is re-measured.

## Impact

- Changed: `dsl/design.py`, `dsl/convert.py`, `lens/build.py`, `backends/kicad/{pro,wks,outline,frame,copper}.py`, `exports/plan.py`, `cli/cmd_export.py`, `docs/dsl.md`, `docs/formats/kicad/{worksheet,board}.md`, `docs/cli-contract.md`.
- Uses c0061's schematic for the schematic key when it is archived; nothing else depends on v0.2a.
