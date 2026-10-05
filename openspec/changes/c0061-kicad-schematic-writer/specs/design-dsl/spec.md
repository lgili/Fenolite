## ADDED Requirements

### Requirement: Schematic in a build
`fenolite build` SHALL write the schematic of the design with the triad, as "Build command" and "Built project files" allow for added options, arguments and steps.
- **Option.** `--schematic write|skip` (default `write`) MUST be passed to `build_design` as the keyword-only argument `schematic`; any other value of the argument MUST raise `ValueError`. With `skip`, the build MUST return the files, the board text and the `result` of a build without this requirement, and none of the lowerings of "Board follows the schematic". With `--target altium` the option MUST be a usage error (exit 2, `FEN-2001`).
- **Steps.** With `schematic="write"`, `build_design` MUST, after the build checks and `Design.validate()` and before `write_triad`: call `schgen.generate_schematic(<the design to write>, parts, name=name, target=target, placements=symbol_placements, vendor=vendor, allow_lossy=allow_lossy)`; return no file when it gives an issue of severity `error`; apply `lens.build.lower_for_schematic` ("Board follows the schematic") to the design handed to `write_triad`. After the vendored footprints it MUST add `<name>.kicad_sch` from `sch.write_schematic(generated.sheet, target=target, allow_lossy=allow_lossy)` and the files of "Symbols of a built project".
- **With an existing board.** The design passed to the generator MUST be the merged layout, so a board-only footprint, which has no resolved symbol, gets no symbol.
- **Placements.** `cmd_build` MUST read `<script folder>/schematic-placements.toml` when it exists and pass the result as `symbol_placements` ("Schematic placements file").
- **Record.** `.fenolite/build.json` MUST record the SHA-256 of the schematic, of `sym-lib-table` and of every symbol library, like every other file outside `.fenolite/`.
- **Replaced sheet.** When `DIR/<name>.kicad_sch` exists and its bytes are neither the planned bytes nor those whose SHA-256 the last build record holds, `cmd_build` MUST add one `build.schematic-replaced` warning naming the file, and the mutation protocol keeps its backup. The build MUST NOT read that file.
- **Output.** `BuildOutput.schematic` MUST hold the `GeneratedSchematic`, or `None` when the schematic is skipped or no file is returned.
- **Result.** `result.schematic` MUST hold `file`, `paper`, `symbols`, `labels`, `no_connects`, `power_flags`, `libraries` (the symbol library files) and `unconnected_pads` (the size of `pad_nets`); with `skip` it MUST be `null`.
- **Evidence.** The build evidence MUST also combine `schgen.EVIDENCE`.

#### Scenario: Blink gets a schematic
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --confirm --json` runs for target 10
- **THEN** `receipt.written` lists `B/blink.kicad_sch`, `B/sym-lib-table`, `B/lib/Mini.kicad_sym` and `B/lib/fenolite.kicad_sym`, and `result.schematic` holds `symbols` 5, `power_flags` 2, `no_connects` 29, `unconnected_pads` 29 and `paper` `A4`

#### Scenario: Skipping the schematic
- **WHEN** the same build runs with `--schematic skip` into an empty folder
- **THEN** `receipt.written` holds no `.kicad_sch`, no `sym-lib-table` and no `.kicad_sym` file, `result.schematic` is `null`, and no pad of the board is on a net whose name starts with `unconnected-`

#### Scenario: Rebuild is identical
- **WHEN** the confirmed build with a schematic runs a second time
- **THEN** every file has the bytes of the first build, and `issues` holds no `build.schematic-replaced`

#### Scenario: Edited schematic replaced
- **GIVEN** a confirmed blink build in `B` whose `blink.kicad_sch` then gets one more `text` item
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, `issues` holds one `build.schematic-replaced` warning, `B/blink.kicad_sch` has the bytes of the first build, and `B/blink.kicad_sch.bak` holds the edited bytes

#### Scenario: Generator error writes nothing
- **GIVEN** a `schematic-placements.toml` that puts one pin of `R1` on one pin of `D1`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.symbol-short`, and no file is written

