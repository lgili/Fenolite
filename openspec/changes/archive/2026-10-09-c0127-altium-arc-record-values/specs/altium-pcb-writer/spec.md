## MODIFIED Requirements

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, corner_ratios=None)` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. A footprint instance of the model holds no graphics, so none is written; the lines and arcs of a footprint in a document that was read are records without a model entity and are counted by RT-A3.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; any other board is written in the frame of a build.
- An `Arc` of the board, and a graphic of kind `arc`, whose `altium` bag holds the pair `arc` (`altium-import`, "Extension bags"; change c0127) MUST be written with the centre, the radius and the two angles of that pair when the pair still says the entity's three points. `lower.kept_arc(entity, points, frame)` decides: it converts the pair as the import does (`adapter.units.arc_points`) and returns the record's geometry (`pcbrecords.ArcGeometry`) when each of the three points it gives lies within `lower.ARC_TOLERANCE` (2 nm per axis, the length tolerance of the written scope) of the entity's point in the frame of the written document; `from_design` puts it into `PcbDocSpec.arc_records` under the entity's id. It returns `None`, and the arc is written from its three points as an arc without the pair is, with no issue, when the pair is stale or unusable: a point lies further away (the arc was moved or reshaped in the model, or the board is written in another frame than the document's), the pair does not parse into three integers of 32 bits and two doubles, the radius is 0 or less, an angle is not finite, or the angles make a full turn. An arc that is written from its kept record MUST NOT be refused because its three points lie on one line: the record holds its circle.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics (an arc gives its start, middle and end), else the box of the board's items; each approximation is counted under `outline`.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; an arc whose three points lie on one line and that is not written from a kept record; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer (`copper-shape`); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body; a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
- `AltiumInputs.written` MUST count the model items that the PCB document holds, per kind of `lower.KINDS`, which are the kinds of `lens.altium_copper.KINDS`.
- The schematic's design (`lower.schematic_design`) MUST give every component with a reference a symbol link, a value and pins, so that the schematic writer can generate a sheet from the circuit; a part of a link that no record holds is replaced by a generic one.

#### Scenario: Footprints without a library
- **GIVEN** a design read from a KiCad board whose footprint libraries are not present
- **WHEN** `lens.altium.write_model` runs
- **THEN** the PCB document holds every footprint as a component with its pads, and no library file is read

#### Scenario: Own documents
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc`
- **THEN** each written project holds a PCB document, a schematic, its library and the project file, the reading of each PCB document equals the first reading inside the written scope, and the unique ids of the components are those of the first document

#### Scenario: Arc written from its record
- **GIVEN** the reading of a document with a free copper arc of centre (1 000 000, 2 000 000) units, radius 100 units and angles 30 to 35 degrees, whose three points give another centre and a radius of 93 units when a record is derived from them, and a second arc of the same centre and radius from 0 to 1 degree, whose three points lie on one line
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k kept_arc` writes the model with `AltiumBackend().write` and reads the written document
- **THEN** `PcbDocSpec.arc_records` names both arcs, both are counted as written, the two arc records of the written document hold the centre, the radius and the angles of the first document, and the second reading holds the same six points as the first

#### Scenario: Stale record ignored
- **GIVEN** the same reading with the first arc moved by 1 µm in the model, its bag unchanged
- **WHEN** `from_design` runs
- **THEN** `PcbDocSpec.arc_records` does not name that arc, no issue names it, and the written record's centre is the one derived from the moved points

#### Scenario: Counted once per kind
- **WHEN** `from_design` runs on the model of `tests/data/altium/board6/board6.PcbDoc`
- **THEN** `counts()` is 2 texts and 6 graphics, and the issues are one `altium.not-lowered` info for `text` and one for `graphic`

### Requirement: Writer options for a model that was read
`backends.altium.pcbdoc` SHALL take what a model that was read needs, each with a default that keeps the bytes of every build.
- `PcbDocSpec.frame` (`None`: `Frame.of(outline)`) and `PcbDocSpec.origin` (`None`: 1000 mil, 1000 mil); `Frame.document()` is the frame of a document that was read, and `Frame.offset` defaults to 1000 mil.
- `PcbDocSpec.free_pads`: `FreePad(pad, extras, net)` values, written as pads without a component after the holes; `pad.position` and `pad.rotation` are those on the board.
- `PlacedComponent.record_unique_id` (`None`: derived from the file name and the link id) and `PlacedComponent.nets_by_pad` (pad id → net name; `None`: `pad_nets` by pad number), so two pads of one number may lie on different nets.
- `PcbDocSpec.arc_records` (entity id → `pcbrecords.ArcGeometry`; empty by default; change c0127): an arc of `PcbDocSpec.arcs` and a graphic of kind `arc` whose id it names are written with that centre, radius and pair of angles instead of the ones derived from their three points, on the entity's layer, net and width, and in the order that their points give. `graphic_problem(graphic, arc_known=True)` does not refuse an arc for three points on one line. `pcbdoc` reads no bag: the caller decides which records still say their entities.
- A component whose designator or comment is empty gets no text record for it, and a component text outside 7-bit ASCII is written with the 8-bit string of a free text beside its wide string.
- No format fact is added: every record is one of `docs/formats/altium/pcb-records.md` and `pcb-document.md`.

#### Scenario: Builds keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)"` rebuilds the committed samples
- **THEN** every file under `tests/data/altium/` keeps its bytes
