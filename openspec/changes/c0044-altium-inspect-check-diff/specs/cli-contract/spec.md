## ADDED Requirements

### Requirement: Diff of document inputs and the records view
`fenolite diff A B` ("Diff command", change c0066) SHALL also accept the inputs of a backend that satisfies `DocumentValidator` (`backend-protocol`, "Document sets and container round trips"), and SHALL offer `--view records` beside `model` and `tree`. Everything "Diff command" says of the result keys, the paged list `differences`, the exit code, determinism and `example_args` applies unchanged.
- **Inputs.** `A` and `B` MAY each be a file that `registry.for_path` gives such a backend for (an Altium document, library or project file), or a folder that holds exactly one project file of such a backend and no `.fenolite/meta.json`. A project file or folder is read with `backend.read` of the project file. `a.kind` and `b.kind` MUST then be the read kind that `backend.documents` gives the file (`altium_pcbdoc`, `altium_schdoc_ascii`, …). A folder that holds `.fenolite/meta.json` stays the built model, whatever else it holds.
- **Model view.** Designs and libraries of any two backends MUST be compared as "Diff command" says: `diff_designs` for two designs, `diff_libraries` for two libraries, exit 2 with `FEN-2001` for a design against a library. `--view tree` on such an input MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Records view.** `--view records` MUST compare two Altium files of one kind as `altium-verification`, "Records view of two Altium files", says, with `summary` per stream. For any other pair of inputs it MUST exit 2 with `FEN-2001` and a hint that names `--view model`. `--ext` with this view MUST exit 2 with `FEN-2001`.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; in the records view it is the readers' evidence of the kind.
- `docs/cli-contract.md`, section "diff", MUST describe the three views and the Altium inputs.

#### Scenario: Two Altium documents in the model view
- **WHEN** `uv run pytest tests/unit/cli/test_diff_cmd.py -k altium_model` runs `fenolite diff tests/data/altium/blink/blink.PcbDoc tests/data/altium/blink/blink.PcbDoc --json`
- **THEN** the exit code is 0, `result.view` is `model`, `result.equal` is `true`, and `result.a.kind` is `altium_pcbdoc`

#### Scenario: A KiCad board against an Altium document
- **WHEN** `fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 0, `result.equal` is `false`, `result.a.kind` is `kicad_pcb` and `result.b.kind` is `altium_pcbdoc`

#### Scenario: Project folder as an input
- **WHEN** `fenolite diff tests/data/altium/blink tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** the exit code is 0, `result.equal` is `true`, and both kinds are `altium_prjpcb`

#### Scenario: Records view refused for KiCad files
- **WHEN** `fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --view records` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `--view model`

#### Scenario: Tree view refused for Altium files
- **WHEN** `fenolite diff tests/data/altium/blink/blink.SchDoc tests/data/altium/blink/blink.SchDoc --view tree` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `--view model`

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
