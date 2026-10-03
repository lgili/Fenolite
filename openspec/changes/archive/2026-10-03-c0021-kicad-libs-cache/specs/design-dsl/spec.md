## MODIFIED Requirements

### Requirement: Library resolution during build
The build SHALL resolve every `lib_symbol_ref` and `lib_footprint_ref` through one c0008 `LibraryResolver(LibraryConfig(target_major=ctx.kicad_target, project_dir=<script folder>))`, built with the process environment and the user's configuration folder. A `cache` source is used only when `FENOLITE_LIBS_CACHE` names one: the build passes no `cache_dir`, and no default cache location is searched (`kicad-library-resolution`, "Library sources").
- Project tables next to `design.py` are the recommended source. Global and template tables follow c0008. Official library variables come only from an `env`, `cache` or `install` source of the target major, in that order, so a 10.0 install is never used for target 9 (`kicad-library-resolution`, "Library sources").
- Every `LibraryError` MUST be collected. If there is at least one, `lens.build.UnresolvedLibrariesError(LibraryError)` (`FEN-3001`) MUST be raised with the first error's hint and one `kicad.lib.*` issue per failure in `issues`.
- `Part.footprint=None` MUST fall back to the symbol's `Footprint` property. When both are empty, the build MUST give `build.no-footprint` (error).
- `value=""` MUST fall back to the symbol's `Value` property.
- A row of origin `scan` (`kicad-library-resolution`, "Table discovery and precedence") MUST be handled by every build rule like any row whose origin is not `project`: its footprints are vendored ("Footprints of every row origin are vendored"), or give `build.global-library` with `vendor="project"`.
- `result.libraries` MUST map each lib id to the origin of its row: `project`, `global`, `template` or `scan`.

#### Scenario: Two unknown lib ids
- **GIVEN** a blink variant whose parts `R1` and `D1` name `Nope:A` and `Nope:B`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and `issues` holds one `kicad.lib.*` issue for each lib id

#### Scenario: A 10.0 install is not used for target 9
- **GIVEN** only a 10.0 install made by `tests/_libs.make_install`, and a design whose footprint row uses `${KICAD9_FOOTPRINT_DIR}`
- **WHEN** `fenolite --kicad-version 9 build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and its hint names `KICAD9_FOOTPRINT_DIR`

#### Scenario: Footprint and value from the symbol
- **GIVEN** `Part("U1", "Mini:Mini_QFP32_IC")` with no footprint and no value, resolved from `Mini_v9.kicad_sym`
- **WHEN** it is built
- **THEN** the component has `lib_footprint_ref == "Mini:Mini_QFP-32_7x7mm_P0.8mm"` and `value == "Mini_QFP32_IC"`

#### Scenario: No footprint anywhere
- **GIVEN** `Part("X1", "Mini:Mini_GND")`, whose symbol has an empty `Footprint` property, with no footprint
- **WHEN** it is built
- **THEN** the exit code is 5, `issues` holds `build.no-footprint` naming `X1`, and nothing is written

#### Scenario: Row origins reported
- **WHEN** the blink is built with the example's own tables and an empty `KICAD_CONFIG_HOME`
- **THEN** `result.libraries["Mini:Mini_R_0603"]` is `project`

#### Scenario: Footprint from a scanned cache
- **GIVEN** a blink variant whose `R1` footprint is `Cached:Mini_R_0603`, a folder `C` whose `10.0.6/kicad-footprints/` holds `Cached.pretty`, a copy of `tests/data/libs/Mini.pretty`, and a stamp equal to the 10.0.6 footprint pin, an empty configuration folder and an install path that does not exist
- **WHEN** it is built for target 10 through `tests/_buildhelp.py` with `cache_dir=C`, a keyword that this change adds and that also turns on `use_global_table`
- **THEN** `summary["libraries"]["Cached:Mini_R_0603"]` is `scan`, `files` holds `lib/Cached.pretty/Mini_R_0603.kicad_mod` byte-equal to its source, and `fp-lib-table` holds a row `Cached`

#### Scenario: Official variant from the cache
- **GIVEN** a verified 10.0.6 cache at `tests/_resources.libs_cache_dir()` and no other library source
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_build_official.py` runs
- **THEN** the test sets `FENOLITE_LIBS_CACHE` to that folder for the build, the build exits 0, and `result.libraries["Device:R"]` is `scan`

### Requirement: Build command
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model`, `placements` and `moves`, prepares layout preservation with `lens.preserve.read_existing` and `lens.preserve.prepare` unless `--discard-layout` is given, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout` and `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global`, `template` or `scan`), `script_output` and `preserved` (`layout-lens`, "Layout preservation evidence"), plus the dispatcher's `plan`.
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
