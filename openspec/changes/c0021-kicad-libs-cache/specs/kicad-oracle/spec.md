## MODIFIED Requirements

### Requirement: DRC verdicts come from the JSON report
Every oracle test and every command that judges a DRC outcome SHALL read it from the JSON report, through `KicadCli.drc` and `read_drc_report`.
- `KicadCli.drc(board, *, files=None, env=None)` MUST run `pcb drc --format json --severity-all -o <out> <board>` through c0009's runner on a copy, and MUST NOT pass `--exit-code-violations`. `DrcRun.report` MUST be `None` when no report was written.
- `KicadCli.drc` MUST pass `env` unchanged to `KicadCli.run`. Its entries reach `kicad-cli` after the runner's own variables: an entry `KICAD_CONFIG_HOME` replaces the runner's empty configuration folder, and the caller's variables whose names start with `KICAD` are still dropped. With `env=None`, `kicad-cli` MUST get the runner's environment unchanged.
- The exit code of `pcb drc` MUST be used only as a load signal.
- A report without violations MUST NOT count as evidence that a library table, a project file or a custom rules file was loaded. Every such proof MUST carry a control that fires only when the file was loaded: the missing-table control here, the canary in the rules proofs.
- `tests/kicad/board/test_drc_report.py::test_drc_json_strict` MUST settle `H-K-DRC-JSON` on both majors: the report parses with `NaN` and `Infinity` rejected, holds the 7 required top-level keys, and `read_drc_report` accepts it. Whether `ignored_checks` is present MUST be recorded per major under the probe id `pcb-drc-ignored-checks`.

#### Scenario: Strict report on both majors
- **GIVEN** the triad written for the running major
- **WHEN** `uv run pytest tests/kicad/board/test_drc_report.py` runs on 9.0.9 and on 10.0.6
- **THEN** each report parses as strict JSON with `source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity` and `coordinate_units`, and `read_drc_report` returns a `DrcReport`

#### Scenario: Exit code is not a verdict
- **GIVEN** a fake `kicad-cli` that exits 0 and writes a report holding one `clearance` violation
- **WHEN** `KicadCli.drc` runs
- **THEN** the arguments hold no `--exit-code-violations`, and `run.report.of_type("clearance")` returns one violation

#### Scenario: No report written
- **GIVEN** a fake `kicad-cli` that exits 3 and writes no report
- **WHEN** `KicadCli.drc` runs
- **THEN** `run.report is None` and `run.run.returncode == 3`

#### Scenario: Extra files next to the board
- **GIVEN** a fake `kicad-cli` that lists its working directory
- **WHEN** `load_board_svg(board, files={"board.kicad_pro": pro, "fp-lib-table": table})` runs
- **THEN** the listing holds the board copy, `board.kicad_pro` and `fp-lib-table`, and the caller's files are unchanged

