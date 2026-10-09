## ADDED Requirements

### Requirement: Layer stacks of any even count
The PCB document writer SHALL write the copper layers of the model's stack-up, for any even count from 2 to 32 with at most 16 signal layers and 16 plane layers, in the model's order, each a signal layer or, when the build declares it a plane, an internal plane on its net, with the dielectrics between them (thickness, material name, permittivity).
- The layer map MUST assign each copper layer of the model to one Altium layer, and two model layers MUST NOT share one. The map MUST be recorded in `docs/formats/altium/pcb-copper.md`.
- A design without a stack-up MUST get the stack that the writer gave it before this change.
- A stack the rules above exclude MUST give `altium.not-lowered` with `where` `stackup` and the default stack of the two outer layers; no partial stack is written.

#### Scenario: Six layers read back
- **GIVEN** the authored design `board6` with the copper layers `F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu`, built with `In2.Cu` as a plane on `GND`
- **WHEN** it is written and the PCB document is read back
- **THEN** the board has six copper layers in that order, `In2.Cu` is a plane, and the dielectric thicknesses equal the design's within 2 nm

#### Scenario: Odd count refused
- **GIVEN** a design whose board has five copper layers
- **WHEN** it is built for Altium
- **THEN** `altium.not-lowered` has `where` `stackup`, and the document holds the default stack

### Requirement: Blind and buried via records
A via whose span is two copper layers of the written stack SHALL be written with its start and end layer, and the board record SHALL hold one drill pair per distinct span.
- A through via MUST be written as before this change.
- A micro via MUST give `altium.via-unsupported` (warning) and MUST NOT be written.

#### Scenario: Three spans
- **GIVEN** `board6` with a through via, a via from `F.Cu` to `In1.Cu` and a via from `In1.Cu` to `In2.Cu`
- **WHEN** the document is written and read back
- **THEN** the three vias have those spans, and the board record holds three drill pairs

### Requirement: Board text records
Board texts SHALL be written as stroke text records with their string, layer, position, height, stroke width and rotation; a text on a bottom-side layer SHALL be mirrored. The model's text has no mirror, justification or font kind, so none is written.
- The string MUST be written in every form that `altium-pcb-reader` ("Text records and wide strings") needs to return it unchanged, non-ASCII characters included.
- A text that has no record (an empty string, a control character or a line break, a height or a stroke width that is not positive, a layer outside the board layer map of `docs/formats/altium/pcb-records.md`) MUST give `altium.not-lowered` with `where` `text/<id>` and the reason in its message.

#### Scenario: Accented text
- **GIVEN** a board text `Tensão 5 V` on `F.SilkS`
- **WHEN** the document is written and read back
- **THEN** the text record returns that string, on the top overlay, at the same place within 2 nm

### Requirement: Board graphics and keep-out records
Board graphics on the non-copper layers of the board layer map SHALL be written as track, arc and region records without a net; keep-outs SHALL be written as region records with the keep-out flag and the restriction set of the model, on the Keep-Out layer when they name every copper layer of the board, else one per copper layer.
- A keep-out record MUST hold its restrictions value in two keys, `KEEPOUTRESTRICTIONS` (the key saved documents hold) and after it `KEEPOUTRESTRIC` (the key KiCad's importer reads; not a key Altium writes), both with the same value (the maintainer's decision of 2026-10-06), so that KiCad imports the keep-out with exactly the restrictions written. That Altium accepts the pair stays `INFERRED` until step X11 of Part X.
- A restriction that the record cannot carry (`no_footprints`) MUST give `altium.not-lowered` with `where` `keepout/<id>` naming the restriction; the keep-out is written with the others, and not at all when it has no other.
- A graphic that has no record (a layer outside the map, a drawn shape without a positive width, a filled circle, a shape without an extent) MUST give `altium.not-lowered` with `where` `graphic/<id>`. A graphic on `Edge.Cuts` is the outline and counts as written.
- The board outline MUST stay as written before this change.

