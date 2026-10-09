# altium-import Specification

## Purpose
Map what the Altium readers return onto the design model: units and frame, identifiers and provenance, layers, nets, footprints, padstacks, copper, zones, outline, the circuit of a schematic with its hierarchy, buses and harnesses, rules and libraries. It defines the registered Altium backend, the import issue codes, the count of unmapped records and the oracles that judge the result.

## Requirements

### Requirement: Adapter package
Fenolite SHALL provide the adapter from the Altium readers' records into the neutral model as the package `fenolite.backends.altium.adapter`.
- It MUST export `import_board(doc, *, file, sha256, issues=None) -> Design`, `import_circuit(sheets, *, options=NetOptions(), issues=None) -> Circuit`, `import_project(project: ProjectInput, *, issues=None) -> Design`, `import_footprints(library, *, name, file, sha256, issues=None) -> Library`, `import_symbols(library, *, name, file, sha256, issues=None) -> Library`, `netlist(sheets, *, options=NetOptions(), issues=None) -> Netlist`, the dataclasses `SheetInput`, `BoardInput`, `RulesInput`, `ProjectInput`, `NetOptions`, `Netlist`, `NetGroup`, `BusGroup`, `HarnessGroup` and `PinKey`, the tables `LAYERS`, `PIN_TYPES`, `EXT_KEYS` and `IMPORT_ISSUE_CODES`, and `EVIDENCE`.
- `doc` is a `read.pcb.PcbDocument` (c0041), a sheet's document a `read.sch.SchDocument` (c0040), `library` a `read.pcblib.PcbLibrary` or a `read.schlib.SchLibrary`, and a project a `ProjectInput` of records, which the backend builds from the `AltiumProject` of `read.project.load_project` (c0042): the adapter opens no file, so it cannot take the project folder itself. The adapter MUST read typed attributes and property lists of those records only: it MUST NOT parse a sector, a stream, a record frame or a project file.
- The adapter MUST NOT open, create or change a file, MUST NOT run a subprocess, and MUST import only the standard library, `fenolite.core`, `fenolite.model`, `fenolite.geometry`, `fenolite.backends.base`, `fenolite.backends.altium.read`, `fenolite.backends.altium.adapter` and `fenolite.backends.altium.import_evidence` (where `EVIDENCE` lives, so that the backend names it without loading a reader). It MUST NOT import a writer module of `fenolite.backends.altium` (`ascii`, `binary`, `schdoc`, `schlib`, `altsym`, `layout`, `project`, `prjpcb`, `pcbrecords`, `pcblib`, `pcbdoc`, `libboard`, `docboard`).
- No function MUST use a float for a length, a coordinate or a stored angle. A double of a record is converted once, by "Units and frame".
- Two calls with equal arguments MUST return equal results and equal issue lists, whatever `PYTHONHASHSEED` is.
- `EVIDENCE` MUST be an `Evidence` whose hypotheses are every registered `H-A-IMP-*` id and whose level is the lowest level among them and among the readers' `EVIDENCE` values.

#### Scenario: Adapter imports no writer
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_package.py -k imports` walks the imports of every module under `backends/altium/adapter/`
- **THEN** none of them names a writer module, `tests` or a third-party package

#### Scenario: Deterministic import
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** `import_board` runs on it in two processes with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2` and both designs are dumped with `canonical.dumps`
- **THEN** the two texts and the two issue lists are equal

### Requirement: Units and frame
`adapter.units` SHALL convert every Altium length, point and angle into the model's integers as `docs/formats/units.md` states.
- A binary PCB length of `u` units of 1/10 000 mil MUST become `fenolite.core.units.u_to_nm(u)`: `u × 127 / 50` rounded half to even. `read.pcbprims.to_nm` of c0041 is the same function.
- A length written as property text (`10mil`, `0.5mil`, `1.27mm`) MUST be parsed as an exact fraction and rounded half to even to nanometres; a text that is not a decimal number with the unit `mil` or `mm` MUST give `altium.import.bad-length` (warning) and the entity that needs it MUST be left unmapped.
- A schematic length MUST be `SchLength.nm()` of c0040: `value × 127 / 50` rounded half to even, exact for every multiple of 50.
- A point of a PCB document or a PCB library MUST become `Point(u_to_nm(x), -u_to_nm(y))`: the model's Y axis points down and Altium's up. No origin is subtracted: the board origin goes to the board's extension bag.
- A point of a schematic library MUST keep its sign on both axes, so that a `SymbolDef` read from a library that Fenolite wrote from a KiCad symbol has that symbol's pin positions.
- A stored angle `d` (a double, in degrees, counter-clockwise) MUST become `round_half_even(Fraction(d) × 10^6)` microdegrees, reduced to `[0, 360°)`. When the double nearest to the result divided by 10^6 is not `d`, the angle is inexact.
- Whenever a conversion is inexact, the entity's `altium` bag MUST hold the original value ("Extension bags"), and `altium.import.inexact` (info) MUST be given once per import with the counts of inexact lengths and angles.
- An arc given by centre, radius and two angles MUST become the model's three points `start`, `mid`, `end`, computed with `fenolite.geometry` in fixed-point arithmetic and rounded half to even; the arc's direction MUST be kept under the Y flip.

#### Scenario: Whole multiples are exact
- **WHEN** `units.pcb_point(100_000, 50)` and `SchLength(100_000).nm()` are computed
- **THEN** the point is `Point(254_000, -127)` and the length is `254_000`

#### Scenario: Ties round to even
- **WHEN** `u_to_nm` converts 25, 75 and -25 units
- **THEN** the results are 64, 190 and -64, and each entity that holds such a value carries it in its `altium` bag

#### Scenario: Angle of a quarter turn
- **WHEN** `units.angle(90.0)`, `units.angle(-90.0)` and `units.angle(33.3)` are computed
- **THEN** the results are `(90_000_000, True)`, `(270_000_000, True)` and `(33_300_000, True)`, and `units.angle(1e-7)` gives `(0, False)`

#### Scenario: Unreadable length text
- **GIVEN** a polygon record whose `VX0` is `abc`
- **WHEN** the board is imported
- **THEN** the zone is not created, `altium.import.bad-length` names the record's locator, and the polygon is counted in `altium.import.unmapped`

### Requirement: Identifiers and provenance
Every entity the adapter creates SHALL have an id by "Identifier derivation" of `design-model` with the backend `altium`, its native id in `native_ids["altium"]` when it has one, and a `Provenance`.
- Native ids MUST be:

| entity | native id |
|---|---|
| design header, board, rule set | `altium_pcbdoc`, `altium_schdoc` or `altium_prjpcb`, the kind that was read |
| net | `net:<name>` |
| net class | `class:<name>` |
| schematic component | `cmp:<unique-id path>`: `\<sheet symbol id>…\<component id>`, the id being the `UNIQUEID` of its lowest shown part |
| pin | `<component native id>:pin:<designator>` |
| module | `module:<unique-id path of its sheet symbols>` |
| footprint instance | `fp:<UNIQUEID of the PCB component>` |
| component synthesised from a PCB document | `cmp:<SOURCEUNIQUEID>` when that text is not empty, else `cmp:fp:<UNIQUEID>` |
| pad | `pad:<its id of UniqueIDPrimitiveInformation>`; without one `<footprint native id>:pad:<name>:<k>`, `k` counting the pads of that name in the footprint from 0 |
| layer, stack layer, stack-up | `layer:<neutral name>`, `stack:<position>`, `stackup` |
| zone | `zone:<polygon UNIQUEID>` when the record holds one |
| rule | `rule:<RULEKIND>:<NAME>:<neutral kind>` |
| library definition | `<library>:<name>`, by "Identifiers of library definitions" |

- An entity without a native id (a track, an arc, a via, a text, a graphic, a body, a bus, a harness interface, a component, footprint or zone whose record holds no unique id) MUST get `content_id(prefix, "altium", <kind that was read>, <section>, content_hash(<model fields>, <occurrence>))`, the occurrence counting earlier entities of equal content, so that ids are unique and an edit of another object changes none.
- Two imports of the same bytes MUST give equal ids. A file hash MUST NOT enter an id.
- `Provenance` MUST hold `backend="altium"`, `file` (the name of the file the record came from, without a folder), `file_sha256` of that file, `locator` and `evidence=adapter.EVIDENCE`. The locator MUST be `<storage>/<stream>#<record index>` for a PCB record (`Tracks6/Data#17`; a vertex adds `:V<k>`), `<stream>#<record index>` for a schematic record (`FileHeader#42`, `Additional#3`), and `<storage>/Data#<index>` in a library. An entity built from several records names the first, in stream order.
- In a project import, each entity's provenance MUST name its own file, so a design holds as many file hashes as files were read.

#### Scenario: Stable ids across imports
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is imported twice
- **THEN** every id of the two designs is equal, the net `GND` has the id `derived_id("net", "altium", "net:GND")`, and no two entities share an id

#### Scenario: Editing another track keeps the id
- **GIVEN** a document with two free tracks, and a copy in which the second track is moved
- **WHEN** both are imported
- **THEN** the first track has the same id in both designs

#### Scenario: Provenance of a project
- **GIVEN** the project of `tests/data/altium/blink/`
- **WHEN** `AltiumBackend().read(blink.PrjPcb)` runs
- **THEN** the component `R1` has `provenance.file == "blink.SchDoc"` with that file's SHA-256, its footprint has `provenance.file == "blink.PcbDoc"`, and both locators name a record that holds `R1`

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

