## ADDED Requirements

### Requirement: TrueType texts keep their font

The Altium import SHALL give a text, a footprint text and a designator or comment field read from a text
record of font type 1 the record's font name as `face`, and its bold and italic bytes as `bold` and
`italic`. A text record of any other font type SHALL be read without a face, as before.

#### Scenario: A TrueType designator keeps its font

- **GIVEN** a component whose designator text record has font type 1 and the font name `Arial`
- **WHEN** the document is imported
- **THEN** the footprint's reference field has the face `Arial`

### Requirement: Union members keep their union index

The Altium import SHALL record the non-zero union index of a via (offset 70 of its record), a track
(offset 36 of the long form of its record), an arc (offset 48 of the long form), a free text (offset 119 of
its first subrecord), a region (its
`UNIONINDEX`) and a component (its `UNIONINDEX`) in the item's `altium` bag under the key `union_index`.

#### Scenario: A stitching via is a union member

- **GIVEN** a via whose record holds the union index 1048581 at offset 70
- **WHEN** the document is imported
- **THEN** the via's `altium` bag holds `union_index` = `1048581`

#### Scenario: A length tuning is a union member

- **GIVEN** a 49-byte track record holding 17 at offset 36 and a 60-byte arc record holding 19 at offset 48
- **WHEN** the document is imported
- **THEN** the track's `altium` bag holds `union_index` = `17` and the arc's `19`

### Requirement: Stroke texts keep the font their record names

The Altium import SHALL record, for a text, a footprint text and a designator or comment field read from a
text record of font type 0 that names a font, the record's bold and italic bytes and its font name in the
item's `altium` bag under the key `stroke_font`, as `<bold><italic> <name>` with each flag `0` or `1`. It
SHALL NOT give such a text a face.

#### Scenario: A stroke comment keeps its font name

- **GIVEN** a component whose comment text record has font type 0, bold 0, italic 0 and the font name `Arial`
- **WHEN** the document is imported
- **THEN** the footprint's comment field has no face and its `altium` bag holds `stroke_font` = `00 Arial`
