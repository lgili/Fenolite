# Importing Altium PCB files into the model

This page states, in Fenolite's own words, how `fenolite.backends.altium.adapter` (change c0043) maps the
records of the PCB reader (`pcb-read.md`, c0041) and of the schematic reader (c0040) into the neutral
model. The adapter parses no byte: it reads typed attributes of records. The connection rules of schematic
sheets are on `connectivity.md`, component bodies on `pcb-bodies.md`, the rule kinds on `rule-file.md`.

- Sources: KiCad's developer page (S-0002); KiCad's importer, read for facts only and never transcribed
  (S-0160, S-0161); Altium's documentation of pads (S-0302), polygons (S-0285) and design rules (S-0286);
  `kicad-cli pcb import --format altium` run as a subprocess (S-0020), the oracle of
  `tests/kicad/altium/test_import_oracle.py`.
- The model is a projection of the records, not their container. What maps to nothing stays in the
  reader's document and is counted by `altium.import.unmapped`.

## Units and frame

| fact | source | label | hypothesis |
|---|---|---|---|
| A binary length of `u` units of 1/10 000 mil is `u × 127 / 50` nm, rounded half to even (`core.units.u_to_nm`); the conversion is exact when `u` is a multiple of 50 | S-0002 | ORACLE-VERIFIED(kicad-cli) (10.0.6; c0041) | H-A-UNIT, H-A-RD-PCB-KICAD-DOC |
| A length written as text (`10mil`, `1.27mm`) is parsed as an exact fraction and rounded half to even | S-0002, S-0160 | INFERRED | H-A-IMP-FRAME |
| Altium's Y axis points up and the model's down: a point `(x, y)` becomes `(x, −y)`. No origin is subtracted; the board origin (`ORIGINX`, `ORIGINY`) goes to the board's bag | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_import_oracle.py) | H-A-IMP-FRAME |
| An angle is stored in degrees, counter-clockwise as seen; it becomes microdegrees through an exact fraction of the stored double, reduced to one turn. The model's positive angle also displays counter-clockwise, so the number is kept under the Y flip | S-0161 | INFERRED | H-A-IMP-FRAME |
| A component's `ROTATION` is the model's footprint rotation, and `LAYER=BOTTOM` the bottom side; a pad's local position is its absolute position through the inverse of the placement, without a mirror | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_import_oracle.py) | H-A-IMP-FRAME |
| An arc from its start angle to its end angle runs counter-clockwise as seen; under the Y flip the three model points are start, middle and end in that order | S-0160, S-0161 | INFERRED | H-A-IMP-FRAME |
| A point of a schematic library keeps its sign on both axes: Fenolite's writer of c0034 writes a KiCad symbol's coordinates unchanged | S-0131 | INFERRED | H-A-IMP-SYMFRAME |

## Layers

| fact | source | label | hypothesis |
|---|---|---|---|
| The copper layers are the chain of the board record from layer 1 through `NEXT`. The first is `F.Cu`, the last `B.Cu`, the j-th between them `In<j>.Cu`, whatever its Altium id: a mid layer and an internal plane are named alike | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_import_oracle.py) | H-A-IMP-LAYERS |
| 33 and 34 are `F.SilkS` and `B.SilkS`; 35 and 36 `F.Paste` and `B.Paste`; 37 and 38 `F.Mask` and `B.Mask`; 55 `Altium.DrillGuide`; 56 `Altium.KeepOut`; 57 to 72 `Mech.1` to `Mech.16`; 73 `Altium.DrillDrawing`. Altium has no fixed fabrication or courtyard layer, so none is guessed | S-0002, S-0160 | INFERRED | H-A-IMP-LAYERS |
| Layer 74 (Multi-Layer) is no model layer: an object on it lies on every copper layer of the chain | S-0161 | INFERRED | H-A-IMP-LAYERS |
| A copper id outside the chain, or an id outside this table, goes to the layer `Altium.<id>` | S-0161 | INFERRED | H-A-IMP-LAYERS |
| A plane stays a copper layer with its net in the bag (`PLANE<k>NETNAME`); no zone is made for it | S-0161 | INFERRED | H-A-IMP-LAYERS |
| The stack-up comes from the physical list (`V9_STACK_LAYER<i>_…`) when the record holds one, else from the numbered layers of the chain with one dielectric between neighbours | S-0160, S-0161 | INFERRED | H-A-IMP-LAYERS |