#### Scenario: Altium target
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --target altium --schematic skip --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Symbols of a built project
A build with a schematic SHALL write the symbols it embeds into project libraries, by the rule that "Footprints of every row origin are vendored" gives footprints: only what the design uses, under the nicknames of the design.
- For each nickname with an embedded symbol, the build MUST write `lib/<nickname>.kicad_sym` with `symembed.write_symbol_library`, holding the embedded definitions of that nickname (flattened, pin-pad variants included) and, for a nickname that the design authors ("Project-authored symbols"), every authored symbol of it, embedded or not, and `sym-lib-table` MUST hold one row per written nickname with `uri "${KIPRJMOD}/lib/<nickname>.kicad_sym"`, written by `libs.write_lib_table` for the target, rows sorted by nickname.
- The node of an authored symbol MUST be the one that `sym.write_symbol_library` writes ("Project-authored symbols"), in the library file and in the sheet alike. A library whose symbols are all authored, none of them with a pin-pad variant, therefore has the same bytes with the schematic written and with it skipped. An authored symbol counts as a project row for the `vendor` policy.
- With `vendor="project"`, a symbol resolved through a row that is not a project row MUST still be embedded in the sheet, MUST get no library file and no row, and MUST give one `build.global-library` info.
- When the sheet holds a power flag, `lib/fenolite.kicad_sym` and its row MUST be written whatever the `vendor` policy. A design whose parts name a library `fenolite`, or that authors a symbol in it, MUST give `build.reserved-library` (error).
- The unsafe-name rule of "Footprints of every row origin are vendored" MUST apply to symbol library files, and `build.library-changed` MUST be given for a symbol library whose planned bytes differ from the recorded hash.
- The copies keep their library's licence; `docs/dsl.md` MUST say so beside the footprint note.

#### Scenario: Libraries of the blink
- **WHEN** the blink is built for target 9
- **THEN** `files` holds `lib/Mini.kicad_sym` with exactly the symbols `Mini_LED`, `Mini_QFP32_IC` and `Mini_R`, `lib/fenolite.kicad_sym` with `PWR_FLAG`, and a `sym-lib-table` with the rows `Mini` and `fenolite` in this order and no `version` child

#### Scenario: Project policy
- **GIVEN** the global setup of "Global footprints vendored"
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `files` holds no `lib/Mini.kicad_sym`, `sym-lib-table` holds only the row `fenolite`, the sheet still embeds the three symbols, and `issues` holds one `build.global-library` info per symbol

#### Scenario: Reserved nickname
- **GIVEN** a design with a part of `fenolite:Thing`
- **WHEN** it is built
- **THEN** `files` is empty and `issues` holds `build.reserved-library`

### Requirement: Schematic placements file
`fenolite.lens.schplacements.read_placements(text, *, file="", issues=None) -> Mapping[str, SymbolPlacement]` SHALL read an optional `schematic-placements.toml`, with `tomllib` and `parse_float=Decimal`, so no float is created.
- Each table MUST be keyed by a component path, or by `<path>#<unit>` for a unit above 1, MUST hold `x` and `y` (the symbol origin in millimetres), and MAY hold `rotation` (0, 90, 180 or 270) and `mirror` (`"x"` or `"y"`). A unit that stays in the flow has no cell of its own to turn in, so a table without a position is refused.
- `x` and `y` MUST be multiples of 1.27 mm. A value off that grid, a missing `x` or `y`, an unknown key, a rotation or mirror outside these values, or a (rotation, mirror) pair outside `schlayout.PROVED_FRAMES` MUST give `build.symbol-placement-invalid` (error) naming the table and the key, appended to `issues`, and the table gives no placement. `cmd_build` MUST plan no write when the file gives an error.
- A table that names no unit of the design MUST give `build.symbol-placement-unknown` (warning), reported by the build.
- A file that is not valid TOML MUST raise `FormatError` (`FEN-3004`) naming the file.

#### Scenario: Position in millimetres
- **GIVEN** the text `["R1"]`, `x = 25.4`, `y = 50.8`
- **WHEN** it is read
- **THEN** `R1` has `x == 25_400_000` and `y == 50_800_000`, rotation 0 and no mirror