#### Scenario: Explicit environment entries reach kicad-cli
- **GIVEN** a fake `kicad-cli` that records its environment and writes a report holding one `clearance` violation, a caller environment with `KICAD9_FOOTPRINT_DIR=/caller`, and a folder `D` under `tmp_path`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k drc_env` calls `KicadCli.drc(board, env={"KICAD_CONFIG_HOME": str(D), "KICAD10_FOOTPRINT_DIR": "/libs"})`, then `KicadCli.drc(board)`
- **THEN** the first run records `KICAD_CONFIG_HOME` equal to `D`, `KICAD10_FOOTPRINT_DIR=/libs`, `LANG=C` and no `KICAD9_FOOTPRINT_DIR`; the second records a `KICAD_CONFIG_HOME` inside the run's temporary directory and no `KICAD10_FOOTPRINT_DIR`; and both reports hold the `clearance` violation

## ADDED Requirements

### Requirement: Library table probes
`tests/kicad/libs/test_lib_tables_drc.py` (marker `needs_kicad`, major-aware) SHALL settle the library-resolution hypotheses with the probes below. Each probe SHALL be registered in `tests/kicad/_probes.py` for majors 9 and 10, and SHALL run `KicadCli.drc(board, files=…, env=…)` ("DRC verdicts come from the JSON report"), never `KicadCli.run` directly.
- **Board.** Every probe uses c0017's altered control `_bench.control(target, _bench.CONTROLS["unmirrored"])`, written for the running major by `_bench.write(…, table=False)`. Its one footprint, `Mini:Mini_QFP-32_7x7mm_P0.8mm`, differs from its library footprint, so a found library gives exactly one `lib_footprint_mismatch`. `<lib>` is a copy of `_triad.library(target)`: `Mini.pretty` on 10, `Mini_v9.pretty` on 9. Every table uses the syntax of the running major.
- **Outcome.** It names whether `lib_footprint_issues` is reported:
  - `absent`: no `lib_footprint_issues` and exactly one `lib_footprint_mismatch`, so the library was found and compared;
  - `present`: at least one `lib_footprint_issues` and no `lib_footprint_mismatch`;
  - `different`: any other report; `reject`: no report; `timeout`: the run timed out;
  - `inconclusive`: for every probe, when `pcb-libdrc-missing-table` is not `present`.
- **Probes.**

| probe id | layout |
|---|---|
| `pcb-libtable-relpath-project` | project row `Mini` with uri `<lib>` (relative, no variable) |
| `pcb-libtable-relpath-nested` | project row `Sub` of type `Table` with uri `${KIPRJMOD}/sub/fp-lib-table`; that nested table's row `Mini` has uri `../<lib>` |
| `pcb-libtable-nested` | the same `Table` row; the nested row `Mini` has uri `${KIPRJMOD}/<lib>` |
| `pcb-libtable-fallback` | project row `Mini` with uri `${KICAD9_FOOTPRINT_DIR}/<lib>`; `env` sets `KICAD10_FOOTPRINT_DIR` to a folder holding `<lib>` |
| `pcb-libtable-fallback-defined` | the same, and `env` also sets `KICAD9_FOOTPRINT_DIR` to an empty folder |
| `pcb-libtable-confighome` | no project table; `env` sets `KICAD_CONFIG_HOME` to a folder D whose `<M>.0/fp-lib-table` has the row `Mini` with the absolute path of a folder `<lib>` |
| `pcb-libtable-confighome-flat` | the same table at `D/fp-lib-table` |
| `pcb-libtable-common` | `env` sets `KICAD_CONFIG_HOME` to D; `D/<M>.0/kicad_common.json` defines `FENOLITE_PROBE_LIBS`, in `environment.vars`, as a folder holding `<lib>`; project row `Mini` with uri `${FENOLITE_PROBE_LIBS}/<lib>` |
| `pcb-libtable-common-env` | the same, and `env` also sets `FENOLITE_PROBE_LIBS` to an empty folder |

- **Configuration files.** D is passed as the `env` entry `KICAD_CONFIG_HOME` of `KicadCli.drc`, because the runner refuses `files` under its `config` folder. D is always a new, empty temporary folder, never the user's configuration folder. Before writing `kicad_common.json`, the `common` probes run `KicadCli.drc` once with D empty. When that run wrote `D/<M>.0/kicad_common.json`, the probe adds the variable to its `environment.vars`; otherwise it writes `{"environment": {"vars": {…}}}`. Which case occurred SHALL be written with `_boards.census` to the file named by `FENOLITE_CENSUS_OUT`.
- **Observation.** `test_common_file_layout` SHALL run `KicadCli.drc` once with `env` setting `KICAD_CONFIG_HOME` to an empty folder under `tmp_path`, and record with `_boards.census` whether `<M>.0/kicad_common.json` was written and whether its `environment` object holds `vars`. It records key names only, never values, and asserts nothing. No KiCad source code is read for the layout of this file.
- **Isolation.** Tested variables reach `kicad-cli` only through the `env` argument of `KicadCli.drc`, and the runner still drops the caller's `KICAD*` variables. Every folder outside the runner's temporary directory is a temporary folder of the probe, removed afterwards. Nothing is written to the repository, except the results files with `FENOLITE_PROBES_WRITE=1`.
- **Settling on 10.0.6.** `test_relpath` asserts `absent` for both `relpath` probes. `test_fallback` asserts `absent` for `pcb-libtable-fallback` and `present` for `pcb-libtable-fallback-defined`. `test_nested` asserts `absent`. `test_config_home` asserts `absent` for `pcb-libtable-confighome` and `present` for `pcb-libtable-confighome-flat`. `test_common_vars` asserts `absent` for `pcb-libtable-common` and `present` for `pcb-libtable-common-env`. An `inconclusive` outcome MUST fail the test with a message naming `H-K-LIB-DRC`.
- **Settling on 9.0.9.** `test_nested` asserts `present` for `pcb-libtable-nested`, on the authored board without corpus. Every other 9.0.9 outcome is recorded by its probe id and MUST NOT fail a test.

#### Scenario: Nested table on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6, where `pcb-libdrc-missing-table` is `present`
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py -k nested` runs
- **THEN** `pcb-libtable-nested` is `absent`: the report holds no `lib_footprint_issues` and exactly one `lib_footprint_mismatch`

#### Scenario: Nested table on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job, and a probe that uses no corpus file
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py -k nested` runs
- **THEN** `pcb-libtable-nested` is `present`

#### Scenario: Relative uris
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_relpath` runs
- **THEN** `pcb-libtable-relpath-project` and `pcb-libtable-relpath-nested` are `absent`

#### Scenario: Fallback only for an undefined variable
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_fallback` runs
- **THEN** `pcb-libtable-fallback` is `absent` and `pcb-libtable-fallback-defined` is `present`

#### Scenario: Configuration folder of the major
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_config_home` runs
- **THEN** `pcb-libtable-confighome` is `absent` and `pcb-libtable-confighome-flat` is `present`

#### Scenario: Process variable wins over kicad_common.json
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_common_vars` runs
- **THEN** `pcb-libtable-common` is `absent` and `pcb-libtable-common-env` is `present`

#### Scenario: Layout of kicad_common.json observed
- **GIVEN** `kicad-cli` 10.0.6, an empty folder under `tmp_path` as `KICAD_CONFIG_HOME`, and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `test_common_file_layout` runs
- **THEN** that file records whether `10.0/kicad_common.json` was written and whether its `environment` object holds `vars`, with key names only

#### Scenario: Silent library check
- **GIVEN** a run in which `pcb-libdrc-missing-table` is not `present`
- **WHEN** a `pcb-libtable-*` probe runs on 10.0.6
- **THEN** its outcome is `inconclusive`, and the test that asserts on it fails naming `H-K-LIB-DRC`

#### Scenario: Outcomes pinned per version
- **GIVEN** the committed `docs/evidence/kicad/probes/10.0.6.json` and `docs/evidence/kicad/probes/9.0.9.json`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on 10.0.6 and on 9.0.9
- **THEN** it passes on both, and each file holds an outcome for every `pcb-libtable-*` id

#### Scenario: Repository untouched
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py` runs on 10.0.6
- **THEN** `git status --porcelain` is unchanged afterwards
