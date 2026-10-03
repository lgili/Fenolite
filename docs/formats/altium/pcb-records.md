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
| In a PCB document a component's designator and comment are texts with the is-designator or is-comment flag and the component's index; KiCad places the reference at the designator text | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |

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

### Worked pad

The `roundrect` pad `1` of the mini 0603 resistor, 0.9 × 0.95 mm at (−0.8, 0) mm with ratio 0.25, gives
subrecord 5 of 114 bytes with layer 1, x −314961, y 0, every size 354331 × 374016, hole 0, shapes 1,
rotation 0.0, plated 0, and subrecord 6 of 596 bytes with alternate shape 9 and percentage 50.
