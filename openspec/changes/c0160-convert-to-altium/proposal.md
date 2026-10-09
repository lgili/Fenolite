## Why

Milestone v0.5a (`docs/roadmap.md`, Phase 5; Open decisions row 38), written against `origin/dev` at `f802b60`. c0159 makes `fenolite convert --to altium` out of today's writers and reports every loss. Measured on 2026-10-09 on the 18 KiCad 10.0.6 demo boards (c0159, design "Context"), today's writers lose more than a conversion should:

- **Two boards are not written at all**: their PCB document needs 119 and 181 FAT sectors, and the compound writer stops at the 109 that the header holds (`backends/altium/cfb.py:65`, `CompoundTooLarge`). DIFAT sectors are a public format fact (S-0145) that the writer never needed for a build.
- **Pads** are lost on 13 of 16 written boards (5 to 144 per board): pads with a per-layer stack, connector pads, pads without a number, custom shapes. The read side already knows the full-stack record (`docs/formats/altium/import.md`, "Pads and padstacks").
- **Drawings on KiCad's user layers** (`Dwgs.User`, `Cmts.User`, `User.N`) and texts on copper are not written: "the layer … has no layer in the document".
- **The schematic** of a converted project is one sheet of generic symbols from the circuit; the KiCad project's own symbols and sheets are not used, and the writer refuses some circuits that were read (decision of 2026-10-06: "a tolerant schematic write for circuits that were read belongs to v0.5a, with `convert`").
- **No PCB library** comes with a converted board: components name footprints that no `.PcbLib` of the project holds (decision of 2026-10-06, c0126 design, item 7: "a derived library belongs to v0.5a, with `convert`").

## What Changes

- **DIFAT sectors** in `cfb.write_compound`, so any size the format allows is written.
- **Pads:** full-stack pad records for a per-layer stack whose layers have plain shapes; a connector pad as a surface pad without paste; a pad without a number as a free pad of the footprint. A custom pad shape stays a reported loss.
- **A layer map** from KiCad's drawing and user layers to Altium mechanical layers, closed and documented; texts on copper layers written as copper texts.
- **A derived PCB library**: one footprint per distinct footprint name of the board, from its first instance in the footprint's frame; instances that differ from it are counted as `changed`.
- **The schematic from the source's own symbols**: a KiCad source's schematic gives the circuit and the symbol graphics (`--altium-symbols graphics`, c0086), one Altium sheet per KiCad sheet (`--altium-sheets modules`, c0037); positions are not kept (`changed`).
- **A tolerant schematic write** for circuits that were read: a comment that starts with `=` and was read from an Altium document is written as read (it names a parameter there); a text outside Windows-1252 is written in the binary form with its `%UTF8%` twin (a corpus-verified read fact) and a plain value that marks the replaced characters; a pin on two nets is written on one, and the other is a reported loss.
- **The maintainer's Part T** of his Altium work: open three converted demo projects in Altium Designer, compile, repour, run the rule check.

Size: 9.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-compound-reader`: ADDED "DIFAT sectors in a written compound file".
- `altium-pcb-writer`: ADDED "Full-stack pad records", "Connector and free pads", "Mechanical layers of KiCad drawings", "Derived PCB library".
- `altium-schematic-writer`: ADDED "Schematic of a converted project", "Tolerant texts and nets of a read circuit".
- `design-conversion`: ADDED "KiCad to Altium closes the measured losses".

## Non-goals

- Custom pad shapes, the fitted flag (Altium keeps "not fitted" in variants, after 1.0), net ties, dimensions.
- Keeping the positions of KiCad's schematic symbols.
- Leaving `experimental`: that needs the kit run (c0091, c0092).

## Evidence level required

- New format rows: `INFERRED` from public sources (S-0145, S-0160, S-0302, registered pages), with Fenolite's reader and KiCad's importer (`ORACLE-VERIFIED(kicad-cli)`, 10.0.6) reading the written files back.
- Altium Designer's view: `ALTIUM-VERIFIED(author-report)` from Part T; never `ALTIUM-VERIFIED(kit)` here.

## Impact

- `backends/altium/cfb.py`, `pcbrecords.py`, `pcblib.py`, `pcbdoc.py`, `lower.py`, `schdoc.py`, `project.py`; `convert/to_altium.py`.
- A build from a script writes the same bytes: the new paths are taken only for content a build never had (asserted by every committed sample and pin).