#### Scenario: Off the grid
- **GIVEN** `x = 25.5`
- **WHEN** the build reads it
- **THEN** `issues` holds one `build.symbol-placement-invalid` error naming `R1` and `x`

#### Scenario: Unknown path
- **GIVEN** a table `["R9"]` and a design without `R9`
- **WHEN** the blink is built
- **THEN** `issues` holds one `build.symbol-placement-unknown` warning, and the build writes its files

### Requirement: Board follows the schematic
`lens.build.lower_for_schematic(design, generated) -> Design` SHALL return the design that `write_triad` writes when a schematic is written, so that KiCad's parity test and its update find the board in agreement with the sheet.
- **Unconnected pads.** Each pad named by `generated.pad_nets` MUST get a net of that name, with the id `derived_id("net", "fenolite", "unconnected:<component path>:<pad number>")`, no net class and no member. Every other pad and net MUST be unchanged.
- **Symbol paths.** `Component.path` of each component named by `generated.paths` MUST be `/<kicad uuid of its instance with the lowest unit>`, which the board writer emits as the footprint's `path`.
- **Stored layout.** `BuildOutput.layout`, the `.fenolite/` texts and `BuildOutput.design` MUST NOT hold those nets: their pads of unconnected pins stay on no net, and `Design.validate()` reports nothing about them.
- **Net names.** Created nets are written in KiCad's stored form by the board writer (`kicad-file-backend`, "Net names in KiCad's stored form"), and labels carry the same form.
- The function MUST be pure, and applying it twice MUST give the result of applying it once.

#### Scenario: Pads of unconnected pins
- **WHEN** the blink is built for target 10 and the board text is parsed
- **THEN** pad `2` of `U1` holds `(net "unconnected-(U1-PA1-Pad2)")`, pad `16` holds `(net "unconnected-(U1-Pad16)")`, and the footprint of `U1` holds a `path` child whose text is `/` followed by the uuid of the symbol `U1` in `blink.kicad_sch`

#### Scenario: Numbered form for target 9
- **WHEN** the blink is built for target 9
- **THEN** the net table of the board holds 29 rows whose names start with `unconnected-(U1-`, each referenced by exactly one pad

#### Scenario: Stored model stays clean
- **WHEN** `.fenolite/circuit.json` and `.fenolite/board.json` of that build are loaded
- **THEN** no net name starts with `unconnected-`, pad `2` of `U1` has no net, and `fenolite check B --stages model.validate --json` reports no `model.single-pin-net` that names an `unconnected-` net

#### Scenario: Slash net
- **GIVEN** a blink variant whose net `LED_A` is named `mod/LED_A`
- **WHEN** it is built for target 10
- **THEN** the pads and the labels hold `mod{slash}LED_A`, `.fenolite/circuit.json` holds `mod/LED_A`, and a second build is byte-identical

## MODIFIED Requirements

### Requirement: Build command
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project] [--schematic write|skip]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model`, `placements` and `moves`, prepares layout preservation with `lens.preserve.read_existing` and `lens.preserve.prepare` unless `--discard-layout` is given, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout`, `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) and `--schematic` ("Schematic in a build") are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global`, `template` or `scan`), `script_output` and `preserved` (`layout-lens`, "Layout preservation evidence"), plus the dispatcher's `plan`.
- Later requirements MAY add `build` options, steps of `cmd_build` and keys of `result`; each such requirement names this one.
- `cmd_build` MUST turn a `DslError` raised by `to_model`, `placements` or `moves`, which run after `run_design_script` has returned, into `DesignScriptError` with `file` = the script path and no locator (`FEN-3004`, exit 3).
- Unless `--discard-layout` is given, `cmd_build` MUST read the existing triad with `read_existing(DIR, <design name>)`, call `prepare(model, placements(design), existing, name=<design name>, moves=moves(design))`, and pass `prepared.placements` as `placements` and `prepared` as `prepared` to `build_design`. With `--discard-layout`, it MUST pass `placements(design)` and no `prepared`.
- `cmd_build` MUST read the last build record once with `lens.build.read_record(DIR)`, pass it to `build_design` and to `lens.build.check_existing` as `record`, and call `check_existing` before it returns the plan, with every planned file except the board, project and rules files, which preservation merges, and the schematic, which every build regenerates ("Edited outputs are not overwritten").
- A build with an issue of severity `error` MUST return no planned write, so it exits 5 and writes nothing.
- `example_args` (with `--dry-run`) and `mutation_example_args` MUST use the packaged `src/fenolite/dsl/_minimal.py` (Apache-2.0 header; a board with one net class and no parts), located through `fenolite.dsl.__file__`, so the consistency suite is hermetic from any working directory.

