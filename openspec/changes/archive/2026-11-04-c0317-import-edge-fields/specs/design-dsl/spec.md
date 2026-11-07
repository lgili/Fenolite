## ADDED Requirements

### Requirement: Outline stroke width in the DSL
`Design.board(..., outline_width=None)` SHALL accept `None` or a nonnegative DSL length and record it for every generated root outline edge, cut-out and slot. Invalid values MUST raise `DslError` naming `outline_width`. The default MUST preserve existing model JSON and native bytes. Footprint edge widths MUST remain their own.

#### Scenario: Uniform generated strokes
- **GIVEN** an authored board with line and arc edges, a cut-out and a chosen outline width
- **WHEN** it is converted to the model and built twice
- **THEN** all generated root edge strokes use that width and both builds have the same bytes

#### Scenario: Invalid width
- **WHEN** a negative length, bare number, bool or float is passed as `outline_width`
- **THEN** it is refused before the board declaration changes
