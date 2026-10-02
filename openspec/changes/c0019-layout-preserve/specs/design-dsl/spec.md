## ADDED Requirements

### Requirement: Path aliases in the DSL
`Design.moved(old, new)` SHALL record that the part at component path `new` was at component path `old` in an earlier build, and `dsl.moves(design) -> Mapping[str, str]` SHALL return the recorded aliases, new path to old path, in path order.
- `old` and `new` MUST be component paths: segments matching `[A-Za-z0-9_.+-]+` joined by `/` ("Design structure and names"). A malformed path, `old == new`, or a second alias with the same `old` or the same `new` MUST raise `DslError` at the call.
- `moves(design)` MUST raise `DslError` when `new` is not the path of a part added to the design, or when `old` is the path of a part added to the design, because the old part would lose its layout to the new one. Chains (`moved("A", "B")` with `moved("B", "C")`) are therefore refused.
- `cmd_build` MUST turn such a `DslError` into `DesignScriptError` (`FEN-3004`, exit 3), as for `to_model` and `placements`.
- Aliases are not model data: `to_model` MUST give the same model with and without them, and no id changes.
- An alias is needed for one build only: the build re-places the footprint under its new path, and later builds match it by uuid (`layout-lens`, "Footprint matching"). An alias that matches nothing gives `layout.alias-unused` (warning).

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

## MODIFIED Requirements

### Requirement: DSL package
The package `fenolite.dsl` SHALL provide a thin, stdlib-only API to describe a design in Python, and MUST import only `core` and `model` (`package-layering`).
- Modules: `design.py` (`Design`, `Rules`), `module.py` (`Module`), `part.py` (`Part`, `PinHandle`, `Net`, `connect`, `Placement`), `interfaces.py` (`Interface`, `Power`, `DiffPair`), `units.py` (`Length`, `mm`, `mil`, `inch`, `nm`), `convert.py` (`to_model`, `placements`, `moves`, `KEYS`, `BOARD_ORIGIN`), `errors.py` (`DslError(ValueError)`) and `_minimal.py`, a packaged hermetic example.
- `fenolite.dsl` MUST re-export `Design`, `Module`, `Part`, `Net`, `connect`, `Interface`, `Power`, `DiffPair`, `Length`, `mm`, `mil`, `inch`, `nm`, `Placement`, `BOARD_ORIGIN`, `to_model`, `placements`, `moves`, `KEYS`, `DSL_BACKEND` (`"dsl"`) and `DslError`.
- Later requirements MAY add modules and re-exported names, which keep the import rule above; each such requirement names this one.
- The root package `fenolite` MUST re-export neither the DSL `Design` nor the model `Design`. Inside `dsl`, the model class MUST be imported as `ModelDesign`.
- Objects MUST join a design only through `add()`. There is no hidden global or "current design" state.
- The DSL MUST store lib ids as strings only. It MUST NOT read a library, a file or the environment, and MUST NOT import a backend.
- There are no part classes, no part picker, no solver and no custom-rule constructor. `Design.moved(old, new)` records a path alias for layout preservation ("Path aliases in the DSL").

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and every import inside `src/fenolite/dsl/` is of the standard library, `fenolite.core` or `fenolite.model`

#### Scenario: Root package exports no Design
- **WHEN** `python -c "import fenolite; print(hasattr(fenolite, 'Design'))"` runs
- **THEN** it prints `False`

#### Scenario: No hidden membership
- **GIVEN** a `Design` and a `Part("R9", "Mini:Mini_R")` that is created but never added
- **WHEN** `to_model(design)` runs
- **THEN** the model holds no component `R9`

#### Scenario: Aliases exported
- **WHEN** `python -c "from fenolite.dsl import moves; print(moves.__module__)"` runs
- **THEN** it prints `fenolite.dsl.convert`

### Requirement: Build command
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model`, `placements` and `moves`, prepares layout preservation with `lens.preserve.read_existing` and `lens.preserve.prepare` unless `--discard-layout` is given, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout` and `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global` or `template`), `script_output` and `preserved` (`layout-lens`, "Layout preservation evidence"), plus the dispatcher's `plan`.
- Later requirements MAY add `build` options, steps of `cmd_build` and keys of `result`; each such requirement names this one.
- `cmd_build` MUST turn a `DslError` raised by `to_model`, `placements` or `moves`, which run after `run_design_script` has returned, into `DesignScriptError` with `file` = the script path and no locator (`FEN-3004`, exit 3).
- Unless `--discard-layout` is given, `cmd_build` MUST read the existing triad with `read_existing(DIR, <design name>)`, call `prepare(model, placements(design), existing, name=<design name>, moves=moves(design))`, and pass `prepared.placements` as `placements` and `prepared` as `prepared` to `build_design`. With `--discard-layout`, it MUST pass `placements(design)` and no `prepared`.
- `cmd_build` MUST read the last build record once with `lens.build.read_record(DIR)`, pass it to `build_design` and to `lens.build.check_existing` as `record`, and call `check_existing` before it returns the plan, with every planned file except the board, project and rules files, which preservation merges ("Edited outputs are not overwritten").
- A build with an issue of severity `error` MUST return no planned write, so it exits 5 and writes nothing.
- `example_args` (with `--dry-run`) and `mutation_example_args` MUST use the packaged `src/fenolite/dsl/_minimal.py` (Apache-2.0 header; a board with one net class and no parts), located through `fenolite.dsl.__file__`, so the consistency suite is hermetic from any working directory.

