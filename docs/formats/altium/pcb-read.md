# Altium PCB files as the reader reads them

This page states, in Fenolite's own words, what the product reader `fenolite.backends.altium.read`
(modules `pcbprops`, `pcbprims`, `pcbstack`, `pcb` and `pcblib`, change c0041) relies on to read PCB
documents (`.PcbDoc`) and libraries (`.PcbLib`) that Altium Designer saved. The writer's short forms are
on `pcb-records.md`, `pcb-library.md`, `pcb-document.md` and `pcb-copper.md`; the container on
`compound-file.md`.

- Sources: KiCad's developer page (S-0002); KiCad's binary parser and importer, read for facts only and
  never transcribed (S-0148, S-0160, S-0161, S-0162, S-0163); AltiumSharp **version 1 only** (S-0150, commit
  `afe796434b6d2110c745c90abe44a6ddf64f5bca`; version 2 is not a source); pyaltiumlib's documentation
  (S-0152); a GPL-3.0 format page read without its code (S-0173), which is never the only source of a row
  and whose two facts attributed to the vendor's software (an enumeration of mask states and a layer
  vocabulary) are not used; Altium's documentation (S-0285, S-0286, S-0287); and eleven public files saved
  by Altium Designer (S-0170 to S-0176, S-0188, S-0199, S-0200), fetched into the corpus cache by
  `tools/corpus_fetch.py` and never committed. Rows measured on those files say "files kept outside the
  repository"; only counts and lengths are recorded.
- A field is typed only with two agreeing sources, or one source and a corpus or oracle check
  (`tests/corpus/test_altium_pcb_census.py`, `tests/kicad/altium/test_pcbdoc_read_oracle.py`,
  `tests/kicad/altium/test_pcblib_read_oracle.py`). Every row starts at `INFERRED`; the census and the two
  oracles raise the rows they check.
- `read.pcbprims.FIELD_LEVELS` holds the label of every row of "Fields";
  `tests/unit/backends/altium/read/test_pcb_field_levels.py` keeps both equal, and
  `tests/unit/test_format_facts.py` checks the fact tables.

## Record lengths

Census of the eleven corpus rows (`docs/evidence/altium-pcb-read.md` holds the counts per row). The reader
types a subrecord at or above the minimum of `read.pcbprims.MINIMUMS`; the list of observed lengths lives
in the census test, so that a new length fails there on purpose and the reader still reads it.

| record | Fenolite writes | saved 2016–2019 | saved 2021–2025 | the reader's minimum |
|---|---|---|---|---|
| track | 36 | 45 | 49 | 33 |
| arc | 47 | 56 | 60 | 45 |
| via | 321 (c0038) | 299 | 321, 351 | 31 |
| fill | — | 46 | 50 | 37 |
| text, first subrecord | 137 | 232 | 252 | 40 |
| pad, fifth subrecord | 114 | 170, 171 | 185, 186, 194 | 110 |
| pad, sixth subrecord | 0, 596 | 0, 651 | 0, 651 | 0 or 596 |
| region | — | variable | variable | 26 |

| fact | source | label | hypothesis |
|---|---|---|---|
| A primitive is one type byte and a fixed number of subrecords, each a 32-bit length and that many bytes: one for an arc (1), via (3), track (4), fill (6), region (11) and component body (12), six for a pad (2), two for a text (5) | S-0002, S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-FRAME |
| Every primitive stream of the saved files ends exactly at a record end; no other type byte occurs | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-FRAME |
| Joined in order, the records of a stream give the stream back byte for byte | S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-IDENTITY |
| The saved subrecord lengths are track 45 and 49; arc 56 and 60; via 299, 321 and 351; fill 46 and 50; text 232 and 252; pad fifth subrecord 170, 171, 185, 186 and 194; pad sixth subrecord 0 and 651 | census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository), S-0173 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-LENGTHS |
| A longer subrecord appends bytes: the fields of the shortest form keep their offsets, and a reader skips to the end of the subrecord after the fields it knows | S-0160, S-0173 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-LENGTHS |
| KiCad's reader takes the extra fields of the long forms from fixed length thresholds: a track or arc tail of at least 9 bytes holds a union index and a 32-bit layer id, a via longer than 74 bytes holds thermal and per-layer diameter fields, a pad fifth subrecord longer than 110 bytes holds the hole rotation, a text first subrecord of at least 123 bytes holds the font fields | S-0160, S-0173 | INFERRED | H-A-RD-PCB-LENGTHS |
| A component body (type 12) is framed like the other primitives; its fields are not read here, and the storages `ComponentBodies6` and `ShapeBasedComponentBodies6` stay bytes | S-0002, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-FRAME |