#### Scenario: Keep-out with two restrictions
- **GIVEN** a keep-out that forbids tracks and vias in a rectangle on all copper layers
- **WHEN** the document is written and read back
- **THEN** one keep-out region with those two restrictions is read, its value 3 in `KEEPOUTRESTRICTIONS` and in `KEEPOUTRESTRIC`

### Requirement: Non-plated holes and slots
A hole of the board SHALL be written as a free pad record with a hole and no copper, its plated byte the hole's `plated`. The model's board hole is round: it has no slot, so no slot is written by this change.
- A hole without a positive drill MUST give `altium.not-lowered` with `where` `hole/<id>`.

#### Scenario: Mounting hole
- **GIVEN** a non-plated hole of 3.2 mm
- **WHEN** the document is written and read back
- **THEN** a free pad with a 3.2 mm hole, plating off and no copper is read

### Requirement: Component bodies are reported
The writer SHALL NOT write a component body record in this change (the cut order of the design, first item), and each `ComponentBody` of a footprint of the board SHALL give one `altium.not-lowered` with `where` `body/<id>` that names its height. No model file is embedded.

#### Scenario: Body height
- **GIVEN** a board footprint with a body of height 2.5 mm
- **WHEN** the design is built for Altium
- **THEN** `result.pcb.not_lowered` holds `body` with the count 1, and one `altium.not-lowered` with `where` `body/<id>` names 2.5 mm

### Requirement: Unpoured polygons are a contract
Every zone SHALL be written as a polygon record in the unpoured state with its net, layer, outline, priority (as the pour index) and island removal, and the writer MUST NOT write poured copper for it. Clearance and thermal reliefs are not keys of the record: Altium takes them from its rules.
- The build MUST report `altium.zones-unpoured` (info) once, with the count, and the documentation MUST say that the board is repoured in Altium.

#### Scenario: Two polygons
- **GIVEN** `board6` with a `GND` zone on `F.Cu` and one on `B.Cu`
- **WHEN** it is built for Altium
- **THEN** the document holds two unpoured polygons, no region of poured copper, and one `altium.zones-unpoured` with the count 2

### Requirement: Written items are accounted
The writer SHALL return, per kind of model item (footprint, pad, track, arc, via, zone, text, graphic, keep-out, hole, body, rule), the number of items written and the number not lowered, and every item of the board MUST be in exactly one of the two.

