## ADDED Requirements

### Requirement: Body facts before body code
`docs/formats/altium/pcb-bodies.md` SHALL hold a section "Written form of an extruded body" with one row for each binary field and each key that `pcbrecords.body_record` writes, and the writer MUST NOT write a key or a field that has no row there.
- Each row MUST state the value rule (a constant, a value of the model, or a choice of Fenolite among values that saved records hold), a source of `docs/evidence/sources.md`, an evidence label and a hypothesis of `docs/hypotheses.md`.
- A row whose value no source supports MUST be marked `stand-in` and MUST name the hypothesis that an author report settles; this change has two, `MODELID` and `MODEL.CHECKSUM` (`H-A-PCBX-BODY-OPEN`). While a stand-in row exists, component bodies MUST be written only on request ("Component bodies in an Altium build" of `altium-build`).
- `pcbrecords.BODY_KEYS` MUST be the keys of the written record in order, and a unit test MUST compare it with the rows of the section in both directions.
- `tests/corpus/test_altium_bodies.py` MUST hold the rows over the extruded bodies (`MODEL.MODELTYPE=0`) of the public PCB documents of the corpus manifest and MUST print, per document, the number of bodies of each kind; it reports counts and value forms only.

#### Scenario: Keys and rows agree
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcb_bodies.py -k facts` reads the section and `BODY_KEYS`
- **THEN** every key of `BODY_KEYS` has exactly one row, every row of a key is in `BODY_KEYS`, the rows of `MODELID` and `MODEL.CHECKSUM` are marked `stand-in` and name `H-A-PCBX-BODY-OPEN`, and no other row is

#### Scenario: The rows hold over the public documents
- **WHEN** `uv run pytest tests/corpus/test_altium_bodies.py -rA` runs with the corpus cached
- **THEN** every extruded body holds the constants, the key order (apart from the two optional keys the section names), `MODEL.EXTRUDED.MINZ` equal to `STANDOFFHEIGHT`, `MODEL.EXTRUDED.MAXZ` equal to `OVERALLHEIGHT`, a `BODYPROJECTION` of 0 on a top component and 1 on a bottom one, whole units in every vertex and a twin with the same property text at the same index of `ShapeBasedComponentBodies6`; the documents with extruded bodies come from at least three repositories; and no `MODELID` of an extruded body is an entry of `Models`

### Requirement: Extruded component body records
`pcbrecords.body_record(layer, vertices, *, component, standoff, overall, bottom, identifier="", model_id="", shape_based=False, form="saved")` SHALL return one component body primitive (type 12) of an extruded body in the form that "Written form of an extruded body" states, and `pcbdoc.write_pcbdoc` SHALL write the bodies of `PcbDocSpec.bodies` into `ComponentBodies6` and `ShapeBasedComponentBodies6`.
- The primitive MUST be the type byte 12 and one subrecord: the common prefix with `layer`, no net, no polygon and the component index (`0xFFFF` for none), five zero bytes, the 32-bit length of the property text with its NUL, the text, the 32-bit vertex count and the vertices. `vertices` are binary units, at least three, without a closing vertex; fewer MUST raise `ValueError`. The plain form holds each vertex as two doubles; the shape-based form holds each as 37 bytes, none round, and repeats the first vertex after the last.
- `layer` MUST be a mechanical layer 1 to 16 (ids 57 to 72), else `ValueError`; `V7_LAYER` is its text.
- `standoff` and `overall` are binary units, written as mil text in `STANDOFFHEIGHT` and `OVERALLHEIGHT` and again in `MODEL.EXTRUDED.MINZ` and `MODEL.EXTRUDED.MAXZ`; `overall` not above `standoff`, and a negative `standoff` (no saved extruded body holds one), MUST raise `ValueError`. `BODYPROJECTION` MUST be 1 when `bottom` and 0 otherwise. `IDENTIFIER` MUST be the decimal character codes of `identifier` joined by commas, empty for an empty identifier. `MODEL.2D.X` and `MODEL.2D.Y` MUST be the centre of the bounding box of `vertices` as mil text, a half unit rounded towards zero.
- With `form="saved"` the text MUST hold the 35 keys of `BODY_KEYS` in order, `MODELID` being `model_id` and `MODEL.CHECKSUM` being `0`; an empty `model_id` MUST raise `ValueError`. With `form="short"` it MUST hold the first 21 keys, ending at `TEXTUREROTATION`.
- `pcbrecords.body_model_id(body_id)` MUST return a GUID text in braces that depends on `body_id` alone, so that a build is repeatable.
- `PcbDocSpec.bodies` holds one `PlacedBody` per body to write: the index of its component in `PcbDocSpec.components`, the Altium layer id, the outline placed in the frame of the placements, the heights in nanometres, the side, the identifier, the `MODELID` stand-in and the id of the model's body (for the caller's accounts; no record holds it). `PcbDocSpec.body_form` is `saved` (the default) or `short`; no command and no option of a build sets `short`. `write_pcbdoc` MUST convert each outline point with `to_units` after the document's frame, drop equal neighbours, and write record `i` of both storages from body `i`, in the order of `bodies`, with each `Header` the count. A body whose component index is outside `components`, or that keeps fewer than three vertices, MUST raise `ValueError`: the caller checks with `pcbdoc.body_problem` and places with `pcbdoc.place_body(body, *, component, at, rotation, bottom, frame)`, which returns the `PlacedBody` or the reason. The layers of the bodies MUST be among the layers in use of the board record.
- A spec without bodies MUST give the document it gave before this change, byte for byte. No record of `Models`, `ModelsNoEmbed`, `Textures` or `UniqueIDPrimitiveInformation` is written for a body.

#### Scenario: Rectangle on a top component
- **GIVEN** a body with the vertices `(0, 0), (10000, 0), (10000, 5001), (0, 5001)` on layer 69, component 2, standoff 0 and overall 984252 units, not bottom, the identifier `U1`
- **WHEN** `body_record` is called in the plain and in the shape-based form
- **THEN** both records hold the same 35 keys in the order of `BODY_KEYS`, `V7_LAYER=MECHANICAL13`, `OVERALLHEIGHT=98.4252mil`, `MODEL.EXTRUDED.MAXZ=98.4252mil`, `STANDOFFHEIGHT=0mil`, `BODYPROJECTION=0`, `IDENTIFIER=85,49`, `MODEL.2D.X=0.5mil`, `MODEL.2D.Y=0.25mil`, `MODEL.CHECKSUM=0` and `MODEL.MODELTYPE=0`; the plain record ends with four vertices of 16 bytes and the other with five of 37; and `read_bodies` frames each with an empty tail, the component 2 and the heights given

#### Scenario: Short form
- **WHEN** `body_record(..., form="short")` is called
- **THEN** the text holds 21 keys, the last is `TEXTUREROTATION`, and no key starts with `MODEL`

#### Scenario: Document with three bodies
- **GIVEN** a `PcbDocSpec` with three bodies on two components, one of them on the bottom side
- **WHEN** it is written and read with `read_pcbdoc` and `read_bodies`
- **THEN** each of the two storages holds three records and a `Header` of 3, record `i` of one has the text of record `i` of the other, and the same spec without bodies gives the bytes of the document before this change

### Requirement: Component bodies of a library footprint
`pcblib` SHALL write each body of `LibFootprint.bodies` as one component body primitive in the footprint's stream when bodies are asked for, and none otherwise.
- The primitive MUST be `body_record` in the plain form with no component (`0xFFFF`), `bottom=False`, the outline in the library's frame and the layer rule of "Component bodies are reported"; it MUST be counted in the stream's header as every primitive is, and written after the footprint's other primitives. The footprint's list of unique ids MUST hold no entry for a body: the one saved library with a body lists its pads only (`tests/corpus/test_altium_bodies.py -k library`).
- Only a body that "Component bodies are reported" writes is written; `check_footprint` MUST list each other body of the definition in its notes.
- A library without a written body MUST be the bytes it was before this change.
- The fact page MUST say that no extruded body of a saved library was read: the form is the document's, and the one library body of the corpus names a model (`H-A-PCBX-BODY-LIB`, `INFERRED`).

#### Scenario: Footprint with a body
- **GIVEN** a `FootprintDef` with two pads and one extruded body of 1.2 mm with a rectangle outline
- **WHEN** the library is written with bodies and read with `read_pcblib`
- **THEN** the footprint holds one primitive of type 12 after its pads, `read_bodies` frames it with no component, the overall height reads 1.2 mm within one unit, and the library written without bodies equals the library of today

## MODIFIED Requirements

### Requirement: Component bodies are reported
The writer SHALL write a component body record for each `ComponentBody` of a footprint of the board that is extruded, has an outline and a height above its standoff, when bodies are asked for (`altium-build`, "Component bodies in an Altium build"), and each other `ComponentBody` SHALL give one `altium.not-lowered` with `where` `body/<id>` that names its height and its reason. No model file is embedded, and no body is written that the model does not hold.
- `pcbdoc.body_problem(body)` MUST return why a body has no record, or `None`: the kind `model` ("a body that names a 3D model needs the model's data, which the model does not hold"); an outline of fewer than three distinct points ("the body has no outline"); a standoff below the board surface, which no saved extruded body holds; and a height that is not above the standoff in the units of the record. The function reads `kind`, `outline`, `height` and `standoff` of the body as the model holds them and no other field. A body whose footprint is no component of the written document has the reason "its footprint is not written", and a body whose placed outline keeps fewer than three vertices in whole units has no outline: `pcbdoc.place_body` and the lowering decide these two.
- Without the request every body MUST be reported, with the reason "component bodies are not written without --altium-bodies extruded" and the body's height, and no record is written: the document is the document of change c0085.
- A written body MUST be one record of "Extruded component body records": the component is the body's footprint; the outline is the body's outline placed by the position and rotation that the document gives the footprint's component, without a mirror (the outline of a footprint instance is held as seen from the top, as its pads are); `STANDOFFHEIGHT` and `OVERALLHEIGHT` are `standoff` and `height`; `bottom` is the footprint's side; the identifier is `name`; `MODELID` is `body_model_id(body.id)`.
- The layer MUST be the Altium id of `ComponentBody.layer` when the layer map gives it a mechanical layer 1 to 16, and otherwise Mechanical 13 for a body of a top footprint and Mechanical 14 for a body of a bottom one.
- A footprint without a body MUST get no record and no issue: no outline is derived from a courtyard or from any other graphic, and no height is assumed.
- Each body MUST be counted once, as written or as not lowered ("Written items are accounted").

#### Scenario: Body height
- **GIVEN** a board footprint with a body of height 2.5 mm
- **WHEN** the design is built for Altium without `--altium-bodies`
- **THEN** `result.pcb.not_lowered` holds `body` with the count 1, and one `altium.not-lowered` with `where` `body/<id>` names 2.5 mm and the option

#### Scenario: Body written
- **GIVEN** the same footprint, placed on the bottom side and turned by 90 degrees, with a rectangle outline
- **WHEN** the design is built with `--altium-bodies extruded` and the document is imported
- **THEN** `result.pcb.written` holds `body` with the count 1 and no issue names the body, both body storages hold one record with `BODYPROJECTION=1` on Mechanical 14 and the index of the footprint's component, and the imported footprint holds one extruded body with the height 2.5 mm and the outline of the model within 2 nm

#### Scenario: Bodies that have no record
- **GIVEN** a footprint with a body of kind `model`, a body without outline and a body whose height equals its standoff, and a second footprint without a body
- **WHEN** the design is built with `--altium-bodies extruded`
- **THEN** `result.pcb.not_lowered.body` is 3, each of the three has one `altium.not-lowered` with its own reason, the second footprint has no issue, and both body storages are empty

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, corner_ratios=None, rewrite=False, bodies="off")` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. A footprint instance of the model holds no graphics, so none is written, and the definition holds no body: the bodies of an instance are written into the document (change c0121), not into a library; the lines and arcs of a footprint in a document that was read are records without a model entity and are counted by RT-A3.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; any other board is written in the frame of a build.
- An `Arc` of the board, and a graphic of kind `arc`, whose `altium` bag holds the pair `arc` (`altium-import`, "Extension bags"; change c0127) MUST be written with the centre, the radius and the two angles of that pair when the pair still says the entity's three points. `lower.kept_arc(entity, points, frame)` decides: it converts the pair as the import does (`adapter.units.arc_points`) and returns the record's geometry (`pcbrecords.ArcGeometry`) when each of the three points it gives lies within `lower.ARC_TOLERANCE` (2 nm per axis, the length tolerance of the written scope) of the entity's point in the frame of the written document; `from_design` puts it into `PcbDocSpec.arc_records` under the entity's id. It returns `None`, and the arc is written from its three points as an arc without the pair is, with no issue, when the pair is stale or unusable: a point lies further away (the arc was moved or reshaped in the model, or the board is written in another frame than the document's), the pair does not parse into three integers of 32 bits and two doubles, the radius is 0 or less, an angle is not finite, or the angles make a full turn. An arc that is written from its kept record MUST NOT be refused because its three points lie on one line: the record holds its circle.
- `rewrite=True` (change c0128) says that `design` is the reading of an Altium document and that the write gives that document back. A via whose drill equals its diameter MUST then be written (`PcbDocSpec.allow_full_drill`): a document that Altium saved holds such vias (`pcb-copper.md`, "Via"; `H-A-PCBX-VIA-FULL`). Without `rewrite` such a via is left out and counted, as before: a design from a script, from a KiCad board or from any other source is written with the rule of a build. `rewrite=True` for a design whose board was not read from an Altium document (`"altium"` is no key of `board.native_ids`) MUST raise `ValueError`; a design without a board takes the argument without effect. The argument changes nothing else: the frame, the kept arc records and every other item are written the same with and without it; component bodies are written by `bodies` alone, in a rewrite as in any other write.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics (an arc gives its start, middle and end), else the box of the board's items; each approximation is counted under `outline`.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; an arc whose three points lie on one line and that is not written from a kept record; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter (in a rewrite: is above its diameter), or is 0 or less; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer (`copper-shape`); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body that "Component bodies are reported" does not write, which is every body when `from_design` is called without `bodies="extruded"` (change c0121); a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
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
