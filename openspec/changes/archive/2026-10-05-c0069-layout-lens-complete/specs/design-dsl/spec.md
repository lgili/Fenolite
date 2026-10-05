## ADDED Requirements

### Requirement: Net aliases in the DSL
`Design.moved_net(old, new)` SHALL record that the net named `new` was named `old` in an earlier build, and `dsl.net_moves(design) -> Mapping[str, str]` SHALL return the recorded net aliases, new name → old name, in name order; `fenolite.dsl` SHALL re-export `net_moves` (an addition under "DSL package").
- `old` and `new` MUST be non-empty strings. `old == new`, or a second alias with the same `old` or the same `new`, MUST raise `DslError` at the call.
- `net_moves(design)` MUST raise `DslError` when `new` is not the name of a net of the design, or when `old` is, because the old net's copper would move to the new one. Chains are therefore refused.
- `cmd_build` MUST turn such a `DslError` into `DesignScriptError` (`FEN-3004`, exit 3).
- Net aliases are not model data: `to_model` MUST give the same model with and without them.
- A net alias is needed for one build only: the build writes the copper under the new name (`layout-lens`, "Copper items follow their nets").

#### Scenario: Net alias recorded
- **GIVEN** a design holding the net `LED_ANODE` and `d.moved_net("LED_A", "LED_ANODE")`
- **WHEN** `net_moves(d)` is called
- **THEN** it returns `{"LED_ANODE": "LED_A"}`

#### Scenario: Old net still present
- **GIVEN** a design holding the nets `VIN` and `VBUS`, and `d.moved_net("VIN", "VBUS")`
- **WHEN** `net_moves(d)` is called
- **THEN** `DslError` is raised naming `VIN`

#### Scenario: Model unchanged by net aliases
- **GIVEN** the blink design with and without `d.moved_net("LED_X", "LED_A")`
- **WHEN** `canonical.dump_texts(to_model(d))` is computed for both
- **THEN** the texts are equal

### Requirement: Placements file in a build
`cmd_build` SHALL read `<script folder>/placements.toml` when it exists and pass its entries to the layout lens as `source`, as "Build command" allows for added steps and `result` keys.
- The file MUST be read with `lens.placements.read_placements(text, origin=dsl.BOARD_ORIGIN, file="placements.toml")`; a `FormatError` MUST exit 3 (`FEN-3004`) before any planned write.
- Its `layout.source-invalid` issues MUST be reported, and an error among them MUST stop the build as any other build error does (exit 5, nothing written).
- Without `--discard-layout`, the entries MUST be passed to `prepare` as `source`. With `--discard-layout`, `cmd_build` MUST call `prepare` with an `ExistingProject` whose three texts are `None` and the same `source`, so no file of the output folder is read and the file still applies ("Placement precedence").
- With `--target altium`, the placements passed on MUST be those that `prepare` gives with an `ExistingProject` whose texts are `None` and the same `source`, so both targets place a part from the file.
- `result.preserved.source` MUST hold `file` (`placements.toml`, or `null` when no file was read), `used` (component paths that took their placement from the file), `stale` and `unknown` (paths of `layout.source-stale` and `layout.source-unknown`); "Layout preservation evidence" allows the key.
- `.fenolite/build.json` MUST record the SHA-256 of the file that was read, so `check` can tell that the layout's source changed.

#### Scenario: File places a part
- **GIVEN** a blink variant whose `R1` has no `place()`, and a `placements.toml` beside its script with `[part."R1"]`, `x = 20`, `y = 10`
- **WHEN** it is built into an empty folder with `--confirm --json`
- **THEN** `R1` is at (120 mm, 110 mm), `issues` hold no `layout.unplaced`, and `result.preserved.source.used` is `["R1"]`

#### Scenario: File survives a discarded layout
- **GIVEN** a confirmed blink build in `B` edited by `edit_blink`, and a `placements.toml` written by `fenolite sync --to-source --confirm`
- **WHEN** the blink is built again with `--discard-layout --confirm`
- **THEN** `D1` is 4 mm right of its `place()` position, the segments and the via of the edit are gone, and `issues` hold one `layout.place-overridden` naming `D1`