#### Scenario: Nothing is lost silently
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k accounted` builds `board6`, the routed samples and a variant of `board6` with one item of every kind that has no record
- **THEN** for each kind, written plus not lowered equals the number of items in the model, and each not-lowered item has an issue

## MODIFIED Requirements

### Requirement: Four-layer stack
`docboard.board_records(..., stack=…)` SHALL write the layer stack of a `docboard.StackSpec` with any even number of copper layers that "Layer stacks of any even count" allows (change c0085; two or four before it), each inner layer a signal layer or an internal plane with a net (`docs/formats/altium/pcb-copper.md`, "Layer stack"; S-0160, S-0176, S-0199, S-0200; `H-A-PCB-CU-STACK`, `H-A-PCB-CU-PLANE`).
- `StackSpec` MUST hold `copper` (the Altium ids from top to bottom, as `copper_stack` gives them), one copper thickness per layer, one `Dielectric(kind, thickness, epsilon_r, material)` between each pair of neighbours (`kind` is `unspecified`, `core` or `prepreg`; lengths in nanometres), and `plane_nets`, one net name per plane of `copper`, in plane order. A `plane_nets` whose length differs from the number of planes, or a net name that fails `text_problem`, MUST raise `ValueError`.
- `StackSpec.default(copper, plane_nets=())` MUST give 1.4 mil copper and, for two layers, the dielectric of c0035 (`unspecified`, 12.6 mil, `4.800`, `FR-4`); for four layers a prepreg of 0.2 mm, a core of 1.0 mm and a prepreg of 0.2 mm, each `4.800` and `FR-4`; for more layers prepregs of 0.2 mm and cores in turn, the outermost a prepreg, the cores sharing 1.0 mm. These values are Fenolite's choices.
- For two copper layers and the default stack, the record MUST equal the record of c0035 byte for byte.
- For four or more copper layers the numbered keys MUST link the ids of `copper` in order through `LAYER<id>PREV` and `LAYER<id>NEXT` (0 before the first and after the last); every other copper link stays 0. Each linked layer MUST carry its `COPTHICK`, and each but the bottom the dielectric below it (`DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL`).
- The physical stack of the `V9_STACK_LAYER<i>` list and the head of the `LAYER_V8_<i>` list MUST hold 13 layers: paste, overlay, solder, `Top Layer`, `Dielectric 1`, the first inner layer, `Dielectric 2`, the second inner layer, `Dielectric 3`, `Bottom Layer`, solder, overlay, paste. The dielectrics MUST have the long ids 17039361, 17039362 and 17039363 from the top (the numbering S-0199 saves). A stack of more layers MUST grow by one dielectric and one copper entry per inner layer, `Dielectric n` with the long id 17039360 + n.
- A **signal** inner layer MUST be written as S-0199 and S-0200 save it: `NAME` (`Mid-Layer <n>`), `LAYERID` (16777217 + n), `USEDBYPRIMS`, `COPTHICK` and `COMPONENTPLACEMENT=1`.
- A **plane** MUST be written as S-0176 saves it: `NAME` (`Internal Plane <k>`), `LAYERID` (16842752 + k), `USEDBYPRIMS`, `COPTHICK` and `PULLBACKDISTANCE=20mil`; and line 1 of the record MUST hold `PLANE<k>NETNAME=<net name>`. Every other `PLANE<n>NETNAME` stays `(No Net)`.
- No primitive is written for a plane: no `Split Plane` polygon record, no pull-back track and no region (`H-A-PCB-CU-PLANE`); its `USEDBYPRIMS` is `FALSE`. Split planes are not written.
- The cache list MUST hold every layer once, in the form S-0176 saves (found when the written stack was compared with it, 2026-10-03): the 102 layers of a two-layer document in their order, then `Dielectric 2` and `Dielectric 3` (and the further dielectrics of a larger stack). A mid layer or a plane of the stack keeps its place in its run and carries its stack keys.
- `pcbdoc.write_pcbdoc` MUST take the stack from `PcbDocSpec.stack` (`None` is `StackSpec.default` for `PcbDocSpec.copper_layers` without planes) and MUST raise `ValueError` when `stack.copper` does not hold one id per name of `copper_layers`, or when a plane's net is not in `PcbDocSpec.nets`.
- `DIELTYPE` MUST be 0 for `unspecified`, 1 for `core` and 2 for `prepreg`; `DIELCONST` three decimals; `DIELHEIGHT` and `COPTHICK` mil text.
- The layer set `&Signal Layers` MUST also list the signal inner layers (`MidLayer1`, `MidLayer2`), `&Plane Layers` the planes (`InternalPlane1`, `InternalPlane2`), and `&All Layers` both. The first drill pair stays `LAYERPAIR0LOW=TOP`, `LAYERPAIR0HIGH=BOTTOM`; "Blind and buried via records" adds one pair per span of a blind or buried via.
- A stack with one signal inner layer and one plane is composed from the two entry forms; no saved document with such a stack was read, and the fact page MUST say so on its row.

#### Scenario: Two layers keep their bytes
- **WHEN** `docboard.board_text` runs for the blink outline with `stack=StackSpec.default((1, 32))` and without `stack`
- **THEN** both texts are equal, and equal to the text c0035's test pins

#### Scenario: Chain of four signal layers
- **WHEN** `Board6` of the routed sample is read with `tests/_altium_pcb_read.py`
- **THEN** following `NEXT` from layer 1 gives 2, 3, 32, then 0; `V9_STACK_LAYER4_NAME` is `Dielectric 1`, `V9_STACK_LAYER5_LAYERID` is `16777218` and `V9_STACK_LAYER5_COMPONENTPLACEMENT` is `1`; and the record has 27 lines

#### Scenario: Ground plane under the top layer
- **WHEN** `board_fields` runs with `StackSpec.default((1, 39, 3, 32), plane_nets=("GND",))`
- **THEN** following `NEXT` from layer 1 gives 39, 3, 32, then 0; `PLANE1NETNAME` is `GND` and `PLANE2NETNAME` is `(No Net)`; `V9_STACK_LAYER5_NAME` is `Internal Plane 1` with `LAYERID=16842753` and `PULLBACKDISTANCE=20mil` and without `COMPONENTPLACEMENT`; `V9_STACK_LAYER7_NAME` is `Mid-Layer 2`; and the layer set `&Plane Layers` is `InternalPlane1`

#### Scenario: Two planes
- **WHEN** `board_fields` runs with `StackSpec.default((1, 39, 40, 32), plane_nets=("GND", "VIN"))`
- **THEN** the chain is 1, 39, 40, 32; `PLANE1NETNAME` is `GND` and `PLANE2NETNAME` is `VIN`; `&Signal Layers` lists no mid layer; and the cache list names `Internal Plane 1` and `Internal Plane 2` once each, with `PULLBACKDISTANCE`

#### Scenario: Dielectric values from the spec
- **WHEN** `board_fields` runs with a four-layer `StackSpec` whose core is 0.71 mm of `4.5`
- **THEN** `V9_STACK_LAYER6_DIELHEIGHT` is `27.9528mil`, `V9_STACK_LAYER6_DIELCONST` is `4.500` and `V9_STACK_LAYER6_DIELTYPE` is `1`

#### Scenario: Plane without a net refused
- **WHEN** `StackSpec.default((1, 39, 3, 32))` is built without `plane_nets`
- **THEN** it raises `ValueError` naming Internal Plane 1

### Requirement: Via records
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX, start=1, end=32)` SHALL write one via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer at 29 and the end layer at 30: 1 and 32 for a through via, the ids of the two copper layers of its span for a blind or buried via (change c0085, "Blind and buried via records").
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242, stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index. It MUST raise `ValueError` for a via whose `via_type` is `micro`, whose `layers` are not two different copper layers of the board, or whose drill is not below its diameter.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Micro via refused
- **WHEN** a spec holds a via with `via_type="micro"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` whose two layers are both `F.Cu`, a span that is not two different copper layers of the board (a blind via with a span of two copper layers is written since change c0085, "Blind and buried via records")
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

