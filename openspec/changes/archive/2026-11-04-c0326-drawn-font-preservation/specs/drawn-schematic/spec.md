## ADDED Requirements

### Requirement: Closed drawn font syntax
The drawn TOML codec SHALL read and canonically write optional fonts on fields, labels and sheet pins, explicit label/pin justification and sheet-property poses. Width and height MUST use exact decimal mm mapped to integer nm. Unknown keys, unsupported effects and inexact lengths MUST refuse with a locator.

#### Scenario: Asymmetric font round trip
- **GIVEN** a drawing with different font width and height on every typed text surface
- **WHEN** it is written, read and written again
- **THEN** the model and both texts are equal without swapping axes

#### Scenario: Unknown effect
- **WHEN** a drawn font table contains an unknown key
- **THEN** reading refuses and names the table and key

#### Scenario: Fraction below Decimal context precision
- **WHEN** a font length has fractional nanometres beyond the ambient decimal precision
- **THEN** reading refuses the exact remainder rather than rounding it into an accepted integer

### Requirement: Drawn field text authority
Styled drawn fields MUST continue to obtain Reference, Value and Footprint text from code. The drawing MUST NOT hide conflicting source text in generic properties or opaque placeholders. A font-preservation change SHALL leave an independent footprint-text disagreement visible to fidelity comparison.

#### Scenario: Conflicting footprint texts
- **GIVEN** an original PCB selector different from its visible schematic Footprint text
- **WHEN** the drawing is converted and rebuilt with preserved fonts
- **THEN** the code selector remains authoritative and the remaining text difference is reported
