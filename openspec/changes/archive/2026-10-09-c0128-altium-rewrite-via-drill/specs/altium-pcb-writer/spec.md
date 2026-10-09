## MODIFIED Requirements

### Requirement: Via records
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX, start=1, end=32)` SHALL write one via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer at 29 and the end layer at 30: 1 and 32 for a through via, the ids of the two copper layers of its span for a blind or buried via (change c0085, "Blind and buried via records").
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242, stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index. It MUST raise `ValueError` for a via whose `via_type` is `micro`, whose `layers` are not two different copper layers of the board, or whose drill is not below its diameter. With `PcbDocSpec.allow_full_drill` (change c0128; `False` by default, and no build sets it) a via whose drill equals its diameter MUST be written instead: the hole at 25 holds the value of the diameter at 21, and every other byte is that of any via. A drill above the diameter and a drill of 0 or less MUST be refused in both cases.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Via with a full drill
- **GIVEN** a spec with a through via of diameter 600 000 nm and drill 600 000 nm
- **WHEN** `write_pcbdoc` runs, and again with `allow_full_drill=True`
- **THEN** the first raises `ValueError` naming the via's id, as before change c0128; the second writes one via record whose 32-bit values at 21 and 25 are both 236220, and with a drill of 600 001 nm it raises `ValueError` too

#### Scenario: Micro via refused
- **WHEN** a spec holds a via with `via_type="micro"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` whose two layers are both `F.Cu`, a span that is not two different copper layers of the board (a blind via with a span of two copper layers is written since change c0085, "Blind and buried via records")
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, corner_ratios=None, rewrite=False)` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. A footprint instance of the model holds no graphics, so none is written; the lines and arcs of a footprint in a document that was read are records without a model entity and are counted by RT-A3.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; any other board is written in the frame of a build.
- An `Arc` of the board, and a graphic of kind `arc`, whose `altium` bag holds the pair `arc` (`altium-import`, "Extension bags"; change c0127) MUST be written with the centre, the radius and the two angles of that pair when the pair still says the entity's three points. `lower.kept_arc(entity, points, frame)` decides: it converts the pair as the import does (`adapter.units.arc_points`) and returns the record's geometry (`pcbrecords.ArcGeometry`) when each of the three points it gives lies within `lower.ARC_TOLERANCE` (2 nm per axis, the length tolerance of the written scope) of the entity's point in the frame of the written document; `from_design` puts it into `PcbDocSpec.arc_records` under the entity's id. It returns `None`, and the arc is written from its three points as an arc without the pair is, with no issue, when the pair is stale or unusable: a point lies further away (the arc was moved or reshaped in the model, or the board is written in another frame than the document's), the pair does not parse into three integers of 32 bits and two doubles, the radius is 0 or less, an angle is not finite, or the angles make a full turn. An arc that is written from its kept record MUST NOT be refused because its three points lie on one line: the record holds its circle.
- `rewrite=True` (change c0128) says that `design` is the reading of an Altium document and that the write gives that document back. A via whose drill equals its diameter MUST then be written (`PcbDocSpec.allow_full_drill`): a document that Altium saved holds such vias (`pcb-copper.md`, "Via"; `H-A-PCBX-VIA-FULL`). Without `rewrite` such a via is left out and counted, as before: a design from a script, from a KiCad board or from any other source is written with the rule of a build. `rewrite=True` for a design whose board was not read from an Altium document (`"altium"` is no key of `board.native_ids`) MUST raise `ValueError`; a design without a board takes the argument without effect. The argument changes nothing else: the frame, the kept arc records and every other item are written the same with and without it.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics (an arc gives its start, middle and end), else the box of the board's items; each approximation is counted under `outline`.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; an arc whose three points lie on one line and that is not written from a kept record; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter (in a rewrite: is above its diameter), or is 0 or less; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer (`copper-shape`); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body; a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
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

#### Scenario: Full drill in a rewrite only
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the drill of its first via set to the via's diameter, and of a second via set above its diameter
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k full_drill` calls `from_design` without and with `rewrite=True`
- **THEN** without it both vias are counted as not written with the reason `the drill is not below the diameter`; with it the first via is written with a hole equal to its diameter, reads back with that drill, and only the second is counted; and `rewrite=True` on the design read from `tests/data/kicad/board/two_layer.kicad_pcb` raises `ValueError`

#### Scenario: Counted once per kind
- **WHEN** `from_design` runs on the model of `tests/data/altium/board6/board6.PcbDoc`
- **THEN** `counts()` is 2 texts and 6 graphics, and the issues are one `altium.not-lowered` info for `text` and one for `graphic`

### Requirement: Writer options for a model that was read
`backends.altium.pcbdoc` SHALL take what a model that was read needs, each with a default that keeps the bytes of every build.
- `PcbDocSpec.frame` (`None`: `Frame.of(outline)`) and `PcbDocSpec.origin` (`None`: 1000 mil, 1000 mil); `Frame.document()` is the frame of a document that was read, and `Frame.offset` defaults to 1000 mil.
- `PcbDocSpec.free_pads`: `FreePad(pad, extras, net)` values, written as pads without a component after the holes; `pad.position` and `pad.rotation` are those on the board.
- `PlacedComponent.record_unique_id` (`None`: derived from the file name and the link id) and `PlacedComponent.nets_by_pad` (pad id → net name; `None`: `pad_nets` by pad number), so two pads of one number may lie on different nets.
- `PcbDocSpec.arc_records` (entity id → `pcbrecords.ArcGeometry`; empty by default; change c0127): an arc of `PcbDocSpec.arcs` and a graphic of kind `arc` whose id it names are written with that centre, radius and pair of angles instead of the ones derived from their three points, on the entity's layer, net and width, and in the order that their points give. `graphic_problem(graphic, arc_known=True)` does not refuse an arc for three points on one line. `pcbdoc` reads no bag: the caller decides which records still say their entities.
- `PcbDocSpec.allow_full_drill` (`False` by default; change c0128): `True` lets `via_records` write a via whose drill equals its diameter ("Via records"). `lower.from_design` sets it for a rewrite only; the build (`lens/altium.py`, `lens/altium_copper.py`) never sets it and keeps refusing such a via with `altium.copper-invalid`.
- A component whose designator or comment is empty gets no text record for it, and a component text outside 7-bit ASCII is written with the 8-bit string of a free text beside its wide string.
- No format fact is added: every record is one of `docs/formats/altium/pcb-records.md` and `pcb-document.md`.

#### Scenario: Builds keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)"` rebuilds the committed samples
- **THEN** every file under `tests/data/altium/` keeps its bytes
