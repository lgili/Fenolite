## ADDED Requirements

### Requirement: Placement legality in a build
`lens.build.build_design` SHALL run `placement.legality.check` on the layout it is about to write, before the plan is returned, with the backend's `placed_extents`, the rings of `board_outline` and the `min` of the design's board-wide `edge_clearance` rule (0 without one).
- Each `place.*` issue MUST be reported with a severity no higher than `warning`, so a build never refuses and never exits 5 for placement.
- Parts that the build stages (`layout.unplaced`) MUST NOT be judged.
- `lens.build.BUILD_ISSUE_CODES` MUST include the `place.*` codes that `check` can give, each with severity `warning` or `info`.
- `result.placement` MUST hold the counts of issues by code.

#### Scenario: Overlap reported, build written
- **GIVEN** a blink variant whose `R1` and `D1` are placed 0.1 mm apart on the same side
- **WHEN** `fenolite build … --confirm` runs
- **THEN** the exit code is 0, the board is written, and `issues` holds one `place.courtyard-overlap` warning naming `D1,R1`

#### Scenario: Part over the edge
- **GIVEN** a blink variant whose `U1` is placed across the outline's right edge
- **WHEN** the build runs with `--dry-run`
- **THEN** `issues` holds `place.outside-outline` naming `U1` as a warning, and nothing is written

#### Scenario: Staged parts are not judged
- **GIVEN** a blink variant in which `R1` has no `place()`
- **WHEN** the build runs
- **THEN** `issues` holds `layout.unplaced` for `R1` and no `place.outside-outline` for it

#### Scenario: Clean blink stays clean
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `issues` holds no `place.*` issue, and every file has the bytes it had before this change
