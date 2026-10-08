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
| An internal plane (a layer of the chain with an id from 39 to 54, on a net or not) is stored in negative: any object on its layer is a place without copper, a line that splits a plane is placed on that layer and set to no net, and the rest of the layer is copper that the document does not store. A free track, arc, fill, region or text on such a layer is therefore no copper and no drawing of the board: the import makes no entity of it, with or without a net, counts it as `plane-cuts` and holds the count of each layer in its bag (`plane_cuts`). The two public documents with planes hold 74 and 43 such tracks and no other free primitive there, and KiCad's import of each holds exactly that many tracks fewer than a read that keeps them, and none on a plane layer | S-0531, S-0550, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06; test_triangle_level5.py) | H-A-IMP-PLANE-CUT |
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
| The holes of a poured region are free of its copper: the fill is the region's outline without its holes, and another region of the same polygon may lie inside a hole as an island. The model holds the fill as one ring with a bridge of zero width to each hole (`geometry.keyhole_ring`); a hole outside its outline is dropped and reported (`altium.import.zone-hole-outside`) | S-0160 (the holes of a region record), S-0020 (`kicad-cli pcb import` on the document of S-0172: the same pieces of copper per net in both reads, five islands among them) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06; test_triangle_level5.py) | H-A-IMP-ZONE-HOLES |
| The board outline of the board record becomes graphics on `Edge.Cuts`, one per segment, a line or an arc | S-0161 | INFERRED | H-A-IMP-FRAME |
| A free fill is a rectangle given by two corners and a rotation about its centre; a free region is a polygon | S-0160, S-0285 | INFERRED | H-A-IMP-FRAME |

## Primitives of a component

Change c0126. Until then the import counted these records as `footprint-graphics` and made no entity of
them.

