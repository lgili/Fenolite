## ADDED Requirements

### Requirement: Generated outline stroke width
The KiCad writer SHALL use `Outline.stroke_width` for every generated root line and arc, including lowered cut-outs and slots, or the existing 100000 nm default when absent. It MUST retain the existing geometry, deterministic identifiers and suppression of edges already drawn by footprints. Reading the result MUST preserve the written graphic widths.

#### Scenario: Native line and arc
- **GIVEN** an authored outline with a nondefault width and both line and arc edges
- **WHEN** it is written for targets 9 and 10 and read back
- **THEN** each root edge graphic has the chosen width and the footprint edges keep theirs
