## MODIFIED Requirements

### Requirement: PCB library outputs
The Altium build SHALL plan `<name>.PcbLib` (`project.pcblib_name`) when at least one KiCad footprint is written, with `pcblib.write_pcblib` and one `pcblib.LibFootprint` per distinct `kicad` link whose footprint resolves and passes `pcblib.check_footprint`.
- A footprint with net-tie groups (`FootprintDef.net_ties`) MUST NOT be refused for a graphic on a copper layer (change c0448): the library writes such a graphic on `F.Cu` or `B.Cu` as it writes a graphic of another layer, and names any other one in `altium.primitive-dropped`; the PCB document writes it as a conversion does (`altium-pcb-writer`, "Copper of a net-tie footprint", change c0431). A copper graphic of a footprint without net-tie groups is still refused.
- A pad margin that the model holds (`Pad.mask_margin`, `Pad.paste_margin`) is written as a manual expansion (`altium-pcb-writer`, change c0440) and MUST NOT be named by `altium.primitive-dropped` (change c0448); a margin the model does not hold, because its KiCad child is no single number, still is.
- A refused footprint MUST give one `altium.footprint-unsupported` warning that names the link and the reason, and MUST NOT be written. Items the check drops MUST give one `altium.primitive-dropped` warning per footprint, naming each kind and count; texts, properties and 3D model links MUST give one `altium.footprint-extras-dropped` info per footprint.
- Two distinct `kicad` links whose footprints get equal storage names under the MS-CFB order (`project.storage_name`), such as `Mini:R` and `Other:R`, MUST give `altium.footprint-name-collision` (warning), and neither footprint is written: no part gets the wrong footprint.
- The planned write MUST have the kind `altium_pcblib`. `lens.altium.PCB_WRITE_KINDS` MUST be `("altium_pcbdoc", "altium_pcblib")`; `project.WRITE_KINDS` MUST NOT change.
- `<name>.PrjPcb`, when planned, MUST list the PCB library (`altium-schematic-writer`, "Project file"). When the project file is kept and a PCB file is planned, the build MUST add one `altium.pcb-not-in-project` info that names the PCB files to add in Altium.
- A compound file that raises `cfb.CompoundTooLarge` MUST give `altium.pcb-too-large` (error), and the build writes nothing.
- The library MUST follow c0032's edited-output rule and build record, and MUST be byte-identical across builds of one script with one library configuration.

#### Scenario: Library of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbLib` is written with the kind `altium_pcblib`, `result.libraries` lists it, `result.footprints` is `3`, `B/blink.PrjPcb` lists it, and `issues` holds one `altium.primitive-dropped` naming the filled polygon of `Mini_QFP-32_7x7mm_P0.8mm`

#### Scenario: Name collision writes neither
- **GIVEN** a blink variant whose `R1` uses `Mini:Mini_R_0603` and a second part uses `Other:Mini_R_0603`, where `Other` is a second `fp-lib-table` entry naming `tests/data/libs/Mini.pretty`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds `altium.footprint-name-collision` naming both links, the planned library holds neither footprint, and `altium.pcbdoc-not-written` names both parts

#### Scenario: Refused footprint
- **GIVEN** a blink variant whose `R1` names an authored footprint with a `trapezoid` pad
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds `altium.footprint-unsupported` naming the pad, and the planned library holds the two other footprints

#### Scenario: A net tie with copper and pads with a mask margin are written
- **GIVEN** the authored board `tests/data/kicad/convert/net_tie_copper.kicad_pcb` (net tie `NT1` whose `F.Cu` line joins its two pads), its pad 1 given `(solder_mask_margin 0.05)`, imported with `import --to python`
- **WHEN** `uv run pytest tests/unit/lens/test_build_altium_parity.py -n 0 -q` builds it with `--target altium --confirm`
- **THEN** the library and the document hold `NT1`, the document's `NT1` is a component of kind 4 that owns a top-layer track between its pads, pad 1 has solder mask mode manual with 0.05 mm, no `altium.footprint-unsupported` or `altium.primitive-dropped` names `NT1`, and `convert --to altium` of the same board writes the same three items

#### Scenario: Edited library refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/blink.PcbLib` changed afterwards
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 7 with `FEN-7001`, `build.layout-exists` names `B/blink.PcbLib`, and no file changes