### Requirement: Layers and stack-up
`import_board` SHALL give the board its layers and stack-up from `BoardRecord`, with neutral names from the closed table `adapter.LAYERS`.
- **Copper by position.** The copper layers are `BoardRecord.copper_chain`. The first MUST be `F.Cu`, the last `B.Cu`, and the j-th layer between them `In<j>.Cu`, whatever its Altium id: a mid layer and an internal plane are named alike. A chain of one layer, or an empty chain, MUST give `altium.import.bad-stack` (error) and the layers `F.Cu` and `B.Cu`.
- **Other layers.** 33 and 34 are `F.SilkS` and `B.SilkS`, 35 and 36 `F.Paste` and `B.Paste`, 37 and 38 `F.Mask` and `B.Mask`, 56 `Altium.KeepOut` (kind `user`), 57 to 72 `Mech.<n>` for Mechanical n (kind `mechanical`), 55 `Altium.DrillGuide` and 73 `Altium.DrillDrawing` (kind `user`). Layer 74 (Multi-Layer) is no model layer: an object on it lies on every copper layer.
- A `Layer` MUST be created for every copper layer of the chain, for `Edge.Cuts` (kind `edge`), and for every other layer that at least one imported object lies on. `Layer.ordinal` MUST be the chain position for copper (0 for `F.Cu`), and for the others the Altium id plus 100, so the order is stable. `Layer.ext["altium"]` MUST hold `layer_id`, `altium_name` (the name the record gives the layer, which a user may have changed) and, for a plane with a net, `plane_net`. The layer of an internal plane on which the import left objects out ("Objects on an internal plane") MUST also hold `plane_cuts`, their number as a decimal integer; a layer without such an object MUST NOT hold the key.
- A primitive on a copper id outside the chain, or on an id outside the table, MUST go to the layer `Altium.<id>` (kind `user`) with one `altium.import.layer-outside-stack` warning per id.
- **Stack-up.** When `BoardRecord.stack` holds copper or dielectric entries, `Board.stackup` MUST hold one `StackLayer` per such entry, top to bottom: copper entries with the neutral copper name, kind `copper` and the copper thickness; dielectric entries with kind `dielectric`, the height as thickness, and `material`, `epsilon_r` and `loss_tangent` as the record's decimal texts. Otherwise the stack-up MUST be built from the numbered layers of the chain (`COPTHICK`, `DIELHEIGHT`, `DIELCONST`, `DIELMATERIAL`), one dielectric between each pair of neighbours. Entries of the physical list of any other kind (overlays, paste, solder mask and their coverlay dielectrics) MUST be kept out of the stack-up: saved documents list them around the copper, and the scenario below counts copper and dielectric only.
- A plane layer MUST stay a `Layer` of kind `copper` (c0038, Decision 5). No zone MUST be synthesised for a plane. An internal plane is a layer of the chain whose Altium id is 39 to 54, whatever `PLANE<n>NETNAME` holds. The model holds nothing of a plane's own copper: the document stores a plane in negative, as the objects that cut it.

#### Scenario: Two-layer board
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is imported
- **THEN** the copper layers are `F.Cu` (ordinal 0) and `B.Cu` (ordinal 1) with `layer_id` 1 and 32, `Edge.Cuts` exists, and the stack-up is copper, dielectric, copper with the dielectric constant `4.800` as text

#### Scenario: Plane and mid layer by position
- **GIVEN** a board record whose chain is 1 → 39 → 3 → 32 with `PLANE1NETNAME=GND`
- **WHEN** the layers are built
- **THEN** layer 39 is `In1.Cu` with `plane_net` `GND`, layer 3 is `In2.Cu`, a track on layer 3 lies on `In2.Cu`, and the board holds no zone

#### Scenario: Layer outside the chain
- **GIVEN** a two-layer document with one track on layer 2
- **WHEN** it is imported
- **THEN** the track lies on `Altium.2`, and one `altium.import.layer-outside-stack` warning names layer 2

### Requirement: Nets and net classes of a board
`import_board` SHALL create one `Net` per record of `Nets6` and one `NetClass` per net class of `Classes6`.
- Net names MUST be kept as written. Two records with one name MUST give one net and one `altium.import.duplicate-net` warning.
- A `ClassRecord` with `kind == 0` and `superclass` false is a net class: `NetClass(name)` with every physical field `None`. Values of a class come from rules ("Rules where they map") and are never folded into the class.
- `Net.netclass_id` MUST be the class that lists the net; when several do, the first by name, with the others in the pair `classes` and one `altium.import.multi-class` info per import.
- A class member that names no net MUST give `altium.import.unknown-member` (warning). Classes of other kinds and super classes are unmapped.

#### Scenario: Classes of the routed sample
- **GIVEN** `tests/data/altium/routed/` of c0038, whose class `PWR` lists `GND` and `VIN`
- **WHEN** its PCB document is imported
- **THEN** the circuit holds the net class `PWR`, and the nets `GND` and `VIN` have its id as `netclass_id`

#### Scenario: Super class skipped
- **GIVEN** a `Classes6` with one record `NAME=All Nets`, `SUPERCLASS=TRUE`
- **WHEN** the document is imported
- **THEN** the circuit holds no net class, and the record is counted in `altium.import.unmapped`

### Requirement: Footprint instances and pads
`import_board` SHALL create one `FootprintInstance` per record of `Components6` from the record and from the primitives that carry its index.
- `position` MUST be the converted `x`, `y`; `side` `bottom` when `layer` is `BOTTOM`, else `top`; `locked` from the record; `lib_ref` `<stem of source_footprint_library>:<pattern>`, or the pattern alone when the library text is empty.
- `rotation` MUST be the model angle `θ` for which `Transform.placement(position, θ, mirror=(side == "bottom"))`, followed by the Y flip, is the placement the writer of c0035 writes as `ROTATION` (its inverse): reading a document that Fenolite wrote gives the rotation it was written from.
- **Pad frame.** `Pad.position` MUST be the point `p` for which `Transform.placement(position, rotation).apply(p)`, without a mirror, is the pad's absolute position, and `Pad.rotation` the pad's angle minus the instance's, as "Board entities read from file backends" requires. A bottom footprint therefore holds mirrored pad coordinates, as a bottom footprint read from a KiCad board does.
- `Pad.number` is the pad name. `Pad.kind` MUST be `thru_hole` for a hole above 0 that is plated, `np_thru_hole` for one that is not, and `smd` otherwise. `Pad.drill` is the hole size, `None` without a hole. `Pad.shape` MUST be `circle` for shape 1 with equal sizes, `oval` for shape 1 with unequal sizes, `rect` for 2, `roundrect` for shape 1 with alternate shape 9 (the percentage in the pair `corner_percent`), and `custom` for 3 (octagonal) and any other value, with the value in the bag.
- `Pad.layers` MUST be real layers: every copper layer of the chain for a pad on Multi-Layer, else the one copper layer of the pad. Mask and paste layers are not listed; an expansion and its mode go to `paste` and `mask` as `<mode>,<expansion in units>` when the mode is not 1 (the expansion follows a rule), so a pad with rule expansions has no such pair.
- `Pad.net_id` MUST be the net of the pad's net index, `None` without one.
- `attributes` MUST be `("through_hole",)` when a pad has a hole, `("smd",)` when the footprint has pads and none has a hole, and `()` without pads.
- Tracks, arcs, texts, fills and regions that carry a component index MUST NOT become board objects: they are counted as `footprint-graphics` in `altium.import.unmapped`. A pad without a component index MUST become a footprint of its own with `attributes == ("board_only",)`, the reference `""` and `lib_ref == ""`.
- A component index that names no record is reported by the reader; the adapter MUST treat such a primitive as free.