#### Scenario: Confirmation required
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --json` runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists every planned file, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm`
- **THEN** the exit code is 0, and `receipt.written` lists `B/blink.kicad_pcb`, `B/blink.kicad_pro`, `B/blink.kicad_dru`, `B/blink.kicad_sch`, `B/fp-lib-table`, `B/sym-lib-table`, the three footprints under `B/lib/Mini.pretty/`, the two symbol libraries under `B/lib/` and the seven files under `B/.fenolite/`

#### Scenario: Rebuild is identical
- **WHEN** the confirmed build runs a second time
- **THEN** the exit code is 0, every file that the first build wrote has the same bytes as after the first build, and the only new files are the `.bak` copies that the mutation protocol keeps

#### Scenario: Output folder is the script folder
- **WHEN** `fenolite build examples/blink_2layer/design.py --out examples/blink_2layer --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Vendoring policy on the command line
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global row of a `KICAD_CONFIG_HOME` authored in the test and set in the environment of the run
- **WHEN** `fenolite build design.py --out B --dry-run --json` runs, and then the same command with `--vendor project`
- **THEN** the first `result.vendored` lists `lib/G.pretty/Mini_R_0603.kicad_mod`, and the second lists no file under `lib/G.pretty/` and its `issues` hold `build.global-library` naming `G:Mini_R_0603`

#### Scenario: Consistency suite
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory
- **THEN** it passes, with `build` covered by the mutation protocol

#### Scenario: Rebuild over an edited board
- **GIVEN** a confirmed target-10 blink build in `B` whose board was replaced by `tests/_layout_edit.py::edit_blink` of its text
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the exit code is 0, `result.preserved.board` is `true`, and `result.preserved.kept` lists `D1`, `R1` and `U1`

### Requirement: Built project files
`lens.build.build_design(design, placements, *, name, copper, resolver, target=DEFAULT_TARGET, allow_lossy=False, vendor="all", record=None, prepared=None) -> BuildOutput` SHALL return every file of a self-contained KiCad project as bytes, and SHALL return no file when any issue has severity `error`.
- The steps MUST run in this order: resolve libraries; fill pins and resolve net members; place, stage, set layers and assign pad nets; run the build checks (those of "Pins and pads in a build", "Placement of built parts", "User properties on built footprints" and "Footprints of every row origin are vendored") and `Design.validate()`; when `prepared` holds an existing board, merge it with `lens.preserve.merge_layout` and run `Design.validate()` on the merged layout; call c0010's `triad.write_triad(<model>, name=name, target=target, existing_project=<the existing project text of prepared, or None>, allow_lossy=allow_lossy, issues=…)`, which lowers rules through c0018 and net classes through c0010, `<model>` being the merged layout when there is an existing board and the built design otherwise; merge the rules text with `lens.preserve.merge_rules` when `prepared` holds an existing rules text; with an existing board, drop the fills whose digests changed with `lens.preserve.drop_stale_fills` and, when one was dropped, write the board again with `write_board`; derive `BuildOutput.layout` from the written board text (`layout-lens`, "Preservation is the build's normal form"); add the vendored footprints, `fp-lib-table`, the `.fenolite/` texts and `.fenolite/build.json`; combine evidence.
- Later requirements MAY add keyword-only arguments with defaults to `build_design`, and steps between or within the steps above; each such requirement names this one.
- An issue of severity `error` before the writer MUST return a `BuildOutput` with its issues and empty `files`. Writer refusals (`LossyWriteError`, `RulesLossError`, `FEN-7001`) MUST propagate with their issues.
- `BuildOutput` is a frozen dataclass with `design`, `files: Mapping[str, bytes]` (paths relative to `--out`), `issues`, `evidence`, `summary` and `layout: Design | None`. `design` is the model built from the script at the given placements; `layout` is the model of the written board, and `None` when no file is returned.
- The layout MUST be `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, the six layer files under `.fenolite/` and `.fenolite/build.json`, `<name>.kicad_sch` unless the schematic is skipped, and `sym-lib-table` and `lib/<nickname>.kicad_sym` when the schematic is written ("Schematic in a build", "Symbols of a built project") or the design authors symbols ("Project-authored symbols").
- Every vendored footprint MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, and `fp-lib-table` MUST hold one row per vendored nickname with `uri "${KIPRJMOD}/lib/<nickname>.pretty"`, written by `libs.write_lib_table` for the target. With `vendor="all"`, every footprint that the build places is vendored, whatever the origin of its row; with `vendor="project"`, only footprints resolved through a project-table row are ("Footprints of every row origin are vendored"). Any other `vendor` MUST raise `ValueError`.
- With `vendor="project"`, footprints from rows of another origin MUST NOT be vendored and get no row (`build.global-library`, info). A vendored file whose header version is newer than the target's newest format MUST give `build.library-too-new` (warning). With `record`, a vendored file whose bytes differ from the hash recorded for its path MUST give `build.library-changed` (warning).
- The build MUST NOT write a `.kicad_prl`, a `native/` folder or a date, and with the schematic skipped it MUST write a `sym-lib-table` and symbol files only for the symbols that the design authors ("Project-authored symbols").
- The `.fenolite/` layer texts MUST come from `canonical.dump_texts` of `BuildOutput.layout`, with an empty `findings.json` and no `FootprintDef`. `.fenolite/build.json` MUST have `schema` `fenolite.build-record.v0`, sorted keys and no date, and MUST record the SHA-256 of every file outside `.fenolite/` that the build writes. It is regenerable and marks a built project.

