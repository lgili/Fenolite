## MODIFIED Requirements

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, options=None, corner_ratios=None)` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads, graphics, fields and texts taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. Its graphics, its fields `Reference` and `Value` and its texts are written as "Footprint items of a written component" says. An instance that holds none (a model stored before change c0126, a design read from KiCad without the projection) is written with its pads alone, as before.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; any other board is written in the frame of a build.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics (an arc gives its start, middle and end), else the box of the board's items; each approximation is counted under `outline`.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer (`copper-shape`); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body; a graphic or a text of a footprint that the records do not carry (`footprint-graphic`, `footprint-copper`, `footprint-text`); a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
- `AltiumInputs.written` MUST count the model items that the PCB document holds, per kind of `lower.KINDS`, which are the kinds of `lens.altium_copper.KINDS`.
- The schematic's design (`lower.schematic_design`) MUST give every component with a reference a symbol link, a value and pins, so that the schematic writer can generate a sheet from the circuit; a part of a link that no record holds is replaced by a generic one.

#### Scenario: Footprints without a library
- **GIVEN** a design read from a KiCad board whose footprint libraries are not present
- **WHEN** `lens.altium.write_model` runs
- **THEN** the PCB document holds every footprint as a component with its pads, and no library file is read

#### Scenario: Own documents
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc`
- **THEN** each written project holds a PCB document, a schematic, its library and the project file, the reading of each PCB document equals the first reading inside the written scope, and the unique ids of the components are those of the first document

#### Scenario: Counted once per kind
- **WHEN** `from_design` runs on the model of `tests/data/altium/board6/board6.PcbDoc`
- **THEN** `counts()` is 1 graphic (the one on the keep-out layer), the one issue is an `altium.not-lowered` info for `graphic`, and `written` counts 27 under `footprint-graphic`

## ADDED Requirements

### Requirement: Footprint items of a written component
`backends.altium.lower` SHALL write the graphics, the fields and the texts of a footprint instance as primitives of its component, and SHALL count what the records do not carry.
- The definition that `lower` hands to `pcbdoc.place_component` MUST hold the instance's graphics in the top-side form: for a bottom footprint each point is mirrored about the local X axis and each layer swapped for its other side, the inverse of what `place_component` applies, as the pads are (`lower._library_pad`). The order is the instance's.
- A `line`, an unfilled `rect`, an unfilled `circle` and an `arc` MUST be written with `pcblib.graphic_records` ("Footprint line and arc records"), with the component's index.
- **Layers.** The layers are those of `pcbrecords.LAYER_MAP` that are no copper layer and, for a board that was read from an Altium document, `Mech.13` to `Mech.16` as the layers 69 to 72, which every written document enables. With the group of fills and regions, the paste and solder-mask layers of `pcbrecords.BOARD_LAYER_MAP` are layers of a footprint's graphics too. The same four names MUST be taken for the free texts and graphics of such a board. For such a board `Mech.<n>` for n from 1 to 12 MUST be the layer `56 + n`, for footprint and board items alike, and the board record MUST enable each mechanical layer that a primitive lies on; a document that uses none of them keeps its bytes. The meaning of the enable key MUST be a fact row with a public source before the code is written.
- A graphic on a copper layer MUST NOT be written: it is counted under `footprint-copper`, a kind of `lower.LOSS_KINDS`, so its loss is a warning and needs `allow_lossy`. A graphic on a layer without a layer in the document, a degenerate arc and, until its group is implemented, a `polygon` or a filled shape are counted under `footprint-graphic` (info). With the group of fills and regions, a filled `rect`, a filled `circle` and a `polygon` without holes are region records with the component's index.
- **Fields.** `pcbdoc.PlacedComponent.designator` and `.comment` (`TextPlace | None`, `None` by default) MUST carry the place of the fields `Reference` and `Value` of an instance that has them: position, layer, height, stroke, rotation, and whether the text is shown (`NAMEON`, `COMMENTON`). `None` MUST give the bytes the writer gave before.
- **Texts.** Until its group is implemented, a text of `texts` is counted under `footprint-text` (info). With it, a text is a text record with the component's index and its string as stored; a text that the record cannot hold (a line break, a height that is not positive, a layer without a layer in the document) stays counted.
- `footprint-graphic`, `footprint-copper` and `footprint-text` are kinds of `lower.MORE_KINDS`: `lower.KINDS`, and with it `result.pcb` of a build, do not change. `AltiumInputs.written` counts the written items under the same three keys.
- **Corner ratio.** The corner percentage of a rounded pad MUST come from `Pad.corner_ratio`, else from the pair `corner_percent` of its `altium` bag, else from the caller's `corner_ratios`; without any, the pad is not written and counted as today.
- `pcblib.check_footprint` is unchanged: a library footprint with a graphic on a copper layer is still refused, and its drops are those of "Footprint content checks".
- Every record field written MUST be a row of `docs/formats/altium/pcb-records.md` or `pcb-document.md`; a field without a row is not written, and its item is counted.

#### Scenario: Silkscreen survives a rewrite
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_items.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc` and imports the written documents
- **THEN** each footprint of each reading holds the graphics of the first reading within 2 nm, 27 per document, and no `footprint-graphic` is counted as not written

#### Scenario: A bottom footprint
- **GIVEN** the model of `blink.PcbDoc`, whose `D1` is on the bottom side
- **WHEN** it is written and imported
- **THEN** the graphics of `D1` are on the bottom layers they were on, at the points they were at, within 2 nm

#### Scenario: Mechanical layers of a rewrite
- **GIVEN** an authored document, built in the test, whose one component owns a track on Mechanical 1 and a track on Mechanical 5
- **WHEN** it is imported, written with `AltiumBackend().write` and imported again
- **THEN** the footprint holds one `line` on `Mech.1` and one on `Mech.5` at the points of the first reading within 2 nm, the board record of the written document enables Mechanical 1 and 5, and no `footprint-graphic` is counted as not written

#### Scenario: Copper inside a footprint
- **GIVEN** the model of `blink.PcbDoc` with one `line` on `F.Cu` added to the graphics of `R1`
- **WHEN** `AltiumBackend().write(design)` runs, and again with `allow_lossy=True`
- **THEN** the first raises `LossyWriteError` with one `altium.not-lowered` warning whose `where` is `footprint-copper`, and the second writes the document without that line and counts it

#### Scenario: Designator at its place
- **GIVEN** the model of `blink.PcbDoc` with the field `Reference` of `R1` moved by 2 mm and its field `Value` made visible
- **WHEN** it is written and imported
- **THEN** the two fields of `R1` come back at those places within 2 nm, both visible

#### Scenario: Builds keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)"` rebuilds the committed samples
- **THEN** every file under `tests/data/altium/` keeps its bytes
