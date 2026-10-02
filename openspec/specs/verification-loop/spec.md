# verification-loop Specification

## Purpose
Check a KiCad project without writing to it: `fenolite check` runs model validation, ERC lite, KiCad's DRC on a closed copy of the project with a rules canary, and the RT1 round trip, in a fixed order, each stage with its own status and evidence. `fenolite inspect` summarises a file's header and counts, and `fenolite doctor` reports the `kicad-cli` binaries and their command matrices. Contract: `docs/cli-contract.md`; facts: `docs/formats/kicad/cli.md` and `docs/formats/kicad/drc.md`.
## Requirements
### Requirement: Check command input
`fenolite check PATH` SHALL be registered by `src/fenolite/cli/cmd_check.py` with `mutates=False`, and SHALL check the KiCad project that `PATH` names without writing any file.
- **Board.** The board MUST be found with `fenolite.backends.kicad.projectset.resolve_board(PATH)` (`kicad-oracle`, "Check project copy set"). An ambiguous folder MUST exit 2 with `FEN-2001` and a hint listing the candidates. A missing path or board MUST exit 3 with `FEN-3001`.
- **Flags.** `--stages a,b` MUST select a subset of `STAGE_ORDER`; an unknown or empty stage name MUST exit 2 with `FEN-2001`. `--kicad-cli PATH` MUST be passed to `find_kicad_cli` as the explicit path. `--timeout SECONDS` MUST default to 300 and MUST be passed to `KicadCli`.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the board's folder, and native otherwise. Built input MUST load its model with `model.canonical.load_dir(<root>/.fenolite)`. The board's `generator` atom MUST NOT decide it.
- **Injection.** The command MUST narrow `registry.for_path(board)` with `isinstance(backend, Validator)` (`Validator` is `@runtime_checkable`), exit 2 with `FEN-2001` when no backend validates the board, and pass the narrowed backend as the `Validator` and `KicadOracle(KicadCli(path, timeout=…))` as the `Oracle` to `fenolite.checks.stages.run_checks`. It MUST build the oracle only when `drc.kicad` is selected.
- **Result.** `result.project` MUST hold `board`, `built`, `files` and `skipped`, with names relative to `<root>`. `result.stages` MUST hold one object per selected stage. `input.path` MUST be the board name relative to `<root>`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--stages", "model.validate,erc.lite,roundtrip")`, which runs no subprocess. `fenolite.cli._examples.EXAMPLE_BOARD` MUST be the absolute path of `tests/data/kicad/board/two_layer.kicad_pcb`, resolved at import from `Path(fenolite.__file__).resolve().parents[2]`, so that the consistency suite passes from any working directory of a source checkout.

#### Scenario: Project folder resolved
- **GIVEN** a folder holding `a.kicad_pro`, `a.kicad_pcb` and `b.kicad_pcb`
- **WHEN** `fenolite check <folder> --stages roundtrip --json` runs
- **THEN** `result.project.board` is `a.kicad_pcb` and the exit code is 0

#### Scenario: Ambiguous folder
- **GIVEN** a folder holding `a.kicad_pcb` and `b.kicad_pcb` and no project file
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names both boards