## Fields

One row per typed field of a binary record. "Offset" is counted from the start of the subrecord's bytes
(after its length word); "from length" is the subrecord length from which the field exists: below it the
field is `None`. The common prefix (`Prefix`) is the first 13 bytes of the subrecord that holds the
geometry (the only one of a track, arc, via, fill or region; the fifth of a pad; the first of a text).
Bytes after the last typed offset are the record's `tail`: after 36 for a track of at least 35 bytes,
47 for an arc of at least 47, 31 for a via, 37 for a fill, 114 for a pad's fifth subrecord and 596 for its
sixth, 119 for a text of at least 123 bytes (40 below), and after the last hole for a region.

| record | field | subrecord | offset | from length | source | label | hypothesis |
|---|---|---|---|---|---|---|---|
| Prefix | layer | the geometry subrecord | 0 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| Prefix | flags1 | the geometry subrecord | 1 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| Prefix | flags2 | the geometry subrecord | 2 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| Prefix | net | the geometry subrecord | 3 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| Prefix | polygon | the geometry subrecord | 5 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| Prefix | component | the geometry subrecord | 7 | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| Prefix | locked | the geometry subrecord | 1 (bit 2 clear) | 13 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | x1 | 1 | 13 | 33 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | y1 | 1 | 17 | 33 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | x2 | 1 | 21 | 33 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | y2 | 1 | 25 | 33 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | width | 1 | 29 | 33 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| TrackRecord | sub_polygon | 1 | 33 | 35 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-LENGTHS |
| ArcRecord | cx | 1 | 13 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | cy | 1 | 17 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | radius | 1 | 21 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | start_angle | 1 | 25 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | end_angle | 1 | 33 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | width | 1 | 41 | 45 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ArcRecord | sub_polygon | 1 | 45 | 47 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-LENGTHS |
| ViaRecord | x | 1 | 13 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | y | 1 | 17 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | diameter | 1 | 21 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | hole | 1 | 25 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | start_layer | 1 | 29 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | end_layer | 1 | 30 | 31 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ViaRecord | tented_top | 1 | 1 (bit 5) | 31 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-LENGTHS |
| ViaRecord | tented_bottom | 1 | 1 (bit 6) | 31 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-LENGTHS |
| FillRecord | x1 | 1 | 13 | 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| FillRecord | y1 | 1 | 17 | 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| FillRecord | x2 | 1 | 21 | 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| FillRecord | y2 | 1 | 25 | 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| FillRecord | rotation | 1 | 29 | 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| PadRecord | name | 1 | 0 | 0 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-KICAD-LIB |
| PadRecord | x | 5 | 13 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | y | 5 | 17 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | size_top | 5 | 21 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | size_mid | 5 | 29 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | size_bottom | 5 | 37 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | hole | 5 | 45 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | shape_top | 5 | 49 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | shape_mid | 5 | 50 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | shape_bottom | 5 | 51 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | rotation | 5 | 52 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | plated | 5 | 60 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | stack_mode | 5 | 62 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | paste_expansion | 5 | 86 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | solder_expansion | 5 | 90 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | paste_mode | 5 | 101 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | solder_mode | 5 | 102 | 110 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | hole_rotation | 5 | 106 | 114 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | inner_sizes | 6 | 0 (x), 116 (y) | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | inner_shapes | 6 | 232 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | hole_shape | 6 | 262 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | slot_length | 6 | 263 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | slot_rotation | 6 | 267 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | hole_offsets | 6 | 275 (x), 403 (y) | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-PAD |
| PadRecord | alternate_shapes | 6 | 532 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| PadRecord | corner_percentages | 6 | 564 | 596 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| TextRecord | x | 1 | 13 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | y | 1 | 17 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | height | 1 | 21 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | stroke_font | 1 | 25 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | rotation | 1 | 27 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | mirrored | 1 | 35 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | stroke_width | 1 | 36 | 40 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | is_comment | 1 | 40 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | is_designator | 1 | 41 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-TEXT-2 |
| TextRecord | font_type | 1 | 43 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | bold | 1 | 44 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | italic | 1 | 45 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | font_name | 1 | 46 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | inverted | 1 | 110 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | margin | 1 | 111 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | wide_index | 1 | 115 | 123 | S-0160, S-0002, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-TEXT-2 |
| TextRecord | short_text | 2 | 0 | 1 | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-PCB-TEXT-2 |
| TextRecord | text | WideStrings6 or WideStrings | the entry of wide_index | — | S-0002, S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-TEXT-2 |
| RegionRecord | hole_count | 1 | 14 | 26 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| RegionRecord | properties | 1 | 18 | 26 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| RegionRecord | outline | 1 | 22 + the text length | 26 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| RegionRecord | holes | 1 | after the outline | 26 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| RegionRecord | closing | 1 | after the last outline vertex (shape-based form) | 26 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| RegionVertex | x | a vertex of 16 or 37 bytes | 0 (double; 1 as 32-bit in the shape-based form) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | y | a vertex of 16 or 37 bytes | 8 (double; 5 as 32-bit) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | is_round | a vertex of 16 or 37 bytes | 0 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | cx | a vertex of 16 or 37 bytes | 9 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | cy | a vertex of 16 or 37 bytes | 13 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | radius | a vertex of 16 or 37 bytes | 17 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | start_angle | a vertex of 16 or 37 bytes | 21 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |
| RegionVertex | end_angle | a vertex of 16 or 37 bytes | 29 (shape-based form only) | 16 or 37 | S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | INFERRED | H-A-RD-PCB-REGION |