## Pads and padstacks

| fact | source | label | hypothesis |
|---|---|---|---|
| Pad shape 1 is round (a circle with equal sizes, an oval otherwise), 2 rectangular, 3 octagonal; shape 1 with the alternate shape 9 is a rounded rectangle whose corner radius is a percentage | S-0160, S-0161, S-0302 | INFERRED | H-A-IMP-PADSTACK |
| A hole size above 0 makes a through-hole pad, plated or not by the plated flag; a pad on Multi-Layer lies on every copper layer | S-0161, S-0302 | INFERRED | H-A-IMP-PADSTACK |
| Stack mode 0 is Simple (one shape on all layers), 1 Top-Middle-Bottom (three sizes and shapes), 2 Full Stack (a size and a shape per signal layer: the top, the mid layers in order, the bottom). In the full stack the tables of the sixth subrecord are read by index: sizes and shapes of Mid-Layer n at n − 1; alternate shapes, corner percentages and hole offsets at 0 for the top, at the layer id − 1 for a mid layer and at 31 for the bottom | S-0160, S-0302 | INFERRED | H-A-IMP-PADSTACK |
| Hole shape 0 is round, 1 square (rectangular), 2 a slot with round ends; a slot has a length along its axis, and the hole has a rotation, which the import reads as relative to the pad | S-0160, S-0302 | INFERRED | H-A-IMP-PADSTACK |
| The copper of a pad may be offset from its hole centre, per layer | S-0160, S-0302 | INFERRED | H-A-IMP-PADSTACK |
| Paste and solder mask expansions follow a rule or a manual value; the model lists no mask or paste layer for a pad, the modes and values go to the bag | S-0302 | INFERRED | H-A-IMP-PADSTACK |

## Vias, zones and shapes

| fact | source | label | hypothesis |
|---|---|---|---|
| A via spans from its start layer to its end layer; it is a through via when they are the outer layers, blind when one is, buried otherwise (every via of the documents compared is a through via) | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_import_oracle.py) | H-A-IMP-LAYERS |
| A polygon of type `Polygon` on a copper layer is a zone: its vertices are the outline (the last repeats the first), `NET` its net, `NAME` its name | S-0161, S-0285, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_import_oracle.py) | H-A-IMP-ZONE |
| `POURINDEX` gives the pour order, the lowest first; the zone poured first gets the highest model priority | S-0161 | INFERRED | H-A-IMP-ZONE |
| The regions of `Regions6` that carry a polygon's index are its poured copper; tracks and arcs with a polygon index are the strokes of a hatched pour | S-0161, S-0285 | INFERRED | H-A-IMP-ZONE |
| The board outline of the board record becomes graphics on `Edge.Cuts`, one per segment, a line or an arc | S-0161 | INFERRED | H-A-IMP-FRAME |
| A free fill is a rectangle given by two corners and a rotation about its centre; a free region is a polygon | S-0160, S-0285 | INFERRED | H-A-IMP-FRAME |

## Rules

Rule records go through `read.rules.map_rules` (c0042): `rule-file.md` holds the kinds that map and the
scope grammar. The adapter keeps each mapped rule and replaces its id, native id, provenance and bag.

| fact | source | label | hypothesis |
|---|---|---|---|
| The lower a rule's priority number the higher its priority, 1 the highest; a disabled rule takes no part in the check, so it is not mapped | S-0286 | INFERRED | H-A-RD-PRJ-RULE-MAP |

## Identifiers

| entity | native id |
|---|---|
| design header, board, rule set | `altium_pcbdoc`, `altium_schdoc` or `altium_prjpcb` |
| net | `net:<name>` |
| net class | `class:<name>` |
| schematic component | `cmp:<unique-id path>` |
| pin | `<component native id>:pin:<designator>` |
| module | `module:<unique-id path of its sheet symbols>` |
| footprint instance | `fp:<UNIQUEID of the PCB component>` |
| component synthesised from a PCB document | `cmp:<SOURCEUNIQUEID>`, else `cmp:fp:<UNIQUEID>` |
| pad | `pad:<id of UniqueIDPrimitiveInformation>`, else `<footprint native id>:pad:<name>:<k>` |
| layer, stack layer, stack-up | `layer:<neutral name>`, `stack:<position>`, `stackup` |
| zone | `zone:<polygon UNIQUEID>` |
| rule | `rule:<RULEKIND>:<NAME>:<neutral kind>` |
| library definition | `<library>:<name>` |

