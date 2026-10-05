## Why

A built project has a board and no schematic. KiCad then has nothing to run ERC on, its DRC cannot test parity, and the netlist and BOM exports of `kicad-cli` have no input. Plan D10 gives v0.2a a minimal schematic: one symbol per part, a global label per net, embedded symbols, no drawing effort.

Measured at proposal time with a hand-made sheet on 9.0.9 and 10.0.6: the minimal token set loads; ERC reports nothing once unconnected pins carry no-connect flags, power nets a power flag, and the symbol libraries are in the project table; parity reports nothing once the pads of unconnected pins carry the names KiCad derives (`unconnected-(U1-PA1-Pad2)`). Three traps: a `/` in a net name becomes `{slash}`, hidden power-input pins join one global net whatever label they carry, and parity matches footprints by reference.

## What Changes

- `build` writes `<name>.kicad_sch` for targets 9 and 10: every unit of every part on a grid by module, one global label per connected pin, no-connect flags from the marks (c0036), a power flag per power-interface net without a power output, title block, `fenolite.path` on each symbol. `--schematic skip` keeps the v0.1 output.
- Symbols are embedded and written to project libraries (`lib/<nickname>.kicad_sym`, `sym-lib-table`): only those used, flattened, with pad numbers when a part maps pins to pads (c0056), hidden power-input pins shown.
- The board follows the schematic: pads of unconnected pins take KiCad's net names in the written file only; a net name with `/` is stored as `{slash}`; footprints carry their symbol's path.
- `schematic-placements.toml` beside the script fixes symbol positions.
- `sch.write_schematic` for created sheets, gated per target.
- `check`: a pad on no net is a block of its own in the assignment compare.
- Oracle tests on both majors: ERC and parity report nothing on the examples; each negative control is caught.

Size: 14 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-schematic`: ADDED writing per target, generated content, layout, embedded symbols, unconnected-pin names, issue codes.
- `design-dsl`: ADDED "Schematic in a build", "Symbols of a built project", "Schematic placements file", "Board follows the schematic"; MODIFIED "Build command", "Built project files", "Edited outputs are not overwritten", "Footprints of every row origin are vendored".
- `kicad-file-backend`: ADDED "Net names in KiCad's stored form".
- `kicad-oracle`: ADDED "Schematic naming facts are probed", "Generated schematics pass ERC and parity".
- `verification-loop`: MODIFIED "Assignment compare stage".
- `layout-lens`: ADDED "Boards updated from the schematic keep their layout".

## Non-goals

- No ERC stage and no parity in `check` (c0062), no own netlist (c0063), no BOM (c0064).
- No wires, no readable layout, no sheet per module (v0.2b); no buses (v0.3).
- No preservation of schematic edits: an edited schematic is replaced, with a warning and a backup (v0.5b).
- No schematic for `--target altium`; no symbol authoring (c0058).
- No drawing sheet for the schematic in the project file.

## Evidence level required

- The written form and ERC without violations on the examples: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-SCH-MINIMAL`, `H-K-SCH-PINFRAME`).
- Unconnected-pin names and the slash rule: `KICAD-VERIFIED` per major (`H-K-SCH-UNCONNECTED`, `H-K-SCH-SLASH`).
- Parity without findings and its negative controls: `KICAD-VERIFIED` (`H-K-SCH-PARITY`).
- Power flags, hidden power pins, library rows: `KICAD-VERIFIED` (`H-K-SCH-POWER`, `H-K-SCH-LIBTABLE`).
- A KiCad re-save of a generated sheet: recorded on 10.0, never a gate (`H-K-SCH-RESAVE`).
- A real "Update PCB from Schematic": the maintainer's report only (`H-K-SCH-UPDATE` stays `INFERRED`).

## Impact

- New: `backends/kicad/{schgen,schlayout,symembed,netnames}.py`, `lens/schplacements.py`, `docs/schematic.md`.
- Changed: `backends/kicad/sch.py`, `pcb.py` (net spelling), `lens/build.py`, `cli/cmd_build.py`, `checks/assignment_compare.py`.
- Depends on c0060; c0062, c0063 and c0064 depend on it.