#### Scenario: Unknown stage or missing path
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages drc` and `fenolite check missing.kicad_pcb` run
- **THEN** the first exits 2 with `FEN-2001`, and the second exits 3 with `FEN-3001`

#### Scenario: Built input detected
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`, which writes `.fenolite/` with `dump_dir`
- **WHEN** `fenolite check <project> --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** `result.project.built` is `true` and the `erc.lite` stage has status `ok`

#### Scenario: Example arguments are hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `check` with its `example_args`
- **THEN** the exit code is 0, and `input.path` is `two_layer.kicad_pcb`

#### Scenario: Consistency suite from another folder
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory, as in c0011's scenario "Consistency suite"
- **THEN** it passes for `check`, `inspect` and `doctor`

### Requirement: Check stages and statuses
`fenolite.checks.stages` SHALL define `STAGE_ORDER` and `run_checks(*, project, stages, model, built, validator, oracle, cache_error="") -> CheckReport`, where a non-empty `cache_error` says that `.fenolite/` failed `load_dir`. `STAGE_ORDER` MUST hold `model.validate`, `erc.lite`, `drc.kicad` and `roundtrip` in this relative order; this change defines exactly these four, and a later change MAY insert a stage through its own ADDED requirement. `run_checks` MUST run the selected stages in `STAGE_ORDER`, whatever order `--stages` gives, and MUST leave unselected stages out of `CheckReport.stages`.
- Each stage MUST return a frozen `StageResult(name, status, evidence, issues, summary, reason)`. `StageResult.to_json()` MUST return `{name, status, reason, evidence, summary}`, with `evidence` as `{level, oracle, hypotheses}`.
- `status` MUST be `ok` when the stage ran and gave no issue of severity `error`, `errors` when it gave at least one, and `skipped` when it did not run. A skipped stage MUST give no issue and a `reason`. The four stages of this change MUST use only `native-input`, `read-refused` and `cache-unreadable`; a stage added later defines its own reasons.
- `CheckReport.issues`, which the envelope's `issues` MUST equal, MUST be the input issues (`check.read-refused`, `check.cache-unreadable`) followed by the issues of each stage in stage order.
- `run_checks` MUST call `validator.validate` at most once per run.
- The functions of the four stages MUST be `checks.validate.validate_stage`, `checks.erc_lite.erc_stage`, `checks.drc.drc_stage` and `checks.roundtrip.roundtrip_stage`.
- `checks` MUST import only `core`, `model`, `geometry` and `backends.base` (`package-layering`), and MUST reach KiCad only through the injected `Validator` and `Oracle`.

#### Scenario: Fixed order
- **GIVEN** a fake `Validator` and a fake `Oracle`
- **WHEN** `run_checks` is called with `stages=("roundtrip", "model.validate")`
- **THEN** `CheckReport.stages` names `model.validate` then `roundtrip`, and holds no `erc.lite` or `drc.kicad` entry

#### Scenario: Skipped by design
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** `erc.lite` has status `skipped`, reason `native-input` and no issue, and the other two stages have status `ok`

#### Scenario: Checks stay backend-free
- **GIVEN** a module under `src/fenolite/checks/` that imports `fenolite.backends.kicad`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `checks → backends.kicad`

### Requirement: Evidence per check stage
Each `StageResult` SHALL carry the evidence of its own stage, and a skipped stage SHALL carry `UNVERIFIED`. The envelope evidence SHALL be `Evidence.combine` of the stages with status `ok` or `errors` and of the stages skipped with reason `read-refused` or `cache-unreadable`, because their input failed. A stage skipped with reason `native-input` MUST NOT count, and the envelope MUST be `UNVERIFIED` when nothing counts.

| stage | evidence |
|---|---|
| `model.validate`, native | `Validation.read.evidence` (`pcb.EVIDENCE`: `INFERRED`, `H-K-PCB-READ`) |
| `model.validate`, built | `INFERRED` (Fenolite's structural rules) |
| `erc.lite` | `erc_lite.EVIDENCE`: `INFERRED`, `H-K-CHECK-ERC` |
| `drc.kicad` | `DrcOutcome.evidence` (for KiCad, `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`; `KICAD-VERIFIED` only once `H-K-DRC-JSON`, `H-K-CHECK-COPYSET` and `H-K-CHECK-CANARY`, or its `-2` successor, are) when a report exists and the stage gave neither `<oracle>.drc.rules-not-loaded` nor `<oracle>.drc.rules-unchecked`; `UNVERIFIED` otherwise |
| `roundtrip` | `Validation.read.evidence` |

#### Scenario: Lowest level of the stages that ran
- **GIVEN** fakes for which `drc.kicad` gives `KICAD-VERIFIED`, `roundtrip` gives `INFERRED` and `erc.lite` is skipped
- **WHEN** `uv run pytest tests/unit/checks -k envelope_evidence` runs `run_checks`
- **THEN** `CheckReport.evidence.level` is `INFERRED`, and its hypotheses hold those of both stages that ran

#### Scenario: No stage ran
- **GIVEN** a fake `Validator` that raises `FormatError`
- **WHEN** `run_checks` is called with `stages=("roundtrip",)` on native input
- **THEN** `roundtrip` is skipped with reason `read-refused`, and `CheckReport.evidence.level` is `UNVERIFIED`

#### Scenario: Refused read lowers the envelope
- **GIVEN** a fake `Validator` that raises `FormatError`, and a fake `Oracle` that returns a report with canary `not-applicable` and level `KICAD-VERIFIED`
- **WHEN** `uv run pytest tests/unit/checks -k refused_envelope` runs `run_checks` with `stages=("drc.kicad", "roundtrip")` on native input
- **THEN** `drc.kicad` has level `KICAD-VERIFIED`, `roundtrip` is skipped with reason `read-refused`, and `CheckReport.evidence.level` is `UNVERIFIED`

#### Scenario: Verified DRC stage
- **GIVEN** the authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k canary` runs on 9.0.9 and on 10.0.6
- **THEN** the `drc.kicad` stage has the level of `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` and oracle `kicad-cli <running version>`, and that level is `KICAD-VERIFIED` once both constants are (c0017 raises `drc.EVIDENCE`, task 9.2 `oracle.EVIDENCE`)

