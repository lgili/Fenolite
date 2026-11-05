## MODIFIED Requirements

### Requirement: Drawn field text authority
Styled drawn fields MUST continue to obtain Reference, Value and Footprint text from code, except that a
drawn symbol marked `empty_footprint` SHALL write an empty Footprint field while its part keeps its
footprint. The drawing MUST NOT hide conflicting source text in generic properties or opaque
placeholders. A font-preservation change SHALL leave an independent footprint-text disagreement visible
to fidelity comparison.

#### Scenario: Conflicting footprint texts
- **GIVEN** an original PCB selector different from its visible schematic Footprint text
- **WHEN** the drawing is converted and rebuilt with preserved fonts
- **THEN** the code selector remains authoritative and the remaining text difference is reported

#### Scenario: Empty source Footprint field
- **GIVEN** a source symbol whose visible Footprint field is empty while its board footprint is set
- **WHEN** it is imported and built
- **THEN** `schematic.toml` marks that unit `empty_footprint = true`, the part keeps the board footprint,
  and the built schematic field is empty in the same pose and font

## ADDED Requirements

### Requirement: Empty Footprint flag of drawn symbols
A drawn symbol's `empty_footprint` flag SHALL mean that the unit's source `Footprint` field is empty
while its part builds with a footprint (`DrawnSymbol.empty_footprint`; `schematic.toml` key
`empty_footprint`, boolean, written only when true).
`fenolite.backends.kicad.drawn.extract` SHALL set it only when given the footprint each reference builds
with (`footprints`) and that footprint is not empty; without `footprints` it SHALL set nothing. A
non-boolean value MUST raise `FormatError` (`FEN-3004`) naming its locator.

#### Scenario: Flag read, written and extracted again
- **GIVEN** a drawn value with one unit flagged
- **WHEN** it is written, read, lowered for KiCad 9 and 10 and extracted again with the same footprints
- **THEN** each value equals the first and the lowered unit's Footprint field is empty

#### Scenario: Parts without a footprint
- **GIVEN** a source symbol with an empty Footprint field whose part has no footprint
- **WHEN** the import extracts the drawing
- **THEN** the unit is not flagged
