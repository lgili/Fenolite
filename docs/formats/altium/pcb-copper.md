# Altium PCB document: copper (`.PcbDoc`)

This page states, in Fenolite's own words, what the experimental writer `fenolite.backends.altium.pcbdoc`
(change c0038) relies on to write copper into an Altium PCB document: routed tracks and arcs, vias,
polygon pours, a layer stack of two or four copper layers, net classes and design rules. The document
itself is in `pcb-document.md`, the primitive records in `pcb-records.md`.

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0161),
  AltiumSharp **version 1 only** (S-0150, commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`; version 2 is
  not a source), a GPL-3.0 format page read for facts, without source code (S-0173), Altium's
  documentation (S-0195, S-0196, S-0197, S-0198) and `kicad-cli` run as a subprocess (S-0020, S-0166).
- Six documents saved by Altium Designer and published under Apache-2.0, BSD-2-Clause and MIT (S-0172,
  S-0174, S-0175, S-0176, S-0199, S-0200) were read in a scratch folder with the test readers. They are
  not in the repository and nothing of them is copied: the rows state the rules their streams follow.
  Nothing was decompiled, and no third-party code was transcribed.
- Every Altium row is `INFERRED` under an `H-A-PCB-CU-*` hypothesis until the maintainer reports Part C of
  `docs/evidence/altium-pcb.md`. Rows that only say what KiCad's importer reads name `H-A-PCB-CU-KICAD` or
  `H-A-PCB-CU-ROUNDTRIP`; they carry `ORACLE-VERIFIED(kicad-cli)` once their oracle
  (`tests/kicad/altium/test_pcbdoc_copper_oracle.py`, `test_copper_from_oracle.py`) passed on 10.0.6, and
  that label says nothing about Altium.
- `tests/unit/test_format_facts.py` checks the tables.

## Tracks and arcs

| fact | source | label | hypothesis |
|---|---|---|---|
| A routed track is the record of a footprint line (`pcb-records.md`): type 4 with one subrecord, the common 13-byte prefix (layer byte, two flag bytes, net index at 3, polygon index at 5, component index at 7), then x1, y1, x2, y2 and the width as 32-bit values. A free routed track has the component index `0xFFFF`, the polygon index `0xFFFF` and the index of its net in `Nets6` (`0xFFFF` without a net). A routed arc is the arc record (type 1) with the same prefix | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-TRACK |
| Altium saves a track with 49 bytes and an arc with 60: after the short form come a solder-mask expansion, a paste-mask expansion, a 32-bit long layer id and a keep-out byte. Readers accept the short forms: KiCad needs 36 bytes for a track and 47 for an arc, and Altium Designer 26.5 opens them in the document of c0035 (`pcb-document.md`) | S-0160, S-0173, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-TRACK |
| The first flag byte of a routed track is `0x0C` in nearly every saved track; bit 2 clear means locked | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-TRACK |
| The layer byte of a track on an inner signal layer is 2 to 31 (Mid-Layer 1 to 30). A saved board holds tracks with the layer bytes 3 and 5 (Mid-Layer 2 and 4), flags `0C`, polygon and component `0xFFFF` | S-0002, S-0160, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-TRACK |
| KiCad reads a 36-byte track and a 47-byte arc with a net index on layers 1, 2, 3 and 32 as tracks and arcs on `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` with that net | S-0160, S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |

## Via

| fact | source | label | hypothesis |
|---|---|---|---|
| A via is record type 3 with one subrecord. It starts with the common 13-byte prefix on layer 74 (Multi-Layer), then, as 32-bit values, x at offset 13, y at 17, the diameter at 21 and the hole at 25, and as bytes the start layer at 29 and the end layer at 30 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0173, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| A through via has start layer 1 and end layer 32 on any layer count: the vias of the four-layer board say 1 and 32 too | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| Altium saves a via subrecord of 321 bytes (351 with one polygon-connect entry of 30 bytes). AltiumSharp version 1 writes 209 bytes. KiCad reads a simple via when the subrecord has at most 74 bytes and more fields past 74, 246 and 307 bytes; it needs at least 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0173, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| Fields after offset 30 of the 321-byte form, with the values of a plain through via: 31 the plane-connection style (byte, 0); 32 the thermal-relief air gap (32-bit, 10 mil); 36 the conductor count (16-bit, 4); 38 the conductor width (32-bit, 10 mil); 42 and 46 two lengths of 20 mil (plane relief expansion and plane clearance); 50 the paste expansion (0); 54 the solder-mask expansion (4 mil); 61 to 64 four cache flags (0); 66 the solder-mask cache state (0); 74 the diameter stack mode (byte, 0 = simple); 75 to 202 thirty-two 32-bit diameters, one per signal layer, each the via's diameter for a simple via | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0173, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| Fixed bytes of the tail, constant in the saved 321-byte vias: at 203 a 16-bit 15 and at 205 a 32-bit 259 (where version 1 stops, at byte 208); at 242 the back solder-mask expansion (32-bit, 4 mil); at 254 the byte `0x2A`; at 259 and 275 two 16-byte ids; at 291 and 295 two hole tolerances `0x7FFFFFFF`; at 300 the polygon-connect count (32-bit, 0); at 304 its entry size (32-bit, 30); at 308 the byte 9; at 320 the byte 1. The meaning of the bytes at 203, 254, 308 and 320 is not known | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0173, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| Flags of a via: `0x0C` unlocked and untented; bit 5 tents the top, bit 6 the bottom. The net index is at 3; polygon and component are `0xFFFF` for a free via | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| Vias are not listed in `UniqueIDPrimitiveInformation`; only pads are | S-0174, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| A blind, buried or micro via needs a via type and a drill pair in the layer stack. The documents read hold one pair only (`LAYERPAIR0LOW=TOP`, `LAYERPAIR0HIGH=BOTTOM`) | S-0197, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-VIA |
| KiCad reads a 321-byte via with start 1 and end 32 as a through via between `F.Cu` and `B.Cu` with its net, position, diameter and drill; start 1 and end 2 reads as a blind via, start 2 and end 3 as a buried one | S-0160, S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |

## Polygon pour

| fact | source | label | hypothesis |
|---|---|---|---|
| A polygon pour is one property record of `Polygons6`: the seven common keys with `LAYER` (`TOP`, `BOTTOM`, `MID<n>`, `PLANE<n>`), `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER`, `REMOVEDEAD`, `GRIDSIZE`, `TRACKWIDTH`, `HATCHSTYLE`, `USEOCTAGONS`, `MINPRIMLENGTH`, eight keys per vertex (`KIND<k>`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>`; the first vertex repeated last), `SHELVED`, `RESTORELAYER`, `RESTORENET`, `REMOVEISLANDSBYAREA`, `REMOVENECKS`, `AREATHRESHOLD`, `ARCRESOLUTION`, `NECKWIDTHTHRESHOLD`, `POUROVERSTYLE`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS`, optionally `AUTONAME`, `OPTIMALVOIDROTATION`, optionally `OBEYPOLYGONCUTOUT`, and last `NET` (the net's index; absent without a net) | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| It is the key set of the board outline inside `Board6` (`pcb-document.md`), with a net, a name and a pour index | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| `NAME` holds the character codes of the name in decimal, joined by commas (`71,78,68` is `GND`). Altium's generated names have the form `<net>_L<layer position, two digits>_P<number, three digits>` with `AUTONAME=TRUE` | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| `HATCHSTYLE` is `Solid`, `45Degree`, `90Degree`, `Horizontal`, `Vertical` or `None`. A solid pour is built from regions, a hatched one from tracks and arcs | S-0160, S-0196 | INFERRED | H-A-PCB-CU-REPOUR |
| `POURINDEX` is the pour order from 0, unique in a document: a lower index is poured first. `POUROVER` and `POUROVERSTYLE` choose which same-net copper a pour covers; `REMOVEDEAD` removes islands. Saved solid pours hold `POUROVER=TRUE`, `REMOVEDEAD=TRUE`, `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `POUROVERSTYLE=1` | S-0196, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| The poured copper is stored apart: one region per piece in `Regions6` with the polygon's index in its prefix, and the same number of records in `ShapeBasedRegions6` | S-0161, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| The outline alone is a state Altium saves: a saved board holds a polygon that is not shelved and has no region, track or arc, and its keys differ from a poured neighbour only in pour-over, index, net and name. No key marks a polygon as poured | S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| Altium documents the state: an unpoured polygon is drawn by its outline only; "Tools » Polygon Pours » Repour All" (or repour selected, modified or violating polygons) fills it; the Unpoured Polygon rule reports such polygons when the rule exists | S-0195, S-0196 | INFERRED | H-A-PCB-CU-REPOUR |
| Clearance and connection of a pour come from design rules (Clearance, Polygon Connect Style), not from the polygon record | S-0196, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| A polygon on a mid layer has `LAYER=MID<n>` and the keys of a polygon on an outer layer | S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| KiCad imports a polygon as a zone with its layer, net and outline; without regions the zone has no fill. It does not take the polygon's name. A lower pour index gives a higher zone priority | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |

