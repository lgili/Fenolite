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
of the via record of that id, and as `UNIONINDEX` of the region or component record of that id. It SHALL
write a free track or arc that is a union member in the long form of its record (49 and 60 bytes) with the
index at offset 36 and 48, the long id of its layer and the restriction byte 0. It SHALL write the index of
a free text member, and of a member component for its designator and comment, at offset 119 of the text
record. Every other record SHALL keep 0.

#### Scenario: A via written with its union

- **GIVEN** a `PcbDocSpec` whose `unions` give the via `v1` the index 1048581
- **WHEN** the document is written
- **THEN** the record of `v1` holds 1048581 at offset 70 and every other via holds 0

#### Scenario: A text keeps its union

- **GIVEN** a board whose free text and whose first footprint are members of the union 77
- **WHEN** the document is written
- **THEN** the free text's record and the component's designator and comment records hold 77 at offset 119,
  and every other text 0

#### Scenario: A length tuning comes back in its union

- **GIVEN** a board whose first track is a member of the union 17 and whose arc is a member of the union 19
- **WHEN** the document is written
- **THEN** the track record is 49 bytes with 17 at offset 36 and the arc record 60 bytes with 19 at offset
  48, and every other track keeps 36 bytes

### Requirement: A stroke text is written with the font its bag names

The Altium PCB writer SHALL write a text or a field without a face whose `altium` bag holds a well-formed
`stroke_font` as a text record of font type 0 with that font name, bold and italic. A text without one, or
with a value that is not two flags, a space and a name of at most 31 characters, SHALL be written with no
font name, as before.

#### Scenario: A stroke free text with its font

- **GIVEN** a free board text without a face whose `altium` bag holds `stroke_font` = `11 Trebuchet MS`
- **WHEN** the board is written
- **THEN** its text record holds font type 0, bold 1, italic 1 and the font name `Trebuchet MS`

### Requirement: Empty texts and line breaks are written

The Altium PCB writer SHALL write a board text whose string is empty as a text record with an empty
string, and SHALL write each line feed of a text's string as CR LF (`H-A-TEXT-CRLF`) in the record and in
its wide string. It SHALL still refuse a text that holds any other control character.

#### Scenario: An empty text and a two-line text

- **GIVEN** a board with a free text whose string is empty and one whose string is `two\nlines`
- **WHEN** the board is written
- **THEN** both texts have a record, the second holds `two\r\nlines`, and reading the document back gives
  an empty string and `two\nlines`