| fact | source | label | hypothesis |
|---|---|---|---|
| The common prefix: offset 0 the layer id (one byte), 1 and 2 two flag bytes, 3 the net index, 5 the polygon index and 7 the component index (unsigned 16-bit, `0xFFFF` none), 9 to 12 four bytes not read. Bit 2 of the first flag byte set means unlocked. A pull-back track of a plane carries the polygon index `0xFFFE`, which names no polygon | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), census of S-0176 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| A text's first subrecord has the prefix with the component index at 7; a via's has the prefix too, on layer 74, and its flags bits 5 and 6 tent the top and the bottom | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| A fill (type 6) is the prefix, the two corners (x1, y1, x2, y2 as 32-bit) and the rotation as a double at 29; a fill is a rectangle on any layer, rotated about its centre, and a keep-out when its layer or flag says so | S-0160, S-0285, census of S-0172, S-0174, S-0176, S-0188, S-0199 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| Lengths are signed 32-bit integers of 1/10 000 mil; one unit is exactly 2.54 nm. Angles and region vertices of the plain form are IEEE-754 doubles | S-0002, S-0160, S-0163 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |

## Property text

| fact | source | label | hypothesis |
|---|---|---|---|
| A property block is a 32-bit little-endian word whose low 24 bits are the payload length, then the payload; the payload ends with one NUL that the length counts. The top byte is 0 in the property storages | S-0002, S-0148, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-FRAME |
| The text is `KEY=VALUE` fields separated by `\|`. A long record holds one CR before a `\|RECORD=Board` field; the CR belongs to the separator. Keys repeat (`RECORD`, the common keys of the board record) | S-0002, S-0160, census of S-0170 to S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-CODEC |
| Text bytes are 8-bit; KiCad's parser decodes them as ISO-8859-1, in which every byte is one character, and prefers the value of a `%UTF8%<KEY>` field, which holds UTF-8, over `<KEY>` | S-0148, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-CODEC |
| Lengths in property text are decimal mils followed by `mil`, such as `10mil` or `-0.0001mil`; booleans are `TRUE` and `FALSE` (`T`, `F` in older files); angles are in a scientific form with a leading space | S-0163, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-CODEC |
| `Rules6` holds per rule a 16-bit kind number, then one property block | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-RULE |

## Keys

The typed keys of property records. Every other key stays in the record's `fields`, in order and with
its duplicates.

