## MODIFIED Requirements

### Requirement: Diff command
`fenolite diff A B [--view model|tree] [--ext] [--allow KINDS] [--three-way THEIRS --out FILE]` SHALL be registered by `src/fenolite/cli/cmd_diff.py` with `mutates=True`, `paged = "differences"` and `default_limit = 200`, and SHALL list the differences between two inputs without running any external tool. It SHALL plan a write only for `--three-way` (`file-safety`, "Three-way difference of KiCad boards"); without it, no write is planned and no confirmation is asked.
- **Inputs.** `A` and `B` MUST each be a KiCad board, footprint file, symbol library or schematic (`.kicad_sch`, read with `sch.read_schematic`), or a folder that holds `.fenolite/meta.json` (the built model, loaded with `model.canonical.load_dir`). A missing path MUST exit 3 with `FEN-3001`, an input that nothing reads MUST exit 2 with `FEN-2001`, and a read error MUST exit 3 with its code.
- **Model view** (the default). Two designs MUST be compared with `checks.diff.diff_designs`, two libraries with `diff_libraries` and two sheets with `diff_sheets` (`verification-loop`, "Model difference report"). Inputs of two families MUST exit 2 with `FEN-2001`. `--ext` MUST pass `ext=True`.
- **Tree view.** `--view tree` MUST take two KiCad S-expression files of one kind and compare their parsed trees: `result.equal` is `tree_equal`, `result.first_difference` the locator of `sexpr.first_difference` or `null`, and `result.heads` the root child heads whose counts differ, each with its count in `a` and in `b`. Its `differences` list MUST be empty. A `.fenolite/` folder MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Result.** `result` MUST hold `view`, `equal`, `a` and `b` (each `{path, kind}`, `path` being the file or folder name without its parent), `summary` (per entity kind, the counts `added`, `removed` and `changed`), `differences` (objects `{path, change, a, b}`, in report order), `total` and `truncated` (true when the page is not the whole list).
- **Exit code.** A difference is a result, not a finding: the exit code MUST be 0 whether or not the inputs differ, unless `--allow` or `--three-way` reports an error finding (`file-safety`, "Gated differences" and "Three-way conflicts"). `issues` MUST hold the readers' issues, those of `A` first, then those findings.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; a `.fenolite/` model counts as `INFERRED`. `input` MUST describe `A`.
- **Determinism.** Two runs on the same inputs MUST give the same stdout apart from `elapsed_ms`, and the output MUST hold no absolute path.
- `example_args` MUST be `(EXAMPLE_BOARD, EXAMPLE_BOARD)` and MUST run no subprocess from any working directory. `mutation_example_args` MUST merge `EXAMPLE_BOARD` three ways into `merged.kicad_pcb`. `docs/cli-contract.md` MUST have a section "diff" with the views, the result keys and the matching keys.

#### Scenario: A file against itself
- **WHEN** `uv run fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.view` is `model`, `result.equal` is `true`, `result.total` is 0 and `result.differences` is empty

#### Scenario: One footprint moved
- **GIVEN** a copy of `two_layer.kicad_pcb` in `tmp_path` whose first footprint is moved by 1 mm in X by a token edit
- **WHEN** `uv run pytest tests/unit/cli/test_diff_cmd.py -k moved` runs `fenolite diff <original> <copy> --json`
- **THEN** the exit code is 0, `result.equal` is `false`, and `result.differences` holds exactly one object, whose `change` is `changed` and whose `path` is `/footprint/<ref>/position`

#### Scenario: Built model against its board
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite diff <project> <project>/<board>.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.a.kind` is `fenolite_model`, and `result.b.kind` is `kicad_pcb`

#### Scenario: Two schematics
- **GIVEN** a copy of `tests/data/kicad/schematic/flat.kicad_sch` whose `R1` is moved by 2.54 mm
- **WHEN** `fenolite diff <original> <copy> --json` runs
- **THEN** `result.differences` holds exactly one object, with the path `/symbol/R1#1/position`

#### Scenario: Tree view sees opaque content
- **GIVEN** a copy of `flat.kicad_sch` with one more `wire`
- **WHEN** `fenolite diff <original> <copy> --json` runs, and again with `--view tree`
- **THEN** the model view reports `equal` true, and the tree view reports `equal` false with `result.heads.wire` holding the two counts

#### Scenario: Page of differences
- **GIVEN** two authored designs with five differences
- **WHEN** `fenolite diff A B --limit 2 --json` runs
- **THEN** `result.differences` holds two objects, `result.total` is 5, `result.truncated` is `true`, and `result.page.next` is not `null`

#### Scenario: Diff is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `diff` with its `example_args`
- **THEN** the exit code is 0