## Layer stack

| fact | source | label | hypothesis |
|---|---|---|---|
| Layer ids: 1 top, 2 to 31 Mid-Layer 1 to 30 (signal), 32 bottom, 39 to 54 Internal Plane 1 to 16. Long ids: signal `0x01000000 + id` (top 16777217, Mid-Layer 1 16777218, Mid-Layer 2 16777219), bottom `0x0100FFFF`, plane `0x01010000 + n` (16842753, 16842754), dielectric `0x01040000 + n` (17039361 …) | S-0002, S-0160, S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| The numbered keys link the copper stack through `LAYER<id>PREV` and `LAYER<id>NEXT` (0 before the first and after the last): 1 → 2 → 3 → 32 for four signal layers, 1 → 3 → 5 → 32 on a board with Mid-Layer 2 and 4, 1 → 39 → 40 → 32 for two planes. Each linked layer holds `NAME`, `PREV`, `NEXT`, `MECHENABLED`, `COPTHICK` and the dielectric below it (`DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL`); the bottom layer keeps the default dielectric | S-0160, S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| The mid-layer number is free: a saved stack uses Mid-Layer 2 and 4 and no Mid-Layer 1. A layer's position comes from the chain, not from its number | S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| A signal mid layer in the physical lists (`V9_STACK_LAYER<i>`, `LAYER_V8_<i>`, `V9_CACHE_LAYER<i>`) has `NAME` (`Mid-Layer <n>`), `LAYERID`, `USEDBYPRIMS`, `COPTHICK` and `COMPONENTPLACEMENT=1`, the keys of the top layer, and no `COPPERORIENTATION`. An unused mid layer of the cache list has `COMPONENTPLACEMENT=0` | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| An internal plane in the lists has `NAME` (`Internal Plane <k>`), `LAYERID`, `USEDBYPRIMS`, `COPTHICK` and `PULLBACKDISTANCE` (`20mil`), and no `COMPONENTPLACEMENT` | S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-PLANE |
| The physical stack grows by one dielectric and one copper entry per inner layer. With the overlay entries a four-layer stack has 13 entries (paste, overlay, solder, top, dielectric, inner, dielectric, inner, dielectric, bottom, solder, overlay, paste); two saved boards leave the overlays out and have 11 | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| Dielectric names and long ids are labels, not positions. One saved board numbers them from the top: `Dielectric 1`, `2`, `3` with the ids 17039361, 17039362, 17039363 | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| `DIELTYPE` is 1 on a core, 2 on a prepreg, 3 on solder resist and 0 on the untouched default (12.6 mil, `4.800`, `FR-4`: every unlinked numbered layer and the two-layer stack of c0035). `DIELCONST` has three decimals; `DIELHEIGHT` and `COPTHICK` are mil text. `DIELLOSSTANGENT` is optional | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| Cache list (`V9_CACHE_LAYER<i>`): every layer appears once. In the document of 2023 the list is the 102 layers of a two-layer document in their order (the outer run paste, overlay, solder, top, `Dielectric 1`, bottom, solder, overlay, paste; then the 30 mid layers, the 16 planes and the rest) followed by the further dielectrics of the stack; a mid layer or a plane of the stack keeps its place in its run and carries its stack keys (and the sub-stack keys of a document). The two documents of 2021 order the list in another way (the stack last) | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| Layer sets: `&Signal Layers` lists `MultiLayer`, `TopLayer`, the signal mid layers (`MidLayer1`, `MidLayer2`) and `BottomLayer`; `&Plane Layers` lists the planes of the stack (`InternalPlane1`, `InternalPlane2`) with `LAYERSET3ACTIVELAYER.7=PLANE1`, and is empty with `UNKNOWN` without one; `&All Layers` lists both kinds, the mid layers between `TopLayer` and `BottomLayer` and the planes after `BottomPaste` | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| `TOGGLELAYERS` has one flag per numbered layer; a saved board sets all of them, another only the enabled layers. The routing keys (`ROUTINGDIRECTION…`, `…_MRLASTWIDTH`) name all 32 signal layers whatever the stack | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository), S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |
| Plane net: `PLANE<k>NETNAME` in the first line of `Board6` names the net of Internal Plane k; `(No Net)` otherwise. The key has no effect for a plane outside the stack | S-0176, S-0199 (files kept outside the repository) | INFERRED | H-A-PCB-CU-PLANE |
| What a saved plane holds besides: one `Polygons6` record with `POLYGONTYPE=Split Plane` on `PLANE<k>` (ten keys, the vertices and `NET`) and pull-back tracks and arcs on the plane's layer, without a net and with the polygon index `0xFFFE`. It has no region. All of it derives from the outline, the pull-back distance and the net. Whether Altium rebuilds it when it is missing is not known | S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-PLANE |
| Altium treats a plane as a negative layer with its own connect and clearance rules (Plane Connect, Plane Clearance); a pour on a signal layer is a polygon | S-0198, S-0196 | INFERRED | H-A-PCB-CU-PLANE |
| A stack that mixes one signal mid layer and one plane (1 → 39 → 3 → 32 or 1 → 2 → 39 → 32) is composed from the two entry forms above. No saved document with such a stack was read | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-PLANE |
| The bottom layer of the saved four-layer boards carries `COPPERORIENTATION=1` (and the lower plane of one board). The document of c0035 does not write the key and opens | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |

