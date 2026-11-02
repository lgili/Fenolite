## ADDED Requirements

### Requirement: Uniform outline strokes in an import
The import SHALL preserve a uniform nonnegative root `Edge.Cuts` width through `outline_width=` when it differs from the default. Mixed or negative root widths MUST remain `outline-width` findings and refuse strict import. `layer-table` MUST still report source non-copper names differing from the created table. Other unexpressed content MUST remain refused.

#### Scenario: Wide outline and short layer table
- **GIVEN** an authored board with one nondefault outline width and no `Eco1.User` or `Eco2.User`
- **WHEN** it is imported
- **THEN** the width is emitted, only the missing layers are reported, and strict import refuses them

#### Scenario: Mixed stroke widths
- **GIVEN** an authored board whose root edges use two widths
- **WHEN** it is imported without lossy permission
- **THEN** it exits 7 with located `outline-width` findings and writes nothing
