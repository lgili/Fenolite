## MODIFIED Requirements

### Requirement: Placements file in a build
`cmd_build` SHALL read `<script folder>/edits.toml` when it exists, and otherwise `<script folder>/placements.toml` when that exists, and pass the position entries to the layout lens as `source` and the whole edits to the property merge (`edit-merge`, "Edits file schema", "Property merge in a build"), as "Build command" allows for added steps and `result` keys.
- `edits.toml` MUST be read with `lens.edits.read_edits(text, origin=dsl.BOARD_ORIGIN, file="edits.toml")`, and `placements.toml` with `lens.placements.read_placements(text, origin=dsl.BOARD_ORIGIN, file="placements.toml")`, whose entries are position edits without a recorded script request; a `FormatError` of either MUST exit 3 (`FEN-3004`) before any planned write.
- When both files exist, `placements.toml` MUST NOT be read, and `edit.legacy-file` (warning) MUST name it with the hint "delete placements.toml; edits.toml replaces it".
- Their `layout.source-invalid` issues MUST be reported, and an error among them MUST stop the build as any other build error does (exit 5, nothing written).
- Without `--discard-layout`, the entries MUST be passed to `prepare` as `source`. With `--discard-layout`, `cmd_build` MUST call `prepare` with an `ExistingProject` whose three texts are `None` and the same `source`, so no file of the output folder is read and the file still applies ("Placement precedence"); the value, footprint and property edits then apply over the script without a CAD side.
- With `--target altium`, the placements passed on MUST be those that `prepare` gives with an `ExistingProject` whose texts are `None` and the same `source`, and the value, footprint and property edits MUST apply over the script, so both targets build a part from the file.
- `result.preserved.source` MUST hold `file` (`edits.toml`, `placements.toml`, or `null` when no file was read), `used` (component paths that took their placement from the file), `stale` and `unknown` (paths of `layout.source-stale` and `layout.source-unknown`); "Layout preservation evidence" allows the key.
- `.fenolite/build.json` MUST record the SHA-256 of the file that was read, so `check` can tell that the layout's source changed.

#### Scenario: File places a part
- **GIVEN** a blink variant whose `R1` has no `place()`, and a `placements.toml` beside its script with `[part."R1"]`, `x = 20`, `y = 10`
- **WHEN** it is built into an empty folder with `--confirm --json`
- **THEN** `R1` is at (120 mm, 110 mm), `issues` hold no `layout.unplaced`, and `result.preserved.source.used` is `["R1"]`

#### Scenario: File survives a discarded layout
- **GIVEN** a confirmed blink build in `B` edited by `edit_blink`, and an `edits.toml` written by `fenolite sync --to-source --confirm`
- **WHEN** the blink is built again with `--discard-layout --confirm`
- **THEN** `D1` is 4 mm right of its `place()` position, the segments and the via of the edit are gone, and `issues` hold one `layout.place-overridden` naming `D1`

#### Scenario: Invalid file stops the build
- **GIVEN** a `placements.toml` whose `R1` table has `side = "left"`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` hold `layout.source-invalid` naming `R1` and `side`, and nothing is written


#### Scenario: Value edit applied without the board
- **GIVEN** an `edits.toml` beside the blink script whose `R1` table holds `value = "4k7"` and whose `over` table holds `value = "330"`, the script's value
- **WHEN** the blink is built into an empty folder with `--confirm --json`, and then with `--target altium` into another
- **THEN** both builds write `R1` with the value `4k7`, and `.fenolite/circuit.json` of each holds `4k7`

#### Scenario: Both files present
- **GIVEN** an `edits.toml` and a `placements.toml` beside the script
- **WHEN** the build runs with `--dry-run --json`
- **THEN** `result.preserved.source.file` is `edits.toml` and `issues` hold one `edit.legacy-file` naming `placements.toml`