### Requirement: Check is read-only
`check`, `inspect` and `doctor` SHALL leave every file and folder under the project directory unchanged, and SHALL create nothing there.
- The three commands MUST be `mutates=False` and MUST return no `PlannedWrite`.
- `kicad-cli` MUST run only through c0009's `KicadCli`, on copies. Canary files MUST be staged in a private temporary folder outside the project directory and removed afterwards.
- A `.fenolite/`, `native/` or `*.kicad_prl` entry MUST NOT be created under the project directory.
- The proof MUST be a snapshot of the project directory: every path of a file or folder (by `lstat`), and the SHA-256 and `st_mtime_ns` of every file. It MUST be equal before and after the command.
- Files that KiCad created or changed in the copy MUST be named, sorted, in `summary.tool_writes` of `drc.kicad` (supporting data for `H-K-PRO-PRL`).

#### Scenario: Fake kicad-cli that writes
- **GIVEN** a fake `kicad-cli` that writes `x.kicad_prl` next to its input and rewrites its input board, passed as the only candidate (`MACOS_KICAD_CLI` patched to a missing path)
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py` runs `check` and `inspect` on a project folder, and `doctor` with that folder as working directory
- **THEN** each snapshot is equal before and after, and no new `.fenolite/`, `native/` or `.kicad_prl` entry exists in the folder afterwards

#### Scenario: Real kicad-cli on both majors
- **GIVEN** the authored built project, the native `two_layer` project and the broken-rules project
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k read_only` runs on 9.0.9 and on 10.0.6
- **THEN** every snapshot is equal, and `summary.tool_writes` of `drc.kicad` names each file KiCad wrote in the copy, such as `<stem>.kicad_prl`

#### Scenario: Demo boards untouched
- **GIVEN** the `rt0` corpus and kicad-cli 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_check_demos.py` checks each of the 21 readable non-heavy demo boards in a folder with a `{}` project and a `(version 1)` rules file
- **THEN** every snapshot is equal

### Requirement: Model validation stage
`checks.validate.validate_stage(design, *, built, evidence) -> StageResult` SHALL report the structural findings of the model under check.
- Native input MUST use `Validation.read.design`. Built input MUST use the `.fenolite/` model.
- The stage MUST report the `model.*` findings of `Design.validate()` with their severities.
- It MUST report `check.footprint-unresolved` (error, `where` = the reference) for each component that is not DNP and has an empty `lib_footprint_ref` or no footprint instance.
- On built input it MUST report `check.symbol-unresolved` (error, `where` = the reference) for each component with an empty `lib_symbol_ref`, DNP or not, whose `properties` hold a `fenolite.path` key.
- A component of built input whose `properties` hold no `fenolite.path` key is board-only: a footprint added in KiCad, which a rebuild keeps with the component that `read_board` gives it and no symbol (`layout-lens`, "Orphan and board-only footprints"). It MUST NOT be reported as `check.symbol-unresolved`; every other rule of this stage applies to it.
- A `.fenolite/` folder that `load_dir` cannot load MUST give one `check.cache-unreadable` warning, and `model.validate` and `erc.lite` MUST be skipped with reason `cache-unreadable`. The other stages MUST still run.

#### Scenario: Clean built project
- **GIVEN** the authored built project, in which every component has a `lib_symbol_ref` and a placed footprint
- **WHEN** `fenolite check <project> --stages model.validate --json` runs
- **THEN** the stage has status `ok` and level `INFERRED`, and the exit code is 0

#### Scenario: Unresolved footprint and symbol
- **GIVEN** a built model with one component whose `lib_footprint_ref` and `lib_symbol_ref` are empty and whose `properties` hold a `fenolite.path` key, and one DNP component whose `lib_symbol_ref` is set and that has no footprint instance
- **WHEN** `uv run pytest tests/unit/checks -k validate_stage` runs the stage
- **THEN** it reports one `check.footprint-unresolved` and one `check.symbol-unresolved` for the first component, nothing for the DNP one, and status `errors`

#### Scenario: Board-only component not asked for a symbol
- **GIVEN** a built model whose component `H1` has an empty `lib_symbol_ref`, no `fenolite.path` key in its `properties`, a `lib_footprint_ref` and a placed footprint
- **WHEN** `uv run pytest tests/unit/checks -k validate_stage` runs the stage
- **THEN** it reports neither `check.symbol-unresolved` nor `check.footprint-unresolved` for `H1`

#### Scenario: Rebuilt blink with a mounting hole added in KiCad
- **GIVEN** a confirmed target-10 blink build in `B` whose board gets, by token edit, a footprint `H1` that stands in for a mounting hole added in KiCad (made from `Mini_R_0603`, without a `fenolite.path` property, pad `1` on `GND` and pad `2` on no net), after which `fenolite build examples/blink_2layer/design.py --out B --confirm` runs again
- **WHEN** `fenolite check B --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** the exit code is 0, no issue has severity `error`, and no `check.symbol-unresolved` is reported