#### Scenario: Confirmation required
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --json` runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists every planned file, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm`
- **THEN** the exit code is 0, and `receipt.written` lists `B/blink.kicad_pcb`, `B/blink.kicad_pro`, `B/blink.kicad_dru`, `B/fp-lib-table`, the three footprints under `B/lib/Mini.pretty/` and the seven files under `B/.fenolite/`

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
- The layout MUST be `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, the six layer files under `.fenolite/` and `.fenolite/build.json`.
- Every vendored footprint MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, and `fp-lib-table` MUST hold one row per vendored nickname with `uri "${KIPRJMOD}/lib/<nickname>.pretty"`, written by `libs.write_lib_table` for the target. With `vendor="all"`, every footprint that the build places is vendored, whatever the origin of its row; with `vendor="project"`, only footprints resolved through a project-table row are ("Footprints of every row origin are vendored"). Any other `vendor` MUST raise `ValueError`.
- With `vendor="project"`, footprints from rows of another origin MUST NOT be vendored and get no row (`build.global-library`, info). A vendored file whose header version is newer than the target's newest format MUST give `build.library-too-new` (warning). With `record`, a vendored file whose bytes differ from the hash recorded for its path MUST give `build.library-changed` (warning).
- The build MUST NOT write a `sym-lib-table`, a symbol file, a `.kicad_prl`, a `native/` folder or a date.
- The `.fenolite/` layer texts MUST come from `canonical.dump_texts` of `BuildOutput.layout`, with an empty `findings.json` and no `FootprintDef`. `.fenolite/build.json` MUST have `schema` `fenolite.build-record.v0`, sorted keys and no date, and MUST record the SHA-256 of every file outside `.fenolite/` that the build writes. It is regenerable and marks a built project.

#### Scenario: Files of a target-9 build
- **WHEN** the blink is built for target 9
- **THEN** `files` holds exactly the triad `blink.*`, `fp-lib-table` without a `version` child, three files under `lib/Mini.pretty/` byte-equal to their sources in `tests/data/libs/Mini_v9.pretty/`, the six layer files under `.fenolite/` and `.fenolite/build.json`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of a blink build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, it holds no date, and it maps each of the seven files outside `.fenolite/` to its SHA-256

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
`lens.build.check_existing(out_dir, files, *, record, discard_layout) -> None` SHALL refuse to replace a file outside `.fenolite/` that changed since Fenolite last wrote it, except the board, project and rules files of the triad, which layout preservation merges instead (`layout-lens`). For each other planned file outside `.fenolite/` that already exists, that is `fp-lib-table` and the vendored footprints under `lib/`:
- bytes equal to the planned bytes: an identical rewrite, allowed;
- SHA-256 equal to the one recorded in `.fenolite/build.json`: untouched since the last build, allowed, so a DSL edit never needs `--discard-layout`;
- otherwise (edited, or found without a record): `LayoutExistsError` MUST be raised, with `cli_code = "FEN-7001"` (exit 7), one `build.layout-exists` issue per file, and the hint "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder".

Further rules:
- `cmd_build` MUST NOT pass the board, project and rules files to the check.
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

### Requirement: Build issue codes
The build SHALL report its own findings only with the codes of the closed table `lens.build.BUILD_ISSUE_CODES`, which MUST also hold every row of `lens.preserve.PRESERVE_ISSUE_CODES` (`layout-lens`, "Layout issue codes"). Every `kicad.*` code, such as those of the writers (`kicad.board.*`, `kicad.project.*`) and of the readers and the resolver (`kicad.board.*`, `kicad.version.*`, `kicad.lib.*`), the writers' `rules.*` codes and the codes of `Design.validate()` (`model.*`) MUST pass through unchanged. Later requirements MAY add codes that join the `build` envelope unchanged, from steps they add to the build or to `cmd_build`; each such requirement names this one.

| code | severity | when |
|---|---|---|
| `build.unknown-pin` | error | a designator is neither a pin number nor a pin name |
| `build.pin-on-two-nets` | error | a resolved pin is on two nets |
| `build.pin-without-pad` | error | a connected pin has no pad of its number |
| `build.no-footprint` | error | neither the part nor the symbol names a footprint |
| `build.no-board` | error | the design has no `board()` |
| `build.name-case-collision` | error | net or class names differ only in letter case |
| `build.layout-exists` | error | `fp-lib-table` or a vendored footprint changed since the last build (carried by `LayoutExistsError`) |
| `build.property-reserved` | error | a user property has a reserved name or prefix |
| `build.property-invalid` | error | a user property name or value is not printable text, a name has surrounding whitespace, or two names differ only in letter case |
| `build.property-conflict` | error | the footprint definition holds a property of the same name with another value |
| `build.vendor-unsafe-name` | error | a vendored nickname holds a path separator or a non-printable character, or two vendored paths differ only in letter case |
| `build.pin-ambiguous` | warning | a pin number is also another pin's name |
| `build.unused-pin-without-pad` | warning | an unconnected pin has no pad of its number |
| `build.library-too-new` | warning | a vendored file is newer than the target's newest format |
| `build.library-changed` | warning | a vendored file differs from the copy that the last build recorded |
| `layout.unplaced` | warning | a part was staged beside the outline, its footprint being new or off the board |
| `build.pad-without-pin` | info | a numbered pad has no pin of its number |
| `build.global-library` | info | with `vendor="project"`, a footprint came from a row whose origin is not `project` and is not vendored |
| `build.interface-not-lowered` | info | a `diff_pair` interface is kept in the model only |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` collects every issue code produced by the build tests
- **THEN** each code other than `kicad.*`, `rules.*`, `model.*` and the codes that later requirements add under this requirement is a key of `BUILD_ISSUE_CODES` with the severity of this table or of `PRESERVE_ISSUE_CODES`, and every key of this table is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the blink with `R1` not placed
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 0 and `issues` holds one `layout.unplaced` warning naming `R1`

