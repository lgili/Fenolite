## ADDED Requirements

### Requirement: Placement legality in a build
`fenolite build` with the KiCad target (`--target kicad`, the default) SHALL judge the placement of the board it is about to write with `fenolite.placement.legality.check` (`placement`, "Placement legality"), in `cmd_build.placement_guard`, after `lens.build.build_design` returns its files and before `cmd_build` returns its plan, on `--dry-run` and `--confirm` alike. When `build_design` refused (no files), the check MUST NOT run and `result.placement.ran` MUST be false. With `--target altium` the check MUST NOT run and `result` holds no `placement`.
- **What is judged.** `cmd_build` MUST read the planned `<name>.kicad_pcb` text back with `read_board`, take the extents from c0028's `BoardFrame.placed_extents` of `KicadBackend`, the rings from `backends.kicad.outline.board_outline` of that board, and `edge_clearance` from `placement.legality.edge_clearance` of the built model design (0 without a board-wide `edge_clearance` rule). The check therefore judges the bytes that will be written, preserved placements (`layout-lens`) included. It MUST read and write no file.
- Each `place.*` issue MUST be reported with a severity no higher than `warning`, so a build never refuses and never exits 5 for placement.
- Parts that the build stages (`result.staged`, reported as `layout.unplaced`) MUST NOT be judged.
- **Codes.** The codes are those of `placement.ISSUE_CODES` (`placement`, "Placement issue codes"). They are not build findings: they join the envelope's `issues` as "Build issue codes" allows for codes that later requirements add, and `lens.build.BUILD_ISSUE_CODES` and `build_design` stay unchanged, because `lens` may not import `placement` (`package-layering`).
- `result.placement` MUST hold `ran` and `counts`, the number of issues by code.
- The step of `cmd_build` and the `result` key are additions that "Build command" allows.

#### Scenario: Overlap reported, build written
- **GIVEN** a blink variant whose `R1` and `D1` are placed on the same side with courtyards that overlap by 0.1 mm and copper that stays clear
- **WHEN** `fenolite build … --confirm` runs
- **THEN** the exit code is 0, the board is written, and `issues` holds one `place.courtyard-overlap` warning naming `D1,R1`

#### Scenario: Part over the edge
- **GIVEN** a blink variant whose `R1` is placed across the outline's right edge
- **WHEN** the build runs with `--dry-run`
- **THEN** `issues` holds `place.outside-outline` naming `R1` as a warning, and nothing is written

#### Scenario: Staged parts are not judged
- **GIVEN** a blink variant in which `R1` has no `place()`
- **WHEN** the build runs
- **THEN** `issues` holds `layout.unplaced` for `R1` and no `place.outside-outline` for it

#### Scenario: Clean blink stays clean
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `issues` holds no `place.*` issue, `result.placement.counts` is empty, and every file has the bytes it had before this change
