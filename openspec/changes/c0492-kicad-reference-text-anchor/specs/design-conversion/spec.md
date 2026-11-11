## ADDED Requirements

### Requirement: Text anchors survive a round trip through KiCad
An Altium → KiCad → Altium conversion SHALL write every text and designator record at the source record's
position, rotation and mirror (change c0492).

#### Scenario: Texts at four angles on both sides
- **GIVEN** an authored PCB document with designators and free stroke texts at 0°, 90°, 180° and 270° on
  both sides
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** each text record of the result holds the source's position, rotation and mirror

#### Scenario: A field moved in KiCad
- **GIVEN** the KiCad board of that conversion with one `Reference` field changed to `(justify center)` and
  moved by half its box, so its ink stays in place
- **WHEN** it is converted to Altium
- **THEN** the designator record is written within one stroke width of the source position