#### Scenario: Files of a target-9 build
- **WHEN** the blink is built for target 9
- **THEN** `files` holds exactly the triad `blink.*`, `blink.kicad_sch`, `fp-lib-table` and `sym-lib-table` without a `version` child, three files under `lib/Mini.pretty/` byte-equal to their sources in `tests/data/libs/Mini_v9.pretty/`, `lib/Mini.kicad_sym` and `lib/fenolite.kicad_sym`, the six layer files under `.fenolite/` and `.fenolite/build.json`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of a blink build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, it holds no date, and it maps each of the eleven files outside `.fenolite/` to its SHA-256

#### Scenario: Errors produce no files
- **GIVEN** a blink variant with `connect(led, r1["X"])`
- **WHEN** `build_design` runs
- **THEN** the returned `files` is empty and `issues` holds `build.unknown-pin`

#### Scenario: Unsafe class pattern refused
- **GIVEN** a blink variant with a net `D[0]` in class `PWR` and a net `D0` beside it
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, `issues` holds `kicad.project.pattern-unsafe`, and nothing is written

#### Scenario: Global footprint vendored
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global `fp-lib-table` row of a `KICAD_CONFIG_HOME` authored in the test, the other footprints resolving through the project table
- **WHEN** `build_design` runs with the default `vendor`
- **THEN** `files` holds `lib/G.pretty/Mini_R_0603.kicad_mod`, byte-equal to its source, `fp-lib-table` holds the rows `G` and `Mini` in this order, and `issues` holds no `build.global-library`

#### Scenario: Global footprint kept out on request
- **GIVEN** the same variant
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `issues` holds one `build.global-library` info naming `G:Mini_R_0603`, `files` holds no file under `lib/G.pretty/`, and `fp-lib-table` holds no row named `G`

#### Scenario: Unknown vendoring policy
- **WHEN** `build_design` runs with `vendor="none"`
- **THEN** `ValueError` is raised naming `all` and `project`

