## ADDED Requirements

### Requirement: Explicit outline strokes across rebuilds
An explicit `Outline.stroke_width` SHALL participate in outline equality so a changed script width follows the existing signed/locked replacement policy. An absent width MUST retain the existing geometry-only equality behavior. Hand-edited outline geometry MUST retain its existing precedence unless the outline is locked.

#### Scenario: New script stroke on an existing board
- **GIVEN** a board built with an explicit outline width
- **WHEN** the script changes that width and builds over its unchanged native board
- **THEN** the native root strokes use the new width and another build keeps the same bytes
