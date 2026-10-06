## Why

The schematic that `build` writes in v0.2a (c0061) is minimal: one sheet, symbols in a grid, a global label on every connected pin. KiCad accepts it, but a reader follows labels to see that a resistor sits on an IC pin, and four modules share one A1 page.

The plan gives v0.2b the "readable" layout (2-pin parts snapped to IC pins, orthogonal wires) and one hierarchical sheet per `Module`. Probes on 9.0.9 and 10.0.6 (2026-10-05) give the rules:

- Pinless sheet symbols load; global labels name nets across sheets by their own text, so net names stay the board's.
- A child sheet's file name is resolved from the folder of the sheet that names it; a name that resolves to nothing is dropped without an ERC finding.
- A wire joins the pins at its two ends; a pin in the middle of a wire stays unconnected.
- A wired pair of pins with one global label takes the label's name.

## What Changes

- **One sheet per module.** A root sheet with the top-level parts and one pinless sheet symbol per module; one child sheet per module under `sheets/`, nested as the modules are. Nets keep global labels. `--schematic-layout grid` keeps c0061's form.
- **Readable layout.** A 2-pin part on a net of an IC pin is snapped beside that pin, turned along it, and joined to it by one straight wire; the wired pair carries one global label, the far pin its own. The snap is skipped when the part would overlap something, so the result is never worse than c0061's grid.
- **Model and writer.** `SchematicSheet` gains `wires` (two-point orthogonal segments); the writer emits wires and sheet symbols, and `sheet_instances` only in the root.
- **Board paths.** A footprint's `path` becomes `/<sheet uuids>/<symbol uuid>`, the form of KiCad's netlist for a symbol in a child sheet.
- **Own netlist.** c0063's netlist reads the sheet tree and the wires, so the build's guard still proves the schematic without a tool.
- **Oracles.** Examples and generated designs with nested modules: no ERC violation, empty parity, own netlist equal to `kicad-cli`'s, on both majors.

Size: 13 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-schematic`: MODIFIED "Modelled schematic content", "Schematic writing per target", "Generated sheet content", "Deterministic sheet layout", "Generated schematic issue codes", "Own netlist of a generated sheet", "Netlist grammar check", "Generated schematics are documented"; ADDED "Readable sheet layout", "Hierarchical sheets of a design".
- `design-model`: MODIFIED "Schematic sheet definitions", "Identifiers of schematic entities".
- `design-dsl`: MODIFIED "Board follows the schematic", "Schematic netlist guard in a build"; ADDED "Hierarchical sheets in a build".
- `kicad-oracle`: ADDED "Hierarchy and wire facts are probed", "Hierarchical schematics pass the oracles".
- `cli-contract`: MODIFIED "Netlist command" (the source `fenolite` reads the child sheets).

The requirements of c0063 ("Own netlist of a generated sheet", "Netlist grammar check", "Schematic netlist guard in a build", "Netlist command") are modified from c0063's own delta: this change archives after it (`design.md`, "Corrections on 2026-10-06").

## Non-goals

- No hierarchical labels and no sheet pins.
- No sheet used twice (v0.5b), no buses (v0.3).
- No bent wire, no junction, no routing between symbols: only the straight snap wire.
- No reading of an edited schematic; c0069's `sync` copies its symbol moves.
- No power symbols in place of labels.

## Evidence level required

- New rows `H-K-SCH-HIER-FILE`, `H-K-SCH-HIER-PATH` and `H-K-SCH-WIRE-END`, settled by probes on both majors; until then `schgen.EVIDENCE` and `sch_netlist.EVIDENCE` stay `INFERRED`.
- KiCad's ERC, parity test and netlist judge the schematics, as in v0.2a.

## Impact

- Changed: `model/schematic.py`, `backends/kicad/{sch,schgen,schlayout,sch_netlist}.py`, `lens/build.py`, `cli/cmd_build.py`, `docs/schematic.md`, `docs/formats/kicad/schematic.md`, `tests/_gendesigns.py`, `tests/_layout_edit.py`.
- Depends on c0060, c0061 and c0063, which add every requirement modified here; this change archives after them.
- Built projects change once: satellites, and for modules new files under `sheets/` and new paths; positions, pad nets and net names do not change.