#### Scenario: Vendored file newer than the target
- **GIVEN** a blink variant whose project table names a folder holding a copy of `Mini_v9.pretty/Mini_R_0603.kicad_mod` authored in the test with header version `20260206` and no 10-only token
- **WHEN** `build_design` runs for target 9
- **THEN** `issues` holds one `build.library-too-new` warning naming the vendored file, and `files` holds the vendored copy byte-equal to its source

#### Scenario: The built folder moves whole
- **GIVEN** a confirmed blink build copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy locates `Mini:Mini_R_0603`
- **THEN** the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

#### Scenario: Cache texts come from the layout
- **WHEN** `build_design` runs for the blink without `prepared`
- **THEN** `output.layout` is not `None`, and the six `.fenolite/` texts in `files` equal `canonical.dump_texts(output.layout)`

#### Scenario: Existing project text is merged
- **GIVEN** a `prepared` whose existing project text holds a net class `USER` that the design lacks
- **WHEN** `build_design` runs
- **THEN** the planned `blink.kicad_pro` holds the classes `PWR` and `USER`

### Requirement: Edited outputs are not overwritten
`lens.build.check_existing(out_dir, files, *, record, discard_layout) -> None` SHALL refuse to replace a file outside `.fenolite/` that changed since Fenolite last wrote it, except the board, project and rules files of the triad, which layout preservation merges instead (`layout-lens`), and the schematic, which every build regenerates and replaces with a warning ("Schematic in a build"). For each other planned file outside `.fenolite/` that already exists, that is `fp-lib-table`, `sym-lib-table` and the vendored footprints and symbol libraries under `lib/`:
- bytes equal to the planned bytes: an identical rewrite, allowed;
- SHA-256 equal to the one recorded in `.fenolite/build.json`: untouched since the last build, allowed, so a DSL edit never needs `--discard-layout`;
- otherwise (edited, or found without a record): `LayoutExistsError` MUST be raised, with `cli_code = "FEN-7001"` (exit 7), one `build.layout-exists` issue per file, and the hint "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder".

Further rules:
- `cmd_build` MUST NOT pass the board, project, rules and schematic files to the check.
- The check MUST run before the plan is returned, so `--dry-run` refuses too, and nothing is written.
- `--discard-layout` MUST skip the check, and the build then preserves nothing (`layout-lens`, "Existing project files"); the mutation protocol keeps a `.bak` of each replaced file unless `--no-backup` is given. `--allow-lossy` MUST NOT skip the check.
- Without a record (for example after `.fenolite/` was deleted), only identical bytes are allowed.

#### Scenario: DSL edit needs no flag
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the value of `R1` is changed in `design.py` and the build runs again with `--confirm`
- **THEN** the exit code is 0, and `B/blink.kicad_pcb` holds the new value

#### Scenario: Edited board is merged, not refused
- **GIVEN** a confirmed blink build in `B` whose board gets one segment by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the segment is kept, and `issues` holds no `build.layout-exists`

#### Scenario: Edited vendored footprint refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/lib/Mini.pretty/Mini_R_0603.kicad_mod` changed afterwards
- **WHEN** the build runs again with `--confirm`, and then with `--dry-run`
- **THEN** both exit 7 with `FEN-7001`, the envelope's `issues` holds `build.layout-exists` naming `B/lib/Mini.pretty/Mini_R_0603.kicad_mod`, and no file under `B` changes

#### Scenario: Discarding the layout
- **GIVEN** the same edited footprint file
- **WHEN** the build runs with `--discard-layout --confirm`
- **THEN** the exit code is 0, and `B/lib/Mini.pretty/Mini_R_0603.kicad_mod.bak` holds the edited bytes

#### Scenario: Lost record
- **GIVEN** two copies of a confirmed blink build, each with its `.fenolite/` folder deleted
- **WHEN** the build runs again with `--confirm` into the first copy unchanged, and into the second copy after one byte of its `fp-lib-table` is changed
- **THEN** the first run exits 0 with identical bytes, and the second exits 7 with `build.layout-exists` naming `fp-lib-table`

#### Scenario: Lossy flag does not skip the check
- **GIVEN** the edited footprint file
- **WHEN** the build runs with `--allow-lossy --confirm`
- **THEN** the exit code is 7 with `build.layout-exists`