#### Scenario: Placements of the blink sample
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`, written from `examples/blink_2layer/design.py`
- **WHEN** it is imported and compared with the board that the KiCad build of the same script writes, read by `KicadBackend`
- **THEN** the three footprints have that board's `side` and `rotation`, and the footprint names of the script; their positions differ from that board's by one common translation within 2 nm per axis; and each pad's `number`, `shape`, `kind`, `net` name and footprint-local `position` equals that board's within 2 nm

#### Scenario: Bottom footprint keeps mirrored pads
- **WHEN** `Transform.placement(D1.position, D1.rotation).apply(pad.position)` is computed for the two pads of `D1`, which is on the bottom side
- **THEN** each result equals the pad's absolute position in the document, converted by "Units and frame", within 1 nm

#### Scenario: Free pad
- **GIVEN** a document with one pad whose component index is `0xFFFF`
- **WHEN** it is imported
- **THEN** the board holds a footprint with `attributes == ("board_only",)` and that one pad at local position (0, 0)

### Requirement: Padstacks of imported pads
A pad whose geometry differs per layer, whose hole is not round or whose copper is offset from its hole SHALL get a `Padstack` in the form of "Padstack holes and offsets" of `design-model`.
- `stack_mode` 0 (simple) with a round hole and zero offsets MUST give `padstack is None`.
- Mode 1 (top, middle, bottom) MUST give one `PadstackLayer` per copper layer of the pad: the top values on `F.Cu`, the bottom values on `B.Cu`, the middle values on every inner layer. Mode 2 (full stack) MUST give the top and bottom values and, for the j-th inner layer, the inner size and shape of the Altium mid layer that the chain names there; an inner layer that is a plane takes the middle values.
- `Pad.shape` and `Pad.size` MUST be those of the top layer, or of the pad's own layer for a surface pad.
- `hole_shape` MUST be `round`, `square` or `slot` from the record's 0, 1 and 2; `hole_length` the slot length for a slot, else `None`; `hole_rotation` the slot rotation of the record added to the pad's angle relative to the footprint (the record's angle is read as relative to the pad, `INFERRED`).
- `PadstackLayer.offset` MUST be the layer's hole offset, rotated into the footprint frame, `Point(0, 0)` when the sixth subrecord is empty.
- In a library definition the inner layers of mode 1 are the one entry `In*.Cu`, and those of mode 2 the entries `In<n>.Cu` for mid layer n.
- A `stack_mode` or a hole shape outside these values MUST give `altium.import.padstack-unknown` (warning), `padstack is None`, and the value in the pair `stack_mode`.

#### Scenario: Simple pad has no padstack
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** it is imported
- **THEN** every pad has `padstack is None`

#### Scenario: Top, middle and bottom sizes
- **GIVEN** a through-hole pad of mode 1 with the sizes 60 × 60, 50 × 50 and 70 × 70 mil on a four-layer board
- **WHEN** the board is imported
- **THEN** the pad has `size` 1 524 000 × 1 524 000 nm and a padstack of four layers whose sizes are 60, 50, 50 and 70 mil on `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`

#### Scenario: Slot
- **GIVEN** a pad with hole shape 2, hole size 40 mil, slot length 100 mil and slot rotation 90 degrees on a footprint at 0 degrees (whole units: 1 mm is no whole number of units)
- **WHEN** it is imported
- **THEN** `pad.drill == 1_016_000`, and the padstack has `hole_shape == "slot"`, `hole_length == 2_540_000`, `hole_rotation == 90_000_000` and no layer entry

### Requirement: Tracks, arcs and vias
`import_board` SHALL map free copper primitives to `Track`, `Arc` and `Via`.
- A track or an arc on a copper layer of the chain that is no internal plane, without a component index and without a polygon index, MUST become a `Track` (`start`, `end`, `width`, `layer`, `net_id`) or an `Arc` (`start`, `mid`, `end`, `width`, `layer`, `net_id`). A full circle (0 to 360 degrees) on copper has no `Arc` form and MUST become a `Graphic` of kind `circle` with the pair `net`.
- A track or an arc on the layer of an internal plane, without a component index and without a polygon index, MUST NOT become a `Track`, an `Arc` or a `Graphic`, with or without a net ("Objects on an internal plane"). No view of the imported board has to take such an item out again.
- A track or an arc with a polygon index is poured copper of a zone ("Zones from polygons") and MUST NOT become a board track.
- A via MUST become `Via(position, diameter, drill, layers, net_id, via_type)`. `layers` MUST be the two neutral copper names of its start and end layers. `via_type` MUST be `through` when they are the outer layers, `blind` when exactly one is, and `buried` otherwise; `micro` is never inferred. A start or end layer outside the chain MUST give `altium.import.via-span` (warning), the outer layers and the pair `via_layers`.
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

### Requirement: Zones from polygons
`import_board` SHALL map each record of `Polygons6` whose `polygon_type` is `Polygon` and whose layer is a copper layer of the chain to one `Zone`.
- `outline` MUST be the vertices in order, converted, without the repeated last vertex. A record with an arc vertex MUST give `outline == ()`, which the model defines as "kept by the backend", and one `altium.import.zone-arc` info per import with the count.
- `layers` is the one layer; `net_id` the net of the record's net index; `name` the record's name.
- `priority` MUST be `max(pour_index) − pour_index` over the mapped zones, so the zone poured first has the highest priority, the inverse of what c0038 writes. The original goes to `pour_index`.
- `fills` MUST hold one `ZoneFill(layer, polygon)` per region of `PcbDocument.regions_of(index)` on a copper layer, in stream order. Tracks and arcs of a hatched pour are counted as `pour-primitives`, not mapped.
- `polygon` MUST be `keyhole_ring(outline, holes).ring` ("Keyhole ring of a polygon with holes" of `geometry-kernel`), `outline` and each hole being the region's vertices rounded by "Units and frame", without a repeated last vertex and without repeated neighbours. The copper of a fill is therefore the region's outline without its holes: a point inside a hole is outside the polygon under the non-zero and the even-odd rule, and a region without a hole gives its outline unchanged.
- A hole that the ring does not hold is not in the model and MUST be counted as `region-holes`: one with fewer than three distinct points or without area, and one that lies outside its outline. The holes outside their outline MUST also give one `altium.import.zone-hole-outside` warning per import, located at `Regions6/Data`, whose message holds the count of such holes and the count of regions that hold them.
- A polygon of another type (a split plane, a cutout), or on a layer outside the chain, is unmapped.

#### Scenario: Unpoured zones of the routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/`, whose two zones are written without poured copper
- **WHEN** it is imported
- **THEN** the board holds the zones with the model's nets, layers and outlines within 2 nm, each on one layer, with `fills == ()`, and the zone that the model gives the highest priority has the highest priority

#### Scenario: Outline with an arc
- **GIVEN** a polygon whose second vertex has `KIND1=1`
- **WHEN** it is imported
- **THEN** the zone has `outline == ()`, its net and layer are set, and `altium.import.zone-arc` reports one zone

#### Scenario: Pour with a hole and an island
- **GIVEN** a document with one polygon on layer 1 and two regions of it: a square with one square hole, and a smaller square that lies inside that hole
- **WHEN** it is imported
- **THEN** the zone has two fills, the first polygon holds the four points of the outline followed by the anchor, the hole and the anchor again, a point inside the hole and outside the island is `OUTSIDE` of the first polygon, the copper check's touch test finds the two fills apart, the copper check reports no short with a track of another net that lies in the hole, the net of the polygon has two pieces of copper, and no `region-holes` is counted

#### Scenario: Hole outside its outline
- **GIVEN** a polygon with three regions: one with a hole that lies wholly outside its outline, one with such a hole and a hole inside its outline, and one with a hole of three equal points
- **WHEN** it is imported
- **THEN** the first and the third fill are their region's outline, the second holds its inner hole, one `altium.import.zone-hole-outside` warning located at `Regions6/Data` reports 2 holes of 2 regions, and `region-holes` counts 3

### Requirement: Outline, graphics and texts
`import_board` SHALL map the board outline and the free primitives that are not copper connections.
- **Outline.** `Board.outline` MUST be `None`, as for every imported board. Each segment of `BoardRecord.outline` MUST become one `Graphic` on `Edge.Cuts` with width 0: kind `line` for a line vertex, kind `arc` (three points) for an arc vertex. A segment of zero length is dropped.
- A free track on a layer that is not copper MUST become a `Graphic` of kind `line`; a free arc one of kind `arc`, or `circle` for a full turn (centre and one point on the circle); a free fill one of kind `rect` when its rotation is a multiple of 90 degrees and of kind `polygon` (four corners) otherwise, `filled`; a free region one of kind `polygon`, `filled`.
- A free fill or region on a copper layer that is no internal plane MUST also become such a `Graphic`, with its net name in the pair `net`, and MUST be counted by one `altium.import.copper-shape` info per import. The model has no copper shape with a net.
- A free text on a layer that is no internal plane MUST become `Text(text, position, layer, size, thickness, rotation)`, `size` being the height on both axes. The text comes from the wide string when the record names one.
- A free fill, region or text on the layer of an internal plane MUST give no entity and MUST NOT be counted by `altium.import.copper-shape` ("Objects on an internal plane").
- Primitives on `Altium.KeepOut` are graphics; no `Keepout` is synthesised.

#### Scenario: Outline of the blink sample
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is imported
- **THEN** `board.outline is None`, `Edge.Cuts` holds four `line` graphics that form a closed rectangle of the board's size, and `design.validate()` reports no error

#### Scenario: Copper region with a net
- **GIVEN** a document with one free region on layer 1 on the net `GND`
- **WHEN** it is imported
- **THEN** the board holds one filled `polygon` graphic on `F.Cu` whose bag holds `("net", "GND")`, no zone, and `altium.import.copper-shape` reports one shape

