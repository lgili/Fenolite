## ADDED Requirements

### Requirement: Polygon Manager counts pending repours
The K6.5 instructions SHALL ask how many polygons the Polygon Pour Manager lists as needing a repour. The instructions SHALL distinguish that status from zero area. The authored `P5` and `P5_NONET` polygons intentionally hold no copper and count only if the manager flags them as needing a repour.

#### Scenario: Empty negative controls
- **GIVEN** the computed `pour` sample with intentionally empty `P5` and `P5_NONET`
- **WHEN** the Polygon Pour Manager lists no polygons as needing a repour
- **THEN** K6.5 receives zero and the two empty polygons are not counted