Every other entity gets a content id from its model fields and an occurrence counter.

## Extension-bag keys

The closed table `adapter.EXT_KEYS`. A value is text of the record or a decimal integer.

| key | on | value |
|---|---|---|
| `u` | any entity | `<field>=<integer>,…`: the original integers of inexact length conversions |
| `deg` | any entity | `<field>=<float.hex()>,…`: the stored doubles of inexact angles |
| `layer_id` | layer | the Altium layer id |
| `altium_name` | layer | the name the board record gives the layer |
| `plane_net` | layer | the net of an internal plane |
| `origin` | board | `ORIGINX,ORIGINY` as written |
| `stack_mode` | pad | the stack mode when it is not 0 |
| `corner_percent` | pad | the corner percentage of a rounded rectangle |
| `shape` | pad | the shape number of a `custom` pad |
| `paste` | pad | `<mode>,<expansion in units>` |
| `mask` | pad | `<mode>,<expansion in units>` |
| `plated` | pad | `0` for a hole that is not plated |
| `via_layers` | via | `<start id>,<end id>` when they are not the outer layers of the chain |
| `net` | graphic | the net name of a copper shape |
| `pour_index` | zone | `POURINDEX` |
| `hatch_style` | zone | `HATCHSTYLE` |
| `component_kind` | component | `COMPONENTKIND` when it is not 0 |
| `part_ids` | component | the unique ids of its parts, joined by commas |
| `source_designator` | footprint | `SOURCEDESIGNATOR` |
| `source_lib_reference` | footprint | `SOURCELIBREFERENCE` |
| `electrical` | pin | a pin type number outside the table |
| `pin_symbols` | symbol definition | `<number>=<inner edge>,<outer edge>,<inside>,<outside>;…` for pins with other symbols |
| `alias` | net | one pair per further name |
| `classes` | net | the other classes of a net in several classes |
| `label` | bus | the bus identifier's text |
| `harness_type` | interface | the harness type |
| `scope1` | rule | `SCOPE1EXPRESSION` |
| `scope2` | rule | `SCOPE2EXPRESSION` |
| `rule_kind` | rule | `RULEKIND` |

## Differences from KiCad's importer

`tests/kicad/altium/test_import_oracle.py` compares the import with `kicad-cli pcb import --format altium`
10.0.6 on the two authored documents and on the seven `altium-pcbdoc` corpus rows (2026-10-05). KiCad holds
a converted length in steps of 10 nm and moves the board, so positions are compared after one translation
and within 10 nm. Each difference below comes from KiCad's importer, is excluded by kind and is counted by
the test; no file is excluded. Compared and equal: 424 footprints (side, rotation, position), 1 526 pads (net,
position in the footprint; size and round drill for 1 465 simple ones), 3 069 tracks and 24 arcs with a net,
1 166 vias and 44 zone outlines; the copper layer count of every document.

| kind | what KiCad does | how the oracle treats it |
|---|---|---|
| references | KiCad names a footprint after the shown string of its designator text, with the prefix `UNK` before a digit (S-0161); the import takes `SOURCEDESIGNATOR` first | footprints are paired by KiCad's name; a name that several footprints share is not compared (3 footprints of one row) |
| free pads | KiCad makes a footprint without a reference of a pad that belongs to no component, as the import does | counted, not paired (20 pads of four rows) |
| pads without a number | KiCad returns an unplated hole without its pad number and does not return a pad on a paste layer (`pcb-read.md`, "What KiCad does not import") | the numbered pads on copper are compared; the others are left out |
| pad size and drill | KiCad's pad of another stack mode or of a custom shape is not a plain pad | size and round drill are compared for simple pads of a plain shape only |
| copper tracks and arcs without a net | KiCad returns no track for them (in one row some come back as graphic lines on the copper layer); the import keeps them as tracks without a net | counted, not compared (123 tracks of three rows) |
| zone vertices | KiCad drops an outline vertex that repeats its neighbour | the import's outline is compared without such a vertex (2 vertices of two rows) |
| zones with an arc | the model keeps no arc vertex, so the import's outline is empty | not compared (6 zones of two rows) |
| board edge | KiCad draws the edge from the board record and adds graphics of other layers to `Edge.Cuts` | not compared: the requirement lists no edge comparison |