## Net classes

| fact | source | label | hypothesis |
|---|---|---|---|
| One property record of `Classes6` per class: the seven common keys with `LAYER=MULTILAYER`, `NAME`, `KIND`, `SUPERCLASS`, optionally `AUTOGENERATEDCLASS`, the members `M0`, `M1`, … (net names for a net class), `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE`, `UNIQUEID`, optionally `AUTOGENERATEDCLASSKIND` | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-CLASS |
| `KIND`: 0 net, 1 component, 2 from-to, 3 pad, 4 layer, 6 differential pair, 7 polygon | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-CLASS |
| Altium saves 15 to 20 classes: the super classes (`All Nets`, `All Components` and the like, `SUPERCLASS=TRUE`) and generated component classes. The document of c0035 writes none and opens | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-CLASS |
| KiCad makes a net class of each `KIND=0` class that is not a super class; `pcb import` writes no project file, where KiCad 10 keeps classes, so the import cannot be compared | S-0161, S-0020 | INFERRED | H-A-PCB-CU-CLASS |

## Rules

| fact | source | label | hypothesis |
|---|---|---|---|
| Each rule of `Rules6` is a 16-bit rule-kind number, then one property block. Numbers: 0 Clearance, 2 Width, 6 PlaneConnect, 9 RoutingLayers, 11 RoutingVias, 12 PlaneClearance, 20 PolygonConnect, 62 UnpouredPolygon | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| Common keys of a rule, in order: the seven common keys with `LAYER=TOP`, `RULEKIND`, `NETSCOPE`, `LAYERKIND=SameLayer`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY` (1 is the highest), `COMMENT`, `UNIQUEID`, `DEFINEDBYLOGICALDOCUMENT=FALSE`, then the kind's keys | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| Clearance (`RULEKIND=Clearance`): `NETSCOPE=DifferentNets`, `GAP`, `GENERICCLEARANCE`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT`, `OBJECTCLEARANCES` (empty for one value) | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| Width (`RULEKIND=Width`): `NETSCOPE=AnyNet`, `MAXLIMIT`, `MINLIMIT`, `PREFEREDWIDTH` (this spelling) | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| Routing Via Style (`RULEKIND=RoutingVias`): `NETSCOPE=AnyNet`, `HOLEWIDTH`, `WIDTH`, `VIASTYLE=Through Hole`, `MINHOLEWIDTH`, `MINWIDTH`, `MAXHOLEWIDTH`, `MAXWIDTH` | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| A class rule has `SCOPE1EXPRESSION=InNetClass('<name>')` and a higher priority (a lower number) than the `All` rule of its kind; a rule for everything has `SCOPE1EXPRESSION=All` and `SCOPE2EXPRESSION=All` | S-0161, S-0174 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |
| Altium saves 39 to 41 rules of many kinds. The document of c0035 writes none and opens; whether Altium accepts three kinds without the rest is not known | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-RULES |

