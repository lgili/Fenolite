## MODIFIED Requirements

### Requirement: PCB document output
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline without cutouts and without arcs (`design-model`, "Board outline arcs") and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, cutouts, arcs, Altium footprint links, or the footprints not written) and the components concerned.
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- The parts of `design.hole()` (`design-dsl`, "Board holes in the DSL"), whose symbols are in the library `Fenolite_Holes`, are not components of the Altium build: they MUST be left out of the schematic, of `<name>.PcbLib` and of the components of the document, and they do not count as components with a footprint link. The build MUST hand each one to the document as a board hole instead (`altium-pcb-writer`, "Non-plated holes and slots"). A round hole that is not plated becomes a `Hole` of the part's `drill` at the part's placement, written as the free pad record of that requirement and counted under the kind `hole` of `result.pcb.written`. A slot (`length`) and a plated hole (`pad`) have no record there, because the board hole of the model is round and has neither copper nor a net: each MUST give one `altium.not-lowered` info whose `where` is `hole/<component id>`, naming the ref and what the record lacks, and MUST be counted under `hole` of `result.pcb.not_lowered`. The pin of a plated hole is then absent from its net in the Altium project, and the message MUST say so. The courtyard of a hole part has no counterpart on a free pad and is not written. Without a PCB document the hole parts are counted by the `holes` issue of the next rule.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs. With a copper source, a component takes the source's placement instead, and none is staged ("Copper from a routed KiCad board").
- When the PCB document is planned, the board, the placements and the net classes MUST NOT be reported by `altium.not-lowered`: the document holds them ("Copper in an Altium build"). Differential pairs still are. A board's keep-outs, texts, graphics and holes are written, or reported item by item, as "Complete board in an Altium build" states; only a build without a PCB document reports them with one issue per kind, and these kinds extend the list of c0032's `altium.not-lowered` row.
- The planned write MUST have the kind `altium_pcbdoc`, and the project file MUST list it as `[Document2]`.
- The document MUST follow c0032's edited-output rule: a document changed in Altium is refused with `FEN-7001`, and `--discard-layout` replaces it with a `.bak`. Fenolite never merges an edited document.

#### Scenario: Document of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is written with the kind `altium_pcbdoc`, `result.pcb_document` is `B/blink.PcbDoc`, `B/blink.PrjPcb` lists it as `[Document2]`, and `issues` holds no `altium.not-lowered` and no `altium.pcb-staged`

#### Scenario: No board, no document
- **GIVEN** a blink variant without `design.board(...)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbLib` is planned, no `.PcbDoc` is planned, and `issues` holds `altium.pcbdoc-not-written` naming the missing board

#### Scenario: Unplaced part is staged
- **GIVEN** a blink variant whose `R1` is not placed
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** `B/blink.PcbDoc` is planned, `issues` holds `altium.pcb-staged` naming `R1`, and `R1`'s component record has the position the KiCad build of the same variant stages it at, converted as `altium-pcb-writer` "PCB document placement" says

#### Scenario: An outline with arcs, no document
- **GIVEN** a blink variant with `board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(2)))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, no `.PcbDoc` is planned, and `issues` holds `altium.pcbdoc-not-written` naming the arcs

#### Scenario: A round hole becomes a free pad
- **GIVEN** a blink variant with `d.hole("H1", mm(4), mm(4), drill=mm(3.2))`
- **WHEN** it is built with `--target altium --confirm --json` and the PCB document is read back
- **THEN** the exit code is 0, `result.pcb.written` holds `hole` with the count 1, the document holds one free pad with a 3.2 mm hole, plating off and no copper at the placement of `H1`, neither the schematic nor `blink.PcbLib` holds `H1` or a footprint of `Fenolite_Holes`, and no `altium.not-lowered` names `H1`

#### Scenario: A plated hole and a slot are reported
- **GIVEN** a blink variant with `h2 = d.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))`, `connect(gnd, h2[1])` and `d.hole("H3", mm(25), mm(4), drill=mm(1), length=mm(3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is planned without them, `result.pcb.not_lowered` holds `hole` with the count 2, and `issues` holds two `altium.not-lowered` infos whose `where` starts with `hole/`: one names `H2`, its copper and the net `GND`, the other names `H3` and its slot
