## MODIFIED Requirements

### Requirement: Extension bags
The adapter SHALL keep in `ext["altium"]` what a record states about an entity and the model has no field for, as `ExtBag(min_version=None, payload=…)` with pairs in the order of the closed table `adapter.EXT_KEYS`.
- The pair `("u", "<field>=<integer>,…")` MUST list, in model field order, the original integer of every converted length of the entity whose conversion was inexact; `("deg", "<field>=<float.hex()>,…")` likewise for inexact angles.
- An `Arc`, and a `Graphic` of kind `arc`, that is read from an arc record of `Arcs6` MUST hold the pair `("arc", "<centre x>,<centre y>,<radius>,<start angle>,<end angle>")` (change c0127): the centre and the radius as the record's integers of 1/10 000 mil in the document's frame (Y up), and the two angles as `float.hex()` of the stored doubles. The model holds three points, each rounded to a nanometre, and the record's centre and radius cannot be recovered from them in every case; the pair holds them, so that a write can give the record back (`altium-pcb-writer`, "Imported boards are written from the model"). A full circle, which becomes a `circle` graphic, and an arc of the board outline, which is a vertex of the board record and no arc record, hold no such pair. The pair enters no id: the content id of an arc is that of its model fields.
- `EXT_KEYS` MUST be closed, and each key MUST be a row of `docs/formats/altium/import.md`. It MUST hold at least: `u`, `deg`, `layer_id` and `altium_name` (layers), `plane_net` (a plane layer), `origin` (the board), `stack_mode`, `corner_percent`, `paste`, `mask`, `plated` (pads), `via_layers` (a via whose start and end are not the outer layers), `arc` (an arc that an arc record gave), `net` (a copper graphic with a net), `pour_index`, `hatch_style` (zones), `component_kind`, `part_ids`, `source_designator`, `source_lib_reference` (components and footprints), `electrical` (a pin type outside the table), `pin_symbols` (symbol definitions), `alias` (nets, one pair per further name), `classes` (a net in more than one class), `label` (buses), `harness_type` (interfaces), `scope1`, `scope2`, `rule_kind` (rules).
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

#### Scenario: Closed key table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_ext.py -k closed` imports every authored Altium file under `tests/data/altium/`
- **THEN** every key of every `altium` bag is in `EXT_KEYS`, and every key of `EXT_KEYS` is a row of `docs/formats/altium/import.md`
