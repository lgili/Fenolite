## MODIFIED Requirements

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

### Requirement: Unmapped records are counted
The adapter SHALL report what it reads and does not map, so that nothing is dropped silently.
- One `altium.import.unmapped` info per import MUST list, by kind and in sorted order, the count of every record that gave no model entity: `footprint-graphics`, `pour-primitives`, `plane-cuts`, `region-holes`, `texts`, `classes`, `polygons`, `bodies`, `dimensions`, `schematic-graphics`, `symbol-graphics`, and the name of every storage that the readers keep as bytes and that is not empty.
- The count of mapped entities plus the counts of this issue MUST equal the number of records the readers returned, per record kind.
- Without anything unmapped, the issue is not given.

#### Scenario: Census adds up
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_census.py` imports every authored Altium document under `tests/data/altium/`
- **THEN** for each record kind of each file, the mapped and the unmapped counts add up to the reader's record count

## ADDED Requirements

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
