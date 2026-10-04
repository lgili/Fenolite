## ADDED Requirements

### Requirement: Place command
`fenolite place PATH [--strategy grid|manual] [--move REF=X,Y[,ROT[,SIDE]]]... [--only REF,…] [--pitch L] [--gap L] [--margin L] [--force] [-o OUT]` SHALL be registered by `src/fenolite/cli/cmd_place.py` with `mutates=True`, and SHALL move footprints of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Grid.** With `--strategy grid` (the default without `--move`), the command MUST place every footprint that is off the board (`layout-lens`, "Placement precedence"), or those of `--only`, with `placement.grid.place`, in component-path order (reference order for footprints without `fenolite.path`). It only translates.
- **Manual.** Each `--move` MUST name a reference and a position in the frame of the DSL's `place()` (relative to the top-left corner of the bounding box of the board ring, Y down; relative to the file origin when the board has no outline), with lengths in the DSL's syntax, an optional rotation in degrees and an optional side. An unknown reference MUST give `place.unknown-ref`. A rotation or side change MUST resolve definitions from the project's `fp-lib-table`.
- **Legality.** After the moves, `placement.legality.check` MUST run on the whole layout. With any `place.*` error and without `--force`, the command MUST return no `PlannedWrite` and exit 5. With `--force` it MUST write and still report the issues.
- **Write.** One `PlannedWrite` for the board, at `--out` when given and at the board's path otherwise; none when nothing moved. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `strategy`, `moved` (`ref`, `path`, `from`, `to`, each placement as `x`, `y` in nm, `rotation` in µdeg and `side`; sorted by reference), `unplaced` and `legality` (counts by code).
- **Built projects.** When `.fenolite/` holds a locked placement for a moved part, the command MUST report `place.script-locked` (warning), because the next build restores the script's placement.
- No subprocess MUST run. Two runs on equal boards MUST write equal bytes.
- `example_args` MUST be `(EXAMPLE_BOARD, "--move", "R1=12mm,8mm", "--out", "fenolite-placed.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`.

#### Scenario: Grid places staged parts
- **GIVEN** a confirmed build of a blink variant with `R1` and `D1` staged
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k grid` runs `fenolite place <dir> --confirm`
- **THEN** both footprints lie inside the outline, `result.moved` lists them, `result.unplaced` is empty, and the exit code is 0

#### Scenario: Illegal move refused
- **GIVEN** the built blink
- **WHEN** `fenolite place <dir> --move R1=<the position of D1> --confirm` runs
- **THEN** the exit code is 5, `issues` holds `place.courtyard-overlap`, and no file changes; with `--force` the board is written

#### Scenario: Unknown reference
- **WHEN** `fenolite place <dir> --move R99=1mm,1mm --dry-run` runs
- **THEN** the exit code is 5 and `issues` holds `place.unknown-ref` naming `R99`

#### Scenario: Nothing to place
- **GIVEN** a built blink with every part placed
- **WHEN** `fenolite place <dir> --confirm` runs
- **THEN** the exit code is 0, `result.moved` is empty, and no file changes

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `place` with its `example_args`
- **THEN** the exit code is 0 and the plan names `fenolite-placed.kicad_pcb`