### Requirement: Polygon pour records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, without poured copper (S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196; `H-A-PCB-CU-REPOUR`).
- A record MUST hold, in this order: the seven common keys with `LAYER` = the layer text; `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=TRUE`, `REMOVEDEAD=TRUE` (`FALSE` for a zone whose islands are never removed, change c0085), `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`; per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` as the board outline writes them, the first vertex repeated last; `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`, `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`, `POUROVERSTYLE=1`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS=FALSE`, `AUTONAME` (only when the name is generated), `OPTIMALVOIDROTATION=TRUE`, and `NET` (the net's index; left out without a net).
- `NAME` MUST be the character codes of the name in decimal, joined by commas. The name is `Zone.name`, or `<net name>_L<layer position, two digits from 01>_P<pour index, three digits>` when it is empty (`NONET` stands for a missing net), in upper case, with `AUTONAME=TRUE`.
- `POURINDEX` MUST number the records from 0 in the order of falling `Zone.priority`, then net name, first outline point, zone id and stack position, so a zone of higher priority is poured first.
- `Regions6` and `ShapeBasedRegions6` MUST hold no region of a polygon (they hold the filled graphics and keep-outs of change c0085 only, and stay empty without them), and `Zone.fills` MUST NOT be written: the polygons are unpoured, and Altium fills them on a repour.
- A zone with fewer than three outline points, a zone layer outside the copper layers or on a plane, or a name that fails `text_problem` MUST raise `ValueError` naming the zone's id.

#### Scenario: Ground zone on two layers
- **GIVEN** a zone on `In1.Cu` and `B.Cu` with the net `GND`, four outline points and priority 0, and a second zone on `F.Cu` with priority 2
- **WHEN** `Polygons6` is read
- **THEN** it holds three records; the `F.Cu` record has `POURINDEX=0`; the two `GND` records have `LAYER=MID1` and `LAYER=BOTTOM`, five vertices, `NET` equal to the index of `GND`, and names that decode to `GND_L02_P001` and `GND_L04_P002`; `Regions6` is empty

#### Scenario: Zone without an outline refused
- **WHEN** a spec holds a zone whose `outline` is empty
- **THEN** `write_pcbdoc` raises `ValueError` naming the zone's id

### Requirement: Copper layer map
`pcbrecords.LAYER_MAP` SHALL also map the inner copper layers of a four-layer board as signal layers, `pcbrecords.layer_text` SHALL give the layer text of a copper layer id in a property record (`TOP`, `MID<n>`, `BOTTOM`, `PLANE<n>`), and `pcbrecords.copper_stack` SHALL give the Altium ids of a stack whose inner layers are signal layers or internal planes, by position (change c0085) (S-0002, S-0160, S-0176, S-0199, S-0200). This requirement extends c0035's "PCB layer map", whose eight rows and pairs hold unchanged.

| Fenolite layer | as | Altium id | Altium name | layer text |
|---|---|---|---|---|
| `F.Cu` | signal | 1 | Top Layer | `TOP` |
| `In1.Cu` | signal | 2 | Mid-Layer 1 | `MID1` |
| `In2.Cu` | signal | 3 | Mid-Layer 2 | `MID2` |
| `B.Cu` | signal | 32 | Bottom Layer | `BOTTOM` |
| first inner layer that is a plane | plane | 39 | Internal Plane 1 | (no primitive is written on it) |
| second inner layer that is a plane | plane | 40 | Internal Plane 2 | (no primitive is written on it) |
| k-th inner layer of any stack | signal | k + 1 | Mid-Layer k | `MID<k>` |
| p-th inner layer that is a plane | plane | 38 + p | Internal Plane p | (no primitive is written on it) |

- `pcbrecords.copper_stack(names, planes=())` MUST return the Altium ids of a board's copper layers from top to bottom. `names` are the model's copper layers in stack order, distinct, an even count that "Layer stacks of any even count" allows: the first is the top layer (1), the last the bottom layer (32); `planes` MUST name only inner layers of `names`, without repeats. Any other input MUST raise `ValueError` naming it.
- A signal inner layer keeps its row of the table whatever the other inner layers are: the k-th inner layer is Mid-Layer k, whatever its name. Planes are numbered from the top: the first plane is Internal Plane 1, the second Internal Plane 2. So Mid-Layer 2 may be written without Mid-Layer 1, a state Altium saves (S-0200).
- `LAYER_MAP` and `COPPER_LAYER_TEXT` MUST NOT hold a plane: a primitive on a plane layer has no id (`ValueError`).
- No inner layer has a flip partner: `FLIP_PAIRS` MUST stay as c0035 wrote it.

#### Scenario: Four signal layers
- **WHEN** `pcbrecords.copper_stack(("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))` runs
- **THEN** it returns `(1, 2, 3, 32)`

#### Scenario: Planes numbered from the top
- **WHEN** `copper_stack` runs for the four layers with `planes=("In1.Cu",)`, with `planes=("In2.Cu",)` and with `planes=("In1.Cu", "In2.Cu")`
- **THEN** it returns `(1, 39, 3, 32)`, `(1, 2, 39, 32)` and `(1, 39, 40, 32)`

#### Scenario: Other stacks refused
- **WHEN** `copper_stack` gets `("F.Cu", "In1.Cu", "B.Cu")`, `("F.Cu", "In1.Cu", "In1.Cu", "B.Cu")`, `planes=("F.Cu",)` with four layers, or `planes=("In1.Cu",)` with two layers
- **THEN** each call raises `ValueError` that names the input