#### Scenario: Unreadable cache
- **GIVEN** the authored built project whose `.fenolite/board.json` holds `{`
- **WHEN** `fenolite check <project> --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** the issues hold one `check.cache-unreadable` warning, both model stages are skipped with reason `cache-unreadable`, and `roundtrip` has status `ok`

### Requirement: ERC lite stage
`checks.erc_lite` SHALL define `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`, `erc_lite(design) -> tuple[Issue, ...]`, `erc_stage(design) -> StageResult`, `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`) and `REMOVE_IN = (0, 2)`. The stage MUST run on built input only; on native input it MUST be skipped with reason `native-input`.
- `erc.lite.output-conflict`: a net with two or more member pins whose `etype` is `output` or `power_out`.
- `erc.lite.power-undriven`: a net with a `power_in` member pin and no `power_out` member pin, whose id is not a value of the `members` of any `Interface` with `kind == "power"` (c0011's `Power(hv, lv)`, which acts as a power flag).
- `erc.lite.floating-pin`: a pin whose `etype` is not `no_connect` and that no net lists, reported once per pin.
- Pins of components with `dnp == True` MUST be ignored by the three rules.
- Every finding MUST have severity `warning`.
- `check_removal(version: str) -> None` MUST raise `RuntimeError` naming `erc.lite` and `REMOVE_IN` when `version` is at least `REMOVE_IN`. A unit test MUST call it with `fenolite.__version__`, so the suite fails once the package reaches 0.2 and the stage is removed or replaced by `sch erc` (v0.2a).

#### Scenario: One case per rule
- **GIVEN** one authored model per rule and a clean control model
- **WHEN** `uv run pytest tests/unit/checks -k erc_lite` runs
- **THEN** each rule model gives exactly its own warning, and the control gives none

#### Scenario: Power interface drives a net
- **GIVEN** a model whose net `VCC` has one `power_in` pin and no `power_out` pin, and an `Interface(kind="power")` whose `members` name the id of `VCC`
- **WHEN** `erc_lite` runs
- **THEN** it reports no `erc.lite.power-undriven`

#### Scenario: Removal deadline
- **GIVEN** `fenolite.__version__` patched to `0.2.0`, and the live version below `0.2`
- **WHEN** `uv run pytest tests/unit/checks -k remove_in` runs
- **THEN** it passes: `check_removal` raises `RuntimeError` naming `erc.lite` and `REMOVE_IN` for the patched version (`pytest.raises`), and returns `None` for the live version

### Requirement: DRC stage and the rules canary
`checks.drc.drc_stage(oracle, project, *, built) -> StageResult` SHALL run DRC once through `oracle.drc(project)` and SHALL turn the rules verdict into issues. DRC violations MUST always be counted in `summary`. `summary.violations_judged` MUST be `true` exactly when the run also maps DRC violations to issues. This change maps none, so its stage gives `false`; per-violation issues are c0020's, through its own ADDED requirement.
- **Rules verdict.** Codes MUST start with `f"{oracle.name}.drc."`:
  - canary `absent`, or a `<stem>.kicad_dru` in the copy set without a `<stem>.kicad_pro`: `rules-not-loaded`, severity `error` on built input and `info` on native input;
  - canary `inconclusive`: `rules-unchecked` (warning), with `canary_reason` in the message, except for reason `no-report`, which gives only `check.oracle-failed`;
  - canary `fired`, or `not-applicable` without a rules file: no issue.
- **Summary.** `summary` MUST hold `tool_version`, `canary`, `canary_reason`, `canary_removed`, `violations` (total), `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes` and `violations_judged`, counted on the report from which every canary violation was removed.
- **Copy skips.** Each `SkippedFile` of the project MUST give one `check.copy-skipped` info naming the file and its reason. It MUST NOT lower the stage evidence.
- **No report.** When KiCad wrote no report or timed out, the stage MUST report `check.oracle-failed` (error) with `DrcOutcome.message`, and `retryable: true` on a timeout.

#### Scenario: Built project with a firing canary
- **GIVEN** the authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k canary` runs on 9.0.9 and on 10.0.6
- **THEN** `fenolite check` exits 0, `summary.canary` is `fired`, `summary.canary_removed` is at least 1, and no count includes a canary item

