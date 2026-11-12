## ADDED Requirements

### Requirement: Polygon Manager counts pending repours
The K6.5 instructions SHALL ask how many polygons the Polygon Pour Manager lists as needing a repour. The instructions SHALL distinguish that status from zero area. The authored `P5` and `P5_NONET` polygons intentionally hold no copper and count only if the manager flags them as needing a repour.

#### Scenario: Empty negative controls
- **GIVEN** the computed `pour` sample with intentionally empty `P5` and `P5_NONET`
- **WHEN** the Polygon Pour Manager lists no polygons as needing a repour
- **THEN** K6.5 receives zero and the two empty polygons are not counted

### Requirement: Batch DRC retains the polygon negative control
K6.6 SHALL retain the complete native DRC text report. The check SHALL allow at most one exact `Dead Copper - Net Not Assigned` finding under `Un-Routed Net Constraint` for the authored `P5_NONET` on Top Layer, if the kit board confirms that control is netless and holds no copper. Every other finding naming a polygon SHALL fail the check.

#### Scenario: Preserve the one expected report finding
- **GIVEN** a native batch DRC report for the computed `pour` sample and its netless, empty `P5_NONET` control
- **WHEN** the report contains the exact expected diagnostic, alone among polygon findings
- **THEN** K6.6 passes with the raw report still intact
- **AND** a duplicate, another polygon name, or a different diagnostic on that control fails
