## ADDED Requirements

### Requirement: Imported texts keep Altium's anchor
The Altium import SHALL give every text and footprint field it reads from a PCB document `h_justify="left"`
and `v_justify="bottom"`, so its position is the lower-left corner of its text box as the document stores
it (change c0492).
- The rotation and mirror MUST be read as before.
- The content id of a text or field MUST NOT change.
- The anchor MUST be recorded in `docs/formats/altium/pcb-records.md` with hypothesis `H-A-IMP-TEXT-ANCHOR`
  and an evidence label.

#### Scenario: A designator converted to KiCad
- **GIVEN** an authored PCB document with one component whose designator is a 1 mm stroke text at 0°, and
  the same component on the bottom side, mirrored, at 90°
- **WHEN** it is converted to KiCad
- **THEN** each `Reference` field is written with `(justify left bottom)`, mirrored on the bottom
- **AND** its ink box lies within one stroke width of the ink box of `kicad-cli pcb import altium` for the
  same document