#### Scenario: Rules not loaded on a built project
- **GIVEN** the authored built project whose `<stem>.kicad_dru` is `tests/data/kicad/rules/broken.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there)
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k rules` runs on both majors
- **THEN** `check` exits 5 and its only error issue is `kicad.drc.rules-not-loaded`

#### Scenario: Rules not loaded on a native project
- **GIVEN** the native `two_layer` project with the same rules file
- **WHEN** `fenolite check <project> --json` runs
- **THEN** `kicad.drc.rules-not-loaded` has severity `info`, the stage level is `UNVERIFIED`, and the exit code is 0

#### Scenario: Rules file without a project file
- **GIVEN** a folder holding a board and `<stem>.kicad_dru` but no `<stem>.kicad_pro`
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the issues hold `kicad.drc.rules-not-loaded` and `summary.canary` is `not-applicable`

#### Scenario: Verdicts named by the oracle
- **GIVEN** a fake `Oracle` named `fake` that returns canary `inconclusive` with reason `selector-unproven`
- **WHEN** `uv run pytest tests/unit/checks -k drc_stage` runs the stage on built input
- **THEN** it reports one `fake.drc.rules-unchecked` warning naming `selector-unproven`, and the stage level is `UNVERIFIED`

#### Scenario: Skipped copy does not lower evidence
- **GIVEN** a fake `Oracle` whose canary `fired`, and a project set with one `SkippedFile("../Other.pretty", "outside-root")`
- **WHEN** the stage runs
- **THEN** it reports one `check.copy-skipped` info naming `../Other.pretty`, and the stage keeps the oracle's `KICAD-VERIFIED`

#### Scenario: Built blink is clean
- **GIVEN** c0011's `examples/blink_2layer` built into `tmp_path` for the running major with `fenolite build … --confirm`
- **WHEN** `uv run pytest tests/kicad/check/test_check_built.py` runs `fenolite check <dir> --json` on both majors
- **THEN** it exits 0 with four stages, `erc.lite` run, `summary.canary` `fired`, `summary.violations_judged` `false` and `roundtrip` `ok`

### Requirement: Round-trip stage
`checks.roundtrip.roundtrip_stage(validation) -> StageResult` SHALL report RT1 of the board for native and built input alike, because the board is the layout authority (`design-model`, "Layout authority").
- It MUST report the reader's issues (`kicad.board.*`, `kicad.version.*`) of `Validation.read.issues`, and MUST leave out their `model.*` findings.
- When `Validation.roundtrip.passed` is false, it MUST report one `check.rt1-failed` error whose `where` is `RoundTrip.difference`.
- `summary` MUST hold `level`, `tree_equal`, `model_equal`, `opaque_equal` and `opaque_count`.
- The stage MUST NOT compare the board with `.fenolite/` (c0019).

