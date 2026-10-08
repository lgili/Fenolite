# Altium PCB primitive records

This page states, in Fenolite's own words, the binary records that the PCB writers
`fenolite.backends.altium.pcbrecords`, `pcblib` and `pcbdoc` (change c0035) write, and that the independent
test decoder `tests/_altium_pcb_read.py` reads back. The same records fill a footprint's `Data` stream in a
PCB library (`pcb-library.md`) and the per-kind storages of a PCB document (`pcb-document.md`).

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0161, S-0163),
  AltiumSharp **version 1 only** (S-0150, commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`; version 2
  is not a source, `LEGAL.md` P1, see `pcb-library.md`, "Version 2 not used") and an MIT PcbDoc writer
  (S-0143). No code was transcribed.
- The KiCad importer is a reader: a record it accepts may still be refused by Altium. Rows therefore stay
  `INFERRED` until an author report (`docs/evidence/altium-pcb.md`); a `kicad-cli` round trip settles
  only `H-A-PCB-KICAD-LIB` and `H-A-PCB-KICAD-DOC`.
- Rows that only say what KiCad's importer reads carry `ORACLE-VERIFIED(kicad-cli)` since the round trips of 2026-10-03 passed on 10.0.6; that label says nothing about Altium.
- `tests/unit/test_format_facts.py` checks the tables.

## Units, framing and texts

| fact | source | label | hypothesis |
|---|---|---|---|
| Binary lengths and coordinates are signed 32-bit integers in 1/10 000 mil, so one unit is exactly 2.54 nm; a length in nanometres is `nm · 50 / 127` units, which is not an integer in general | S-0002, S-0160, S-0163 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| Angles are IEEE-754 doubles in degrees; positive angles turn counter-clockwise, and the Y axis points up (a reader from a Y-down tool negates Y) | S-0002, S-0160 | INFERRED | H-A-PCB-GRAPHICS |
| Lengths in property text are decimal mils followed by `mil`, such as `10mil` or `0.5mil` | S-0163 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| Every integer is little-endian | S-0002, S-0160 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| A property block is a 32-bit word (the payload length in the low 24 bits, record type 0 in the top byte), then `\|KEY=VALUE…` text and one NUL that the length counts; it is the framing of a schematic text record | S-0002, S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| A string block is a 32-bit length, then one length byte and the 8-bit characters, without NUL; the 32-bit length is the length byte plus the characters | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| A primitive record is one type byte (1 arc, 2 pad, 3 via, 4 track, 5 text, 6 fill, 11 region, 12 component body), then subrecords, each a 32-bit length and that many bytes. A reader skips to the end of a subrecord after the fields it knows, so a longer subrecord is read and a shorter one is refused; an unknown type stops a reader | S-0002, S-0160 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |

## Common prefix

| fact | source | label | hypothesis |
|---|---|---|---|
| Tracks, arcs, pads (subrecord 5) and texts start with 13 bytes: offset 0 the layer id (one byte), 1 and 2 two flag bytes, 3-4 the net index, 5-6 the polygon index, 7-8 the component index (unsigned 16-bit; `0xFFFF` means none), 9-12 four bytes that readers skip | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| In the first flag byte, bit 2 set means unlocked. A writer writes `0x0C` and `0x00` as the two flag bytes, and `FF FF FF FF` at 9-12 | S-0160, S-0143, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-GRAPHICS |
| Nets and components are indexed by their zero-based position in their own storage; in a library footprint every index is `0xFFFF` | S-0160, S-0161, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |

## Track and arc

| fact | source | label | hypothesis |
|---|---|---|---|
| A track (type 4) is one subrecord of at least 36 bytes: the prefix, then at 13 x1, 17 y1, 21 x2, 25 y2, 29 the width (32-bit each), 33 a 16-bit sub-polygon index (0) and 35 one byte (0). One open-source writer writes 35 bytes, which KiCad's reader refuses; 36 bytes satisfy both readers | S-0160, S-0143, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-GRAPHICS |
| An arc (type 1) is one subrecord of at least 47 bytes: the prefix, then at 13 the centre x, 17 the centre y, 21 the radius (32-bit each), 25 the start angle and 33 the end angle (doubles), 41 the width (32-bit) and 45 a 16-bit sub-polygon index. AltiumSharp version 1 writes 45 bytes, without the index; KiCad refuses that arc (local probe of the format research) | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0020 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-GRAPHICS |
| An arc runs counter-clockwise from its start angle to its end angle; a full circle is 0 to 360 degrees | S-0002, S-0160 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-GRAPHICS |

## Pad

| fact | source | label | hypothesis |
|---|---|---|---|
| A pad (type 2) has six subrecords: 1 the pad name as one length byte and the characters (the subrecord length must be exactly 1 + the name length, and not 0); 2 one byte `00`; 3 one length byte and `\|&\|0`; 4 one byte `00` (what version 1 writes in 2 to 4) | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| Subrecord 5 holds the geometry and is at least 110 bytes: the prefix; 13 x, 17 y; 21 and 25 the top size x and y, 29 and 33 the middle size, 37 and 41 the bottom size; 45 the hole size (0 for a surface pad); 49, 50 and 51 the top, middle and bottom shape; 52 the rotation (double, degrees); 60 plated (one byte); 61 one byte; 62 the pad mode (0 simple) | S-0002, S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| Offsets 63 to 85 are not read by KiCad. Version 1 writes there: one byte 0, a 32-bit 0, a 32-bit 10 mil (100 000 units), a 16-bit 4, a 32-bit 10 mil, a 32-bit 20 mil and a 32-bit 20 mil | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| Then 86 the paste-mask expansion and 90 the solder-mask expansion (32-bit), 94 to 100 seven zero bytes, 101 the paste-mask mode and 102 the solder-mask mode (0 none, 1 from the rules, 2 manual; version 1 writes 0 and 1), 103 to 105 three zero bytes | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| At 106: when subrecord 5 is exactly 110 bytes, a 32-bit value that KiCad requires to be 0; when it is longer, a double hole rotation over 106 to 113. Version 1 and an MIT writer both write 114 bytes; version 1 puts a 32-bit 0 at 106, a 16-bit jumper id 0 at 110 and a 16-bit 0 at 112, which a reader takes as the double 0.0 | S-0160, S-0143, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| Subrecord 6 may be empty. When present it is at least 596 bytes: 29 inner sizes x and 29 inner sizes y (32-bit, offsets 0 and 116), 29 inner shapes (one byte each, 232), one byte (261), the hole shape (262: 0 round, 1 square, 2 slot), the slot length (32-bit, 263), the slot rotation (double, 267), 32 hole offsets x and 32 y (32-bit, 275 and 403), one byte that version 1 sets when the pad has rounded corners (531), 32 alternate shapes (one byte each, 532) and 32 corner percentages (one byte each, 564; 0 to 100, 100 fully round) | S-0002, S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| Shapes: 1 round, 2 rectangle, 3 octagonal. A round pad with unequal sizes is an oval. A rounded rectangle is main shape 1 with alternate shape 9 in subrecord 6 and a corner percentage; KiCad reads the percentage `p` as the corner ratio `p / 200`. The alternate shape and percentage of index 0 belong to the top layer | S-0160, S-0161, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-PAD |
| A pad with a hole size above 0 is a through-hole pad: plated 1 is plated, 0 not plated. A through-hole pad must lie on layer 74 (Multi-Layer); a surface pad lies on its copper layer | S-0161 | INFERRED | H-A-PCB-PAD |

## Text

| fact | source | label | hypothesis |
|---|---|---|---|
| A text (type 5) has two subrecords. The first is at least 40 bytes: the prefix (with the component index at 7), 13 x, 17 y, 21 the height, 25 a 16-bit stroke font (1 default), 27 the rotation (double), 35 mirrored (one byte), 36 the stroke width (32-bit) | S-0002, S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-DOC-VIEWER |
| The long form of the first subrecord, at least 123 bytes, adds 40 is-comment and 41 is-designator (one byte each), 42 one byte, 43 the font type (0 stroke), 44 bold, 45 italic, 46 the font name as 64 bytes of UTF-16LE, 110 inverted, 111 the margin (32-bit) and 115 the wide-string index (32-bit). The MIT writer writes 137 bytes; the offsets after 43 follow the field sizes in order and are inferred | S-0002, S-0160, S-0143 | INFERRED | H-A-PCB-DOC-VIEWER |
| `kicad-cli` 10.0.6 refuses a document whose texts use a 123-byte first subrecord ("Texts6 stream was not parsed correctly") and reads 137-byte ones, the MIT writer's length (local runs on Fenolite's own files, 2026-10-03) | S-0020, S-0143 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| The second subrecord is the text as one length byte and up to 255 8-bit characters. When the wide-string index names an entry of `WideStrings6`, a reader takes that entry instead | S-0002, S-0160 | INFERRED | H-A-PCB-DOC-VIEWER |
| A free text of a board (change c0085) is the text record without a component (index `0xFFFF`) and with both the is-comment and the is-designator byte 0; its stroke font is 1 and its font type 0 (stroke). The seven saved documents hold free texts of the font types 0 and 1 on the overlay layers; a free text on a bottom layer is mirrored in every one read, and one on a top layer is not | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-TEXT |
| The 8-bit string of a text is in a code page of the machine that saved it: a saved text of CJK characters holds two bytes per character there, and its wide string holds the characters. KiCad decodes the 8-bit string as ISO-8859-1 and takes the wide string when the index names one, so a text survives through its wide string | S-0148, S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-TEXT |
| KiCad imports a free 137-byte stroke text with its wide string (accented characters included), layer, height, stroke width and rotation; it anchors the text at its lower-left corner and mirrors a text whose mirror byte is set | S-0160, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| In a PCB document a component's designator and comment are texts with the is-designator or is-comment flag and the component's index; KiCad places the reference at the designator text | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |

## Regions and keep-outs

Change c0085 writes regions for filled graphics and for keep-outs. The framing of a region is on
`pcb-read.md` ("Regions"); the rows here are what the writer relies on besides.

| fact | source | label | hypothesis |
|---|---|---|---|
| A region without a net, a polygon and a component has `0xFFFF` in the three indexes of its prefix, flags `0C 00`, and five zero bytes between the prefix and the length of its property text (a hole count of 0 among them): every region of the seven saved documents holds zero in the byte at 13 and in the two bytes at 16 | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-READBACK |
| The property text of a saved free region holds, in this order, `V7_LAYER`, `NAME` (one space), `KIND`, `SUBPOLYINDEX`, `UNIONINDEX`, `ARCRESOLUTION`, `ISSHAPEBASED` and `CAVITYHEIGHT`. Of the 328 regions read, 297 hold `KIND=0` (a copper or drawn shape; 1 is a cutout), 202 `SUBPOLYINDEX=-1` (the others belong to a pour), 306 `ARCRESOLUTION=0.5mil`, 313 `ISSHAPEBASED=FALSE` and all `CAVITYHEIGHT=0mil` | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository), S-0285 | INFERRED | H-A-PCBX-READBACK |
| `V7_LAYER` names the region's layer: `TOP`, `BOTTOM`, `MID<n>`, `TOPOVERLAY`, `BOTTOMOVERLAY`, `TOPPASTE`, `BOTTOMPASTE`, `TOPSOLDER`, `BOTTOMSOLDER`, `MECHANICAL<n>` and `KEEPOUT` occur with the layer bytes 1, 32, n + 1, 33 to 38, 56 + n and 56 | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-READBACK |
| Every region of `Regions6` has one record at the same position in `ShapeBasedRegions6` with the same property text, whose outline holds each vertex as 37 bytes and the first vertex again after the last; a vertex of a straight edge has the round flag 0 and zero in its centre, radius and angles | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-READBACK |
| A keep-out is a primitive whose second flag byte is 2. In the seven saved documents that byte is 2 on two arcs of a copper layer and on one region of the Keep-Out layer (56), and 0 on every other track, arc, fill, region, text, pad and via but for six vias; KiCad's parser takes a track, an arc, a fill or a region with that byte at 2 as a keep-out | S-0470, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-KEEPOUT |
| A keep-out region carries its restrictions as the last key of its property text, `KEEPOUTRESTRICTIONS=<n>`, in `Regions6` and in `ShapeBasedRegions6` alike; the one saved keep-out region holds 24, with `V7_LAYER=KEEPOUT`. A keep-out arc of the long form holds the value in one byte after its long layer id (31 on the two saved arcs, where every plain track and arc holds 0) | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-KEEPOUT |
| KiCad's parser reads the restrictions of a region from a key named `KEEPOUTRESTRIC` and takes 31 (every restriction) when the key is absent, so it does not read the key that the saved documents hold | S-0470, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| A keep-out region that holds `KEEPOUTRESTRIC=<n>` after `KEEPOUTRESTRICTIONS=<n>` imports into KiCad with exactly the restrictions of n. `KEEPOUTRESTRIC` is not a key Altium writes itself: no saved document read holds it, and it is written for KiCad's importer alone | S-0470, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| That Altium opens a region whose property text holds both keys, and takes the restrictions from `KEEPOUTRESTRICTIONS`, is not known from any source: a reader of property text takes the keys it knows, and no saved document was seen with a key it does not know of this kind | S-0160, S-0470 | INFERRED | H-A-PCBX-KEEPOUT |
| The bits of the restrictions value, as KiCad's importer reads its key: 1 forbids vias, 2 tracks, 4 poured copper, and 8 with 16 together pads (8 or 16 alone forbids no pad kind of KiCad). The value 31 is every restriction, and the saved value 24 the two pad bits | S-0470, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| A keep-out region with the layer byte 56 imports into KiCad as one rule area on every copper layer of the stack; with the layer byte of a copper layer, as a rule area on that layer alone | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| Older saved documents draw a keep-out as tracks and arcs on layer 56 with the second flag byte 0, and three hold regions on layer 56 with the keys `LAYER=KEEPOUT`, `KEEPOUT=TRUE` and `ISBOARDCUTOUT=TRUE`; neither form is written | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-KEEPOUT |
| KiCad imports a free 36-byte track and a free 47-byte arc on an overlay or a mechanical layer as a line, an arc or a circle of its width on `F.SilkS`, `B.SilkS` or `User.<n>`, and a free region there as a filled polygon | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |

## Free pads as holes

| fact | source | label | hypothesis |
|---|---|---|---|
| A hole of a board that belongs to no footprint is a pad without a component (index `0xFFFF`) on Multi-Layer (74): the seven saved documents hold fourteen free pads on that layer, six of them not plated. Four of those six have no name and no net, the round shape 1 and every size equal to the hole size, so no copper ring remains; their sixth subrecord is empty | S-0160, S-0161, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-PCBX-HOLE |
| A pad without a name has a first subrecord of one byte, the length 0 | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository), S-0160 | INFERRED | H-A-PCBX-HOLE |
| KiCad imports a free pad as a footprint of its own; a free pad on Multi-Layer with the plated byte 0 becomes one non-plated through hole of the pad's hole size at its place | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | H-A-PCBX-KICAD |
| A slotted hole is hole shape 2 with a slot length and rotation in the sixth subrecord (see "Pad"); every slotted hole of the saved documents is plated and belongs to a component | census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository), S-0160 | INFERRED | H-A-PCBX-HOLE |

## Layers

| fact | source | label | hypothesis |
|---|---|---|---|
| Layer ids: 1 Top Layer, 2 to 31 Mid-Layer 1 to 30, 32 Bottom Layer, 33 Top Overlay, 34 Bottom Overlay, 35 Top Paste, 36 Bottom Paste, 37 Top Solder, 38 Bottom Solder, 39 to 54 Internal Plane 1 to 16, 55 Drill Guide, 56 Keep-Out Layer, 57 to 72 Mechanical 1 to 16, 73 Drill Drawing, 74 Multi-Layer | S-0002, S-0160 | INFERRED | H-A-PCB-GRAPHICS |
| Newer files add a 32-bit layer id in optional tail bytes; readers fall back to the one-byte id, so a record without the tail stays within Mechanical 1 to 16 | S-0160 | INFERRED | H-A-PCB-GRAPHICS |
| KiCad's library import maps Mechanical n to `User.n`, with or without mechanical-kind keys, so no KiCad round trip can check which mechanical layer stands for fabrication or courtyard (local probe of the format research) | S-0020, S-0162 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| Altium has no fixed fabrication or courtyard layer | S-0002 | INFERRED | H-A-PCB-GRAPHICS |

## Fenolite's choices

These are choices of the writer, not format facts:

- `nm → units` rounds `nm · 50 / 127` half away from zero (at most 1.27 nm per value); KiCad rounds back on
  import. No `--allow-lossy` is needed.
- Angles are computed from exact coordinates with `decimal` at 40 digits and converted to a double once,
  so the bytes are the same on every platform; no trigonometric function of `math` produces a written
  value.
- The layer map, one table (`pcbrecords.LAYER_MAP`):

  | Fenolite layer | Altium id | Altium name |
  |---|---|---|
  | `F.Cu` | 1 | Top Layer |
  | `B.Cu` | 32 | Bottom Layer |
  | `F.SilkS` | 33 | Top Overlay |
  | `B.SilkS` | 34 | Bottom Overlay |
  | `F.Fab` | 69 | Mechanical 13 |
  | `B.Fab` | 70 | Mechanical 14 |
  | `F.CrtYd` | 71 | Mechanical 15 |
  | `B.CrtYd` | 72 | Mechanical 16 |

  Through-hole pads go to 74. The flip pairs are 1/32, 33/34, 69/70 and 71/72; 74 is its own pair.
- A track is written with 36 bytes and an arc with 47. A rectangle is four tracks (start, (end.x,
  start.y), end, (start.x, end.y)); a circle is one arc from 0 to 360 degrees; a KiCad arc keeps its
  exact centre, rounded once, and runs counter-clockwise in the Y-up frame (start and end swap when the
  three points turn clockwise there).
- Pad subrecord 5 is 114 bytes with version 1's values at 63 to 85, mask expansions 0, paste mode 0 and
  solder mode 1. Subrecord 6 is empty except for a rounded rectangle: 596 bytes, every inner size the
  pad size, every inner shape 1, hole shape 0, no slot, zero offsets, the rounded flag 1, every alternate
  shape 9 and every percentage `round(200 · ratio)` clamped to 0 … 100.
- Text subrecord 1 is the long form of 137 bytes, zero where nothing is set; the font name is empty.
- **Free texts (change c0085).** A board text is a stroke text of that form with its own height, stroke
  width and rotation, at the text's position, on the layer of the board layer map below. The model's text
  has no mirror and no justification, so none is written but one: a text on a bottom-side layer is
  mirrored, as the saved documents have it. The 8-bit string holds the text in ISO-8859-1 with `?` for a
  character outside it and at most 255 characters; the wide string holds the text. An empty text, a text
  with a control character or a line break, and a text without a positive height and stroke width are not
  written.
- **Board layer map (change c0085)**, `pcbrecords.BOARD_LAYER_MAP`, for free texts and graphics: the six
  non-copper rows of the table above and `F.Paste` 35, `B.Paste` 36, `F.Mask` 37, `B.Mask` 38. An item on
  another layer (copper, `Edge.Cuts`, a user layer) is not written.
- **Graphics (change c0085).** A line is one 36-byte track without a net, an arc one 47-byte arc, a circle
  one arc from 0 to 360 degrees; a drawn rectangle is four tracks and a drawn polygon one track per edge,
  closed. A filled rectangle or polygon is one region with `KIND=0`, `SUBPOLYINDEX=-1`, `UNIONINDEX=0`,
  `ARCRESOLUTION=0.5mil`, `ISSHAPEBASED=FALSE` and `CAVITYHEIGHT=0mil`, written in `Regions6` and, with
  37-byte vertices, in `ShapeBasedRegions6`; its drawn width is not written. A filled circle, a drawn
  shape without a positive width and a shape without an extent are not written.
- **Keep-outs (change c0085).** One keep-out region (second flag byte 2; after the keys of a saved
  region `KEEPOUTRESTRICTIONS` and then, by the maintainer's decision of 2026-10-06, `KEEPOUTRESTRIC` with
  the same value, so that KiCad's import carries the restrictions) on
  layer 56 when the keep-out names every copper layer of the board, else one per copper layer it names,
  on that layer. The value is 1 for `no_vias`, 2 for `no_tracks`, 4 for `no_copper_pour` and 24 for
  `no_pads`. `no_footprints` has no bit; a keep-out with no other restriction is not written.
- **Holes (change c0085).** A board hole is a free round pad on layer 74 without a name, a net or copper:
  every size is the drill, the plated byte is the hole's `plated`, and subrecord 6 is empty. The model's
  board hole is round, so no slot is written.

### Worked pad

The `roundrect` pad `1` of the mini 0603 resistor, 0.9 × 0.95 mm at (−0.8, 0) mm with ratio 0.25, gives
subrecord 5 of 114 bytes with layer 1, x −314961, y 0, every size 354331 × 374016, hole 0, shapes 1,
rotation 0.0, plated 0, and subrecord 6 of 596 bytes with alternate shape 9 and percentage 50.