| fact | source | label | hypothesis |
|---|---|---|---|
| A track, an arc, a fill, a region and a text carry in their prefix, at offset 7, the index of the component they belong to (`0xFFFF`: none). The primitives of a placed component are stored at absolute board coordinates with that index, and a document holds no footprint definition (`pcb-records.md`, the common prefix; `pcb-document.md`, "Components"). The import gives such a primitive to the footprint of its component: a track is a `line`, an arc an `arc` (a full turn: a `circle`), a fill a filled `rect` or, when it is turned against the footprint, a filled `polygon`, and a region a filled `polygon`, as for a library footprint, in the order tracks, arcs, fills, regions and, within each, record order | S-0160, S-0161, S-0150 | INFERRED | H-A-IMP-FPGFX |
| The points of such a graphic are taken into the footprint's frame with the inverse of the placement of its component (position and angle, no mirror), the transform of its pads, so a footprint on the bottom side holds mirrored coordinates and its items name the layers they lie on. This is Fenolite's reading of the record values, not a field of the format | S-0161 | INFERRED | H-A-IMP-FPGFX |
| A text of a component whose designator flag is set is the component's designator, and one whose comment flag is set its comment (`pcb-read.md`, `TextRecord.is_designator` and `is_comment`). The first of each gives the field `Reference` or `Value` of the footprint: the place, the layer, the height, the stroke width, and the angle relative to the footprint; the string stays in the component. A further designator or comment text of the same component, and every other text of a component, is a text of the footprint with its string as stored | S-0160, S-0002 | INFERRED | H-A-IMP-FPGFX |
| `NAMEON` and `COMMENTON` of a component record say whether its designator and its comment are shown (`pcb-read.md`, `ComponentRecord.name_on` and `comment_on`); they give `visible` of the two fields. A record without the key gives a visible field: Fenolite's choice, the default of a field of the model | S-0160, S-0161 | INFERRED | H-A-IMP-FPGFX |
| An arc of a component keeps its record (centre, radius, angles, in the document's frame) in the pair `arc`, as a free arc does since change c0127; a graphic of a component on a copper layer keeps its net name in the pair `net`; a primitive of a component on an internal plane is no item of its footprint (a line there is a cut in the plane, change c0124) and stays counted as `footprint-graphics` | S-0160, S-0161 | INFERRED | H-A-IMP-FPGFX |

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
| `plane_cuts` | layer | the number of free primitives on the layer of an internal plane that the import left out: they cut the plane and are no copper |
| `origin` | board | `ORIGINX,ORIGINY` as written |
| `stack_mode` | pad | the stack mode when it is not 0 |
| `corner_percent` | pad | the corner percentage of a rounded rectangle |
| `shape` | pad | the shape number of a `custom` pad |
| `paste` | pad | `<mode>,<expansion in units>` |
| `mask` | pad | `<mode>,<expansion in units>` |
| `plated` | pad | `0` for a hole that is not plated |
| `via_layers` | via | `<start id>,<end id>` when they are not the outer layers of the chain |
| `pad_removed` | via | `<layer id>,…`: the Altium layer ids, in ascending order, for which the table at 209 of the via record holds a non-zero byte: the layers on which the via has no pad shape (change c0132; `pcb-copper.md`, "Via"). The model's via holds one diameter, so the pair is the only place that says it; it enters no id. The copper check on Altium input reads it ("Clearance of the copper check"); a write counts it and writes a pad on every layer |
| `arc` | arc, graphic of kind `arc` | `<centre x>,<centre y>,<radius>,<start angle>,<end angle>` of the arc record it was read from: three integers in units of 1/10 000 mil in the document's frame, and the two angles as `float.hex()` of the stored doubles (change c0127). The three points of the model do not give the record back in every case; a write of the model uses the pair when it still says the points |
| `net` | graphic | the net name of a copper shape |
| `pour_index` | zone | `POURINDEX` |
| `hatch_style` | zone | `HATCHSTYLE` |
| `component_kind` | component | `COMPONENTKIND` when it is not 0 |
| `part_ids` | component | the unique ids of its parts, joined by commas |
| `pin_pads` | component | one pair per pin map record that `pin_pad_map` does not say in full: `<pin>=<pad>,<pad>…` (no pad, or a pad that another pin holds; a record of several pads is in the map since change c0123) |
| `sheet_symbol` | module | the unique id of the sheet symbol of a `Repeat` channel |
| `channel_index` | module | the channel index of a `Repeat` channel |
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
| `cell` | rule | the pair of item kinds of a rule that holds one cell of a Clearance record's object matrix, such as `via-via` (change c0130) |
| `cells_not_lifted` | rule | on the rule of a Clearance record's generic value: the entries of its object matrix that no rule holds, as written and joined by `;` (an object kind the copper check holds no item of; change c0130) |

## The copper check and the parity comparison

What `fenolite check` needs of the import beyond the model (change c0088): the board frame of the pads
(`backends/altium/frame.py`), the clearance in force (`AltiumBackend.design_rules`) and the schematic side
of the parity comparison (`adapter/parity.py`). No record is read that the import does not read already.

### Board frame of the pads

| fact | source | label | hypothesis |
|---|---|---|---|
| A pad lies at the footprint's position plus its own position turned by the footprint's angle, with no further mirror on the bottom side, and is turned by the sum of the two angles: the inverse of how the import stores it ("Pads and padstacks"). The copper of a layer of a stack lies at the pad's position plus that layer's offset | S-0160, S-0302 | INFERRED | H-A-IMP-FRAME |
| The corner radius of a rounded rectangle is its corner percentage of half the shorter side (100 is fully round), the inverse of what the writer stores for KiCad's corner ratio (`pcbrecords.corner_percent`) | S-0160, S-0150 | INFERRED | H-A-IMP-PADSTACK |
| A shape the import does not resolve (an octagon, a rounded rectangle without its percentage, a rounded rectangle of a per-layer stack, whose percentage is not in the model) is checked as the rectangle of its size, which contains it; the copper check then says `approximated` | S-0160 | INFERRED | H-A-IMP-PADSTACK |
| The import reads no courtyard: the extent of a footprint is the hull of its pads' copper | S-0160 | INFERRED | H-A-IMP-FRAME |

### Clearance of the copper check

| fact | source | label | hypothesis |
|---|---|---|---|
| A polygon holds no clearance of its own: the gap its pour keeps comes from the Clearance rule that applies to it. The model's default zone clearance (0.5 mm) is therefore no value of the document, and the copper check judges a fill with the clearance rules alone (the zone's own clearance is 0, "none") | S-0530 | INFERRED | H-A-DRC-SAME |
| An internal plane is drawn in negative: a line or an arc on its layer is a void, and the rest of the layer is copper that the document does not store. The objects on the layer of a plane are no copper, and the plane's own copper is not judged. Since change c0124 the import leaves those objects out ("Layers"), so the check takes nothing out of the board; it names the planes as copper it did not judge | S-0531 | INFERRED | H-A-DRC-SAME |
| The document counts in units of 2.54 nm and the model in whole nanometres, so copper that is exactly a clearance apart in the document reads up to 4 nm closer. Measured on the seven public PCB documents: with the rule values as written, 1 447 clearance findings are short by 1 to 4 nm and by nothing else (626, 359, 118, 232 and 112 on the five documents that hold a mapped Clearance rule; four documents and 1 088 before change c0125); the clearance rules are lowered by 5 nm for the check | S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (`tests/corpus/test_altium_copper.py`, 2026-10-06) | CORPUS-VERIFIED (2026-10-06; test_altium_copper.py) | H-A-DRC-SAME |
| The slack of the copper check is one file unit per item of the pair (change c0131, the maintainer's rule of 2026-10-06): 2 × 2.54 = 5.08 nm for a pair, held as 5 whole nanometres, rounded down so that no gap is passed that the rule reports. The conversion moves a track or a via by up to 0.96 nm (a point 0.71, half a width 0.25), a vertex of a pour by 0.71 nm (1.21 at the bridge of a hole), a round or oval pad by 2.37 nm (its centre is rounded three times through the frame of its footprint) and a rectangular pad by 3.18 nm (each corner once more); an arc is judged with a band of 1 001 nm. One unit covers every item but a rectangular pad, and the pair slack every pair but a pad against a rectangular pad (5.55 and 6.36 nm). Measured on the eight public PCB documents (the heavy one included): the slack removes 6 075 findings (6 111 since change c0132 judges the vias without a pad by their holes), all 1 to 4 nm short and none between two pads, and 25 findings 8 to 20 nm short stay errors (2, 7 and 16 on three documents; 9 since change c0152, next row) | S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 (`tests/corpus/test_altium_copper.py`, 2026-10-07) | CORPUS-VERIFIED (2026-10-07; test_altium_copper.py) | H-A-DRC-SAME |
| Altium's own clearance check does not report copper 3.5 file units (8.89 nm) inside its rule: on the public document of S-0172 Altium Designer 26.5.0, with the Clearance rules alone, shows no violation of a 5 mil rule (50 000 units) between a rectangular pad of 637 795 × 637 795 units (its edge on a half unit) and a straight track segment 50 000 units wide whose edge the document's integers put 49 996.5 units from the pad's edge, nor between that pad and the six other segments of the loop (49 997.6 units from its corners). The shortfall is in the document: the import reads the straight gap as 126 991 nm against an exact 126 991.11, and no arc or polygonised end takes part. What Altium's tolerance is, no public source states; it is at least 3.5 units. The copper check therefore lowers every clearance rule by `CLEARANCE_SLACK_NM` = max(5, ceil(8.89)) = 9 nm (change c0152): rounded up because the model's gap is itself whole nanometres, so 8 nm would still report the pair; the unit's slack of the previous row is inside it, and so is the worst case of the conversion for a pad against a rectangular pad (6.36 nm). Measured on the eight public PCB documents: of the 25 findings of the previous row, 16 that are 8 or 9 nm short go, and 9 that are 10 to 20 nm short stay errors (1 on `-01`, 8 on `-08`); none of these was checked in Altium | S-0616, S-0172 (`tests/corpus/test_altium_copper.py`, 2026-10-08) | ALTIUM-VERIFIED(author-report) (AD 26.5.0; 2026-10-08; no artefact) | H-A-DRC-SAME |
| A via without a pad shape on a layer is copper there by its hole alone: the via is drilled through the layer, copper of another net inside the hole would meet the plated barrel, and a polygon keeps its clearance to the hole. The copper check therefore judges such a via with its diameter on the layers where it has a pad and with its drill as diameter on the layers that the pair `pad_removed` names; nothing is left unjudged. Measured on the one public document that holds such vias: the 28 shorts between seven of them and the pours of other nets, and one clearance finding of a track beside one, are gone, and no other finding of the document changes | S-0600, S-0601 (`tests/corpus/test_altium_copper.py`, 2026-10-07) | INFERRED | H-A-IMP-VIA-PADLESS |
| A Clearance record that is enabled and that the rule table does not map (a matrix of differing clearances, a scope outside the grammar, a key outside the table) may govern any pair: the check counts such records and says that its rules are incomplete. A record whose scope is a kind of layer the board does not hold governs no pair and is not counted (`rule-file.md`, "Layer scopes of Clearance"; the check maps the records with the board's copper layers, as the import does) | S-0286, S-0462, S-0555 | INFERRED | H-A-RD-PRJ-RULE-MAP |

### Schematic side of the parity comparison

| fact | source | label | hypothesis |
|---|---|---|---|
| The schematic names a footprint by the file of its footprint model and the model's name, and the PCB document by the library the component was placed from and the pattern: only the name is common. On the five public project sets 503 placed footprints differ in the library alone, and 5 in the name too | S-0174, S-0175, S-0176, S-0187, S-0188 (`tests/corpus/test_altium_copper.py`, 2026-10-06) | CORPUS-VERIFIED (2026-10-06; test_altium_copper.py) | H-A-DRC-PARITY |
| The name the import gives a net is not always the name the PCB document holds for it (a net of a repeated sheet, a net named by precedence): on the two hierarchical sets 139 pads (129 and 10) are on a net of another name whose pads are the same. A schematic net and a board net are one net when, over the pads both hold on a net, every pad of the one is on the other | S-0187, S-0188 (`tests/corpus/test_altium_copper.py`, 2026-10-06) | CORPUS-VERIFIED (2026-10-06; test_altium_copper.py) | H-A-DRC-PARITY |
| A pin names the pad of its own designator unless the component holds a pin-to-pad map, which then decides | S-0130, S-0131 | INFERRED | H-A-IMP-NETLIST |

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
| references | KiCad names a footprint after the shown string of its designator text, with the prefix `UNK` before a digit (S-0161); the import takes the designator text too, and `SOURCEDESIGNATOR` only without one (since change c0045; before it took `SOURCEDESIGNATOR` first, which the components of a repeated sheet share) | footprints are paired by KiCad's name; a name that several footprints share is not compared (3 footprints of one row) |
| free pads | KiCad makes a footprint without a reference of a pad that belongs to no component, as the import does | counted, not paired (20 pads of four rows) |
| pads without a number | KiCad returns an unplated hole without its pad number and does not return a pad on a paste layer (`pcb-read.md`, "What KiCad does not import") | the numbered pads on copper are compared; the others are left out |
| pad size and drill | KiCad's pad of another stack mode or of a custom shape is not a plain pad | size and round drill are compared for simple pads of a plain shape only |
| copper tracks and arcs without a net | KiCad returns no track for them (in one row some come back as graphic lines on the copper layer); the import keeps them as tracks without a net, except on the layer of an internal plane, where it makes no track either ("Layers", change c0124) | counted, not compared (6 tracks of one row; until change c0124 also the 74 and 43 lines on the planes of two rows) |
| zone vertices | KiCad drops an outline vertex that repeats its neighbour | the import's outline is compared without such a vertex (2 vertices of two rows) |
| zones with an arc | the model keeps no arc vertex, so the import's outline is empty | not compared (6 zones of two rows) |
| board edge | KiCad draws the edge from the board record and adds graphics of other layers to `Edge.Cuts` | not compared: the requirement lists no edge comparison |