## Oracle

| fact | source | label | hypothesis |
|---|---|---|---|
| KiCad builds the copper stack from the numbered keys only, by chain position: 1 → 2 → 3 → 32 gives `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, the inner layers of type `signal`; a plane in the chain (39 or 40) becomes the copper layer of its position with the type `power`. This holds for the chains 1 → 39 → 40 → 32, 1 → 39 → 3 → 32 and 1 → 2 → 39 → 32, without any split-plane record | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| A track or polygon written on Mid-Layer 2 of the chain 1 → 39 → 3 → 32 arrives on `In2.Cu` | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| KiCad warns once per internal plane that is outside the stack ("could not be mapped"): sixteen warnings without a plane in the chain, fifteen with one, fourteen with two | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| A plane's net is not in the imported board: KiCad makes zones from split-plane records only. Net classes and rules give no error and are not in the imported `.kicad_pcb` | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| Copper copied from a KiCad board into the document and imported back equals the source board's copper | S-0161, S-0166, S-0020 | INFERRED | H-A-PCB-CU-ROUNDTRIP |

## Not written

- The 49-byte track and the 60-byte arc: their tails add nothing the model holds, and the short forms
  open in Altium Designer 26.5 (`H-A-PCB-CU-TRACK`).
- `Regions6` and `ShapeBasedRegions6`: polygons are written unpoured, and a zone's fills are not copied
  (`H-A-PCB-CU-REPOUR`). Hatched pours, shelved polygons and polygon cutouts.
- Blind, buried and micro vias, via types and a second drill pair; tented vias; the two 16-byte ids of a
  via (zero); the polygon-connect entry of the 351-byte form.
- The `Split Plane` polygon record and the pull-back tracks of a plane, split planes, and the Plane
  Connect and Plane Clearance rules (`H-A-PCB-CU-PLANE`): Altium's defaults apply.
- `COPPERORIENTATION`, `DIELLOSSTANGENT`, the hole-shape pairs (`HOLESHAPEHASHSIZE=0`).
- Super classes, generated component classes and every class kind but 0.
- Every rule kind but Clearance, Width and Routing Via Style; tear-drops; differential pairs.

## Fenolite's choices

- **Layers.** `F.Cu` is layer 1 (`TOP`), `In1.Cu` as a signal layer is Mid-Layer 1 (id 2, `MID1`),
  `In2.Cu` Mid-Layer 2 (id 3, `MID2`), `B.Cu` layer 32 (`BOTTOM`). A signal inner layer keeps its id
  whatever the other inner layer is. Planes are numbered from the top: the first inner layer that is a
  plane is Internal Plane 1 (id 39), the second Internal Plane 2 (id 40). No primitive is written on a
  plane. Only stacks of two and of four copper layers are written.
- **Tracks and arcs.** The short forms (36 and 47 bytes) with flags `0C 00`, after the component
  primitives in `Tracks6` and `Arcs6`, sorted by stack position of the layer, net name, start, end, width
  and entity id. Points are converted like placed points (`pcb-document.md`, frame).
- **Vias.** The 321-byte form with the values of the "Via" table and zero in every other byte, the two
  ids included; flags `0C 00` (not tented); start 1 and end 32; sorted by net name, position, diameter and
  entity id. Through vias only.
- **Polygons.** One record per zone layer, solid, in the key order of the first row of "Polygon pour"
  without `OBEYPOLYGONCUTOUT`: `POUROVER=TRUE`, `REMOVEDEAD=TRUE`, `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`,
  `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`, line vertices, `SHELVED=FALSE`,
  `RESTORELAYER=UNKNOWN`, an empty `RESTORENET`, `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`,
  `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`,
  `POUROVERSTYLE=1`, `IGNOREVIOLATIONS=FALSE`, `OPTIMALVOIDROTATION=TRUE`. The name is the zone's name, or
  `<net name>_L<layer position from 01>_P<pour index, three digits>` in upper case with `AUTONAME=TRUE`
  (`NONET` without a net). `POURINDEX` counts from 0 in the order of falling zone priority, then net name,
  first outline point, zone id and stack position. No region is written.
- **Stack.** The numbered keys link the copper ids in order. Each linked layer but the bottom carries the
  dielectric below it. The physical lists (`V9_STACK_LAYER<i>` and the head of `LAYER_V8_<i>`) hold 13
  entries with the overlays, as the nine-entry list of c0035 has them; the cache list keeps the order of
  a two-layer document and ends with `Dielectric 2` and `Dielectric 3`, the form of 2023. Dielectrics are `Dielectric 1` to `3` with the long ids 17039361 to 17039363 from the
  top. A signal mid layer has `COMPONENTPLACEMENT=1`; a plane `PULLBACKDISTANCE=20mil`, and
  `PLANE<k>NETNAME` names its net. The default values are Fenolite's: 1.4 mil copper; for two layers the
  dielectric of c0035 (`DIELTYPE=0`, 12.6 mil, `4.800`, `FR-4`), so the bytes of a two-layer document do
  not change; for four layers a prepreg of 0.2 mm, a core of 1.0 mm and a prepreg of 0.2 mm, each `4.800`
  and `FR-4`. `TOGGLELAYERS` stays 82 ones.
- **Classes.** One `KIND=0`, `SUPERCLASS=FALSE` record per net class in name order, members in name
  order, `UNIQUEID` = `project.unique_id("pcbdoc:<file name>:class:<name>")`.
- **Rules.** Written only when the document holds copper or a net class. Per kind (Clearance, Width,
  RoutingVias) one rule `<Kind>_<class>` per class that holds the value, scope `InNetClass('<class>')`,
  priorities from 1 in class-name order, then one rule named after the kind with the scope `All`.
  Defaults of the `All` rules: clearance 0.2 mm, width 0.25 mm, via 0.6 mm with a 0.3 mm hole. Width and
  via limits span the preferred value and the written copper of the rule's scope.
- **Refusals.** A blind, buried or micro via, copper on a layer outside the stack or on a plane, a zone
  without an outline and a stack of another layer count give an error and no file.