#### Scenario: Edited symbol library refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/lib/Mini.kicad_sym` changed afterwards
- **WHEN** the build runs again with `--confirm`
- **THEN** it exits 7 with `FEN-7001`, and `issues` holds `build.layout-exists` naming `B/lib/Mini.kicad_sym`

### Requirement: Footprints of every row origin are vendored
With `vendor="all"`, the default of `build_design` and of `fenolite build`, the build SHALL copy every footprint it places into the project's library folder, whatever the origin of the row that resolved it, so that a built project needs no global or template table.
- Row origins are those of `LibraryResolver`: `project`, `global` and `template`, and any origin that a later change adds, such as c0021's `scan`. A footprint of any origin MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, `nickname` being the nickname of the row that resolved it, with one `fp-lib-table` row per vendored nickname ("Built project files").
- Lib ids MUST stay unchanged: the board's footprint names, `Component.lib_footprint_ref` and the `.fenolite/` texts keep the nicknames of the design. In KiCad's library check, the vendored row hides a global row with the same nickname, and with it the items that were not vendored (`H-K-VENDOR-SHADOW`).
- Only placed footprints MUST be copied: no whole library and no 3D model. Symbols follow the same rule in "Symbols of a built project".
- With `vendor="project"` (`fenolite build --vendor project`), a footprint of a row whose origin is not `project` MUST NOT be copied and gets no row. Each such footprint gives `build.global-library` (info), as c0011 did.
- **Unsafe names.** A vendored nickname that holds `/` or `\`, or a character that fails `str.isprintable()`, MUST give `build.vendor-unsafe-name` (error) with the build checks, and two vendored paths that differ but are equal after `str.casefold()` MUST give it too. Then no file is written outside `lib/`, and the folder survives a file system that ignores letter case.
- **Library changes.** When `record` (the hashes that `read_record` returns) holds a hash for the path of a vendored file, and the planned bytes have another SHA-256, the build MUST give `build.library-changed` (warning) naming the file, because its library changed since the last build. The planned copy still replaces an old copy that is untouched since the last build ("Edited outputs are not overwritten").
- Vendored bytes are the source bytes, so two builds with the same libraries give identical files ("Reproducible builds").
- Copies are written only into the `--out` folder. The official libraries are CC-BY-SA 4.0 with an exception for designs, and redistributing the collection is not covered by it (S-0048). `docs/dsl.md` MUST say so without legal advice, and MUST name `--vendor project`.

#### Scenario: Global footprints vendored
- **GIVEN** the blink built from a folder without project tables, every symbol and footprint served by the global tables of a `KICAD_CONFIG_HOME` authored in the test, whose rows `Mini` name a temporary copy of `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`
- **WHEN** `build_design` runs for target 9, and again for target 10
- **THEN** each `files` holds the three footprints under `lib/Mini.pretty/`, byte-equal to the copy, and an `fp-lib-table` with the one row `Mini` naming `${KIPRJMOD}/lib/Mini.pretty`; `issues` holds no `build.global-library`; `summary["libraries"]["Mini:Mini_R_0603"]` is `global`; and the board names the footprint `Mini:Mini_R_0603`

#### Scenario: Template footprints vendored
- **GIVEN** a fake install made with `tests/_libs.make_install`, whose template tables name the same copies through `${KICAD10_FOOTPRINT_DIR}` and `${KICAD10_SYMBOL_DIR}`, and an empty configuration folder
- **WHEN** the blink is built for target 10 from a folder without project tables
- **THEN** `summary["libraries"]["Mini:Mini_R_0603"]` is `template`, and the files under `lib/Mini.pretty/` and the table are those of the previous scenario

#### Scenario: Vendoring kept to project rows on request
- **GIVEN** the global setup of the first scenario
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `files` holds no footprint under `lib/`, `fp-lib-table` holds no row, and `issues` holds one `build.global-library` info for each of the three footprints

#### Scenario: Unsafe nickname
- **GIVEN** a global row named `a/b`, made in the test, that serves `R1`'s footprint
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.vendor-unsafe-name` naming `a/b`

