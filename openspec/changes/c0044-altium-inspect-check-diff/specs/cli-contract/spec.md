## ADDED Requirements

### Requirement: Diff command
`fenolite diff A B [--view model|records] [--ext] [--limit N]` SHALL be registered by `src/fenolite/cli/cmd_diff.py` with `mutates=False`, and SHALL list the differences between two inputs without writing a file and without running any external tool.
- **Inputs.** `A` and `B` MUST each be a file that `registry.for_path` gives a backend for, a project file or folder of a backend that satisfies `DocumentValidator`, or a folder that holds `.fenolite/meta.json` (the built model, loaded with `model.canonical.load_dir`). A missing path MUST exit 3 with `FEN-3001`, an input that no backend reads MUST exit 2 with `FEN-2001`, and a read error MUST exit 3 with its code.
- **Model view** (the default). Two designs MUST be compared with `checks.diff.diff_designs` and two libraries with `checks.diff.diff_libraries` (`verification-loop`, "Model difference report"). A design against a library MUST exit 2 with `FEN-2001`. `--ext` MUST pass `ext=True`.
- **Records view.** `--view records` MUST compare two Altium files of one kind as `altium-verification`, "Records view of two Altium files", says. For any other pair of inputs it MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Result.** `result` MUST hold `view`, `equal`, `a` and `b` (each `{path, kind}`, `path` being the file or folder name without its parent), `summary` (per entity kind or stream, the counts `added`, `removed` and `changed`), `differences` (at most `--limit` objects `{path, change, a, b}`, in report order), `total` and `truncated`. `--limit` MUST default to 200; a value below 1 MUST exit 2 with `FEN-2001`.
- **Exit code.** A difference is a result, not a finding: the exit code MUST be 0 whether or not the inputs differ, and `issues` MUST hold only the readers' issues, those of `A` first.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; a `.fenolite/` model counts as `INFERRED`. `input` MUST describe `A`.
- **Determinism.** Two runs on the same inputs MUST give the same stdout apart from `elapsed_ms`, and the output MUST hold no absolute path.
- `example_args` MUST be `(EXAMPLE_BOARD, EXAMPLE_BOARD)` and MUST run no subprocess from any working directory. `docs/cli-contract.md` MUST have a section "diff" with the views, the result keys and the matching keys.

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

#### Scenario: Records view refused for KiCad files
- **WHEN** `fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --view records` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `--view model`

#### Scenario: Limit truncates the list
- **GIVEN** two authored designs with five differences
- **WHEN** `fenolite diff A B --limit 2 --json` runs
- **THEN** `result.differences` holds two objects, `result.total` is 5 and `result.truncated` is `true`

#### Scenario: Diff is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `diff` with its `example_args`
- **THEN** the exit code is 0

## MODIFIED Requirements

### Requirement: Inspect command
`fenolite inspect FILE [--summary | --streams]` SHALL be registered by `src/fenolite/cli/cmd_inspect.py` with `mutates=False`, and SHALL describe one file without running any external tool. `--summary` is the default view and summarises one KiCad file, or one file of a backend that satisfies `DocumentValidator` (`altium-verification`, "Altium file summary"). `--streams` lists the storages and streams of a compound file ("Inspect stream tree"). Giving both views MUST exit 2 with `FEN-2001`.
- **Kinds.** Boards, footprint files and symbol libraries (file or `.kicad_symdir` folder) MUST be read through `registry.for_path(FILE).read`. `.kicad_sch` and `.kicad_wks` files MUST be read header-only through `versions.inspect`, with root-child counts by head. A file whose backend satisfies `DocumentValidator` MUST be summarised as "Altium file summary" says. With the `--summary` view, `.kicad_pro`, `.kicad_dru` and every other file that no backend reads MUST exit 2 with `FEN-2001`; when such a file starts with the compound file signature, the hint MUST name `--streams`.
- **Result.** `result` MUST hold `kind`, `format_version`, `major`, `status`, `generator`, `generator_version`, `counts`, `opaque_count` and `model_findings`. Board `counts` MUST hold `footprints`, `pads`, `nets`, `tracks`, `arcs`, `vias`, `zones`, `fills`, `keepouts`, `graphics` and `texts`. `opaque_count` MUST be `pcb.opaque_count` of the design for a KiCad board and `null` for every other KiCad kind. `model_findings` MUST count the `model.*` findings by severity. `input.path` MUST be the file name without its folder, so the output does not depend on the working directory.
- **Issues.** Reader issues MUST be reported as issues. `model.*` findings MUST only be counted, so a board that KiCad saves with duplicate references exits 0.
- **Errors.** A read error MUST exit 3 with its code (`FEN-3002`, `FEN-3003` or `FEN-3004`), and a missing file with `FEN-3001`.
- **Evidence.** The envelope evidence MUST be the reader module's `EVIDENCE`, and `INFERRED` (`H-K-TOK-CONSTANTS`) for header-only kinds.
- `example_args` MUST be `(EXAMPLE_BOARD, "--summary")`, with `fenolite.cli._examples.EXAMPLE_BOARD` as in "Check command input" (`verification-loop`), and MUST run no subprocess from any working directory.

#### Scenario: Authored board summary
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.kind` is `kicad_pcb`, `format_version` is `20241229`, `major` is 9, `counts` is footprints 2, pads 4, nets 3, tracks 3, arcs 1, vias 1, zones 1, fills 2, keepouts 1, graphics 6 and texts 1, and `opaque_count` equals `pcb.opaque_count` of the read design

#### Scenario: Model findings are counted
- **GIVEN** a copy of the authored board whose second footprint has the reference of the first
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k findings` runs `inspect` on it
- **THEN** the exit code is 0 and `result.model_findings.error` is at least 1

#### Scenario: Unreadable and deferred files
- **WHEN** `fenolite inspect` runs on `tests/data/kicad/sexpr/mirror/unbalanced.kicad_pcb` and on a `.kicad_pro` file
- **THEN** the first exits 3 with `FEN-3004`, and the second exits 2 with `FEN-2001`

#### Scenario: Inspect is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `inspect` with its `example_args`
- **THEN** the exit code is 0

#### Scenario: Compound file of a registered backend is summarised
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 0 and `result.kind` is `altium_pcbdoc`

#### Scenario: Compound file that no backend reads
- **GIVEN** a compound file in `tmp_path` named `x.bin` that holds one stream `Data`
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k unknown_compound` runs `fenolite inspect x.bin --json`
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names `--streams`

#### Scenario: Two views
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --summary --streams` runs
- **THEN** the exit code is 2 with `FEN-2001`
