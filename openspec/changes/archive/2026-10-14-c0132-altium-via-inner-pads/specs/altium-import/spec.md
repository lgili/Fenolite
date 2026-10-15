## MODIFIED Requirements

### Requirement: Extension bags
The adapter SHALL keep in `ext["altium"]` what a record states about an entity and the model has no field for, as `ExtBag(min_version=None, payload=…)` with pairs in the order of the closed table `adapter.EXT_KEYS`.
- The pair `("u", "<field>=<integer>,…")` MUST list, in model field order, the original integer of every converted length of the entity whose conversion was inexact; `("deg", "<field>=<float.hex()>,…")` likewise for inexact angles.
- An `Arc`, and a `Graphic` of kind `arc`, that is read from an arc record of `Arcs6` MUST hold the pair `("arc", "<centre x>,<centre y>,<radius>,<start angle>,<end angle>")` (change c0127): the centre and the radius as the record's integers of 1/10 000 mil in the document's frame (Y up), and the two angles as `float.hex()` of the stored doubles. The model holds three points, each rounded to a nanometre, and the record's centre and radius cannot be recovered from them in every case; the pair holds them, so that a write can give the record back (`altium-pcb-writer`, "Imported boards are written from the model"). A full circle, which becomes a `circle` graphic, and an arc of the board outline, which is a vertex of the board record and no arc record, hold no such pair. The pair enters no id: the content id of an arc is that of its model fields.
- A `Via` whose record names layers without a pad shape ("Tracks, arcs and vias") MUST hold the pair `("pad_removed", "<layer id>,…")` (change c0132): the Altium layer ids of the record, in ascending order, as decimal integers. The model's `Via` holds one diameter, so the pair is the only place where the import says on which layers the via has none. The pair enters no id.
- `EXT_KEYS` MUST be closed, and each key MUST be a row of `docs/formats/altium/import.md`. It MUST hold at least: `u`, `deg`, `layer_id` and `altium_name` (layers), `plane_net` (a plane layer), `origin` (the board), `stack_mode`, `corner_percent`, `paste`, `mask`, `plated` (pads), `via_layers` (a via whose start and end are not the outer layers), `pad_removed` (a via without a pad shape on some layers), `arc` (an arc that an arc record gave), `net` (a copper graphic with a net), `pour_index`, `hatch_style` (zones), `component_kind`, `part_ids`, `source_designator`, `source_lib_reference` (components and footprints), `electrical` (a pin type outside the table), `pin_symbols` (symbol definitions), `alias` (nets, one pair per further name), `classes` (a net in more than one class), `label` (buses), `harness_type` (interfaces), `scope1`, `scope2`, `rule_kind` (rules).
- A value MUST be text taken from the record or a decimal integer; no bag MUST hold bytes, and no bag MUST hold a key outside `EXT_KEYS`.
- The model is a projection of the records, not their container: a record or a key the adapter does not map stays in the reader's document and is counted by "Unmapped records are counted".

#### Scenario: Original integers kept
- **GIVEN** a free track from (25, 0) to (125, 0) units, 75 units wide
- **WHEN** the board is imported
- **THEN** the track's `altium` bag holds the pair `("u", "start.x=25,end.x=125,width=75")`, and `nm_to_u` of the model values is not needed to recover them

#### Scenario: Arc record kept
- **GIVEN** a free arc on the top copper layer with the centre (1 000 000, 2 000 000) units, the radius 100 units and the angles 30 and 35 degrees, and the same arc on a mechanical layer
- **WHEN** the board is imported
- **THEN** the `Arc` and the `arc` graphic both hold the pair `("arc", "1000000,2000000,100,0x1.e000000000000p+4,0x1.1800000000000p+5")`, and a full circle of the same centre and radius holds no pair `arc`

#### Scenario: Layers without a pad shape kept
- **GIVEN** a six-layer document with a through via whose record holds a non-zero byte for the layers 2, 4 and 5, and the same via with a table of zeros
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_copper.py -k pad_removed` imports it
- **THEN** the first via holds the pair `("pad_removed", "2,4,5")`, the second holds no such pair, and both have the id, the diameter and the layers they have without the bytes

#### Scenario: Closed key table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_ext.py -k closed` imports every authored Altium file under `tests/data/altium/`
- **THEN** every key of every `altium` bag is in `EXT_KEYS`, and every key of `EXT_KEYS` is a row of `docs/formats/altium/import.md`

### Requirement: Tracks, arcs and vias
`import_board` SHALL map free copper primitives to `Track`, `Arc` and `Via`.
- A track or an arc on a copper layer of the chain that is no internal plane, without a component index and without a polygon index, MUST become a `Track` (`start`, `end`, `width`, `layer`, `net_id`) or an `Arc` (`start`, `mid`, `end`, `width`, `layer`, `net_id`). A full circle (0 to 360 degrees) on copper has no `Arc` form and MUST become a `Graphic` of kind `circle` with the pair `net`.
- A track or an arc on the layer of an internal plane, without a component index and without a polygon index, MUST NOT become a `Track`, an `Arc` or a `Graphic`, with or without a net ("Objects on an internal plane"). No view of the imported board has to take such an item out again.
- A track or an arc with a polygon index is poured copper of a zone ("Zones from polygons") and MUST NOT become a board track.
- A via MUST become `Via(position, diameter, drill, layers, net_id, via_type)`. `layers` MUST be the two neutral copper names of its start and end layers. `via_type` MUST be `through` when they are the outer layers, `blind` when exactly one is, and `buried` otherwise; `micro` is never inferred. A start or end layer outside the chain MUST give `altium.import.via-span` (warning), the outer layers and the pair `via_layers`.
- A via whose record names layers without a pad shape (`read.pcbprims.via_pad_removed`; `altium-pcb-reader`, "Removed pad shapes of a via record") MUST hold the pair `pad_removed` with those layer ids (change c0132). Its `diameter`, `layers`, `via_type` and id MUST be those of the same record without the bytes: the model holds one diameter for a via, and what stands on a layer without a pad is said by the pair alone (`altium-verification`, "Clearance rules of a PCB document").
- A width, a diameter or a hole of 0 or less MUST give `altium.import.bad-geometry` (warning) and leave the record unmapped.

#### Scenario: Routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/` of c0038
- **WHEN** it is imported and compared with the model the build wrote it from
- **THEN** the tracks, arcs and vias are equal in number, and each has the model's layer, net name, width or diameter and drill within 2 nm, and end points within 2 nm after the common translation

#### Scenario: Line on a plane is no track
- **GIVEN** a document whose chain is 1 → 39 → 3 → 32 with one free track without a net on layer 39, one free track without a net on layer 3 and one free track on the net `GND` on layer 1
- **WHEN** it is imported
- **THEN** the board holds two tracks, on `In2.Cu` and on `F.Cu`, with the ids and the locators they have in the import of the same document without the track on layer 39, and no track, arc or graphic on `In1.Cu`

#### Scenario: Blind via
- **GIVEN** a four-layer document with a via from layer 1 to layer 2
- **WHEN** it is imported
- **THEN** the via has `layers == ("F.Cu", "In1.Cu")` and `via_type == "blind"`