#### Scenario: Library changed since the last build
- **GIVEN** a first build of the global setup and the hashes of its `.fenolite/build.json`, and then pad `1` of the global copy of `Mini_R_0603.kicad_mod` moved 0.05 mm in the test
- **WHEN** `build_design` runs again with `record` set to those hashes
- **THEN** `issues` holds one `build.library-changed` warning naming `lib/Mini.pretty/Mini_R_0603.kicad_mod`, and the planned copy is byte-equal to the changed source; without the change, no such warning is given

#### Scenario: Built folder resolves alone
- **GIVEN** a build of the global setup, written to a folder and copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy, an empty configuration folder and no install locates `Mini:Mini_R_0603`
- **THEN** the origin is `project`, and the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

### Requirement: No-connect marks in a build
The KiCad build (`lens.build.build_design`) SHALL resolve every mark of `Circuit.no_connects` to pin numbers by the rules of "Pins and pads in a build", refuse a pin that is marked and connected, and keep the marks in the `.fenolite/` model. With a schematic, each mark becomes a no-connect flag of the sheet ("Schematic in a build"); no other written KiCad file changes.
- A designator MUST be read as a pin number first, and otherwise as a pin name that marks every pin with that name. A designator that is neither MUST give `build.unknown-pin` (error) naming the ref and the designator. A number that is also another pin's name MUST give `build.pin-ambiguous` (warning), and the number wins.
- After resolution, a pin that is marked and that a net lists MUST give `build.no-connect-on-net` (error) naming the ref, the pin number and the net; the build MUST exit 5 and write nothing. This code joins the `build` envelope under "Build issue codes": it MUST be a key of `lens.build.BUILD_ISSUE_CODES` with severity `error`, and `docs/cli-contract.md` MUST list it.
- After the build, `Circuit.no_connects` MUST hold `PinRef(<component id>, <pin number>)` in `PinRef` order without duplicates, and `.fenolite/circuit.json` MUST store them.
- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, the library tables, the symbol libraries and the vendored files MUST be byte for byte those of the same design without marks: the pad of a marked pin is written as the pad of any unconnected pin ("Board follows the schematic"), and `build.unused-pin-without-pad` applies to a marked pin as to any unconnected pin. `<name>.kicad_sch` MUST differ by one `no_connect` item per marked pin and by nothing else.
- A rebuild takes the marks from the script; the layout lens neither reads nor keeps a mark from the board.
- The marks also serve `fenolite check` ("ERC lite stage" of `verification-loop`), and with `--schematic skip` no written KiCad file depends on them.

#### Scenario: Marks resolved in the built model
- **GIVEN** a blink variant with `u1 = Part("U1", "Mini:Mini_QFP32_IC", ...)`, its `GND` pins connected, and `no_connect(u1[11], u1[12])`
- **WHEN** it is built with `--confirm` into `B` and `B/.fenolite` is loaded with `canonical.load_dir`
- **THEN** the exit code is 0 and `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`

#### Scenario: Written KiCad files do not change
- **GIVEN** the variant above and the same variant without the `no_connect` call
- **WHEN** both are built with the same `--seed` and `--timestamp`
- **THEN** every planned file outside `.fenolite/` except `<name>.kicad_sch` has the same SHA-256 in both receipts, and the schematic of the marked variant holds two `no_connect` items that the other lacks

#### Scenario: A name and a number of one pin
- **GIVEN** `connect(gnd, u1["GND"])` and `no_connect(u1[10])` on `Mini:Mini_QFP32_IC`, whose pin `10` is named `GND`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.no-connect-on-net` naming `U1`, `10` and `GND`, and nothing is written

#### Scenario: Unknown marked designator
- **GIVEN** `no_connect(r1["X"])` on `Mini:Mini_R`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5 and `issues` holds `build.unknown-pin` naming `R1` and `X`

#### Scenario: New code in the closed set
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` and `uv run pytest tests/consistency` run
- **THEN** both pass, `BUILD_ISSUE_CODES["build.no-connect-on-net"]` is `error`, and a build test produces the code
