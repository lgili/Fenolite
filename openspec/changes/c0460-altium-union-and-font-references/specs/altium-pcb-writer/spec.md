## ADDED Requirements

### Requirement: A text with a font face is a TrueType text

The Altium PCB writer SHALL write a text or a field that has a `face` as a text record of font type 1,
with the face as its font name and its bold and italic bytes. It SHALL NOT refuse such a text unless its
face is longer than the record's 31 characters. It SHALL still refuse bold or italic without a face, and
knockout.

#### Scenario: A free text with a face

- **GIVEN** a free board text with the face `Arial` and `bold` set
- **WHEN** the board is written
- **THEN** its text record holds font type 1, bold 1 and the font name `Arial`

### Requirement: Union members are written with their index

The Altium PCB writer SHALL write the union index that `PcbDocSpec.unions` gives an entity id at offset 70
of the via record of that id, and as `UNIONINDEX` of the region or component record of that id. Every other
record SHALL keep 0.

#### Scenario: A via written with its union

- **GIVEN** a `PcbDocSpec` whose `unions` give the via `v1` the index 1048581
- **WHEN** the document is written
- **THEN** the record of `v1` holds 1048581 at offset 70 and every other via holds 0

### Requirement: A stroke text is written with the font its bag names

The Altium PCB writer SHALL write a text or a field without a face whose `altium` bag holds a well-formed
`stroke_font` as a text record of font type 0 with that font name, bold and italic. A text without one, or
with a value that is not two flags, a space and a name of at most 31 characters, SHALL be written with no
font name, as before.

#### Scenario: A stroke free text with its font

- **GIVEN** a free board text without a face whose `altium` bag holds `stroke_font` = `11 Trebuchet MS`
- **WHEN** the board is written
- **THEN** its text record holds font type 0, bold 1, italic 1 and the font name `Trebuchet MS`
