## ADDED Requirements

### Requirement: Layer count across rebuilds
`build` over an existing board SHALL keep the layout of a board of every count of `layers.CREATED_COPPER_COUNTS` whose copper layer names equal those of `layers.created_layers(copper)`, and SHALL name the board's count when they differ.
- The copper rule of "Board content outside the design is kept" MUST hold at 6 and 8 copper layers as at 2 and 4: with equal names the layout is kept, with the board's own layer rows (types and user names set in KiCad) unchanged.
- When the names differ, `layout.copper-mismatch` (error, nothing written) MUST name the board's copper layers, their count and the script's count.
- When `layers.created_count(<the board's copper names>)` gives a count m, the hint MUST name `design.board(..., copper=m)`, which keeps the board's layout, and `--discard-layout`, which creates the board on the script's count without its layout. Otherwise the hint MUST name `--discard-layout` only.
- A change of the count MUST NOT keep the layout through this requirement.

#### Scenario: Six layers rebuilt
- **GIVEN** a confirmed target-10 build of the six-layer blink variant of `design-dsl`, "Copper layer counts in a build"
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, `result.preserved.board` is true, and every file outside `.bak` files has the bytes of the first build

#### Scenario: Layers added in KiCad
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=4`, whose board gets the rows `(8 "In3.Cu" signal)` and `(10 "In4.Cu" signal)` right after the `In2.Cu` row by token edit, as KiCad's board setup adds two layers
- **WHEN** `design.py` is changed to `copper=6` and the build runs with `--confirm`
- **THEN** the exit code is 0, `result.preserved.kept` holds `D1`, `R1` and `U1`, and the written board has the six copper layers `F.Cu`, `In1.Cu` to `In4.Cu` and `B.Cu`

#### Scenario: Mismatch names the board's count
- **GIVEN** the same edited board and `design.py` still declared with `copper=4`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` holds one `layout.copper-mismatch` whose message names 6 and 4 and whose hint names `copper=6` and `--discard-layout`, and nothing is written

#### Scenario: Table that Fenolite does not create
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=8`, whose board gets the rows `(16 "In7.Cu" signal)` and `(18 "In8.Cu" signal)` right after the `In6.Cu` row by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 5, `issues` holds one `layout.copper-mismatch` whose message names 10 and 8 and whose hint names `--discard-layout` and no `copper=` value, and nothing is written
