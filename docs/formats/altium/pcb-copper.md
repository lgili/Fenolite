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
  `docs/evidence/altium-pcb.md`. The report of 2026-10-03 (Altium Designer 26.5, a trial licence) settles
  the repour, the net class and the rules: the rows of the form Fenolite writes for them carry
  `ALTIUM-VERIFIED(author-report)`. The track, via, stack and plane rows stay `INFERRED`. Rows that only say what KiCad's importer reads name `H-A-PCB-CU-KICAD` or
  `H-A-PCB-CU-ROUNDTRIP`; they carry `ORACLE-VERIFIED(kicad-cli)` once their oracle
  (`tests/kicad/altium/test_pcbdoc_copper_oracle.py`, `test_copper_from_oracle.py`) passed on 10.0.6, and
  that label says nothing about Altium.
- Change c0085 adds the rows of `H-A-PCBX-*`: stacks of more than four layers, via spans and drill
  pairs; its sources are those above, S-0470 and S-0188.
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
| A blind or buried via is the via record with the ids of the two copper layers it spans at 29 and 30, the upper layer first, and the other bytes of a through via; an end on an internal plane holds the plane's id (39 to 54). No saved document read holds such a via: every one of their 1 103 vias spans 1 to 32 | S-0160, S-0197, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-VIASPAN |
| The board record lists its drill pairs as `LAYERPAIR<i>LOW`, `LAYERPAIR<i>HIGH`, `LAYERPAIR<i>DRILLGUIDE`, `LAYERPAIR<i>DRILLDRAWING` and `LAYERPAIR<i>SUBSTACK_0` (the sub-stack's GUID) from i = 0. The seven saved documents hold the one pair `TOP` to `BOTTOM`, with `FALSE` in the two drill keys. A further pair in the same keys, its layers named `TOP`, `BOTTOM`, `MID<n>` or `PLANE<n>` as a polygon's `LAYER` is, is composed from that form; no saved document with a second pair was read, and KiCad reads no `LAYERPAIR` key | S-0197, S-0470, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-VIASPAN |
| A saved document can hold a via whose hole equals its diameter: the 32-bit values at 21 and 25 are equal, and nothing else marks the record. In the one public document that holds such vias, 48 of 242 via records are of this kind: through vias (start 1, end 32) on a net, of the 351-byte form, with the stack mode 0 at 74 and the thirty-two layer diameters equal to the diameter. No via record of the eight public documents read (2 933) holds a hole above its diameter. A rewrite of a document that was read writes such a via as the ordinary 321-byte record with the two equal values (change c0128); a build refuses it | S-0565 (the file of S-0176, kept outside the repository), census of the corpus rows `altium-third-party-pcbdoc-01` to `-08` | CORPUS-VERIFIED (8 rows; 2026-10-07) | H-A-PCBX-VIA-FULL |
| The one subrecord of a via has 299, 321, 330 or 351 bytes in the eight public documents read: 646, 2 082, 123 and 82 of their 2 933 via records. One document holds the 299 form alone, one the 321 and the 351 form, five the 321 form alone, and one the 321 form (1 647) and the 330 form (123). Every one of the 2 933 has the stack mode 0 at 74 and spans 1 to 32, and every one of at least 203 bytes has thirty-two equal layer diameters: no document read holds a via with a diameter per layer | S-0601, census of the corpus rows `altium-third-party-pcbdoc-01` to `-08` | CORPUS-VERIFIED (8 rows; 2026-10-07) | H-A-IMP-VIA-PADLESS |
| The thirty-two bytes at 209 to 240 of a via subrecord are all zero in every record of 321 and of 351 bytes read (2 164). In the 123 records of 330 bytes the bytes 210 to 213 are 1, a, b, 1 and the others zero: (a, b) is (0, 1) in 70 records, (1, 1) in 51, (0, 0) in one and (1, 0) in one. The copper layers of that document have the layer ids 1, 2, 3, 4, 5 and 32, so the byte at 208 + id belongs to the layer id; the ids are also the positions of the layers in the stack, so the document does not tell an index by id from an index by position | S-0601, census of the corpus rows `altium-third-party-pcbdoc-01` to `-08` | CORPUS-VERIFIED (8 rows; 2026-10-07) | H-A-IMP-VIA-PADLESS |
| The 330-byte form differs from the 321-byte form in two places and nowhere else: the table at 209, and nine bytes inserted at 254, before the byte `0x2A`, with a 32-bit 1 at 246 and a 32-bit 9 at 250 where the 321-byte form holds two zeros. The nine bytes are `04 00 80 01 00 71 02 00 00` in all 123 records, which are all vias of 16 mil with a hole of 8 mil. **What the count, the length and the nine bytes say is not known:** no public source read explains them. A reader does not read them and a writer does not write them | S-0601, census of the corpus rows `altium-third-party-pcbdoc-01` to `-08` | CORPUS-VERIFIED (1 row; 2026-10-07) | H-A-IMP-VIA-PADLESS |
| Altium's "Remove Unused Pad Shapes" takes the pad shape of a pad or a via off each layer on which no other object touches it; a polygon around it then keeps the clearance to the hole and not to the edge of the removed shape; an option keeps the shapes on the start and end layers, and the shapes can be restored. The page does not say how a document stores this | S-0600 | INFERRED | H-A-IMP-VIA-PADLESS |
| A non-zero byte of the table at 209 says that the via has no pad shape on that layer. On the one document that holds such bytes, measured for each of the 123 vias on each of the four inner layers: where the byte is 1 (419 places), the poured copper of another net stands at the drill radius plus the generic clearance from the via's centre, within 30 nm, at 28 places, never nearer and never at the pad radius plus the clearance, and no track of the via's net ends on the via; where the byte is 0 (73 places), a track of the via's net ends on the via at 72. No via of the 321-byte form has copper of another net nearer than its pad allows (6 588 places; the pour stands at the pad at 1 977). The table is read as indexed by layer id, as the table of diameters at 75 is; one document shows it, and its ids do not tell that index from the position in the stack | S-0600, S-0601 | INFERRED | H-A-IMP-VIA-PADLESS |
| KiCad's importer does not carry the table: `kicad-cli pcb import --format altium` writes the 1 770 vias of that document as through vias between `F.Cu` and `B.Cu` with their size and drill, and none with `remove_unused_layers`, `keep_end_layers` or `zone_layer_connections`; the 123 are written as the others are | S-0601, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-07) | H-A-PCB-CU-KICAD |
| KiCad reads a 321-byte via with start 1 and end 32 as a through via between `F.Cu` and `B.Cu` with its net, position, diameter and drill; start 1 and end 2 reads as a blind via, start 2 and end 3 as a buried one | S-0160, S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |

## Polygon pour

| fact | source | label | hypothesis |
|---|---|---|---|
| A polygon pour is one property record of `Polygons6`: the seven common keys with `LAYER` (`TOP`, `BOTTOM`, `MID<n>`, `PLANE<n>`), `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER`, `REMOVEDEAD`, `GRIDSIZE`, `TRACKWIDTH`, `HATCHSTYLE`, `USEOCTAGONS`, `MINPRIMLENGTH`, eight keys per vertex (`KIND<k>`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>`; the first vertex repeated last), `SHELVED`, `RESTORELAYER`, `RESTORENET`, `REMOVEISLANDSBYAREA`, `REMOVENECKS`, `AREATHRESHOLD`, `ARCRESOLUTION`, `NECKWIDTHTHRESHOLD`, `POUROVERSTYLE`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS`, optionally `AUTONAME`, `OPTIMALVOIDROTATION`, optionally `OBEYPOLYGONCUTOUT`, and last `NET` (the net's index; absent without a net) | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-REPOUR |
| It is the key set of the board outline inside `Board6` (`pcb-document.md`), with a net, a name and a pour index | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| `NAME` holds the character codes of the name in decimal, joined by commas (`71,78,68` is `GND`). Altium's generated names have the form `<net>_L<layer position, two digits>_P<number, three digits>` with `AUTONAME=TRUE` | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| `HATCHSTYLE` is `Solid`, `45Degree`, `90Degree`, `Horizontal`, `Vertical` or `None`. A solid pour is built from regions, a hatched one from tracks and arcs | S-0160, S-0196 | INFERRED | H-A-PCB-CU-REPOUR |
| `POURINDEX` is the pour order from 0, unique in a document: a lower index is poured first. `POUROVER` and `POUROVERSTYLE` choose which same-net copper a pour covers; `REMOVEDEAD` removes islands. Saved solid pours hold `POUROVER=TRUE`, `REMOVEDEAD=TRUE`, `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `POUROVERSTYLE=1` | S-0196, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| The poured copper is stored apart: one region per piece in `Regions6` with the polygon's index in its prefix, and the same number of records in `ShapeBasedRegions6` | S-0161, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| The outline alone is a state Altium saves: a saved board holds a polygon that is not shelved and has no region, track or arc, and its keys differ from a poured neighbour only in pour-over, index, net and name. No key marks a polygon as poured | S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| Altium documents the state: an unpoured polygon is drawn by its outline only; "Tools » Polygon Pours » Repour All" (or repour selected, modified or violating polygons) fills it; the Unpoured Polygon rule reports such polygons when the rule exists | S-0195, S-0196 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-REPOUR |
| Clearance and connection of a pour come from design rules (Clearance, Polygon Connect Style), not from the polygon record | S-0196, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-REPOUR |
| A polygon on a mid layer has `LAYER=MID<n>` and the keys of a polygon on an outer layer | S-0199, S-0200 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-REPOUR |
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
| A stack of more than four copper layers is composed from the entry forms above: the chain of the numbered keys links every copper id in order, the physical lists grow by one dielectric and one copper entry per inner layer, and the cache list ends with the further dielectrics. The saved documents read hold two and four copper layers only | S-0198, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-STACK |
| KiCad reads a chain of six layers with one plane (1 → 2 → 39 → 4 → 5 → 32) as `F.Cu`, `In1.Cu` … `In4.Cu`, `B.Cu`, the plane's position of type `power`, and warns once per internal plane outside the stack | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| The bottom layer of the saved four-layer boards carries `COPPERORIENTATION=1` (and the lower plane of one board). The document of c0035 does not write the key and opens | S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCB-CU-STACK |

## Net classes

| fact | source | label | hypothesis |
|---|---|---|---|
| One property record of `Classes6` per class: the seven common keys with `LAYER=MULTILAYER`, `NAME`, `KIND`, `SUPERCLASS`, optionally `AUTOGENERATEDCLASS`, the members `M0`, `M1`, … (net names for a net class), `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE`, `UNIQUEID`, optionally `AUTOGENERATEDCLASSKIND` | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-CLASS |
| `KIND`: 0 net, 1 component, 2 from-to, 3 pad, 4 layer, 6 differential pair, 7 polygon | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-CLASS |
| Altium saves 15 to 20 classes: the super classes (`All Nets`, `All Components` and the like, `SUPERCLASS=TRUE`) and generated component classes. The document of c0035 writes none and opens | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-PCB-CU-CLASS |
| KiCad makes a net class of each `KIND=0` class that is not a super class; `pcb import` writes no project file, where KiCad 10 keeps classes, so the import cannot be compared | S-0161, S-0020 | INFERRED | H-A-PCB-CU-CLASS |

## Classes and rules of the change order

Change c0048 adds the component classes that "Design » Update PCB Document" derives from the module sheets.

| fact | source | label | hypothesis |
|---|---|---|---|
| A saved board of a multi-sheet project holds one `KIND=1` class per schematic sheet with components: `SUPERCLASS=FALSE`, no `AUTOGENERATEDCLASS` and no `AUTOGENERATEDCLASSKIND` key, and the members `M0`, `M1`, … holding the components' designators; the other keys are those of a net class | S-0172, S-0175, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-ECO-COMPCLASS |
| The class is named after the sheet symbol of its sheet. The change order of Altium Designer 26.5 named the classes of the board example `driver` and `led`, the names of its two sheet symbols; with those two classes in the PCB document, each holding the refs of its sheet's parts, it proposes no component class (maintainer's reports of 2026-10-03 and 2026-10-04) | S-0310, S-0313 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-04; no artefact) | H-A-ECO-COMPCLASS |
| A sheet that is under no sheet symbol, the top sheet or the single sheet of a flat project, gets a class named after the sheet itself: one saved board holds such a class for the parts of its top sheet, a saved single-sheet board holds one named after its sheet, and the change order of Altium Designer 26.5 offered the class `routed`, with every component, for the flat sample `routed.SchDoc` (maintainer's report of 2026-10-04). Two other saved single-sheet boards hold none, and the first flat report (step D3) named no class difference, which that report may simply not have listed. With a written class of this name and content, and the room key in the sheet's section, the change order of the rebuilt flat sample offers no component class and no room (maintainer's repeat of 2026-10-04) | S-0199, S-0200, S-0174, S-0176, S-0313 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-04; no artefact) | H-A-ECO-SHEETCLASS |
| The four classes `Top Side Components`, `Bottom Side Components`, `Inside Board Components` and `Outside Board Components` of a saved board carry `AUTOGENERATEDCLASS=TRUE` and an `AUTOGENERATEDCLASSKIND`; the change order did not ask for them | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-ECO-COMPCLASS |
| A room is a Room Definition rule of the Placement category, scoped `InComponentClass('<name>')`. None of the six saved boards read holds such a rule, so its record is not known | S-0310, S-0172, S-0174, S-0175, S-0176, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-ECO-ROOMS |
| "Supply Nets" is a Signal Integrity rule whose constraint is a voltage. When the PCB is updated from the schematic, Altium suggests one for each net with a power port, under its advanced setting `Schematic.AutoGenerateSupplyNetsRule`: an application setting, not a key of the project. None of the six saved boards read holds the rule, so its record is not known. Both change orders of the report of 2026-10-04 list two such rules with a voltage of 0, for `GND` and `VIN`, and on the build with module sheets nothing else | S-0185, S-0312 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-04; no artefact) | H-A-ECO-SUPPLY |

## Rules

| fact | source | label | hypothesis |
|---|---|---|---|
| Each rule of `Rules6` is a 16-bit rule-kind number, then one property block. Numbers: 0 Clearance, 2 Width, 6 PlaneConnect, 9 RoutingLayers, 11 RoutingVias, 12 PlaneClearance, 20 PolygonConnect, 62 UnpouredPolygon | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| Common keys of a rule, in order: the seven common keys with `LAYER=TOP`, `RULEKIND`, `NETSCOPE`, `LAYERKIND=SameLayer`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY` (1 is the highest), `COMMENT`, `UNIQUEID`, `DEFINEDBYLOGICALDOCUMENT=FALSE`, then the kind's keys | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| Clearance (`RULEKIND=Clearance`): `NETSCOPE=DifferentNets`, `GAP`, `GENERICCLEARANCE`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT`, `OBJECTCLEARANCES` (empty for one value) | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| Width (`RULEKIND=Width`): `NETSCOPE=AnyNet`, `MAXLIMIT`, `MINLIMIT`, `PREFEREDWIDTH` (this spelling) | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| Routing Via Style (`RULEKIND=RoutingVias`): `NETSCOPE=AnyNet`, `HOLEWIDTH`, `WIDTH`, `VIASTYLE=Through Hole`, `MINHOLEWIDTH`, `MINWIDTH`, `MAXHOLEWIDTH`, `MAXWIDTH` | S-0160, S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| A class rule has `SCOPE1EXPRESSION=InNetClass('<name>')` and a higher priority (a lower number) than the `All` rule of its kind; a rule for everything has `SCOPE1EXPRESSION=All` and `SCOPE2EXPRESSION=All` | S-0161, S-0174 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |
| Altium saves 39 to 41 rules of many kinds. The document of c0035 writes none and opens; Altium Designer 26.5 accepts three kinds without the rest: it shows them and its design rule check runs (author report of 2026-10-03) | S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-CU-RULES |

## Rule kinds lowered

Change c0084 writes more rule kinds and scopes. The constraint of each kind is what Altium's public
documentation says (S-0460, S-0461, S-0462; Altium Designer 26, read 2026-10-06, facts only). The keys of
each record are those of rule records in public PCB documents and in one public rule file, read with
Fenolite's own readers (corpus rows `altium-third-party-pcbdoc-01` to `-08` and
`altium-third-party-rules-01`; census of 2026-10-06, files in the corpus cache, never committed). A corpus
row shows which keys Altium writes; what Altium means by them stays `INFERRED` until the author report,
Part U of `docs/evidence/altium-pcb.md`.

| fact | source | label | hypothesis |
|---|---|---|---|
| Board Outline Clearance is the minimum clearance from fabricated design objects to the edges of the board (outline, cavity, cutout and split-line edges); it holds one minimum clearance or a matrix per object and edge kind | S-0460 | INFERRED | H-A-RULE-KINDS |
| A Board Outline Clearance record has the kind number 63, `RULEKIND=BoardOutlineClearance`, `NETSCOPE=DifferentNets` and the keys of Clearance in this order: `GAP`, `GENERICCLEARANCE` (equal to `GAP`), `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`, `OBJECTCLEARANCES` (empty for one value; a list of `ClearanceObj_…` pairs for a matrix). Eight records in five documents; its first scope is `All`, `InNet('…')` or a query, its second `All` | S-0174, S-0175, S-0187, S-0199, S-0200 | INFERRED | H-A-RULE-KINDS |
| Hole Size is the minimum and the maximum hole diameter of pads and vias, as absolute values or as percentages of the pad size | S-0460 | INFERRED | H-A-RULE-KINDS |
| A Hole Size record has the kind number 42, `RULEKIND=HoleSize`, `NETSCOPE=AnyNet` and the keys `ABSOLUTEVALUES`, `MAXLIMIT`, `MINLIMIT`, `MAXPERCENT`, `MINPERCENT` in this order; every record read holds `ABSOLUTEVALUES=TRUE`, `MAXPERCENT=80.000` and `MINPERCENT=20.000`, and both limits (ten records) | S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200, S-0297 | INFERRED | H-A-RULE-KINDS |
| Hole To Hole Clearance is the minimum clearance between the holes of pads and vias, with the option "Allow Stacked Micro Vias" | S-0460 | INFERRED | H-A-RULE-KINDS |
| A Hole To Hole Clearance record has the kind number 52, `RULEKIND=HoleToHoleClearance`, `NETSCOPE=AnyNet` and the keys `GAP` and `ALLOWSTACKEDMICROVIAS` (`TRUE` or `FALSE`) in this order; both scopes are `All` in the nine records read | S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200, S-0297 | INFERRED | H-A-RULE-KINDS |
| Minimum Annular Ring is the minimum ring of a pad or via, measured radially from the edge of the hole to the edge of the pad or via | S-0460 | INFERRED | H-A-RULE-KINDS |
| A Minimum Annular Ring record has the kind number 19, `RULEKIND=MinimumAnnularRing`, `NETSCOPE=AnyNet` and the one key `MINIMUMRING`; four records in three documents, scoped `All`, `IsVia` or `NOT IsVia` | S-0174, S-0199, S-0200 | INFERRED | H-A-RULE-KINDS |
| A Width record holds `MAXLIMIT`, `MINLIMIT` and `PREFEREDWIDTH` in every record read, a Routing Via Style record its seven keys, a Hole Size record both limits: no record read leaves a limit out | S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200, S-0297 | INFERRED | H-A-RULE-KINDS |
| Silk To Solder Mask Clearance is the clearance between a silkscreen primitive and a solder mask opening or the copper exposed through it, by a checking mode; Silk To Silk Clearance is the clearance between silkscreen text and other silkscreen objects. Their records hold `MINSILKSCREENTOMASKGAP` with `CLEARANCETOEXPOSEDCOPPER`, and `SILKTOSILKCLEARANCE`. Neither is the neutral silkscreen clearance, which is one value for both | S-0460, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200, S-0297 | INFERRED | H-A-RULE-KINDS |
| Component Clearance is the minimum distance between components, measured between their 3D bodies or, without them, their selection areas, with a horizontal and a vertical clearance and a check mode. Its record holds `GAP`, `COLLISIONCHECKMODE`, `VERTICALGAP` and `SHOWDISTANCES`; no permitted source says what the mode number means. It is not a clearance between courtyards | S-0461, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200, S-0297 | INFERRED | H-A-RULE-KINDS |
| Creepage Distance is a rule of the Electrical category between a first and a second scoped object, whose distance is checked in three dimensions, with the options "Ignore Internal Layers" and "Apply to Polygon Pour". No public file read holds such a rule, so its record is not known | S-0462 | INFERRED | H-A-RULE-KINDS |
| The clearance of a hole is a row of the object matrix of Clearance (`ClearanceObj_Hole` in `OBJECTCLEARANCES`); the numbers of that text carry no unit and no permitted source explains them. There is no rule kind for the clearance between a hole and copper alone | S-0462, S-0176 | INFERRED | H-A-RULE-KINDS |
| Scopes seen in the records of the lowered kinds: `All`, `InNet('<net>')` and `InNetClass('<class>')` as the first scope with `All` as the second; a Clearance record also holds a query as its second scope (layer and polygon queries in the records read, never a net). The rule that applies is the first one, by priority, whose scopes match | S-0286, S-0296, S-0172, S-0174, S-0175, S-0176, S-0187, S-0200 | INFERRED | H-A-RULE-SCOPE |
| Priorities count from 1 within one rule kind: in the eight documents and the rule file every kind has its own run 1, 2, … without a gap | S-0286, S-0297, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RULE-PRIORITY |

### The lowering table

`rulemap.TABLE`, one row per neutral rule kind. An `exact` row is written and read back; every other row
names why the kind is not written. A dash is a limit the kind does not hold; a rule must give exactly the
limits of its row.

| neutral kind | Altium kind | number | min | opt | max | status |
|---|---|---|---|---|---|---|
| `clearance` | `Clearance` | 0 | `GAP` | — | — | exact |
| `track_width` | `Width` | 2 | `MINLIMIT` | `PREFEREDWIDTH` | `MAXLIMIT` | exact |
| `via_diameter` | `RoutingVias` | 11 | `MINWIDTH` | `WIDTH` | `MAXWIDTH` | exact |
| `via_drill` | `RoutingVias` | 11 | `MINHOLEWIDTH` | `HOLEWIDTH` | `MAXHOLEWIDTH` | exact |
| `hole_size` | `HoleSize` | 42 | `MINLIMIT` | — | `MAXLIMIT` | exact |
| `edge_clearance` | `BoardOutlineClearance` | 63 | `GAP` | — | — | exact |
| `hole_to_hole` | `HoleToHoleClearance` | 52 | `GAP` | — | — | exact |
| `hole_clearance` | — | — | — | — | — | no-counterpart |
| `annular_width` | `MinimumAnnularRing` | 19 | `MINIMUMRING` | — | — | exact |
| `courtyard_clearance` | — | — | — | — | — | no-counterpart |
| `silk_clearance` | — | — | — | — | — | no-counterpart |
| `creepage` | — | — | — | — | — | no-counterpart |

## Oracle

| fact | source | label | hypothesis |
|---|---|---|---|
| KiCad builds the copper stack from the numbered keys only, by chain position: 1 → 2 → 3 → 32 gives `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, the inner layers of type `signal`; a plane in the chain (39 or 40) becomes the copper layer of its position with the type `power`. This holds for the chains 1 → 39 → 40 → 32, 1 → 39 → 3 → 32 and 1 → 2 → 39 → 32, without any split-plane record | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| A track or polygon written on Mid-Layer 2 of the chain 1 → 39 → 3 → 32 arrives on `In2.Cu` | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| KiCad warns once per internal plane that is outside the stack ("could not be mapped"): sixteen warnings without a plane in the chain, fifteen with one, fourteen with two | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| A plane's net is not in the imported board: KiCad makes zones from split-plane records only. Net classes and rules give no error and are not in the imported `.kicad_pcb` | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-KICAD |
| Copper copied from a KiCad board into the document and imported back equals the source board's copper | S-0161, S-0166, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-CU-ROUNDTRIP |

## Not written

- The 49-byte track and the 60-byte arc: their tails add nothing the model holds, and the short forms
  open in Altium Designer 26.5 (`H-A-PCB-CU-TRACK`).
- `Regions6` and `ShapeBasedRegions6`: polygons are written unpoured, and a zone's fills are not copied
  (`H-A-PCB-CU-REPOUR`). Hatched pours, shelved polygons and polygon cutouts.
- Micro vias and via types; tented vias; the two 16-byte ids of a via (zero); the polygon-connect
  entry of the 351-byte form. (Blind and buried vias and their drill pairs are written since c0085.)
- The `Split Plane` polygon record and the pull-back tracks of a plane, split planes, and the Plane
  Connect and Plane Clearance rules (`H-A-PCB-CU-PLANE`): Altium's defaults apply.
- `COPPERORIENTATION`, `DIELLOSSTANGENT`, the hole-shape pairs (`HOLESHAPEHASHSIZE=0`).
- Super classes, the classes with `AUTOGENERATEDCLASS=TRUE`, and every class kind but 0 and 1.
- Rooms (the Room Definition rule) and "Supply Nets" rules: no permitted source holds their records. The
  project file turns the rooms off (`project.md`, "Class generation"); the "Supply Nets" rules stay a
  difference that the change order may propose, and they only add rules (`H-A-ECO-ROOMS`, `H-A-ECO-SUPPLY`).
- Every rule kind outside the lowering table ("Rule kinds lowered"), layer scopes and queries of rules;
  tear-drops; differential pairs.

## Fenolite's choices

- **Layers.** `F.Cu` is layer 1 (`TOP`), `In1.Cu` as a signal layer is Mid-Layer 1 (id 2, `MID1`),
  `In2.Cu` Mid-Layer 2 (id 3, `MID2`), `B.Cu` layer 32 (`BOTTOM`). A signal inner layer keeps its id
  whatever the other inner layer is. Planes are numbered from the top: the first inner layer that is a
  plane is Internal Plane 1 (id 39), the second Internal Plane 2 (id 40). No primitive is written on a
  plane. Since change c0085 the map is by position, for any stack: the first copper layer of the
  model is the top layer (1), the last the bottom layer (32), and the k-th inner copper layer is Mid-Layer k
  (id k + 1) as a signal layer, whatever its name and whatever the other inner layers are; the planes are
  Internal Plane 1, 2, … (39, 40, …) from the top. Two model layers never share an Altium layer. A stack is
  written with an even number of copper layers from 2 to 32 that holds at most 16 signal layers and 16 internal planes;
  any other count gives the stack of the two outer layers and `altium.not-lowered` with `where`
  `stackup`.
- **Tracks and arcs.** The short forms (36 and 47 bytes) with flags `0C 00`, after the component
  primitives in `Tracks6` and `Arcs6`, sorted by stack position of the layer, net name, start, end, width
  and entity id. Points are converted like placed points (`pcb-document.md`, frame).
- **Vias.** The 321-byte form with the values of the "Via" table and zero in every other byte, the two
  ids included; flags `0C 00` (not tented); start 1 and end 32 for a through via, the ids of the two
  layers of its span, the upper one first, for a blind or buried via (change c0085); sorted by net name,
  position, diameter and entity id. The board record gets one drill pair per distinct span besides
  `TOP` to `BOTTOM`, in stack order of the upper and then of the lower layer. A micro via is not written.
- **Polygons.** One record per zone layer, solid, in the key order of the first row of "Polygon pour"
  without `OBEYPOLYGONCUTOUT`: `POUROVER=TRUE`, `REMOVEDEAD=TRUE`, `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`,
  `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`, line vertices, `SHELVED=FALSE`,
  `RESTORELAYER=UNKNOWN`, an empty `RESTORENET`, `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`,
  `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`,
  `POUROVERSTYLE=1`, `IGNOREVIOLATIONS=FALSE`, `OPTIMALVOIDROTATION=TRUE`. The name is the zone's name, or
  `<net name>_L<layer position from 01>_P<pour index, three digits>` in upper case with `AUTONAME=TRUE`
  (`NONET` without a net). `POURINDEX` counts from 0 in the order of falling zone priority, then net name,
  first outline point, zone id and stack position. No region is written: a polygon is unpoured by
  contract (change c0085), and Fenolite never writes poured copper it did not compute for Altium's rules.
  A zone whose islands are never removed has `REMOVEDEAD=FALSE`. Clearance and thermal reliefs are not in
  the record: Altium takes them from its rules.
- **Stack.** The numbered keys link the copper ids in order. Each linked layer but the bottom carries the
  dielectric below it. The physical lists (`V9_STACK_LAYER<i>` and the head of `LAYER_V8_<i>`) hold 13
  entries with the overlays, as the nine-entry list of c0035 has them; the cache list keeps the order of
  a two-layer document and ends with `Dielectric 2` and `Dielectric 3`, the form of 2023. Dielectrics are `Dielectric 1` to `3` with the long ids 17039361 to 17039363 from the
  top. A signal mid layer has `COMPONENTPLACEMENT=1`; a plane `PULLBACKDISTANCE=20mil`, and
  `PLANE<k>NETNAME` names its net. A stack of more layers follows the same rules: `Dielectric n` with the
  long id 17039360 + n from the top (change c0085). The default values are Fenolite's: 1.4 mil copper; for two layers the
  dielectric of c0035 (`DIELTYPE=0`, 12.6 mil, `4.800`, `FR-4`), so the bytes of a two-layer document do
  not change; for four layers a prepreg of 0.2 mm, a core of 1.0 mm and a prepreg of 0.2 mm, each `4.800`
  and `FR-4`; for more layers prepregs of 0.2 mm and cores in turn, the outermost a prepreg, the cores
  sharing 1.0 mm. The model's stack-up names a material and no kind, so the dielectrics of a stack-up get
  the same kinds in turn (one dielectric alone is a core). `TOGGLELAYERS` stays 82 ones.
- **Classes.** One `KIND=0`, `SUPERCLASS=FALSE` record per net class in name order, members in name
  order, `UNIQUEID` = `project.unique_id("pcbdoc:<file name>:class:<name>")`.
- **Component classes (change c0048).** After the net classes, one `KIND=1`, `SUPERCLASS=FALSE` record per
  schematic sheet that holds a component, in code-point order of the class names: the keys of a net class
  record, the members being the refs of the sheet's components in code-point order, `UNIQUEID` =
  `project.unique_id("pcbdoc:<file name>:component-class:<class>")`. The class of a module sheet is named
  after the module, which is the name of its sheet symbol (`H-A-ECO-COMPCLASS`). The class of the top sheet,
  or of the single sheet of a flat build, is named after that sheet: the stem the document shares with it
  (`H-A-ECO-SHEETCLASS`). The two rules are one: a sheet's class carries the name Altium shows for the
  sheet. A module of the top sheet's name shares its class. A component class alone makes no rule.
- **Rules.** Written only when the document holds copper or a net class. Per kind (Clearance, Width,
  RoutingVias) one rule `<Kind>_<class>` per class that holds the value, scope `InNetClass('<class>')`,
  priorities from 1 in class-name order, then one rule named after the kind with the scope `All`.
  Defaults of the `All` rules: clearance 0.2 mm, width 0.25 mm, via 0.6 mm with a 0.3 mm hole. Width and
  via limits span the preferred value and the written copper of the rule's scope.
- **Rules of the design (c0084).** `rulemap.lower` writes a neutral rule only when its row is `exact`,
  its severity is `error`, it gives exactly the limits of its row, and its selectors are all objects, a
  net, a net class or a conjunction of those (a second selector for `clearance` only). Nothing is
  approximated: a `track_width` rule without `opt` and `max`, a `hole_size` rule without `max`, a glob, a
  layer and a `ref` or `item_kind` selector are reported, not written. A `via_diameter` and a `via_drill`
  rule of one selector share one Routing Via Style record; one of them alone is not written. Fixed
  values: `ALLOWSTACKEDMICROVIAS=FALSE` (the neutral rule exempts no hole; the reader maps only that
  value), `ABSOLUTEVALUES=TRUE` with the percentages every record read holds, `OBJECTCLEARANCES` empty.
  Names are `<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, with `_and_` for a conjunction and `_to_`
  before a second scope; a repeated name gets `_2`. Within a kind the rules of the design come first, from
  the most governing to the least (priority 1, 2, … then 0; ties by falling name), then the rules of the
  net classes and the `All` default; a class or default rule whose scopes a rule of the design holds is
  left out. So a board-wide rule of the script governs the classes, as it does in a KiCad build.
- **Refusals.** Copper on a layer outside the stack or on a plane, a via that does not span two
  different copper layers and a zone without an outline give an error and no file. A micro via is left
  out with a warning (change c0085).
