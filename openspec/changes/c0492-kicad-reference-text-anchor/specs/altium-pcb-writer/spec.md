## ADDED Requirements

### Requirement: Text position from its justification
The Altium writer SHALL write each stroke text and footprint field at the lower-left corner of its text
box: its position when it is justified left and bottom, else its position moved by the offset of that
corner in the text frame, turned by its rotation and mirrored as the text is (change c0492).
- The offset MUST come from the stroke font's ink box (`silk.extents`, the glyph table), with no external
  tool.
- A free stroke text with a justification other than centred MUST NOT be refused for its justification.
- A TrueType text with a justification other than left and bottom MUST be refused with a reason that names
  its justification, until its box is measured.

#### Scenario: A centred designator from a script
- **GIVEN** an authored design script with a 1 mm designator, centred, at the part's origin
- **WHEN** it is built as an Altium document and read back
- **THEN** the read text's ink box is centred on the part's origin within one stroke width