#### Scenario: Invalid file stops the build
- **GIVEN** a `placements.toml` whose `R1` table has `side = "left"`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` hold `layout.source-invalid` naming `R1` and `side`, and nothing is written

## MODIFIED Requirements

### Requirement: Path aliases in the DSL
`Design.moved(old, new)` SHALL record that the part or module at path `new` was at path `old` in an earlier build. `dsl.moves(design) -> Mapping[str, str]` SHALL return the part aliases, new component path to old component path, in path order, with every module alias expanded, and `dsl.module_moves(design) -> Mapping[str, str]` SHALL return the module aliases, new module path to old module path, in path order; `fenolite.dsl` SHALL re-export `module_moves` (an addition under "DSL package").
- `old` and `new` MUST be paths: segments matching `[A-Za-z0-9_.+-]+` joined by `/` ("Design structure and names"). A malformed path, `old == new`, or a second alias with the same `old` or the same `new` MUST raise `DslError` at the call.
- An alias whose `new` is the path of a part added to the design is a part alias. One whose `new` is the path of a module added to the design is a module alias: it gives every part path `<new>/<rest>` of the design the alias `<old>/<rest>`. A part alias MUST win over a module alias for its part, and a longer module path over a shorter one.
- `moves(design)` and `module_moves(design)` MUST raise `DslError` when `new` is neither a part path nor a module path of the design, or when `old` is the path of a part or a module added to the design, because the old part would lose its layout to the new one. Chains (`moved("A", "B")` with `moved("B", "C")`) are therefore refused.
- `cmd_build` MUST turn such a `DslError` into `DesignScriptError` (`FEN-3004`, exit 3), as for `to_model` and `placements`.
- Aliases are not model data: `to_model` MUST give the same model with and without them, and no id changes.
- An alias is needed for one build only: the build writes the footprint under its new path, keeping its board node when it can (`layout-lens`, "Kept and re-placed footprints"), and later builds match it by uuid ("Footprint matching"). An expanded alias that matches nothing gives `layout.alias-unused` (warning).

#### Scenario: Alias recorded
- **GIVEN** a design holding `Module("power")` with `Part("R1", "Mini:Mini_R")`, and `d.moved("R1", "power/R1")`
- **WHEN** `moves(d)` is called
- **THEN** it returns `{"power/R1": "R1"}`

#### Scenario: Old part still present
- **GIVEN** a design holding parts `R1` and `R2`, and `d.moved("R1", "R2")`
- **WHEN** `moves(d)` is called
- **THEN** `DslError` is raised naming `R1`

#### Scenario: Unknown new path at build time
- **GIVEN** a `design.py` that calls `d.moved("R0", "R9")` and adds neither a part `R0` nor a part `R9`
- **WHEN** `fenolite build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the message names `R9`

#### Scenario: Same new path twice
- **WHEN** `d.moved("R1", "R7")` is followed by `d.moved("R2", "R7")`
- **THEN** the second call raises `DslError` naming `R7`

#### Scenario: Model unchanged by aliases
- **GIVEN** the blink design with and without `d.moved("R0", "R1")`
- **WHEN** `canonical.dump_texts(to_model(d))` is computed for both
- **THEN** the texts are equal

#### Scenario: Module alias expanded
- **GIVEN** a design holding `Module("supply")` with parts `R1` and `C1`, and `d.moved("power", "supply")`
- **WHEN** `moves(d)` and `module_moves(d)` are called
- **THEN** they return `{"supply/C1": "power/C1", "supply/R1": "power/R1"}` and `{"supply": "power"}`

#### Scenario: Part renamed inside a renamed module
- **GIVEN** the same design with `R1` renamed `R9`, and `d.moved("power/R1", "supply/R9")` besides the module alias
- **WHEN** `moves(d)` is called
- **THEN** it returns `{"supply/C1": "power/C1", "supply/R9": "power/R1"}`

#### Scenario: Old module still present
- **GIVEN** a design holding modules `power` and `supply`, and `d.moved("power", "supply")`
- **WHEN** `module_moves(d)` is called
- **THEN** `DslError` is raised naming `power`