| record | key | field | source | label | hypothesis |
|---|---|---|---|---|---|
| NetRecord | `NAME`, `UNIQUEID` | `name`, `unique_id` | S-0160, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| ComponentRecord | `LAYER`, `X`, `Y`, `ROTATION`, `PATTERN`, `LOCKED`, `NAMEON`, `COMMENTON` | `layer`, `x`, `y`, `rotation`, `pattern`, `locked`, `name_on`, `comment_on` | S-0160, S-0161, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ComponentRecord | `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEHIERARCHICALPATH`, `SOURCEFOOTPRINTLIBRARY`, `SOURCECOMPONENTLIBRARY`, `SOURCELIBREFERENCE`, `UNIQUEID` | `source_designator`, `source_unique_id`, `source_hierarchical_path`, `source_footprint_library`, `source_component_library`, `source_lib_reference`, `unique_id` | S-0161, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-KICAD-DOC |
| ClassRecord | `NAME`, `KIND`, `SUPERCLASS`, `M0`, `M1`, … | `name`, `kind`, `superclass`, `members` | S-0160, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| PolygonRecord | `LAYER`, `NET`, `POLYGONTYPE`, `HATCHSTYLE`, `POURINDEX`, `NAME` and the eight vertex keys | `layer`, `net`, `polygon_type`, `hatch_style`, `pour_index`, `name`, `vertices` | S-0160, S-0161, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-POLYNAME |
| RuleRecord | `RULEKIND`, `NAME`, `ENABLED`, `PRIORITY`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `COMMENT`, `UNIQUEID` and the leading kind number | `rule_kind`, `name`, `enabled`, `priority`, `scope1`, `scope2`, `comment`, `unique_id`, `kind_number` | S-0160, S-0286, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-RULE |
| BoardRecord | `KIND`, `VERSION`, `FILENAME`, `ORIGINX`, `ORIGINY`, `DISPLAYUNIT` | `kind`, `version`, `filename`, `origin`, `display_unit` | S-0002, S-0160, census of S-0170 to S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-STACK |
| BoardRecord | `KIND<k>`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` | `outline` | S-0002, S-0160 | INFERRED | H-A-RD-PCB-KICAD-DOC |
| BoardRecord | `LAYER<i>NAME`, `PREV`, `NEXT`, `MECHENABLED`, `COPTHICK`, `DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL` | `layers`, `copper_chain` | S-0160, S-0161, census of S-0170 to S-0176 (files kept outside the repository) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-STACK |
| BoardRecord | `V9_STACK_LAYER<i>_NAME`, `_LAYERID`, `_COPTHICK`, `_DIELTYPE`, `_DIELCONST`, `_DIELHEIGHT`, `_DIELMATERIAL` and the entry's other keys | `stack` | census of S-0170 to S-0176, S-0199, S-0200 (files kept outside the repository), S-0173 | INFERRED | H-A-RD-PCB-STACK |
| BoardRecord | `PLANE<n>NETNAME`, `LAYERPAIR<i>LOW`, `LAYERPAIR<i>HIGH` | `plane_nets`, `layer_pairs` | S-0160, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-STACK |
| LibFootprint | `PATTERN`, `HEIGHT`, `DESCRIPTION` of `Parameters` | `name`, `height`, `description` | S-0162, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcblib_read_oracle.py) | H-A-RD-PCB-KICAD-LIB |
| LibFootprint | `PRIMITIVEINDEX`, `PRIMITIVEOBJECTID`, `UNIQUEID` of `UniqueIDPrimitiveInformation` | `unique_ids` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), census of S-0170, S-0171 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |

| fact | source | label | hypothesis |
|---|---|---|---|
| A polygon's `NAME` is the character codes of the name in decimal, joined by commas | census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository), S-0173 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-POLYNAME |
| A class's `KIND` is a number (0 net, 1 component); `SUPERCLASS` marks a class that holds every object of its kind; the members are `M0`, `M1`, … until the first missing key | S-0160, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | INFERRED | H-A-RD-PCB-FRAME |
| The copper stack follows `LAYER<i>NEXT` from layer 1 until 0; internal planes 39 to 54 join the chain, with their net in `PLANE<n>NETNAME`, and `(No Net)` names none | S-0160, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-STACK |
| The physical list `V9_STACK_LAYER<i>_…` holds the layers top to bottom with their long ids (`pcb-library.md`, "Long layer ids"); its dielectric names and order may differ from the numbered keys | census of S-0176, S-0199, S-0200 (files kept outside the repository), S-0173 | INFERRED | H-A-RD-PCB-STACK |
| `FILENAME` of a saved board record holds the path of the saving machine; no reader output and no issue message carries it | census of S-0170 to S-0176 (files kept outside the repository), S-0002 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-CODEC |

## Regions

| fact | source | label | hypothesis |
|---|---|---|---|
| A region (type 11, one subrecord) is the 13-byte prefix, one byte, a 16-bit hole count at 14, two bytes, then at 18 a 32-bit length and a property text of that length that starts without `\|` (`V7_LAYER`, `KIND`, `ISBOARDCUTOUT`, `ISSHAPEBASED`, `SUBPOLYINDEX` and others) | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| In `Regions6` and in a library footprint the outline is a 32-bit vertex count and that many vertices of two doubles (x, y in units) | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| In `ShapeBasedRegions6` the outline holds one vertex more than its count, each 37 bytes: a round flag (one byte), the position, the centre and the radius (32-bit each) and two angles (doubles); the extra vertex closes the outline | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| In both forms each hole is a 32-bit vertex count and that many vertices of two doubles; the region ends after the last hole | S-0160, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |
| The poured copper of a polygon is its regions in `Regions6` with the polygon's index in the prefix, and `ShapeBasedRegions6` holds the same number of records | S-0161, census of S-0172, S-0174, S-0175, S-0176 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-REGION |

## Wide strings

| fact | source | label | hypothesis |
|---|---|---|---|
| `WideStrings6/Data` of a document is a table of entries: a 32-bit index, a 32-bit byte length that counts a 2-byte NUL, and the UTF-16LE text with that NUL | S-0002, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-TEXT-2 |
| An entry whose byte length is 2 or less is an empty string, and no text bytes follow its length: the document of 2017 stores its four empty entries that way, with the next entry's index directly after the length | S-0148, census of S-0188 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-TEXT-2 |
| A text whose wide-string index names an entry shows that entry; else it shows the 8-bit string of its second subrecord (one length byte and the characters) | S-0002, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-TEXT-2 |
| In a library footprint, `WideStrings` is one property block of `ENCODEDTEXT<i>` values, each the character codes of the text in decimal joined by commas; entry `i` belongs to the text whose wide-string index is `i` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), census of S-0170, S-0171 (files kept outside the repository) | INFERRED | H-A-RD-PCB-TEXT-2 |
| In a document a component's designator text has the is-designator flag and the component's index, and its shown string is the component's `SOURCEDESIGNATOR`; a component of a repeated sheet (its `SOURCEDESIGNATOR` shared by several components, three ids in `SOURCEUNIQUEID`) shows that designator followed by a channel suffix, and a designator can be changed on the board alone (84 and 2 of 248 texts on the document of 2017) | S-0161, census of S-0172, S-0174, S-0175, S-0176, S-0188 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-TEXT-2 |

## Rules

A rule of `Rules6` is a 16-bit kind number and one property block (see "Property text"). The rule types
are named on Altium's reference pages (S-0287); priorities count from 1, the highest, and a rule has one
or two scope queries (S-0286). The reader keeps every key; c0042's `read.rules.map_rules` reads them.
Kind numbers seen in the seven corpus documents with their `RULEKIND` text, 39 numbers (census of
2026-10-05):

| number | `RULEKIND` | number | `RULEKIND` | number | `RULEKIND` |
|---|---|---|---|---|---|
| 0 | Clearance | 16 | UnRoutedNet | 49 | FanoutControl |
| 2 | Width | 17 | ViasUnderSMD | 50 | Height |
| 4 | MatchedLengths | 19 | MinimumAnnularRing | 51 | DiffPairsRouting |
| 6 | PlaneConnect | 20 | PolygonConnect | 52 | HoleToHoleClearance |
| 7 | RoutingTopology | 21 | AcuteAngle | 53 | MinimumSolderMaskSliver |
| 8 | RoutingPriority | 23 | SMDToCorner | 54 | SilkToSolderMaskClearance |
| 9 | RoutingLayers | 24 | ComponentClearance | 55 | SilkToSilkClearance |
| 10 | RoutingCorners | 25 | ComponentOrientations | 56 | NetAntennae |
| 11 | RoutingVias | 42 | HoleSize | 57 | AssemblyTestpoint |
| 12 | PlaneClearance | 43 | FabricationTestpoint | 58 | AssemblyTestPointUsage |
| 13 | SolderMaskExpansion | 44 | FabricationTestPointUsage | 59 | SilkToBoardRegionClearance |
| 14 | PasteMaskExpansion | 46 | SMDToPlane | 62 | UnpouredPolygon |
| 15 | ShortCircuit | 48 | LayerPairs | 63 | BoardOutlineClearance |

| fact | source | label | hypothesis |
|---|---|---|---|
| Over the corpus a kind number goes with one `RULEKIND` text (the table above); the reader types the number, the text, the name, `ENABLED`, `PRIORITY`, the two scope texts, `COMMENT` and `UNIQUEID`, and parses no scope | S-0160, S-0286, S-0287, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-RULE |

## Storages kept as bytes

| fact | source | label | hypothesis |
|---|---|---|---|
| A saved document holds storages the reader does not type: `ComponentBodies6`, `ShapeBasedComponentBodies6`, `Dimensions6`, `DifferentialPairs6`, `Connections6`, `FromTos6`, `SmartUnions`, `UnionNames`, `BoardRegions`, `Models`, `EmbeddedFonts6`, `FileVersionInfo`, `Texts`, `PrimitiveGuids`, `PrimitiveParameters`, the option and pad-via storages, and violation storages named after a rule; the reader returns their streams unchanged | S-0002, S-0161, census of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-IDENTITY |
| A saved library holds beside its footprints `FileHeader`, `SectionKeys` (when a name is shortened), the `Library` storage with its streams and sub-storages, and `FileVersionInfo`; the reader types `FileHeader`, `SectionKeys` and `Library/Data` and returns every stream | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), census of S-0170, S-0171 (files kept outside the repository) | CORPUS-VERIFIED (11 rows; 2026-10-05) | H-A-RD-PCB-IDENTITY |

## What KiCad does not import

The document oracle (`tests/kicad/altium/test_pcbdoc_read_oracle.py`, `kicad-cli` 10.0.6, 2026-10-05)
compares what `kicad-cli pcb import` returns with the reader's records. Each row below is a difference
of KiCad's import, not of the file; `docs/evidence/altium-pcb-read.md` gives its count per corpus row.

| fact | source | label | hypothesis |
|---|---|---|---|
| KiCad converts a length as `units · 2.54` rounded to the nanometre and then to the nearest 10 nm, so its positions and sizes differ from the exact value by up to 5 nm; the oracle compares with that conversion | S-0163, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| KiCad imports no pad whose layer is Top Paste or Bottom Paste (35, 36): 10 such pads on one row, 0 elsewhere | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| A copper region of a component, and a copper fill of a component without a net, become pads of the footprint without a number (a custom shape for a region, a rectangle for a fill); a component fill with a net becomes none | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| A pad without a component (a free pad) becomes a footprint of its own with a reference of KiCad's; a pad on a paste layer does not | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| A non-plated through-hole pad has no pad number in KiCad | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| KiCad's reference of a footprint is the shown string of the component's designator text (with `UNK` before a name of digits only), which differs from `SOURCEDESIGNATOR` for the 86 components of `H-A-RD-PCB-TEXT-2` on one row | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| Of the free tracks on copper layers KiCad's board holds exactly those with a net; tracks of a component go to its footprint, and component, keep-out and other-layer records are not compared. Arcs are not compared | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| KiCad makes one zone per polygon of `Polygons6`, split planes included; free regions, fills and polygon pours are not compared further | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py) | H-A-RD-PCB-KICAD-DOC |
| The top-layer shape of a simple pad (stack mode 0) is a circle or an oval for shape 1, a rectangle for shape 2, and a rounded rectangle of ratio `percentage / 200` for alternate shape 9; an octagon (shape 3) and a pad of another stack mode keep their sizes and are not compared by shape | S-0160, S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |
| A slotted hole (hole shape 2) is not compared by size | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-05; test_pcbdoc_read_oracle.py, test_pcblib_read_oracle.py) | H-A-RD-PCB-PAD |

## Fenolite's choices

These are choices of the reader, not format facts:

- **Minimums, never a list.** A subrecord at or above its minimum is typed; fields past its end are
  `None`; bytes past the known fields are `tail`. The minimums are those of the shortest form that gives
  every core field (track 33, arc 45, via 31, fill 37, text 40, pad fifth subrecord 110, sixth 0 or 596,
  region 26), lower than the writer's and the test reader's (36 and 47) because the field tables allow it.
- **Lenient by default.** A short record is kept as a `RawPrimitive` with a warning; an unknown type
  byte or a cut subrecord ends its stream, the rest kept as `trailing`; other storages are still read.
  `strict=True` raises `PcbReadError` on the first error.
- **ISO-8859-1.** Property text and 8-bit strings decode as ISO-8859-1 (every byte one character, as
  KiCad's parser does, which keeps the oracle comparable); a `%UTF8%` key is preferred when it decodes.
- **Units kept.** Lengths stay integers of 1/10 000 mil and angles and plain region vertices the stored
  doubles; `to_nm` (half to even, `fenolite.core.units.u_to_nm`) and `to_nm_exact` convert.
- **Lossless.** Every record keeps its bytes (`raw`); a typed field is a view. Two stack views are given,
  the numbered keys and the physical list, without merging them.
