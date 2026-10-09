## Why

Milestone v0.5a (`docs/roadmap.md`, Phase 5; Open decisions row 38), written against `origin/dev` at `f802b60`. Conversion is promised in both directions. From Altium to KiCad nothing writes today:

- Fenolite reads an Altium project into the model (c0043, with c0083, c0122, c0124, c0126) and writes a model as a KiCad board only when the model came from KiCad or from a script. Measured on 2026-10-09: `write_board` of each of the eight public PCB documents of the corpus fails with `KeyError: 'number'` (`backends/kicad/pcb.py:619`): the imported layers carry no KiCad layer row.
- With KiCad's rows given to the layers whose names KiCad knows, six of the eight are written and read back equal to the import at level 5 (four with one `ref-ambiguous` for pads without a reference, as in the triangle); two fail on a slot turned against its pad (`_fpmap.py:475`). The same probe wrote drawings on `Mech.1`, `Mech.2`, `Altium.KeepOut`, `Altium.DrillDrawing` and `Altium.74`, names that no layer row of the written board declares, with no issue: 1 to 27 items per document.
- A KiCad project also needs its schematic, its libraries and its project and rules files; for an imported design none is derived.

## What Changes

- **A KiCad lowering of a foreign board** (`convert/to_kicad.py`, on KiCad's writers): a layer table for 2 to 32 copper layers and the non-copper layers by a closed map (Altium's mechanical layers to KiCad's user layers, as many as the target's layer table holds by a recorded fact; keep-out drawings to rule areas; drill drawings reported), the stack-up, the net names in KiCad's stored form, footprints named `<library>:<name>`, slots turned with a round pad, and a pad of another shape reported.
- **No silent layer**: `write_board` refuses an item on a layer that the board's rows do not declare (`kicad.board.layer-undeclared`), for every caller.
- **The project around the board**: `<name>.kicad_pro` with the net classes, `<name>.kicad_dru` from the neutral rules the import mapped, a footprint library `<name>.pretty` derived from the instances (one per footprint name), a symbol library `<name>.kicad_sym` from the project's `.SchLib` symbols that components link (generic symbols otherwise), and a schematic generated from the circuit by the KiCad schematic generator, one sheet per module.
- **The direction Altium to KiCad** registered in `fenolite convert`, for target 9 or 10, with its report, its profile and its verification.
- **An independent check**: Fenolite's conversion of a public PCB document compared at level 5 with `kicad-cli pcb import` of the same document.

Size: 10 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-conversion`: ADDED "Altium to KiCad direction", "Layers of a converted Altium board", "Slots of a converted Altium board", "Conversion agrees with KiCad's importer".
- `kicad-file-backend`: ADDED "Items on undeclared layers are refused".

## Non-goals

- Altium's schematic drawing (positions, wires, sheet symbols' places): generated, reported `changed`; presentation is after 1.0.
- Variants, the annotation file's channel names beyond what the import gives, Altium's output jobs.
- Polygons repoured: the fills that the document stores are written; `fenolite fill` repours them.
- KiCad 8 output.

## Evidence level required

- The written board: `KICAD-VERIFIED (9.0.x, 10.0.x)` that `kicad-cli` loads it and that its DRC runs (`H-K-CONV-A2K-LOAD`); the schematic: ERC and the schematic parity test run (`H-K-CONV-A2K-SCH`).
- Agreement with KiCad's importer at level 5: `ORACLE-VERIFIED(kicad-cli)` on 10.0.6 (`H-K-CONV-A2K-IMPORT`).
- The read side keeps its labels (`INFERRED`); the reply's level is the lowest of the read, the write and the read-back.

## Impact

- New `convert/to_kicad.py` parts; `backends/kicad/layers.py` (rows for any even copper count), `pcb.py` (the refusal), `_fpmap.py` (slot with a round pad), `mod.py` and `sym.py` writers used for derived libraries.
- The refusal of undeclared layers is new for every caller: no committed board, script or example holds such an item (asserted by the suite before the change lands).
