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