### Requirement: PCB document output
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline whose board ring has at least three vertices (`design-model`, "Board outline arcs"; an arc is the vertex at its start, its mid is none), and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, a board ring of arcs with fewer than three vertices, Altium footprint links, or the footprints not written) and the components concerned.
- An arc of the board ring MUST be written as one arc vertex, as a conversion writes it (`altium-pcb-writer`, "Board outline arcs", change c0441), not refused (change c0448; before, the document was not written).
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- The parts of `design.hole()` (`design-dsl`, "Board holes in the DSL"), whose symbols are in the library `Fenolite_Holes`, are not components of the Altium build: they MUST be left out of the schematic, of `<name>.PcbLib` and of the components of the document, and they do not count as components with a footprint link. The build MUST hand each one to the document as a board hole instead (`altium-pcb-writer`, "Non-plated holes and slots"). A hole that is not plated becomes a `Hole` of the part's `drill` at the part's placement, with the part's `length` and its slot axis turned by the part's rotation (`design-model`, "Slotted board holes"), written as the free pad record of that requirement and counted under the kind `hole` of `result.pcb.written`. A plated hole (`pad`) has no record there, because the board hole of the model has neither copper nor a net: it MUST give one `altium.not-lowered` info whose `where` is `hole/<component id>`, naming the ref and what the record lacks, and MUST be counted under `hole` of `result.pcb.not_lowered`. The pin of a plated hole is then absent from its net in the Altium project, and the message MUST say so. The courtyard of a hole part has no counterpart on a free pad and is not written. Without a PCB document the hole parts are counted by the `holes` issue of the next rule.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs. With a copper source, a component takes the source's placement instead, and none is staged ("Copper from a routed KiCad board").
- The cut-outs and slots of the outline (`lowered_outline`, `kicad-file-backend`) MUST be written as the regions of "Board cut-out regions" (`altium-pcb-writer`) when `pcbdoc.CUTOUT_REGIONS` is true, and counted under `cutout` of `result.pcb.written`; while it is false, each MUST give one `altium.not-lowered` info whose `where` is `cutout/<k>`, `slot/<name>`, or the items of a merged group joined by `+`, and be counted under `cutout` of `result.pcb.not_lowered`.
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

#### Scenario: An outline with arcs is written
- **GIVEN** a blink variant with `board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(2)))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is planned, no `altium.pcbdoc-not-written` is given, and the board record holds four arc vertices of radius 2 mm

#### Scenario: Build and conversion write one outline
- **GIVEN** the board of "A net tie with copper and pads with a mask margin are written", its `Edge.Cuts` rectangle replaced by lines and one arc, imported with `import --to python`
- **WHEN** it is built with `--target altium --confirm` and converted with `convert --to altium`
- **THEN** both documents hold a board record with the same vertices, relative to the first, and the same arc vertex

#### Scenario: A round board, no document
- **GIVEN** a blink variant with `board(outline=shape.circle(mm(25), mm(15), mm(60)))`, a ring of two arcs
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** no `.PcbDoc` is planned, and `altium.pcbdoc-not-written` names the arcs, not a missing outline

#### Scenario: A round hole becomes a free pad
- **GIVEN** a blink variant with `d.hole("H1", mm(4), mm(4), drill=mm(3.2))`
- **WHEN** it is built with `--target altium --confirm --json` and the PCB document is read back
- **THEN** the exit code is 0, `result.pcb.written` holds `hole` with the count 1, the document holds one free pad with a 3.2 mm hole, plating off and no copper at the placement of `H1`, neither the schematic nor `blink.PcbLib` holds `H1` or a footprint of `Fenolite_Holes`, and no `altium.not-lowered` names `H1`

#### Scenario: A plated hole and a slot are reported
- **GIVEN** a blink variant with `h2 = d.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))`, `connect(gnd, h2[1])` and `d.hole("H3", mm(25), mm(4), drill=mm(1), length=mm(3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is planned with `H3` and without `H2`, `result.pcb.not_lowered` holds `hole` with the count 1 and `result.pcb.written` holds `hole` with the count 1, and `issues` holds one `altium.not-lowered` info whose `where` starts with `hole/`, naming `H2`, its copper and the net `GND`

#### Scenario: Cut-outs are written after native acceptance
- **GIVEN** the shared fixture `tests/data/slots/design.py` and the native-accepted default `pcbdoc.CUTOUT_REGIONS` true
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** `B/slots.PcbDoc` is planned, `result.pcb.written` holds `cutout` with the count 3 and `hole` with the count 1, `result.pcb.not_lowered` has no `cutout`, and no `altium.not-lowered` info names `slot/S1`, `slot/S2+slot/S3` or `cutout/1`

#### Scenario: Cut-outs while the gate is off
- **GIVEN** the shared fixture `tests/data/slots/design.py` and `pcbdoc.CUTOUT_REGIONS` explicitly overridden to false in the regression
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** `B/slots.PcbDoc` is planned, `result.pcb.not_lowered` holds `cutout` with the count 3, and three `altium.not-lowered` infos have the `where` `slot/S1`, `slot/S2+slot/S3` and `cutout/1`
