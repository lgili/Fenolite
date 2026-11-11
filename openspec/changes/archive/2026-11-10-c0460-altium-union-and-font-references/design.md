# Design: c0460

## TrueType texts

The reader already types a text record's long form: the font type (43), bold (44), italic (45) and the
font name as 64 bytes of UTF-16LE (46) (`pcb-records.md`, "Text"). The import gives a text of font type 1 a
`face` equal to its font name, plus its bold and italic bytes. This applies to a free text, a footprint
text, and a designator or comment field. A text of font type 0, or of a type other than 1, is imported as
before: it gets no face.

The writer's text record already has the 137-byte long form. A text or field with a `face` is written as
follows:
- font type 1;
- the face, as at most 31 UTF-16 characters and a terminator, in the 64 bytes at 46;
- its bold and italic bytes.

`text_problem_of` refuses a longer face, so the text is counted skipped, as before this change. It no
longer refuses a face, nor bold or italic together with a face. Bold or italic without a face, and knockout, are
still refused: a stroke text holds neither.

The text box at offset 124 stays 0, as in every text the writer writes. Whether Altium measures a
TrueType text again on opening is for the kit run (task 4.1).

The public row `-08` (S-0187) contains two ordinary footprint texts with a TrueType face, zero
height and positive stroke width. The Altium writer accepts a zero-size TrueType footprint text
with a positive stroke width and writes the existing height field unchanged. Fields, free texts,
stroke texts and negative heights keep their existing validation. KiCad 10.0.6 reads the intermediate
board and resaves the two records with a height of 0.001 mm. A conversion of that saved board uses
the current KiCad height. The direct round trip checks record retention. The native comparison in
task 4.1 covers display.

## Union members

A member is any item whose record holds a non-zero union index:
- a via, at offset 70 of its record (S-2190; KiCad's reader takes a union index from the long forms, S-0160);
- a region of `Regions6` or `ShapeBasedRegions6`, as `UNIONINDEX`;
- a component of `Components6`, as `UNIONINDEX`.

The import writes the index into the item's `altium` bag, under the key `union_index`.

The conversion to KiCad gathers every member that the KiCad board writes:
- a via;
- a footprint;
- a filled graphic or zone that was read from a region.

It sets each member's KiCad uuid (`native_ids["kicad"]`, a version-8 uuid of the item's id, as
`fills.fill_uuid` does), so the uuid is known before KiCad writes it. It writes one board property,
`Fenolite.Altium.UnionMembers`, packed as the storages are, mapping each uuid to its index. KiCad keeps an
item's uuid on a save and on an edit; a copy gets a new uuid and is no member.

The conversion back reads the map and gives `PcbDocSpec.unions` the index of each entity that the KiCad
board holds, by entity id. The writer then writes the index:
- at offset 70 of a via record;
- as `UNIONINDEX` of a region record or a component record.

Every other item keeps 0. An index whose `UnionNames` entry is not carried has no meaning, so the map is
written only when `UnionNames` is carried.

## Smart unions

A `SmartUnions` record holds a via stitching definition with placement coordinates in the source's
frame (`PLACEHOLDERX`, `PLACEHOLDERY`). It joins `FRAME_BOUND` with its own reason. The via members still
come back, as plain members of their union.
