## MODIFIED Requirements

### Requirement: Generic component bodies
Each component whose lib id is an Altium link (`altium-build`, "Altium symbol sources") SHALL be written as a component record with one rectangle and one pin per pin of `Component.pins`; `lens.altium.generic_pins` gives every component of one lib id one pin per designator that the nets or the no-connect marks (`Circuit.no_connects`) name on any component of that lib id, so that components sharing a lib id share one body, which is also their library component ("Generic library symbols") (`altium-build`, "Altium build outputs").
- Pins MUST be in natural order: designators split into runs of digits and other characters, digit runs compared as integers and before letters, so `1`, `2`, `10`, `A1`, `B` is the order. The first ⌈n/2⌉ pins go on the left edge from top to bottom, the rest on the right edge from top to bottom.
- Geometry (mils, Fenolite choices): pins 200 long and 100 apart, the first 100 below the top edge; body width `max(600, 100 · ⌈(100 + 2 · 70 · L) / 100⌉)` for the longest shown pin name of `L` characters; body height `100 · (rows + 1)`, at least 200.
- Component record: `RECORD=1`, `LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`, `PARTCOUNT=2`, `DISPLAYMODECOUNT=1`, `CURRENTPARTID=1`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the body's top-left corner), `UNIQUEID`, `COLOR=128`, `AREACOLOR=11599871`; no orientation and no mirror (S-0130, S-0131, S-0137).
- Rectangle record: `RECORD=14`, `OWNERINDEX`, `OWNERPARTID=1`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T` (S-0130, S-0131).
- Pin record: `RECORD=2`, `OWNERINDEX`, `OWNERPARTID=1`, `FORMALTYPE=1`, `ELECTRICAL=4` (passive), `PINCONGLOMERATE`, `PINLENGTH=20`, `LOCATION.X`, `LOCATION.Y`, `NAME`, `DESIGNATOR` (S-0130, S-0131).
  - `LOCATION` MUST be the pin's body end on the body edge. `PINCONGLOMERATE` MUST be the direction (2 leftwards for left pins, 0 rightwards for right pins) plus 0x20, plus 0x10 (number shown), plus 0x08 (name shown) only when the name differs from the designator ("Binary pin record" for the meaning of the bits).
  - The electrical hot end is `LOCATION` plus `PINLENGTH` in the pin's direction, away from the body (S-0130, S-0131, S-0140).
- Children carry absolute sheet coordinates (S-0131).

#### Scenario: Natural order
- **WHEN** `generic_symbol([("10", "10"), ("B", "B"), ("2", "2"), ("A1", "A1"), ("1", "1")])` is called
- **THEN** its pins are in the order `1`, `2`, `10`, `A1`, `B`, with `1`, `2` and `10` on the left and `A1` and `B` on the right

#### Scenario: Four-pin part of the sample
- **WHEN** the records of the sample's `U2` are read
- **THEN** its rectangle is 600 × 300 mil, pins `1` and `2` are on its left edge with `PINCONGLOMERATE=50`, pins `3` and `4` are on its right edge with `PINCONGLOMERATE=48`, every pin has `PINLENGTH=20`, `ELECTRICAL=4` and `OWNERINDEX` equal to the record number of `U2`

#### Scenario: A part without connected pins
- **GIVEN** a component that no net names, and whose lib id no other component uses
- **WHEN** it is written
- **THEN** it has a component record, a 600 × 200 mil rectangle, a designator and a comment, and no pin record

#### Scenario: Components sharing a lib id share a body
- **GIVEN** a variant where `R1` uses pins `1` and `2` and `R2`, with the same lib id, uses only pin `1`
- **WHEN** it is written
- **THEN** both components have pins `1` and `2` and the same rectangle, and only pin `1` of `R2` has a stub

#### Scenario: A marked pin joins the generic body
- **GIVEN** a variant of the sample where `no_connect(u2[5])` marks a designator of `U2` that no net names
- **WHEN** it is written
- **THEN** the body of `U2` holds the pins `1`, `2`, `3`, `4` and `5`, pin `5` has no stub, and the generic library symbol of its lib id holds the same five pins

### Requirement: Binary pin record
`backends.altium.schlib.pin_record(pin)` SHALL return one framed binary record for an `altsym.AltiumPin`: a 32-bit little-endian word `(1 << 24) | <payload length>`, then the payload, without a NUL (S-0131, S-0148, S-0150).
- The payload MUST be, little-endian: record id 2 (4 bytes); byte 0; `OWNERPARTID` (2 bytes, signed); display mode 0 (1 byte); the inner-edge, outer-edge, inside and outside symbol codes (1 byte each); the description as a short string; `FORMALTYPE` 1 (1 byte); the electrical type (1 byte); `PINCONGLOMERATE` (1 byte); the pin length, `LOCATION.X` and `LOCATION.Y` of the body end (2 bytes each, signed, 10-mil units); the colour 0 (4 bytes); then the short strings name, designator, swap group, part-and-sequence and default value.
- A short string MUST be one length byte and that many ASCII bytes. Description, swap group, part-and-sequence and default value MUST be empty.
- `PINCONGLOMERATE` MUST be the direction (0 right, 1 up, 2 left, 3 down, from the body end to the hot end), plus 0x20 on every pin, plus 0x04 when hidden, 0x08 when the name is shown, 0x10 when the number is shown (`altsym.AltiumPin.conglomerate`, the one place of this choice).
- With 0x20 set, 0x08 shows the name and 0x10 the number: every pin Altium saves holds 0x20 (the corpus, S-0614), and Altium Designer 26.5.0 drew the four combinations of the check project `tests/data/altium/pinbits/` as written (S-0613). Without 0x20 Altium Designer 26 reads the two bits as hide flags (S-0612), so a pin without it MUST NOT be written; `H-A-SCHLIB-PINBITS`.
- A name or designator over 255 bytes, a value outside the signed 16-bit range, or a code outside 0 … 255 MUST raise `ValueError`.
- That two public implementations agree on this layout is recorded in the fact page; that Altium shows such pins as written is `H-A-SCHLIB-PIN`. The `FORMALTYPE` byte is 1 here and 0 in S-0150; the page records the difference.

#### Scenario: Worked pin
- **WHEN** `pin_record` is called on pin `1` named `IN`, passive, leftwards, name and number shown, length 20 units, body end (-30, 10) units, part 1
- **THEN** it returns the hex bytes `22000001` `02000000` `00` `0100` `00` `00000000` `00` `01` `04` `3a` `1400` `e2ff` `0a00` `00000000` `02494e` `0131` `00` `00` `00`

#### Scenario: Too long a name
- **WHEN** `pin_record` is called on a pin whose name has 256 characters
- **THEN** it raises `ValueError`

#### Scenario: Name hidden, number shown
- **WHEN** `pin_record` is called on a leftwards pin whose name is hidden and whose number is shown
- **THEN** its `PINCONGLOMERATE` byte is 0x32: 0x20 and 0x10 set, 0x08 clear

#### Scenario: Name shown, number hidden
- **WHEN** `pin_record` is called on a leftwards pin whose name is shown and whose number is hidden
- **THEN** its `PINCONGLOMERATE` byte is 0x2A: 0x20 and 0x08 set, 0x10 clear