#### Scenario: Native board passes
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages roundtrip --json` runs
- **THEN** `roundtrip` has status `ok` and `summary.opaque_count` equals `pcb.opaque_count(read_board(text))`

#### Scenario: Failed round trip
- **GIVEN** a fake `Validator` whose `RoundTrip` has `passed=False` and `difference="/kicad_pcb/footprint[0]/pad[1]"`
- **WHEN** `uv run pytest tests/unit/checks -k roundtrip_stage` runs the stage
- **THEN** it reports one `check.rt1-failed` error with that `where`, and status `errors`

#### Scenario: Demo boards round-trip
- **GIVEN** the `rt0` corpus and kicad-cli 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_check_demos.py` runs
- **THEN** each of the 21 readable non-heavy demo boards has `roundtrip` `ok` with `summary.opaque_count == pcb.opaque_count(read_board(text))`

### Requirement: Inputs Fenolite cannot read
When the board read raises `FormatError` (`FEN-3004`), or its subclass `UnsupportedFormatError` (`FEN-3003`, a board older than the read floor), `check` SHALL report one `check.read-refused` error and SHALL still run `drc.kicad` when it is selected (`H-K-SEXPR-STRICT`). A newer board is read with `kicad.version.future` (`kicad-file-backend`, "Board version policy"), so `FEN-3002` never reaches this path.
- The message MUST start with the FEN code. `where` MUST be the error's own location, `file:locator:@offset` with empty parts left out, as `FormatError` joins it, and `file` relative to the project root.
- Stages that need the board model MUST be skipped with reason `read-refused`: `roundtrip` always, and `model.validate` on native input. On built input, `model.validate` and `erc.lite` MUST use the `.fenolite/` model and run.
- When the canary applies (`kicad-oracle`, "Check canary injection"), it MUST be `inconclusive` with reason `board-unparsed`.
- When no DRC report exists, because KiCad failed too or `drc.kicad` was not selected, `check` MUST exit 3 with the read error's FEN code on stderr. It MUST raise `cmd_check.ReadRefusedError`, a `FormatError` subclass, or its subclass `UnsupportedReadRefusedError` (`cli_code = "FEN-3003"`) when the read error is an `UnsupportedFormatError`. The raised error MUST keep the read error's message, `file`, `locator`, `offset` and `hint`, and MUST carry `issues = CheckReport.issues`, so that the dispatcher puts them in the envelope's `issues` (`cli-contract`, "Refusals carry their issues", c0011) and the envelope's `issues` still equal `CheckReport.issues`.
- The probe `check-unparsed-drc` MUST record whether KiCad writes a DRC report for `unmirrored/trailing-content.kicad_pcb` on each major.

#### Scenario: KiCad reads what Fenolite refuses
- **GIVEN** `tests/data/kicad/sexpr/unmirrored/trailing-content.kicad_pcb` (header rewritten to `20241229` on 9.0.9), and on 10.0.6 also `list-starting-with-list`, `cr-in-string` and `invalid-utf8` (outcomes per `EXPECT.toml`)
- **WHEN** `uv run pytest tests/kicad/check/test_read_refused.py` runs on 9.0.9 and on 10.0.6
- **THEN** each gives `check.read-refused` with `FEN-3004` and a `where` holding the file name and `@<offset>` (and the locator for `list-starting-with-list` and `cr-in-string`, the two that the reader locates), `model.validate` and `roundtrip` skipped with reason `read-refused`, a `drc.kicad` report, exit 5, and the probe `check-unparsed-drc` records `present`

#### Scenario: Both tools refuse
- **GIVEN** `tests/data/kicad/sexpr/unmirrored/empty-list.kicad_pcb`, which KiCad also rejects
- **WHEN** `fenolite check` runs on it with kicad-cli
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the envelope's `issues` hold `check.read-refused` followed by `check.oracle-failed`