#### Scenario: Preservation codes are build codes
- **WHEN** `PRESERVE_ISSUE_CODES` is compared with `BUILD_ISSUE_CODES`
- **THEN** every key of the first is a key of the second with the same severity

### Requirement: Build evidence
The `build` envelope SHALL carry `Evidence.combine` (lowest wins) of `lens.build.BUILD_EVIDENCE` (`INFERRED`; `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP`), `sym.EVIDENCE` and `mod.EVIDENCE` (`H-K-LIB-READ`), `pcb.WRITE_EVIDENCE` (`H-K-PCB-WRITE`), `pro.EVIDENCE` (`H-K-PRO-PATTERNS`), `lowering.EVIDENCE`, when a part is on the bottom side `embed.EVIDENCE`, when a user property is written `lens.build.PROPERTY_EVIDENCE` (`INFERRED`; `H-K-VENDOR-PROPS`, `H-K-VENDOR-DUPNAME`), when a footprint of a row whose origin is not `project` is vendored `lens.build.VENDOR_EVIDENCE` (`INFERRED`; `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`), when an existing board was read `lens.preserve.EVIDENCE` and `pcb.EVIDENCE` (`H-K-PCB-READ`), and when an existing rules text was merged `dru.EVIDENCE`.
- The level MUST stay `INFERRED` while any of these is below `KICAD-VERIFIED`.
- `PROPERTY_EVIDENCE` and `VENDOR_EVIDENCE` MUST stay `INFERRED` after their rows are settled, because the oracle covers the blink and its variants, not every design.
- Later requirements MAY add evidence that joins the envelope only when their feature is used; each such requirement names this one.
- `KICAD-VERIFIED` applies to the blink example only, through the oracle suite (`kicad-oracle`, "Built projects pass the build oracle"), and MUST NOT be reported for an arbitrary build.

#### Scenario: Blink envelope
- **WHEN** the blink is built with `--dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, and `evidence.hypotheses` contains `H-K-BUILD-TRIAD`, `H-K-LIB-READ` and `H-K-PCB-WRITE`

#### Scenario: Bottom parts add the flip rows
- **GIVEN** the blink, whose `D1` is on the bottom, and a variant with `D1` on the top
- **WHEN** both are built with `--dry-run --json`
- **THEN** only the first envelope's `evidence.hypotheses` contains the hypotheses of `embed.EVIDENCE`

#### Scenario: Properties and vendoring add their rows
- **GIVEN** the blink, a variant with `properties={"Part number": "PN-330"}` on `R1`, and a variant whose footprints come from a global table authored in the test
- **WHEN** the three are built with `--dry-run --json`
- **THEN** only the second envelope's `evidence.hypotheses` contains `H-K-VENDOR-PROPS`, only the third contains `H-K-VENDOR-GLOBAL`, and every `evidence.level` is `INFERRED`

#### Scenario: An existing board adds the preservation rows
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** `evidence.hypotheses` contains `H-K-LENS-KEEP` and `H-K-PCB-READ`, and `evidence.level` is `INFERRED`
