## ADDED Requirements

### Requirement: Optional drawn font value
The model SHALL provide a frozen `DrawnFont` with optional size, thickness, bold, italic and face. Size axes MUST be positive integer nm and thickness nonnegative integer nm; booleans MUST retain presence. Empty fonts, floats, invalid names and bool-as-length values MUST refuse.

#### Scenario: Exact asymmetric font
- **GIVEN** an authored font with distinct positive width and height, zero thickness and explicit false bold
- **WHEN** it is constructed and serialized
- **THEN** each value and its presence remain exact

#### Scenario: Invalid model input
- **WHEN** a font contains zero size, a fractional nm, a control character in its face or no attributes
- **THEN** construction refuses before changing any model

### Requirement: Drawn text style surfaces
Drawn fields, labels and sheet pins SHALL carry optional fonts. Labels and pins SHALL carry optional explicit justification. Sheet references SHALL carry optional unique `Sheetname` and `Sheetfile` field poses. Defaults MUST retain the previous model meaning; field poses MUST NOT supply text overrides.

#### Scenario: Sheet property style
- **GIVEN** a sheet reference with an explicitly styled `Sheetname` pose
- **WHEN** it is lowered
- **THEN** its typed sheet name supplies the text and the pose supplies only placement and effects