### Requirement: Component body records
`fenolite.backends.altium.read.bodies` SHALL decode the component-body storages that c0041 keeps as bytes (the `Data` streams of `ComponentBodies6` and `ShapeBasedComponentBodies6` in `PcbDocument.storages`, and the `raw` of the type 12 `RawPrimitive` values of a library footprint; c0041 types no body field), and the adapter SHALL map each component-associated body to a `ComponentBody` ("Component bodies" of `design-model`).
- `read_bodies(data: bytes, *, shape_based: bool = False, storage: str = "", issues=None) -> tuple[BodyRecord, ...]` MUST read the `Data` stream of `ComponentBodies6` or `ShapeBasedComponentBodies6`, and the body primitives (type 12) of a library footprint. `BodyRecord` MUST be a frozen dataclass with `index`, `raw`, `layer`, `component` (`None` for `0xFFFF`), `properties` (the record's property text as the reader's `PropertyRecord`), `outline` (as a region's) and typed views of the keys that `docs/formats/altium/pcb-bodies.md` lists: the standoff height, the overall height, the body projection, the identifier, the model name, the model id and the embed flag.
- `encode(records) == data` MUST hold: the decoder keeps every byte. A record it cannot frame MUST be returned raw with one `altium.pcb-read.short-record` warning, as c0041's primitives are.
- The module MUST obey the import rules of c0041's reader modules. A key MUST be typed only when its row of the fact page has a source; the page MUST say which rows are `INFERRED` (`H-A-IMP-BODY`).
- The adapter MUST give each body with a component index to that component's `FootprintInstance.bodies`, in stream order, and each body of a library footprint to `FootprintDef.bodies`. `kind` MUST be `model` when the record names a model and `extruded` otherwise; `outline` the converted vertices in the footprint frame, without the repeated last vertex; `height` the overall height; `standoff` the standoff height; `layer` the neutral name of the body's layer; `model` the model name; `name` the identifier. The adapter MUST derive authoritative signed z bounds and mounted-face orientation only from publicly evidenced body/projection semantics. Original native properties/raw bytes and model references MUST remain available independently of the projection. An unknown transform or model extent MUST retain those records and report unknown geometry with locators; it MUST NOT emit an invalid legacy body, discard native content or silently clamp its height.
- A body without a component index, and model data of the `Models` storage, are unmapped.

#### Scenario: Bytes kept
- **WHEN** `uv run pytest tests/corpus/test_altium_import.py -k bodies_identity` decodes the body storages of every fetched PCB document and library and encodes them again
- **THEN** each stream is rebuilt byte for byte, and the test reports the number of bodies per file

#### Scenario: Extruded body of a footprint
- **GIVEN** an authored body record with four vertices, an overall height of 40 mil and a standoff of 0, with component index 0
- **WHEN** the document is imported
- **THEN** footprint 0 holds one `ComponentBody` with `kind == "extruded"`, `height == 1_016_000`, `standoff == 0` and four outline points in the footprint frame

#### Scenario: Unproved signed projection
- **GIVEN** an authored body record has a projection whose signed-height meaning is not registered
- **WHEN** the adapter imports it
- **THEN** raw native content and resources remain preserved and its neutral volume is explicitly unknown rather than dropped or clamped

### Requirement: Circuit synthesised from a board
`import_board` SHALL synthesise the circuit of a PCB document read without its schematic, as "Components synthesised from a board" of `design-model` requires.
- One `Component` per footprint instance: `ref` from the footprint's designator text, else from `source_designator`, else `""` (amended by change c0045: the components of a repeated sheet share their source designator, and the board shows the reference that tells them apart); `value` from its comment text; `lib_footprint_ref` the instance's `lib_ref`; `lib_symbol_ref` `<stem of source_component_library>:<source_lib_reference>` when both exist; `path` equal to `ref`.
- One `Pin` per distinct non-empty pad name, in pad order, with `name == ""` and `etype == "unspecified"`: a PCB document states no pin type.
- Net members MUST be `PinRef(component id, pad name)` for every named pad on the net, without duplicates.
- `Design.rules` MUST be the rule set of "Rules where they map", and `Design.header.name` the file stem.

#### Scenario: Board-only import of the blink sample
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** `AltiumBackend().read` reads it
- **THEN** `design.by_ref` holds `U1`, `R1` and `D1`, each with one pin per pad name and `etype == "unspecified"`, and the set of `(ref, pin)` pairs of each net equals that of the model the build wrote the document from

### Requirement: Schematic components and pins
`import_circuit` SHALL create one `Component` per distinct component of the sheets, from the `Component` records and their children.
- Component records of one sheet instance with one designator text are the parts of one component. The component's `ref` is that text; `value` the text of its parameter `Comment`, a text that starts with `=` being replaced once by the parameter it names; `properties` every other parameter of its first part, name to text, the first of a repeated name winning.
- `lib_symbol_ref` MUST be `<stem of source_library>:<lib_reference>`, or the lib reference alone; `lib_footprint_ref` `<stem of the first data file>:<model_name>` of the `Implementation` whose `is_current` is true and whose `model_type` is `PCBLIB`, or the model name alone, or `""`.
- `pins` MUST hold one `Pin` per distinct pin designator over all parts and Part Zero, in the first display mode that holds it: `number` the designator, `name` the pin name, `etype` from the closed table `adapter.PIN_TYPES` (0 `input`, 1 `bidirectional`, 2 `output`, 3 `open_collector`, 4 `passive`, 5 `tri_state`, 6 `open_emitter`, 7 `power_in`); a value outside the table gives `unspecified` and the pair `electrical`.
- `path` MUST be `<module path>/<ref>`, or `ref` on the top sheet.
- A component without a designator record MUST get `ref == ""` and `altium.import.no-designator` (warning). Two components of one sheet instance are never merged for any other reason.
- Only the pins of `SchDocument.shown_children(component)` of each placed part take part in "Connectivity within a sheet"; a pin of a part that is not placed belongs to the component and to no net.

#### Scenario: Components of the KiCad example
- **GIVEN** `tests/data/altium/kicad_example/altium_kicad.SchDoc`, written from `examples/altium_kicad/design.py`, whose `U1` has two parts
- **WHEN** it is imported
- **THEN** the circuit holds one component per reference of the script, `U1` once with the pins of both parts, and every component has the script's value and footprint name

#### Scenario: Unknown electrical type
- **GIVEN** a pin record with `ELECTRICAL=9`
- **WHEN** the sheet is imported
- **THEN** the pin has `etype == "unspecified"`, and its bag holds `("electrical", "9")`

### Requirement: Connectivity within a sheet
`adapter.connectivity` SHALL find the local nets of one sheet from its geometry, in exact integer arithmetic on `SchLength.value`, by the rules of `docs/formats/altium/connectivity.md`.
- **Electrical points.** A pin has one: `Pin.hot_end`. A net label, a power port, a junction and a No ERC directive have one: their location. A port has two: its location and the point `width` further along it. A sheet entry has one, on its symbol's edge at its distance. A harness entry has one, on its connector's edge.
- **Wires.** Two wires connect when an end point of one lies on a segment of the other, ends included; so a T joint connects. Two segments that cross at a point interior to both connect only when a junction lies on that point. Collinear segments that overlap connect.
- **Points on wires.** An electrical point connects to a wire when it lies on one of its segments, ends included. Two electrical points at the same position connect.
- "Lies on" MUST be decided by an exact test: a zero cross product and a position within the segment's box. No tolerance is used.
- A bus, a bus entry and a signal harness line are not wires: they join no net here ("Buses", "Harnesses"). A port or a sheet entry that carries a bus (a text of the bus form) or a harness (a harness type, or a point on a signal harness line or on a harness connector) is no net identifier.
- **Names in a sheet.** Net labels with one text, compared without letter case, join their nets within the sheet. So do power ports with one text. A net label and a power port with one text do not join by name (`H-A-IMP-DUP-NAME`).
- **Hidden pins.** No fact page states a key that holds a hidden pin's net (`H-A-IMP-HIDDEN-PIN`: neither S-0130 nor S-0131 is recorded with one, and S-0185 says that Altium no longer supports it), so no key is read: a hidden pin takes part by its position like any pin.
- **No ERC.** A pin whose electrical point holds a No ERC directive and whose local net holds no other pin, label, port or power port MUST be listed in `Circuit.no_connects` and MUST be in no net.
- The result per sheet is a tuple of local nets, each with its pins, its identifiers by kind and its locators, in a stable order: by the smallest locator of its members.

#### Scenario: Nets of the KiCad example
- **GIVEN** `tests/data/altium/kicad_example/altium_kicad.SchDoc`
- **WHEN** `adapter.netlist` runs on it
- **THEN** the nets, as sets of `(ref, pin)` pairs by name, equal `tests/_altium.py::EXAMPLE_NETS`

#### Scenario: Crossing without a junction
- **GIVEN** a sheet with a horizontal wire and a vertical wire that cross at an interior point of both, each ending on one pin at each end
- **WHEN** the local nets are found
- **THEN** there are two nets of two pins; with a junction record on the crossing there is one net of four pins

#### Scenario: T joint
- **GIVEN** a wire from (10, 10) to (30, 10) and a wire from (20, 10) to (20, 30), in units
- **WHEN** the local nets are found
- **THEN** the two wires are one net, without any junction record

#### Scenario: Pin end inside a segment
- **GIVEN** a pin whose hot end lies at (20, 10) on the wire from (10, 10) to (30, 10)
- **WHEN** the local nets are found
- **THEN** the pin is on the wire's net (`H-A-IMP-PIN-MID`)

#### Scenario: Marked pins of the no-connect sample
- **GIVEN** `tests/data/altium/no_connect/altium_no_connect.SchDoc`
- **WHEN** it is imported
- **THEN** `Circuit.no_connects` holds the pins that `examples/altium_kicad/no_connect.py` marks, none of them is a member of a net, and the other nets equal `tests/_altium.py::NO_CONNECT_NETS`

### Requirement: Net identifier scope
`adapter.netlist` SHALL join local nets across sheets by the scope of `NetOptions.scope`, one of `automatic`, `flat`, `hierarchical`, `strict_hierarchical` and `global` (S-0185).
- `automatic` MUST choose `hierarchical` when the top sheet holds a sheet entry, else `flat` when any sheet holds a port, else `global`. The top sheets are the sheets that no sheet symbol names. The chosen scope MUST be reported by `altium.import.scope` (info).
- **Power ports** join by text across every sheet, except in `strict_hierarchical`, where they join within a sheet only. In `hierarchical` and `strict_hierarchical`, a power port whose local net also holds a port stays local to its sheet (`H-A-IMP-POWER-LOCAL`).
- **Net labels** join across sheets only in `global`.
- **Ports.** In `flat` and `global`, ports with one name join across every sheet. In the hierarchical scopes a port joins only the sheet entry of the same name on each sheet symbol whose file name names the port's sheet.
- **Off-sheet connectors** (a power port record flagged as a cross-sheet connector) with one text join across the sheets that share a parent, in every scope (`H-A-IMP-OFFSHEET`).
- Identifiers of different kinds never join by name. Names are compared without letter case.
- A sheet symbol's file name MUST be matched to a sheet by file name without folder and without letter case; a name with `;` lists several sheets. A sheet that is not among the inputs MUST give `altium.import.sheet-missing` (warning), and its entries stay named points.
- A sheet named by more than one sheet symbol MUST be instantiated once per symbol, each instance with its own unique-id path, and MUST give `altium.import.repeated-sheet` (warning): designators of repeated sheets are not annotated by this change. A designator with a `Repeat(` statement gives the same warning and one instance.
- A sheet symbol that names one of its own ancestors MUST give `altium.import.sheet-loop` (error) and no descent.
- `NetOptions` MUST be built from the project's `[Design]` options by `NetOptions.from_project(project)`; a hierarchy mode whose meaning c0042 marks unknown MUST give `altium.import.scope-unknown` (warning) and `automatic`.

#### Scenario: Hierarchical sample
- **GIVEN** the project of `tests/data/altium/hier/` of c0037 (a top sheet, two module sheets, one harness)
- **WHEN** it is imported with `NetOptions()`
- **THEN** `altium.import.scope` names `hierarchical`, and the nets, as sets of `(ref, pin)` pairs by name, equal those of the model the build wrote the project from

#### Scenario: Ports do not join sideways
- **GIVEN** two module sheets that each hold a port `EN` wired to one pin, and a top sheet whose two sheet symbols have an entry `EN` each, not wired together
- **WHEN** the netlist is built in the hierarchical scope
- **THEN** the two pins are on different nets; in the flat scope they are on one net

#### Scenario: Automatic scope without sheet entries
- **GIVEN** two sheets without sheet symbols, each with a port `CLK`
- **WHEN** the netlist is built with `scope="automatic"`
- **THEN** the scope is `flat` and the two ports join

#### Scenario: Missing sheet
- **GIVEN** a top sheet whose sheet symbol names `Power.SchDoc`, which is not among the inputs
- **WHEN** the netlist is built
- **THEN** `altium.import.sheet-missing` names `Power.SchDoc`, and the wires on the symbol's entries form nets of their own

### Requirement: Net names
`adapter.netlist` SHALL give every net one name and SHALL keep its other names.
- The candidates of a net are the texts of its identifiers. The name MUST be chosen by kind, in this order: net labels, power ports, ports, sheet entries; with `NetOptions.power_port_names_first`, power ports come first. Ports name a net only with `allow_port_names`, sheet entries only with `allow_sheet_entry_names`. Off-sheet connectors rank as ports.
- Among candidates of the winning kind, a candidate of a sheet nearer to the top wins with `higher_level_names_first`, and of a sheet farther from it otherwise; then the smallest text, compared without letter case and then by code point (`H-A-IMP-NAME-TIE`). The name keeps the letter case of the chosen identifier.
- A net without a candidate MUST be named `Net<ref>_<pin>` from its first pin, the pins ordered by reference in natural order and then by designator in natural order (`H-A-IMP-NAME-AUTO`). A net without a candidate that holds fewer than two pins is no net and is dropped: an unconnected pin is in no net, as the models that Fenolite builds hold it and as a PCB document gives its pad no net.
- Every other candidate MUST be kept as a pair `alias`, in sorted order.
- Two nets that end with one name MUST stay two nets: the second and later ones, in the order of their smallest member, are renamed `<name>#<k>` from `k = 2`, and each gives `altium.import.duplicate-net-name` (warning).
- A net of one pin with a candidate is kept, as the model reports it (`model.single-pin-net`). `append_sheet_numbers` is not applied; when the project sets it, `altium.import.option-ignored` (info) names it.
- `Netlist.nets` MUST be sorted by name; each `NetGroup` holds `name`, `aliases`, `pins` (`PinKey(component native id, designator)`, sorted) and `locators`.

#### Scenario: Label beats power port
- **GIVEN** a net with the net label `VBUS` and the power port `5V`
- **WHEN** it is named with the default options and with `power_port_names_first=True`
- **THEN** the names are `VBUS` and `5V`, and the other text is the net's `alias` in each case

#### Scenario: System name
- **GIVEN** a net of the pins `R10-2`, `R2-1` and `U1-3` without an identifier
- **WHEN** it is named
- **THEN** its name is `NetR2_1`

#### Scenario: Same name on two nets
- **GIVEN** a sheet with a net label `GND` on one net and a power port `GND` on another net that no wire joins
- **WHEN** the netlist is built
- **THEN** it holds the nets `GND` and `GND#2`, and one `altium.import.duplicate-net-name` warning names `GND`

### Requirement: Buses
`adapter.netlist` SHALL resolve buses and SHALL record each as a `Bus` ("Buses in the circuit model" of `design-model`).
- A bus identifier is a net label, a port or a sheet entry whose text has the form `<name>[<a>..<b>]`, `a` and `b` decimal integers. Its members are `<name><i>` for `i` from `a` to `b`, rising or falling, in that order.
- A bus group is a set of bus lines connected as wires are ("Connectivity within a sheet", applied to `Bus.points`), with the bus identifiers whose electrical point lies on them and the bus ports and sheet entries they touch.
- A bus line joins no net by itself, and a bus entry is graphics: within a sheet, the member nets are the nets that net labels `<name><i>` name.
- Across sheets, a bus port and the sheet entry of the same text join their members by position: member `k` of one with member `k` of the other. Within a group, identifiers with different names join their members by position likewise. Identifiers of different widths MUST give `altium.import.bus-width` (warning) and join the common prefix.
- One `Bus` MUST be created per bus group after the joins across sheets: `name` the name of its identifier chosen as a net's name is; `members` one `BusMember(index, net_id)` per member that has a net, in identifier order; the pair `label` the identifier's text. A member without a net is left out and counted by `altium.import.bus-member` (info).
- A text with `[` that does not have the form MUST be an ordinary identifier.

#### Scenario: Bus through a port
- **GIVEN** a module sheet with the net labels `D0` to `D3` on four pins of `U1` and a port `D[0..3]` on a bus, and a top sheet whose sheet entry `D[0..3]` is on a bus labelled `DATA[3..0]`, with the labels `DATA0` to `DATA3` on four pins of `U2`
- **WHEN** the netlist is built in the hierarchical scope
- **THEN** `U1`'s `D0` pin and `U2`'s `DATA3` pin are on one net, and the circuit holds one bus of four members

#### Scenario: Bus line is no wire
- **GIVEN** two wires that end on the same bus line, each through a bus entry, with the labels `A0` and `A1`
- **WHEN** the local nets are found
- **THEN** the two wires are on different nets

### Requirement: Harnesses
`adapter.netlist` SHALL resolve signal harnesses and SHALL record each as an `Interface` of kind `harness`, the form c0037 gives a harness.
- A harness group is a set of signal harness lines connected as wires are, with the harness connectors whose connection point lies on them or on a port, and the ports and sheet entries with a `harness_type` that they touch. Across sheets, a harness port joins the sheet entry of the same name, as a port does.
- A port or a sheet entry belongs to a group by touching it, whether or not its record holds a harness type: saved sheets hold sheet entries on harness lines without one.
- Within a group, the harness entries with one name, compared without letter case, are one member: the nets on their electrical points are joined.
- A net label `<harness>.<entry>` on a wire names the member `<entry>` of the harness that goes by `<harness>` on that sheet (the net label on its line, or the name of its port or sheet entry): its net joins that member. Saved sheets use this form in place of a harness connector (S-0188).
- A member's net is named as any net. Without a candidate, and with at least one pin, it MUST be named `<harness>.<entry>`, the harness being the name of the group's port or sheet entry chosen as a net's name is, else its type (`H-A-IMP-HARN-NAME`).
- One `Interface(kind="harness", name=<type>, members={<entry name>: <net id>})` MUST be created per group, the type being the text of the connector's `HarnessType`, else the `harness_type` of its port or sheet entry. An entry whose net holds no pin is left out and counted by `altium.import.harness-entry` (info).
- A harness entry that carries a harness of its own, and `.Harness` definition files, are not resolved: `altium.import.harness-nested` (warning) names the entry.

#### Scenario: Harness of the hierarchical sample
- **GIVEN** the project of `tests/data/altium/hier/` of c0037, whose harness `SPI` crosses two module sheets
- **WHEN** it is imported
- **THEN** the circuit holds one `Interface` named `SPI` of kind `harness` whose members are the model's entries with the ids of the model's net names, and each `SPI_*` net has one pin on each module sheet

#### Scenario: Unwired entry
- **GIVEN** a harness connector with the entries `MOSI` and `HOLD`, where no wire touches `HOLD`
- **WHEN** the netlist is built
- **THEN** the interface has the member `MOSI` only, and `altium.import.harness-entry` counts one entry

### Requirement: Hierarchy as modules
`import_circuit` SHALL record the sheet hierarchy as `Module`s.
- One `Module` per sheet-symbol instance: `path` the designators of the sheet symbols from the top (`SheetName.text`), joined by `/`; `parent` the id of the module above it, `None` under the top sheet; `component_ids` the components of that sheet instance, in reference order.
- Components of a top sheet belong to no module. A design of one sheet has no module.
- A sheet symbol without a `SheetName` MUST take the stem of its file name as its designator.
- Two sheet symbols of one sheet with one designator MUST give `altium.import.duplicate-sheet-name` (warning), and the second path gets the suffix `#2`.

#### Scenario: Modules of the hierarchical sample
- **GIVEN** the project of `tests/data/altium/hier/` of c0037
- **WHEN** it is imported
- **THEN** the circuit holds two modules whose paths are the designators of the two sheet symbols, each with the components of its sheet, and each of those components has `path == "<module path>/<ref>"`

### Requirement: Project import
`import_project` SHALL merge the sheets and the PCB document of one project into one `Design`.
- The circuit MUST be that of `import_circuit` over the project's schematic sheets with `NetOptions.from_project`. The board, its nets and its rules MUST be those of `import_board` of the first PCB document in document order; a further PCB document gives `altium.import.extra-board` (info) and is not read. A project without a PCB document gives `board is None`; one without a sheet gives the design of `import_board`.
- **Component link.** A footprint's `component_id` MUST be the schematic component whose unique-id path, over any of its parts, equals the PCB component's `source_unique_id`. Failing that, the one component whose `ref` equals `source_designator`, with `altium.import.linked-by-designator` (info, one per import with the count). Failing that, the synthesised component is added to the circuit with `altium.import.pcb-only-component` (warning).
- A linked component of a repeated sheet MUST take its `ref` from the PCB component's `source_designator`.
- **Nets.** A PCB net MUST be the schematic net of the same name, compared exactly and then without letter case. A PCB net without one is added to the circuit with the members of its pads and `altium.import.pcb-only-net` (info, one per import with the count). Pad nets are never changed to agree with the schematic: comparing the two is change c0044's.
- Net classes of the board are attached to the merged nets by name.
- `Design.header.name` MUST be the project file's stem.
- The inputs are records: `ProjectInput(name, options, sheets, board, rules)` with `sheets: tuple[SheetInput, ...]` (`SheetInput(file, sha256, document)`), `board` a `BoardInput(file, sha256, document)` or `None`.

#### Scenario: Blink project
- **GIVEN** the five files of `tests/data/altium/blink/`
- **WHEN** `AltiumBackend().read(blink.PrjPcb)` runs
- **THEN** the design holds the three components once each, every footprint's `component_id` is a schematic component, no `altium.import.linked-by-designator` and no `altium.import.pcb-only-component` is given, every pad's net is a schematic net, and `design.validate()` reports no error

#### Scenario: Link by designator
- **GIVEN** the same project with every `SOURCEUNIQUEID` of the PCB document emptied
- **WHEN** it is imported
- **THEN** the footprints are linked to the same components, and `altium.import.linked-by-designator` reports three

#### Scenario: Component only on the board
- **GIVEN** a PCB document with a component `MH1` that the sheets do not hold
- **WHEN** the project is imported
- **THEN** the circuit holds a component `MH1` with one pin per pad name, and `altium.import.pcb-only-component` names `MH1`

### Requirement: Rules where they map
`import_board` and `import_project` SHALL fill `Design.rules` from the rule records through the mapper of c0042, `read.rules.map_rules`, and SHALL never approximate a rule.
- `adapter.rules.import_rules(records, ids, *, file, sha256, issues)` MUST call `map_rules(records, origin=<file name>)` with `records == [r.fields for r in doc.rules]`: `RuleRecord.fields` of c0041 is the record's whole pair list, which is the mapper's input. It MUST take from the returned `RuleMapping` the neutral rules and the unmapped list, and MUST NOT hold a rule table of its own. The kinds that map are those of c0042: Clearance, Width, Routing Via Style and Hole Size.
- The adapter MUST keep each mapped rule's kind, name, limits, selectors, `priority` and `severity` as the mapper gives them, and MUST replace its header: the id and native id of "Identifiers and provenance" (also for the rule set), the provenance, and a bag with the pairs `rule_kind`, `scope1` and `scope2` in place of the mapper's.
- A layer name in a mapped rule MUST be the neutral name of "Layers and stack-up".
- `priority` MUST be the record's, 1 the highest, as the model defines it. A disabled rule MUST NOT be mapped: the mapper lists it as unmapped with the reason `disabled`, because a rule of severity `ignore` would silence the rule that applies in its place.
- Each unmapped rule MUST be counted by one `altium.import.rule-unmapped` info per rule kind, with the count and the mapper's reasons. The mapper's per-rule infos `altium.rule.unmapped` MUST NOT be forwarded; its other issues are.
- Rules of a rule file of the project are imported only when the caller passes them in `ProjectInput.rules`, as `RulesInput(file, sha256, records)`; the backend passes none.

#### Scenario: Rules of the routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/` of c0038, whose `Rules6` holds a clearance, a width and a via rule for the class `PWR` and for all objects
- **WHEN** it is imported
- **THEN** `design.rules` holds a `clearance` rule whose `selector_a` is `netclass PWR` with priority 1, a `track_width` rule with `min`, `opt` and `max`, a `via_diameter` and a `via_drill` rule, and no `altium.import.rule-unmapped`

#### Scenario: Disabled rule
- **GIVEN** a document whose `Rules6` holds a `Width` rule with `ENABLED=FALSE` and no other rule
- **WHEN** it is imported
- **THEN** `design.rules` holds no rule, and one `altium.import.rule-unmapped` counts one `Width` rule with the reason `disabled`

#### Scenario: Scope outside the grammar
- **GIVEN** a rule record whose first scope is `InPolygon`
- **WHEN** it is imported
- **THEN** `design.rules` does not hold it, and `altium.import.rule-unmapped` counts one rule of its kind with the mapper's reason

### Requirement: Footprint libraries
`import_footprints` SHALL map a `PcbLibrary` to a `Library` of `FootprintDef`s.
- One definition per `LibFootprint`, in library order: `name`, `library` (the `name` argument, by default the file stem), `description`, `pads`, `graphics`, `bodies`, and `kind` `through_hole` when a pad has a hole, `smd` when it has pads without holes, `unspecified` without pads.
- Pads follow "Footprint instances and pads" and "Padstacks of imported pads" with the footprint at the origin and angle 0, and `net_id is None`. A pad on Multi-Layer has `layers == ("*.Cu",)`; a surface pad its copper layer.
- Tracks, arcs, fills and regions become `Graphic`s as "Outline, graphics and texts" states, on the neutral layers of `adapter.LAYERS` with the library's own two-layer chain. Texts are counted as unmapped.
- `properties` MUST hold `Description` when the description is not empty and `Height` (the parameter's text) when the footprint states one.
- Ids follow "Identifiers of library definitions" of `design-model`.

#### Scenario: Library of the blink sample
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** `AltiumBackend().read` reads it
- **THEN** the result is a `Library` named `blink` whose footprints have the names the build wrote, each pad with the source definition's number, shape, kind, drill and position within 2 nm, and ids that are unique within the library

### Requirement: Symbol libraries
`import_symbols` SHALL map a `SchLibrary` to a `Library` of `SymbolDef`s.
- One definition per `SchLibComponent`: `name`, `library`, `units` one `SymbolUnit(unit, body_style)` per part and display mode, `pins`, and `properties` with `Reference` (the designator's text), `Value` (the comment), `Description`, `Footprint` (the current footprint model's name) and every other parameter.
- A `SymbolPin` MUST hold `number`, `name`, `etype` from `adapter.PIN_TYPES`, `position` (the pin's electrical end), `rotation` (the direction from the electrical end towards the body, as a KiCad pin's angle is defined), `length`, `unit` (the owner part; 0 for Part Zero), `body_style` (the display mode plus 1) and `hidden`.
- `shape` MUST be `inverted` for a dot on the outer edge, `clock` for a clock on the inner edge, `inverted_clock` for both, and `line` otherwise; other pin symbols go to the pin's entry of the definition's bag.
- `power` MUST be `""`; Altium power ports are sheet objects, not library symbols.
- Body graphics are not in `SymbolDef` and are counted as unmapped.

#### Scenario: Library of the KiCad example
- **GIVEN** `tests/data/altium/kicad_example/altium_kicad.SchLib`, written from `examples/altium_kicad/FenoliteDemo.kicad_sym`
- **WHEN** it is imported and compared with the KiCad symbols read by `KicadBackend`
- **THEN** each symbol has the source's pins by `(unit, number)` with equal `name`, `etype`, `position`, `rotation` and `length`, for every pin type and shape that the writer of c0034 writes without `altium.pin-lossy`

### Requirement: Altium backend
`fenolite.backends.altium.backend.AltiumBackend` SHALL satisfy the `Backend` protocol with `name == "altium"`, and SHALL be a built-in of the registry ("Backend registry" of `backend-protocol`).
- `detect(path)` MUST return `True` exactly for the suffixes `.PrjPcb`, `.SchDoc`, `.SchLib`, `.PcbDoc` and `.PcbLib`, compared without letter case, and MUST NOT open the file.
- `read(path, *, issues=None)` MUST return a `ReadResult` whose `content` is: for a PCB document, the design of `import_board`; for a schematic document in the binary or the ASCII form, a design whose circuit is `import_circuit` of that one sheet, with `board is None`; for a project file, the design of `import_project` over `read.project.load_project(path)`; for a PCB library and a schematic library, a `Library`.
- For a design, `issues` MUST be the readers' issues, then the adapter's, then those of `design.validate()`; `evidence` MUST be `adapter.EVIDENCE`. In a project read, the project reader's `altium.project.document-outside` and `altium.project.document-missing` issues about a sheet or a PCB document are replaced by `altium.import.document-skipped`, so that one document gives one issue.
- A project document outside the project folder, a missing document and a document that a reader refuses MUST NOT stop the import: each gives `altium.import.document-skipped` (warning) with the reason, and the design is built from the rest. A project file that names no readable sheet and no readable PCB document MUST raise `FormatError`.
- Reader errors of the file that `read` was called on MUST be raised unchanged. The backend MUST call the readers in their lenient mode.
- `capabilities()` MUST return `CAPABILITIES`: `read_kinds == ("altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib")`, `write_kinds == ()`, `targets == ()`, `default_target is None`, `downgrade == "unsupported"`, `operations == ("detect", "read")` and `evidence == adapter.EVIDENCE`. The backend MUST NOT offer `lower` or `validate`. It offers `write(design, …)` for a model (`backend-protocol`, "Altium write of a model"; change c0090), which is experimental like the writers of `build`: the report names no write kind and lists no `write` operation until the writers leave that state.
- Registering the backend MUST NOT change what `fenolite inspect` and `fenolite check` accept: `cli-contract` "Inspect command" and `verification-loop` "Check command input" decide that, and this change edits neither command.

#### Scenario: Detection by suffix
- **WHEN** `AltiumBackend().detect` is called on `Path("a.PcbDoc")`, `Path("a.pcbdoc")`, `Path("a.SCHLIB")`, `Path("a.PrjPcb")`, `Path("a.SchDot")` and `Path("a.kicad_pcb")`
- **THEN** it returns `True`, `True`, `True`, `True`, `False` and `False`, and no file is opened

#### Scenario: Backend for a path
- **WHEN** `registry.for_path(Path("board.PcbDoc"))` and `registry.for_path(Path("board.kicad_pcb"))` are called
- **THEN** the first returns the Altium backend and the second the KiCad backend

#### Scenario: Schematic alone
- **GIVEN** `tests/data/altium/sample/altium_sample.SchDoc` (ASCII) and `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **WHEN** `AltiumBackend().read` reads each
- **THEN** both designs have `board is None` and equal circuits, apart from provenance

#### Scenario: Capability invariants
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks every registered backend
- **THEN** the Altium report lists only `detect` and `read`, both callable, with an empty `write_kinds`, empty `targets` and `default_target` `None`, and the backend has a callable `write` that the report does not list

#### Scenario: Skipped document
- **GIVEN** a copy of the blink project under `tmp_path` whose project file also lists `..\outside\x.SchDoc` and `missing.SchDoc`
- **WHEN** the project is read
- **THEN** the circuit, the board and every other issue equal those read without those two lines, apart from two `altium.import.document-skipped` warnings that give the reasons `outside-root` and `missing`

### Requirement: Import issue codes
Every issue of the adapter SHALL carry a code of the closed table `adapter.IMPORT_ISSUE_CODES`, which maps each code to its one severity, and `docs/cli-contract.md` SHALL list the table.
- Errors: `altium.import.bad-stack`, `altium.import.sheet-loop`.
- Warnings: `altium.import.bad-length`, `altium.import.body-unknown`, `altium.import.bad-geometry`, `altium.import.layer-outside-stack`, `altium.import.duplicate-net`, `altium.import.unknown-member`, `altium.import.padstack-unknown`, `altium.import.via-span`, `altium.import.no-designator`, `altium.import.sheet-missing`, `altium.import.repeated-sheet`, `altium.import.channel-naming`, `altium.import.scope-unknown`, `altium.import.duplicate-net-name`, `altium.import.duplicate-sheet-name`, `altium.import.bus-width`, `altium.import.harness-nested`, `altium.import.pcb-only-component`, `altium.import.document-skipped`, `altium.import.zone-hole-outside`.
- Infos: `altium.import.inexact`, `altium.import.multi-class`, `altium.import.zone-arc`, `altium.import.copper-shape`, `altium.import.scope`, `altium.import.option-ignored`, `altium.import.pin-map`, `altium.import.channels`, `altium.import.bus-member`, `altium.import.harness-entry`, `altium.import.extra-board`, `altium.import.linked-by-designator`, `altium.import.pcb-only-net`, `altium.import.rule-unmapped`, `altium.import.unmapped`.
- An issue's `where` MUST be a locator of "Identifiers and provenance", a reference, a `REF-PIN` or a net name; a counting issue's message MUST hold its counts.
- An error issue never stops the import: the adapter raises only for a programming error and for a project with nothing to read.
- No code of this table MUST equal a code of `fenolite.lens.altium.ALTIUM_ISSUE_CODES` or of the readers' tables.

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_codes.py` collects the codes that the adapter's source can give and those the tests have seen
- **THEN** both sets are within `IMPORT_ISSUE_CODES`, every code of the table has one severity, every code is a row of `docs/cli-contract.md`, and none is a code of the build or of a reader

### Requirement: Unmapped records are counted
The adapter SHALL report what it reads and does not map, so that nothing is dropped silently.
- One `altium.import.unmapped` info per import MUST list, by kind and in sorted order, the count of every record that gave no model entity: `footprint-graphics`, `pour-primitives`, `plane-cuts`, `region-holes`, `texts`, `classes`, `polygons`, `bodies`, `dimensions`, `schematic-graphics`, `symbol-graphics`, and the name of every storage that the readers keep as bytes and that is not empty.
- The count of mapped entities plus the counts of this issue MUST equal the number of records the readers returned, per record kind.
- Without anything unmapped, the issue is not given.

#### Scenario: Census adds up
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_census.py` imports every authored Altium document under `tests/data/altium/`
- **THEN** for each record kind of each file, the mapped and the unmapped counts add up to the reader's record count

### Requirement: Own files import to the model they were written from
A design that Fenolite built for the Altium target SHALL import to the same circuit and, where the build writes a PCB document, the same placement.
- For each of `examples/altium_sample`, `examples/altium_kicad` (both scripts), `examples/blink_2layer`, and the hierarchical and routed samples of c0037 and c0038: the nets of the imported project, as sets of `(ref, pin)` pairs by name, MUST equal those of the model, the no-connect marks MUST be equal, and each component MUST have the model's `ref`, `value` and footprint name.
- This is evidence of level `INFERRED`: Fenolite's writers read by Fenolite's readers and adapter.

#### Scenario: Round trip of the examples
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_own_files.py` builds each example under `tmp_path` in the ASCII and in the binary schematic form and imports the written project
- **THEN** every comparison of the requirement holds for every example and both forms

### Requirement: Altium project sets agree
The connectivity rules SHALL be checked on public Altium-saved projects: the netlist that the adapter computes from the sheets of a project MUST equal the pad netlist of the project's PCB document.
- `tests/corpus/test_altium_import.py` MUST, for every project set of the manifest ("Altium project sets" of `corpus-policy`), import the sheets and the PCB document apart, map each PCB component to a schematic component by "Project import", and compare the two partitions of `(component, pad)` pairs into nets. A pin stands for its pads through the pin-to-pad map of its current footprint model (its own designator by default). A pair is compared when the sheets hold the pin and the PCB document the pad; a pad without a pin (a shield tab, a mounting pad) and a pin without a pad are counted, not compared.
- The test MUST pass when the partitions are equal for every linked component, and MUST report per set, as counts and row ids only ("Second-backend corpus rows" of c0039): the sheets, the scope chosen, the nets, the linked and the unlinked components, the nets equal by members and the nets equal by name as well. No part name and no net name of a corpus file is printed.
- A set that differs MUST fail the test unless its project-file row carries the use `altium-import:known-diff`, in which case the differing groups are counted, the count is pinned in the test (`KNOWN_DIFFS`), and the hypotheses that the set exercises stay `INFERRED`. A set MUST NOT be given that use to hide a defect of the adapter: the note of the row states the cause from the project's own files (for instance a PCB document older than its sheets).
- Net names are compared as supporting data only: a system name depends on a choice that no source states (`H-A-IMP-NAME-AUTO`).
- No corpus file and nothing derived from one MUST be written outside pytest's temporary directory and the corpus cache.

#### Scenario: Public project
- **WHEN** `uv run pytest tests/corpus/test_altium_import.py -m needs_corpus -k project_sets` runs with the corpus fetched
- **THEN** for at least three project sets from three repositories the two partitions are equal for every linked component, and the report lists the scope, the counts and a census of the rules exercised per set (four of the five sets agree; set 02 is a known difference of two pins)

#### Scenario: Corpus absent
- **WHEN** the same command runs without the fetched corpus
- **THEN** the tests are skipped with the corpus marker's reason, and none fails

### Requirement: Board import oracle
The board import SHALL be compared with `kicad-cli pcb import --format altium` (10.0), run as a subprocess on a copy under pytest's temporary directory.
- `tests/kicad/altium/test_import_oracle.py` MUST, for every fetched PCB document without the use `heavy` and for the authored documents, import the file with the adapter, convert it with `kicad-cli` and read the result with `KicadBackend`, then compare: the copper layer count; per reference, the side, the rotation and the pad count; per pad, the net name and the position relative to its footprint; the positions of footprints, vias and track ends relative to one common translation; and zone outlines.
- Lengths MUST agree within 10 nm and angles within 1 000 microdegrees. KiCad moves an imported board, so only relative positions are compared.
- A difference that comes from KiCad's importer and not from the file MUST be listed in `docs/formats/altium/import.md` with its cause, and excluded by kind, never by file. The kinds found: references (KiCad names a footprint after its shown designator text; a reference that several footprints share is not compared), pads that KiCad returns without their number or not at all (unplated holes, pads on paste layers), copper tracks and arcs without a net, zone vertices that repeat their neighbour, and zones whose outline holds an arc.
- The test MUST be marked `needs_kicad` and `kicad_min_major(10)`, and the corpus part `needs_corpus`.

#### Scenario: Blink document against KiCad
- **WHEN** `uv run pytest tests/kicad/altium/test_import_oracle.py -k blink` runs with `kicad-cli` 10.0
- **THEN** the two readings agree on two copper layers, three footprints with their sides and rotations, every pad's net and relative position within 10 nm

#### Scenario: KiCad 9
- **WHEN** the same test runs with `kicad-cli` 9.0
- **THEN** it is skipped, not failed

### Requirement: Import facts are documented
The facts and rules the adapter relies on SHALL be recorded with sources and evidence labels before the code that uses them.
- `docs/formats/altium/connectivity.md` MUST state each connection, scope, naming, bus and harness rule as a row with its source ids, its label and its hypothesis.
- `docs/formats/altium/import.md` MUST hold the layer table, the pad, padstack, via, zone and rule mappings, the extension-bag keys, the id table, the frame and unit rules, and the differences from KiCad's importer.
- `docs/formats/altium/pcb-bodies.md` MUST state the body record and each key that `read.bodies` types.
- `docs/altium.md` MUST gain a section "Reading Altium files" with the read kinds, what is not imported, and the issue codes; `docs/design-model.md` the three model deltas; `docs/formats/units.md` the schematic unit and the import rules.
- Facts MUST be in Fenolite's own words. No third-party code, grammar or table MUST be copied; KiCad's importer is read for facts only, and AltiumSharp only as version 1 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`.
- `tests/unit/test_format_facts.py` MUST check the tables of the three pages: every row has a registered source id, a label and, unless verified, a registered hypothesis.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST gain the rows of the adapter and of `read.bodies`.

#### Scenario: Fact tables checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py` runs
- **THEN** both pass, every `H-A-IMP-*` id cited in the repository is a row of `docs/hypotheses.md`, and every source id of the three pages is a row of `docs/evidence/sources.md`

### Requirement: Objects on an internal plane
The import SHALL make no copper and no drawing of a free primitive that lies on the layer of an internal plane: such a layer is stored in negative, so an object on it is a place without copper (`docs/formats/altium/import.md`, "Layers"; `H-A-IMP-PLANE-CUT`).
- A track, an arc (a full circle among them), a fill, a region or a text without a component index and without a polygon index, on a layer of the chain whose Altium id is 39 to 54, MUST give no `Track`, `Arc`, `Graphic` or `Text`, whatever its net index, its width and its radius are. It MUST NOT give `altium.import.bad-geometry`.
- Each such record MUST be counted in the census under its record kind with the category `plane-cuts`, so that `altium.import.unmapped` names the count, and in the pair `plane_cuts` of its layer ("Layers and stack-up"). Its values stay in the reader's record at its index.
- The other items of the import MUST keep their ids, their `native_ids` and their locators: a content id counts the earlier entities of equal content only, and no entity that is kept has the content of one that is left out.
- A primitive with a component index or a polygon index on such a layer is not changed by this requirement: it is counted as `footprint-graphics`, `pour-primitives` or `polygons` as before. A pad and a via are not changed either.
- The import MUST NOT synthesise a zone, a keep-out or any other entity for the plane or for what cuts it.

#### Scenario: Every kind of object on a plane
- **GIVEN** a document whose chain is 1 → 39 → 32 with, on layer 39 and free: a track without a net, a track on the net `GND`, an arc of 90 degrees, a full circle, a fill, a region and a text
- **WHEN** it is imported
- **THEN** the board holds no track, no arc, no text and no graphic outside `Edge.Cuts`, `altium.import.unmapped` lists `plane-cuts 7`, no `altium.import.copper-shape` and no `altium.import.bad-geometry` is given, the layer `In1.Cu` holds the pair `("plane_cuts", "7")`, and the census of each record kind adds up to the reader's count

#### Scenario: Plane without a net name
- **GIVEN** a document whose chain is 1 → 39 → 32 with `PLANE1NETNAME=(No Net)` and one free track on layer 39
- **WHEN** it is imported
- **THEN** the layer `In1.Cu` holds `plane_cuts` and no `plane_net`, and the board holds no track

#### Scenario: Public documents with planes
- **WHEN** `uv run pytest tests/kicad/equivalence/test_triangle_level5.py -k plane` compares Fenolite's read and KiCad's import of the public PCB documents that hold internal planes
- **THEN** both reads hold the same number of tracks, and neither holds a track or an arc on the layer of a plane

### Requirement: Copper locks from an Altium board
`import_board` SHALL give each `Track`, `Arc` and `Via` that "Tracks, arcs and vias" maps the `locked` of its primitive: `True` when `Prefix.locked` is true (bit 2 of the first flag byte clear; `docs/formats/altium/pcb-read.md`, row `Prefix.locked`), `False` otherwise (`design-model`, "Copper locks in the board model"). This requirement adds one field beside "Tracks, arcs and vias" and changes none of its rules.
- A document without a locked free primitive MUST import to the model it imported to before this change.
- A document that Fenolite wrote from a model with locked copper MUST import with the same items locked ("Own files import to the model they were written from"), for the kinds of `pcbrecords.LOCK_WRITTEN`.
- The level is that of the read row, `INFERRED`, until `H-A-PCB-CU-LOCK` is settled.

#### Scenario: Locks survive the round trip
- **GIVEN** the routed sample's model with one track, one arc and one via locked, built for Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_own_files.py -k locked` imports the written project
- **THEN** exactly the track, the arc and the via that were locked have `locked == True`

#### Scenario: A document without locks
- **WHEN** the PCB document of `tests/data/altium/routed/` is imported
- **THEN** no track, arc or via has `locked == True`, and the imported model equals the one of before this change

### Requirement: Via tenting of imported vias
`import_board` SHALL map the two tenting flags of each via record to the via's protection: `Via.protection` MUST be `ViaProtection(tenting_front=<tented_top>, tenting_back=<tented_bottom>)`, both as booleans, and the six other fields MUST be `None`. This requirement adds one field to the `Via` that "Tracks, arcs and vias" maps; everything else there holds.
- Both tenting fields MUST be explicit for every imported via, `False` for a clear flag: an Altium via carries its own flags and follows no board default, and a `None` would be read by the KiCad backend as "tented" (`kicad-file-backend`, "Via protection defaults on boards").
- `Board.via_protection` of an imported board MUST be `None`: the PCB document holds no default that the reader reads.
- Covering, plugging, capping and filling MUST stay `None`: no record read here states them.
- The mapping has the label of the two fields it reads, `INFERRED` (`ViaRecord.tented_top`, `ViaRecord.tented_bottom`; `docs/formats/altium/pcb-read.md`), and `adapter` evidence MUST name `H-A-PCB-CU-VIATENT` beside the hypotheses of the via mapping. A clear flag is read as "not tented"; what the solder-mask expansion of the via does to its mask opening is not read.
- The equivalence levels and RT-A2 do not compare `Via.protection`; `docs/altium.md` ("Round trips") MUST list the field among those left out, with the reason: a `None` has no Altium form, so a written and re-read model differs from the original where a side is stated nowhere.

#### Scenario: Flags become tenting
- **GIVEN** a PCB document with four vias whose flags are `0C`, `2C`, `4C` and `6C`
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_copper.py -k tenting` imports it
- **THEN** the four vias have (`tenting_front`, `tenting_back`) = (`False`, `False`), (`True`, `False`), (`False`, `True`) and (`True`, `True`), every other field of their `protection` is `None`, and `board.via_protection` is `None`

#### Scenario: Stated tenting survives the round trip
- **GIVEN** a design whose two vias have `protect(tenting="front")` and `protect(tenting=False)`, built for the Altium target
- **WHEN** the written PCB document is imported
- **THEN** each imported via has the tenting of the via it was written from

#### Scenario: An imported board written for KiCad
- **GIVEN** the imported board of "Flags become tenting"
- **WHEN** it is written with `write_board` for target 10
- **THEN** the four vias hold `(tenting (front no) (back no))`, `(tenting (front yes) (back no))`, `(tenting (front no) (back yes))` and `(tenting (front yes) (back yes))`, and no via follows KiCad's board default
