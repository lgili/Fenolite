## MODIFIED Requirements

### Requirement: Place command
`fenolite place PATH [--strategy grid|manual|constrained] [--move REF=X,Y[,ROT[,SIDE]]]... [--only REF,…] [--pitch L] [--gap L] [--margin L] [--force] [-o OUT] [--constraints FILE] [--max-candidates N] [--preview-dir DIR]` SHALL be registered by `src/fenolite/cli/cmd_place.py` with `mutates=True`, and SHALL move footprints of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Rules of a built project.** The command MUST load the board folder's `.fenolite/` with `canonical.load_dir` at most once, and take from it the locked placements of "Built projects" and `checks.placement.rules_of(<that model>)`. Without a readable `.fenolite/` it judges no rule.
- **Grid.** With `--strategy grid` (the default without `--move`), the command MUST place every footprint that is off the board (`layout-lens`, "Placement precedence"), or those of `--only`, with `placement.grid.place`, in component-path order (reference order for footprints without `fenolite.path`). It only translates. The bounding box of every rule area of the board that forbids footprints (`Keepout.no_footprints`) MUST join the cut-outs that the grid avoids.
- **Manual.** Each `--move` MUST name a reference and a position in the frame of the DSL's `place()` (relative to the top-left corner of the bounding box of the board ring, Y down; relative to the file origin when the board has no outline), with lengths in the DSL's syntax, an optional rotation in degrees and an optional side. An unknown reference MUST give `place.unknown-ref`. A rotation or side change MUST resolve definitions from the project's `fp-lib-table`.
- **Legality.** For grid/manual, after the moves, `placement.legality.check` MUST run on the whole layout, with the board's keep-outs as `keepouts`. With any `place.*` error and without `--force`, the command MUST return no `PlannedWrite` and exit 5. With `--force` it MUST write and still report the issues.
- **Rules.** After the moves, `checks.placement.judge` MUST run on the layout with the rules of the built project. Each `placement.*` issue MUST be reported with a severity no higher than `warning` and MUST NOT refuse the write.
- **Measures.** `checks.placement.measure` MUST run on the layout after the moves, with the track width plus the clearance of the class `Default` of `KicadBackend().design_rules` on the board's copy set as `pitch` (`None` without that class).
- **Write.** For grid/manual, one `PlannedWrite` for the board, at `--out` when given and at the board's path otherwise; none when nothing moved. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `strategy`, `moved` (`ref`, `path`, `from`, `to`, each placement as `x`, `y` in nm, `rotation` in µdeg and `side`; sorted by reference), `unplaced`, `legality` (counts by code), `rules` (the counts of `judge` by rule family, all zero without rules) and `measures` (`Measures.to_json()` of the layout after the moves, with `change`: `hpwl` and `ratsnest` after minus before, in nm, both 0 when nothing moved).
- **Built projects.** When `.fenolite/` holds a locked placement for a moved part, the command MUST report `place.script-locked` (warning), because the next build restores the script's placement.
- **Evidence.** The envelope MUST carry `placement.EVIDENCE`, combined with `placement.legality.KEEPOUT_EVIDENCE` when the board holds a rule area that forbids footprints, and with `checks.placement.EVIDENCE` when a rule was judged.
- No subprocess MUST run. Two runs on equal boards MUST write equal bytes and return equal results.
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
- **THEN** the exit code is 0, `result.moved` is empty, `result.measures.change` is `{"hpwl": 0, "ratsnest": 0}`, and no file changes

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `place` with its `example_args`
- **THEN** the exit code is 0 and the plan names `fenolite-placed.kicad_pcb`

#### Scenario: Keep-out avoided by the grid and refused for a move
- **GIVEN** a confirmed build of a blink variant with `R1` staged and a rule area on `F.Cu` that forbids footprints over the 8 mm square at the top-left corner of the board, where the grid would otherwise put `R1`
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k keepout` runs `fenolite place <dir> --confirm`, and then `fenolite place <dir> --move R1=4mm,4mm --confirm`
- **THEN** the first run places `R1` outside the area's box with exit code 0; the second exits 5 with `place.keepout` naming `R1`, and writes nothing

#### Scenario: Rules and measures of a move
- **GIVEN** the blink built with `design.near("led", d1, r1.pad(2), within=mm(5))`
- **WHEN** `fenolite place <dir> --move R1=36mm,18mm --dry-run --json` runs, which brings `R1`'s pads within 5 mm of `D1`'s, and then the same command with `--move R1=2mm,2mm`
- **THEN** the first reply holds no `placement.too-far` and a negative `result.measures.change.hpwl`; the second holds one `placement.too-far` warning naming `D1` and exits 0, since a rule never refuses `place`

- **Constrained.** With `--strategy constrained`, the command SHALL use bounded neutral proposals from the integer `fenolite.placement-request.v0` request, preserve manual/grid defaults and refuse `--force`. `--constraints`, `--max-candidates` and `--preview-dir` SHALL apply to this strategy. `result.placement` SHALL contain positions, source/request hashes, unplaced reasons, objective metrics, intrinsic findings and placement assessment. `result.preview` SHALL identify the written/read-back geometry; dry-run previews MUST not write files. The constrained transaction MAY add planned preview writes alongside the board write and SHALL retain its hard-check findings instead of applying grid/manual force semantics.

#### Scenario: Constrained dry-run then confirmed placement
- **GIVEN** an authored request and preview directory
- **WHEN** dry-run is followed by --confirm
- **THEN** dry-run writes nothing and confirmed output has receipts and matching geometry hashes