#### Scenario: Unreadable board without DRC
- **GIVEN** a copy of `two_layer.kicad_pcb` with trailing content
- **WHEN** `fenolite check <copy> --stages model.validate,roundtrip --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, no subprocess runs, and the envelope on stdout has `ok` false and `issues` holding `check.read-refused`

### Requirement: Check issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL map every issue code that `checks` emits to its severities, and SHALL hold at least the codes of this table with these severities. Every code literal under `src/fenolite/checks/` MUST be a key of it; a later change adds its codes to the table through its own ADDED requirement. `docs/cli-contract.md` MUST document every key. `model.*` codes and reader codes MUST pass through unchanged and are not part of the table. No new FEN code is added.

| code | severity | when |
|---|---|---|
| `check.read-refused` | error | the board read raised a format error |
| `check.cache-unreadable` | warning | `.fenolite/` fails `load_dir` |
| `check.footprint-unresolved` | error | a non-DNP component has no footprint reference or instance |
| `check.symbol-unresolved` | error | a built component has no symbol reference |
| `check.rt1-failed` | error | RT1 failed; `where` is the first difference |
| `check.oracle-failed` | error | no DRC report, or a timeout (`retryable: true`) |
| `check.copy-skipped` | info | a named project file was left out of the copy |
| `<oracle>.drc.rules-not-loaded` | error (built), info (native) | rules file not loaded |
| `<oracle>.drc.rules-unchecked` | warning | canary inconclusive |
| `erc.lite.output-conflict` | warning | two driving outputs on one net |
| `erc.lite.power-undriven` | warning | power input without a driver or power interface |
| `erc.lite.floating-pin` | warning | a pin on no net |

#### Scenario: Closed set enforced
- **GIVEN** a module under `src/fenolite/checks/` that emits `check.unknown-code`, which is not a key of `ISSUE_CODES`
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** it fails naming `check.unknown-code`; without that module it passes, and every literal, with `<oracle>` for the oracle prefix, is a key with the severity of this table

#### Scenario: Codes documented
- **GIVEN** `ISSUE_CODES` and `docs/cli-contract.md`
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** every key of `ISSUE_CODES` appears in `docs/cli-contract.md`, with `kicad` for `<oracle>`

### Requirement: Check exit codes
`check` SHALL exit 2 for usage errors (`FEN-2001`), 3 for a missing path (`FEN-3001`) or an unreadable board without a DRC report, and 6 when the tool pre-flight below fails. Otherwise it SHALL exit 5 (`FEN-5001`) when any issue has severity `error`, and 0 when none has.
- When `drc.kicad` is selected, `check` MUST verify before any stage runs that `kicad-cli` exists (else exit 6 with `FEN-6001` and a hint naming `--stages model.validate,erc.lite,roundtrip` and `FENOLITE_KICAD_CLI`), that its major is in `TARGET_MAJORS`, and, when the board parses, that the header's format version is not above `FORMAT_VERSIONS[FileKind.BOARD][<tool major>]`, so a header of a newer major or with status `FUTURE` is refused (else exit 6 with `FEN-6002`). When the board does not parse, the header check MUST be skipped.
- Usage and path errors MUST be reported before this pre-flight.
- `check` MUST NOT skip DRC and exit 0 when `kicad-cli` is missing.

#### Scenario: No kicad-cli
- **GIVEN** no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k missing_tool` runs `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --json`
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names `--stages`

#### Scenario: Unsupported or older major
- **GIVEN** fakes passed with `--kicad-cli`: one whose `version` prints `8.0.7`; one that prints `9.0.9`, with a board whose header is `20260206`; and one that prints `10.0.6`, with a board whose header is `20990101` (status `FUTURE`)
- **WHEN** `fenolite check` runs with each
- **THEN** all three exit 6 with `FEN-6002`, and no stage runs

#### Scenario: Oracle timeout
- **GIVEN** a fake `kicad-cli`, passed with `--kicad-cli`, whose `pcb drc` sleeps longer than `--timeout 1`
- **WHEN** `fenolite check <project> --timeout 1 --json` runs
- **THEN** the issues hold `check.oracle-failed` with `retryable: true`, and the exit code is 5

### Requirement: Check output is deterministic
Two `fenolite check --json` runs on the same project with the same `kicad-cli` SHALL give byte-identical stdout apart from `elapsed_ms`.
- The output MUST NOT hold the DRC report's `date`, a temporary path, the home directory or an absolute path. Paths MUST be relative to the project root.
- Stages MUST follow `STAGE_ORDER`. Issues within a stage MUST be sorted by code, then `where`, then message.
- `project.files`, `project.skipped`, `tool_writes` and the keys of `by_type` and `by_severity` MUST be sorted.

#### Scenario: Two runs on both majors
- **GIVEN** the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k deterministic` runs `fenolite check --json` twice on 9.0.9 and on 10.0.6
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no `<tmp>`, home or absolute path

#### Scenario: Hermetic stages
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,erc.lite,roundtrip --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`

