# verification-loop Specification

## Purpose
Check a KiCad project without writing to it: `fenolite check` runs model validation, ERC lite, KiCad's DRC on a closed copy of the project with a rules canary, and the RT1 round trip, in a fixed order, each stage with its own status and evidence. `fenolite inspect` summarises a file's header and counts, and `fenolite doctor` reports the `kicad-cli` binaries and their command matrices. Contract: `docs/cli-contract.md`; facts: `docs/formats/kicad/cli.md` and `docs/formats/kicad/drc.md`.
## Requirements
### Requirement: Check command input
`fenolite check PATH` SHALL be registered by `src/fenolite/cli/cmd_check.py` with `mutates=False`, and SHALL check the KiCad project that `PATH` names, or the documents of another backend that `PATH` names (**Document input**), without writing any file. Every bullet below but **Document input** describes the KiCad path.
- **Board.** The board MUST be found with `fenolite.backends.kicad.projectset.resolve_board(PATH)` (`kicad-oracle`, "Check project copy set"). An ambiguous folder MUST exit 2 with `FEN-2001` and a hint listing the candidates. A missing path or board MUST exit 3 with `FEN-3001`.
- **Document input.** Before the board is looked for, the command MUST take `PATH` as document input when it is a file for which `registry.for_path(PATH)` gives a backend that satisfies `DocumentValidator` (`backend-protocol`, "Document sets and container round trips"), or a folder that holds exactly one file such a backend detects as a project file (its `documents(folder)` gives a set) and no `.kicad_pro` and no `.kicad_pcb` file. A folder that holds a KiCad project or board and files of such a backend without exactly one project file stays KiCad input. A folder that holds both a KiCad project or board and such a project file MUST exit 2 with `FEN-2001` and a hint that names both. Document input MUST be checked by `fenolite.checks.documents.run_document_checks` ("Document check pipeline"), `--stages` MUST then select a subset of `DOCUMENT_STAGES`, no oracle MUST be built and no subprocess MUST run, and `--kicad-cli` and `--timeout` MUST be accepted and ignored. Its result and exit codes are those of `altium-verification`, "Check on Altium inputs".
- **Flags.** `--stages a,b` MUST select a subset of `STAGE_ORDER`; an unknown or empty stage name MUST exit 2 with `FEN-2001`. `--kicad-cli PATH` MUST be passed to `find_kicad_cli` as the explicit path. `--timeout SECONDS` MUST default to 300 and MUST be passed to `KicadCli`.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the board's folder, and native otherwise. Built input MUST load its model with `model.canonical.load_dir(<root>/.fenolite)`. The board's `generator` atom MUST NOT decide it.
- **Injection.** The command MUST narrow `registry.for_path(board)` with `isinstance(backend, Validator)` (`Validator` is `@runtime_checkable`), exit 2 with `FEN-2001` when no backend validates the board, and pass the narrowed backend as the `Validator` and `KicadOracle(KicadCli(path, timeout=…))` as the `Oracle` to `fenolite.checks.stages.run_checks`. It MUST build the oracle only when a stage of `ORACLE_STAGES` is selected ("Stages added for findings and round trips").
- **Result.** `result.project` MUST hold `board`, `built`, `files` and `skipped`, with names relative to `<root>`. `result.stages` MUST hold one object per selected stage. `input.path` MUST be the board name relative to `<root>`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--stages", "model.validate,roundtrip")`, which runs no subprocess. `fenolite.cli._examples.EXAMPLE_BOARD` MUST be the absolute path of `tests/data/kicad/board/two_layer.kicad_pcb`, resolved at import from `Path(fenolite.__file__).resolve().parents[2]`, so that the consistency suite passes from any working directory of a source checkout.

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
- **WHEN** `fenolite check <project> --stages model.validate,roundtrip --json` runs
- **THEN** `result.project.built` is `true` and the `model.validate` stage has status `ok`

#### Scenario: Example arguments are hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `check` with its `example_args`
- **THEN** the exit code is 0, and `input.path` is `two_layer.kicad_pcb`

#### Scenario: Consistency suite from another folder
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory, as in c0011's scenario "Consistency suite"
- **THEN** it passes for `check`, `inspect` and `doctor`

#### Scenario: Altium project folder dispatched
- **GIVEN** a copy of `tests/data/altium/blink/` in `tmp_path`, with `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_check_altium.py -k dispatch` runs `fenolite check <folder> --json`
- **THEN** `result.project.project` is `blink.PrjPcb`, `result.stages` names only stages of `DOCUMENT_STAGES`, and no subprocess ran

#### Scenario: Folder with two backends
- **GIVEN** a folder that holds `a.kicad_pcb` and `b.PrjPcb`
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names `a.kicad_pcb` and `b.PrjPcb`

#### Scenario: KiCad stage name on document input
- **WHEN** `fenolite check tests/data/altium/blink/blink.PrjPcb --stages drc.kicad` runs
- **THEN** the exit code is 2 with `FEN-2001`, and the hint lists `DOCUMENT_STAGES`

### Requirement: Check stages and statuses
`fenolite.checks.stages` SHALL define `STAGE_ORDER` and `run_checks(*, project, stages, model, built, validator, oracle, cache_error="") -> CheckReport`, where a non-empty `cache_error` says that `.fenolite/` failed `load_dir`. `STAGE_ORDER` MUST hold `model.validate`, `erc.kicad`, `drc.kicad` and `roundtrip` in this relative order, and a later change MAY insert a stage through its own ADDED requirement. `run_checks` MUST run the selected stages in `STAGE_ORDER`, whatever order `--stages` gives, and MUST leave unselected stages out of `CheckReport.stages`.
- Each stage MUST return a frozen `StageResult(name, status, evidence, issues, summary, reason)`. `StageResult.to_json()` MUST return `{name, status, reason, evidence, summary}`, with `evidence` as `{level, oracle, hypotheses}`.
- `status` MUST be `ok` when the stage ran and gave no issue of severity `error`, `errors` when it gave at least one, and `skipped` when it did not run. A skipped stage MUST give no issue and a `reason`. `model.validate`, `drc.kicad` and `roundtrip` MUST use only `native-input`, `read-refused` and `cache-unreadable`; `erc.kicad` uses `no-schematic` and `unsupported-oracle` ("ERC stage"), and a stage added later defines its own reasons.
- `CheckReport.issues`, which the envelope's `issues` MUST equal, MUST be the input issues (`check.read-refused`, `check.cache-unreadable`) followed by the issues of each stage in stage order.
- `run_checks` MUST call `validator.validate` at most once per run.
- The functions of the four stages MUST be `checks.validate.validate_stage`, `checks.erc.erc_stage`, `checks.drc.drc_stage` and `checks.roundtrip.roundtrip_stage`. `STAGE_ORDER` MUST NOT hold `erc.lite`, and `--stages erc.lite` MUST be an unknown stage ("Check command input").
- `checks` MUST import only `core`, `model`, `geometry` and `backends.base` (`package-layering`), and MUST reach KiCad only through the injected `Validator` and `Oracle`.

#### Scenario: Fixed order
- **GIVEN** a fake `Validator` and a fake `Oracle`
- **WHEN** `run_checks` is called with `stages=("roundtrip", "model.validate")`
- **THEN** `CheckReport.stages` names `model.validate` then `roundtrip`, and holds no `erc.kicad` or `drc.kicad` entry

#### Scenario: Skipped by design
- **GIVEN** a fake `kicad-cli` passed with `--kicad-cli`
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,erc.kicad,roundtrip --json` runs
- **THEN** `erc.kicad` has status `skipped`, reason `no-schematic` and no issue, and the other two stages have status `ok`

#### Scenario: Checks stay backend-free
- **GIVEN** a module under `src/fenolite/checks/` that imports `fenolite.backends.kicad`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `checks → backends.kicad`

#### Scenario: The old stage name is refused
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages erc.lite` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Evidence per check stage
Each `StageResult` SHALL carry the evidence of its own stage, and a skipped stage SHALL carry `UNVERIFIED`. The envelope evidence SHALL be `Evidence.combine` of the stages with status `ok` or `errors` and of the stages skipped with reason `read-refused` or `cache-unreadable`, because their input failed. A stage skipped with reason `native-input`, `no-schematic` or `unsupported-oracle` MUST NOT count, and the envelope MUST be `UNVERIFIED` when nothing counts.

| stage | evidence |
|---|---|
| `model.validate`, native | `Validation.read.evidence` (`pcb.EVIDENCE`: `INFERRED`, `H-K-PCB-READ`) |
| `model.validate`, built | `INFERRED` (Fenolite's structural rules) |
| `erc.kicad` | `ErcOutcome.evidence` (for KiCad, `Evidence.combine(erc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`; `KICAD-VERIFIED` only once `H-K-ERC-JSON`, `H-K-ERC-POS` and `H-K-ERC-COPYSET` are) when a report exists; `UNVERIFIED` otherwise |
| `drc.kicad` | `DrcOutcome.evidence` (for KiCad, `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`; `KICAD-VERIFIED` only once `H-K-DRC-JSON`, `H-K-CHECK-COPYSET` and `H-K-CHECK-CANARY`, or its `-2` successor, are) when a report exists and the stage gave neither `<oracle>.drc.rules-not-loaded` nor `<oracle>.drc.rules-unchecked`; `UNVERIFIED` otherwise |
| `roundtrip` | `Validation.read.evidence` |

#### Scenario: Lowest level of the stages that ran
- **GIVEN** fakes for which `drc.kicad` gives `KICAD-VERIFIED`, `roundtrip` gives `INFERRED` and `erc.kicad` is skipped with reason `no-schematic`
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
- A `.fenolite/` folder that `load_dir` cannot load MUST give one `check.cache-unreadable` warning, and `model.validate` MUST be skipped with reason `cache-unreadable`. The other stages MUST still run.

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
- **WHEN** `fenolite check B --stages model.validate,roundtrip --json` runs
- **THEN** the exit code is 0, no issue has severity `error`, and no `check.symbol-unresolved` is reported

#### Scenario: Unreadable cache
- **GIVEN** the authored built project whose `.fenolite/board.json` holds `{`
- **WHEN** `fenolite check <project> --stages model.validate,roundtrip --json` runs
- **THEN** the issues hold one `check.cache-unreadable` warning, `model.validate` is skipped with reason `cache-unreadable`, and `roundtrip` has status `ok`

### Requirement: ERC lite stage
`checks.erc_lite` SHALL define `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`, `erc_lite(design) -> tuple[Issue, ...]`, `erc_stage(design) -> StageResult` and `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`). The three rules are a function for pipelines of inputs that have no ERC oracle; the KiCad pipeline does not run them: `STAGE_ORDER` holds `erc.kicad` instead ("ERC stage"), and `run_checks` MUST NOT call `erc_stage`. `run_document_checks` runs them on the built model, or on the reading of the schematic documents ("Document check pipeline").
- `erc.lite.output-conflict`: a net with two or more member pins whose `etype` is `output` or `power_out`.
- `erc.lite.power-undriven`: a net with a `power_in` member pin and no `power_out` member pin, whose id is not a value of the `members` of any `Interface` with `kind == "power"` (c0011's `Power(hv, lv)`, which acts as a power flag).
- `erc.lite.floating-pin`: a pin whose `etype` is not `no_connect`, that no net lists and that `Circuit.no_connects` does not list (`design-model`, "No-connect marks in the circuit model"), reported once per pin. A mark is matched by `PinRef(<component id>, <pin number>)`, the form the builds store.
- The three rules MUST NOT report a marked pin that a net also lists: that is `model.no-connect-on-net`, a finding of `Design.validate()` and of the `model.validate` stage.
- Pins of components with `dnp == True` MUST be ignored by the three rules.
- Every finding MUST have severity `warning`.
- `REMOVE_IN` and `check_removal` MUST NOT exist: the removal they announced is done for KiCad input, and the rules stay for the other inputs.

#### Scenario: One case per rule
- **GIVEN** one authored model per rule and a clean control model
- **WHEN** `uv run pytest tests/unit/checks -k erc_lite` runs
- **THEN** each rule model gives exactly its own warning, and the control gives none

#### Scenario: Power interface drives a net
- **GIVEN** a model whose net `VCC` has one `power_in` pin and no `power_out` pin, and an `Interface(kind="power")` whose `members` name the id of `VCC`
- **WHEN** `erc_lite` runs
- **THEN** it reports no `erc.lite.power-undriven`

#### Scenario: Marked pin is not floating
- **GIVEN** a model whose component `U1` has the `input` pins `11`, `12` and `13` on no net, and whose `Circuit.no_connects` holds `PinRef(<U1 id>, "11")` and `PinRef(<U1 id>, "12")`
- **WHEN** `uv run pytest tests/unit/checks -k "erc_lite and no_connect"` runs `erc_lite`
- **THEN** it reports exactly one `erc.lite.floating-pin`, whose `where` is `U1-13`

#### Scenario: Not part of the KiCad pipeline
- **GIVEN** a fake `Validator` and a fake `Oracle`
- **WHEN** `uv run pytest tests/unit/checks/test_stages.py -k no_lite` runs `run_checks` with the default stages on built input
- **THEN** no stage is named `erc.lite`, no issue code starts with `erc.lite.`, and `checks.erc_lite` has no attribute `REMOVE_IN`

#### Scenario: Rules run on a schematic reading
- **GIVEN** a fake `DocumentValidator` whose schematic reading holds a component `U1` with the `input` pins `1` and `2`, pin `1` on a net with a `power_out` pin and pin `2` on no net
- **WHEN** `uv run pytest tests/unit/checks/test_documents.py -k erc_native` calls `run_document_checks` with `stages=("erc.lite",)` and `built=False`
- **THEN** `erc.lite` has status `ok` and exactly one `erc.lite.floating-pin` warning, whose `where` is `U1-2`

### Requirement: DRC stage and the rules canary
`checks.drc.drc_stage(oracle, project, *, built, design=None) -> StageResult` SHALL run DRC once through `oracle.drc(project)` and SHALL turn the rules verdict into issues. DRC violations MUST always be counted in `summary`. `summary.violations_judged` MUST be `true` exactly when the run also maps DRC violations to issues. Whenever a report exists, the stage MUST map them with `checks.drc_json.finding_issues(report, oracle=oracle.name, design=design)` ("DRC findings as issues"), where `design` is the board model that `run_checks` read, or `None` when that read was refused; without a report it maps none, and `violations_judged` is `false`.
- **Rules verdict.** Codes MUST start with `f"{oracle.name}.drc."`:
  - canary `absent`, or a `<stem>.kicad_dru` in the copy set without a `<stem>.kicad_pro`: `rules-not-loaded`, severity `error` on built input and `info` on native input;
  - canary `inconclusive`: `rules-unchecked` (warning), with `canary_reason` in the message, except for reason `no-report`, which gives only `check.oracle-failed`;
  - canary `fired`, or `not-applicable` without a rules file: no issue.
- **Summary.** `summary` MUST hold `tool_version`, `canary`, `canary_reason`, `canary_removed`, `violations` (total), `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`, `violations_judged`, `parity`, `parity_judged` ("Parity findings") and `types` (each emitted `<oracle>.drc.<type>` code mapped to the tool's raw type), counted on the report from which every canary violation was removed.
- **Copy skips.** Each `SkippedFile` of the project MUST give one `check.copy-skipped` info naming the file and its reason. It MUST NOT lower the stage evidence.
- **No report.** When KiCad wrote no report or timed out, the stage MUST report `check.oracle-failed` (error) with `DrcOutcome.message`, and `retryable: true` on a timeout.

#### Scenario: Built project with a firing canary
- **GIVEN** the authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k canary` runs on 9.0.9 and on 10.0.6
- **THEN** `summary.canary` is `fired`, `summary.canary_removed` is 0 on a major of `CANARY_TWO_RUN` (the counted report comes from the plain run) and at least 1 otherwise, `summary.violations_judged` is `true`, and no count and no issue includes a canary item

#### Scenario: Rules not loaded on a built project
- **GIVEN** the authored built project whose `<stem>.kicad_dru` is `tests/data/kicad/rules/broken.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there)
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k rules` runs on both majors
- **THEN** `check` exits 5, `kicad.drc.rules-not-loaded` is an error issue, and every other error issue is a `kicad.drc.<type>` finding

#### Scenario: Rules not loaded on a native project
- **GIVEN** the native `two_layer` project with the same rules file
- **WHEN** `fenolite check <project> --json` runs
- **THEN** `kicad.drc.rules-not-loaded` has severity `info`, the stage level is `UNVERIFIED`, and the exit code is 5 only when another issue has severity `error`

#### Scenario: Rules file without a project file
- **GIVEN** a folder holding a board and `<stem>.kicad_dru` but no `<stem>.kicad_pro`
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the issues hold `kicad.drc.rules-not-loaded` and `summary.canary` is `not-applicable`

#### Scenario: Verdicts named by the oracle
- **GIVEN** a fake `Oracle` named `fake` that returns an empty report and canary `inconclusive` with reason `selector-unproven`
- **WHEN** `uv run pytest tests/unit/checks -k drc_stage` runs the stage on built input
- **THEN** it reports one `fake.drc.rules-unchecked` warning naming `selector-unproven`, and the stage level is `UNVERIFIED`

#### Scenario: Skipped copy does not lower evidence
- **GIVEN** a fake `Oracle` that returns an empty report and canary `fired`, and a project set with one `SkippedFile("../Other.pretty", "outside-root")`
- **WHEN** the stage runs
- **THEN** it reports one `check.copy-skipped` info naming `../Other.pretty`, and the stage keeps the oracle's `KICAD-VERIFIED`

#### Scenario: Findings mapped by the stage
- **GIVEN** a fake `Oracle` named `fake` whose report holds one `shorting_items` violation of severity `error` naming the uuid of pad 2 of `R1` of the design passed to the stage, and canary `fired`
- **WHEN** `uv run pytest tests/unit/checks -k drc_stage` runs the stage on native input
- **THEN** it reports one `fake.drc.shorting-items` error whose `where` is `R1-2`, `summary.types` maps that code to `shorting_items`, `summary.violations_judged` is `true`, and the status is `errors`

#### Scenario: No report, nothing judged
- **GIVEN** a fake `Oracle` that returns no report
- **WHEN** the stage runs
- **THEN** it reports `check.oracle-failed`, and `summary.violations_judged` is `false`

#### Scenario: Built blink before routing
- **GIVEN** c0011's `examples/blink_2layer` built into `tmp_path` for the running major with `fenolite build … --confirm`
- **WHEN** `uv run pytest tests/kicad/check/test_check_built.py` runs `fenolite check <dir> --json` on both majors
- **THEN** the stages are `model.validate`, `erc.kicad`, `drc.kicad`, `netlist.assignment_compare` and `roundtrip` in this order, `erc.kicad` runs, `summary.canary` is `fired`, `summary.violations_judged` is `true`, `roundtrip` is `ok`, and every `kicad.drc.unconnected-items` issue names `REF-PIN` pads in its `where`

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
- Stages that need the board model MUST be skipped with reason `read-refused`: `roundtrip` always, and `model.validate` on native input. On built input, `model.validate` MUST use the `.fenolite/` model and run. `erc.kicad` needs no board model and runs on either input.
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
- When `drc.kicad` is selected, `check` MUST verify before any stage runs that `kicad-cli` exists (else exit 6 with `FEN-6001` and a hint naming `--stages model.validate,roundtrip` and `FENOLITE_KICAD_CLI`), that its major is in `TARGET_MAJORS`, and, when the board parses, that the header's format version is not above `FORMAT_VERSIONS[FileKind.BOARD][<tool major>]`, so a header of a newer major or with status `FUTURE` is refused (else exit 6 with `FEN-6002`). When the board does not parse, the header check MUST be skipped.
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
Two `fenolite check --json` runs on the same project with the same `kicad-cli` SHALL give byte-identical stdout apart from `elapsed_ms` whenever the tool repeats its own reports, and Fenolite SHALL add no difference of its own.
- The output MUST NOT hold the DRC report's `date`, a temporary path, the home directory or an absolute path. Paths MUST be relative to the project root.
- Stages MUST follow `STAGE_ORDER`. Issues within a stage MUST be sorted by code, then `where`, then message.
- `project.files`, `project.skipped`, `tool_writes` and the keys of `by_type` and `by_severity` MUST be sorted.
- **What the tool does not repeat.** `kicad-cli` 10.0.6 writes its DRC report in another order from run to run, which the sorting above removes, and on boards with hundreds of violations it does not repeat the entries of the types `clearance`, `hole_clearance` and `unconnected_items` (`H-K-DRC-REPEAT`, `H-K-RT2-STABLE-2`). On such a board two runs MAY differ in the `drc.kicad` issues `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items`, in the `drc.kicad` summary values counted from them (`violations`, `unconnected`, `by_type`, `by_severity`, `types`), in the status of `drc.kicad` and in the exit code when those issues decide them. On a board with 499 or more `clearance` violations the canary state MAY also differ, between `fired` and `inconclusive` with reason `clearance-limit` (`H-K-DRC-LIMIT`; `kicad-oracle`, "Check canary injection"), and with it the issue `kicad.drc.rules-unchecked` and the evidence of `drc.kicad`. Nothing else MAY differ: the other stages, `tool_writes` and every issue of another code MUST be equal, and so MUST the canary state on a board below that count.
- `docs/cli-contract.md` MUST state under `check` which part of the output repeats and MUST name the three codes.

#### Scenario: Two runs on both majors
- **GIVEN** the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k deterministic` runs `fenolite check --json` twice on 9.0.9 and on 10.0.6
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no `<tmp>`, home or absolute path

#### Scenario: Hermetic stages
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,roundtrip --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`

#### Scenario: A board whose DRC report the tool does not repeat
- **GIVEN** `kicad-demo-10-0-6-pcb-07` with a `{}` project and a `(version 1)` rules file, on 10.0.6
- **WHEN** `uv run pytest "tests/kicad/check/test_canary.py::test_two_run_demo_boards[kicad-demo-10-0-6-pcb-07]"` runs the oracle of `drc.kicad` twice
- **THEN** the two outcomes agree in the canary state (the board holds fewer than 499 `clearance` violations), the return code, `tool_writes` and every entry of a type other than `clearance`, `hole_clearance` and `unconnected_items`

#### Scenario: The contract names what does not repeat
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k contract` reads `docs/cli-contract.md`
- **THEN** its `check` section names `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items` as the issues that can differ between two runs, and the reason `clearance-limit`

### Requirement: Stages added for findings and round trips
`fenolite.checks.stages.STAGE_ORDER` SHALL be `("model.validate", "erc.kicad", "copper.clearance", "drc.kicad", "netlist.assignment_compare", "roundtrip", "roundtrip.rt2")`: c0020 inserts `netlist.assignment_compare` before `roundtrip` and `roundtrip.rt2` after it, and c0029 inserts `copper.clearance` between the ERC stage and `drc.kicad`, as "Check stages and statuses" allows.
- `OPT_IN_STAGES` MUST be `("roundtrip.rt2",)` and `DEFAULT_STAGES` MUST be `STAGE_ORDER` without them. `fenolite check` without `--stages` MUST run `DEFAULT_STAGES`, and `--stages` MUST accept every name of `STAGE_ORDER`.
- `ORACLE_STAGES` MUST be `("erc.kicad", "drc.kicad", "netlist.assignment_compare", "roundtrip.rt2")`. When any of them is selected, `cmd_check` MUST run the `kicad-cli` pre-flight of "Check exit codes" and MUST pass `KicadOracle(KicadCli(path, timeout=…))` as the oracle. `copper.clearance` MUST NOT be in `ORACLE_STAGES`: it runs no tool.
- `run_checks` MUST pass the `Validation` of its single `validator.validate` call, or `None` when that read was refused, to `assignment_stage`, and its board model (`Validation.read.design`), or `None`, to `drc_stage`. It MUST pass that board model with `Validation.read.evidence` and the project set to `copper_stage`, with the validator as `rules_source` when `isinstance(validator, DesignRulesSource)` is true and as `frame` when `isinstance(validator, BoardFrame)` is true, and `None` for each otherwise. It MUST still call `validator.validate` at most once per run.
- The functions of the two stages that c0020 adds MUST be `checks.assignment_compare.assignment_stage` and `checks.rt2.rt2_stage`. Each MUST be skipped with reason `read-refused` when the board read was refused, and with reason `unsupported-oracle` when `isinstance(oracle, NetlistOracle)`, respectively `isinstance(oracle, RoundTripOracle)`, is false (`backend-protocol`, "Netlist and round-trip oracles"). A stage skipped with `unsupported-oracle` MUST NOT count in the envelope evidence.
- The function of `copper.clearance` MUST be `checks.copper.copper_stage` ("Copper clearance stage").
- The stages that c0020 and c0029 add MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: Default stages leave RT2 out
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6 that writes a DRC report and an IPC-D-356 export, passed with `--kicad-cli`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `model.validate`, `erc.kicad`, `copper.clearance`, `drc.kicad`, `netlist.assignment_compare` and `roundtrip` in this order, and no `roundtrip.rt2`

#### Scenario: RT2 selected
- **GIVEN** the same project and fake
- **WHEN** `fenolite check <project> --stages roundtrip.rt2,roundtrip --json` runs
- **THEN** `result.stages` names `roundtrip` then `roundtrip.rt2`

#### Scenario: New stages need kicad-cli
- **GIVEN** no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages netlist.assignment_compare --json` and the same command with `--stages roundtrip.rt2` run
- **THEN** both exit 6 with `FEN-6001`, and no stage runs

#### Scenario: Copper stage needs no kicad-cli
- **GIVEN** the same environment without `kicad-cli`, and `two_layer.kicad_pcb`, whose authored `GND_B` fill on `B.Cu` covers pad `2` of `D1` (net `LED_A`)
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages copper.clearance --json` runs
- **THEN** the stage runs, no `FEN-6001` is given, the exit code is 5, `copper.clearance` has status `errors`, and its issues hold exactly one `copper.short`, whose `where` contains `D1-2` and whose message names `GND`, `LED_A` and `B.Cu`

#### Scenario: Refused read skips the new stages
- **GIVEN** a fake `Validator` that raises `FormatError` and a fake oracle that satisfies `NetlistOracle` and `RoundTripOracle`
- **WHEN** `uv run pytest tests/unit/checks -k new_stages` calls `run_checks` with `stages=("netlist.assignment_compare", "roundtrip.rt2")` on native input
- **THEN** both stages are skipped with reason `read-refused` and give no issue

#### Scenario: Oracle without the operation
- **GIVEN** a fake `Oracle` that implements only `drc`
- **WHEN** `run_checks` runs `netlist.assignment_compare` with it
- **THEN** the stage is skipped with reason `unsupported-oracle`, and the envelope evidence does not count it

#### Scenario: New stages stay read-only
- **GIVEN** a fake `kicad-cli` that writes `x.kicad_prl` next to its input and rewrites its input board
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k new_stages` runs `fenolite check <project> --stages copper.clearance,netlist.assignment_compare,roundtrip.rt2`
- **THEN** the project snapshot is equal before and after, and no `.fenolite/`, `native/` or `.kicad_prl` entry was created

### Requirement: DRC findings as issues
`fenolite.checks.drc_json.finding_issues(report, *, oracle, design) -> tuple[Issue, ...]` SHALL map every violation, every unconnected item and every `schematic_parity` entry of a DRC report, after the canary was stripped, to exactly one issue ("Parity findings").
- **Code.** `type_code(oracle, type)` MUST return `f"{oracle}.drc.{suffix}"`. The suffix is the type in lower case, with `_` and every other character outside `[a-z0-9-]` replaced by `-`, runs of `-` collapsed, leading and trailing `-` removed, and `unknown` when nothing remains. A suffix in `RESERVED_SUFFIXES = ("rules-not-loaded", "rules-unchecked", "parity-unchecked")` MUST become `type-<suffix>`, so a KiCad type never takes a verdict code. The suffix rule itself MUST live in `checks.codes.type_suffix`, shared with the ERC codes ("ERC findings as issues"). The raw type MUST be kept in `summary.types`.
- **Severity.** `issue_severity(violation)` MUST give `info` when `excluded` is true, otherwise `error` for `error`, `warning` for `warning`, and `error` for any other value.
- **Where.** The locations of the items, in report order, joined with `, `. `item_locations(design, oracle)` MUST map each uuid that names exactly one entity of the design's board through `native_ids[oracle]`: a numbered pad gives `REF-PIN` (its component's reference, `-`, the pad number), a pad without a number and a footprint give `REF`, and any other entity gives its `provenance.locator`. A uuid that names no entity or several, and every item when `design` is `None`, MUST give `@<x>,<y>`: the item's report position in millimetres, written as an exact decimal without trailing zeros.
- **Message.** The message MUST be `<type>: <description>`, with the parent folder of `report.source` replaced by `<tmp>` and the home directory by `~`, so the check output holds no temporary or absolute path.
- `finding_issues` MUST NOT emit a code literal; every code it emits matches the `ISSUE_CODES` key `<oracle>.drc.<type>` ("Findings stage issue codes").

#### Scenario: Codes without underscores
- **WHEN** `type_code` is called with `("kicad", "shorting_items")`, `("kicad", "lib_footprint_mismatch")`, `("kicad", "rules_not_loaded")` and `("kicad", "")`
- **THEN** it returns `kicad.drc.shorting-items`, `kicad.drc.lib-footprint-mismatch`, `kicad.drc.type-rules-not-loaded` and `kicad.drc.unknown`, each matching `ISSUE_CODE`

#### Scenario: Pad located as REF-PIN
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`, and a `DrcReport` whose one `clearance` violation of severity `error` names the uuid of one of the board's tracks and then the uuid of pad 2 of `R1`
- **WHEN** `uv run pytest tests/unit/checks/test_drc_json.py -k ref_pin` calls `finding_issues(report, oracle="kicad", design=design)`
- **THEN** it returns one `kicad.drc.clearance` error whose `where` is that track's `provenance.locator`, then `, `, then `R1-2`

#### Scenario: Unknown item
- **GIVEN** a violation whose only item uuid names no entity of the design, at x 12.5 mm and y 3.25 mm
- **WHEN** it is mapped
- **THEN** the issue's `where` is `@12.5,3.25`

#### Scenario: Excluded and unknown severities
- **GIVEN** one violation with `excluded` true and severity `error`, and one with severity `fatal`
- **WHEN** they are mapped
- **THEN** the first gives severity `info` and the second severity `error`

#### Scenario: Paths removed from messages
- **GIVEN** a report whose `source` is `/tmp/fenolite-kicad-x/b.kicad_pcb` and whose violation description holds `/tmp/fenolite-kicad-x/lib` and the home directory
- **WHEN** it is mapped
- **THEN** the message holds `<tmp>/lib` and `~`, and no absolute path

#### Scenario: Parity entry mapped
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`, and a `DrcReport` whose `schematic_parity` holds one `net_conflict` entry of severity `warning` naming the uuid of pad 2 of `R1`
- **WHEN** `uv run pytest tests/unit/checks/test_drc_json.py -k parity` calls `finding_issues(report, oracle="kicad", design=design)`
- **THEN** it returns one `kicad.drc.net-conflict` warning whose `where` is `R1-2`

### Requirement: Assignment compare stage
`fenolite.checks.assignment_compare.assignment_stage(oracle, project, *, validation, model, built, min_pins=1) -> StageResult` SHALL compare the net-to-pad assignments of the model, of the re-read board, of the tool's netlist export and of the schematic's netlist as partitions of `REF-PIN` elements, never by net name.
- **Sources.** `board_netlist(design)` (source `board`), with `design = validation.read.design`, MUST give, for each numbered pad of each footprint, `PadAssignment(f"{ref}-{number}", label)`, where the label is the pad's `net_id`, or `NO_NET` (`""`) for a pad on no net; pads with an empty number MUST be counted in `summary.unnumbered` and not compared. `model_netlist(model)` (source `model`, built input only) MUST give each `PinRef` member of a net with the net's id as label, and each other pin of a component with `NO_NET`; an element names the pad of its pin, that is the pin number or the pad that the component's `pin_pad_map` gives it, because the board and the export speak in pad numbers. The export is the `PadNetList` of `oracle.netlist(project, board=design)` (source `export`); a pad that the IPC-D-356 export labels `N/C` MUST get the label `NO_NET`, unless a net of the board is named so. The schematic's netlist is the `PadNetList` of `oracle.schematic_netlist(project)` (source `schematic`), taken when the project has a schematic, that is `<board stem>.kicad_sch` is one of `project.files` (the copy set holds it whenever it lies beside the board, change c0062), and `isinstance(oracle, SchematicNetlistOracle)` is true (`backend-protocol`, "Schematic netlist oracle"). When the `.fenolite/` model could not be loaded, built input compares only (`board`, `export`).
- **Pairs.** The stage MUST compare (`model`, `board`) on built input and (`board`, `export`) on every input. With a schematic netlist, it MUST also compare (`model`, `schematic`) on built input with a loaded model, and (`schematic`, `board`) otherwise, so the model is the hub of built input and the board the hub of native input, and one wrong pad or pin is reported once. When the project has a schematic and its netlist cannot be exported, the stage MUST report `check.oracle-failed` (error, `retryable: true` on a timeout) and MUST still compare the other pairs.
- **Partitions.** `compare(a, b, *, min_pins=1) -> PairResult` MUST use the elements that both sides cover. Two of them are together on a side when they share a label there that is not `NO_NET`. An element whose label is `NO_NET` is a block of its own: two pads on no net are not connected to each other, so a side that names the net of an unconnected pin, as KiCad does with its `unconnected-(…)` nets, equals a side that leaves that pin on no net. An element with two labels on one side MUST always be a difference; apart from such elements, `compare` MUST give no difference exactly when the two relations are equal.
- **min_pins.** Blocks of fewer than `min_pins` elements MUST be left out of their side, and their elements counted as uncovered with reason `below-min-pins`. The default 1 keeps single-pin nets.
- **Location.** Each difference MUST name one element. For each block of either side, when one block of the other side holds more of its elements than every other block does, each of its elements outside that block MUST be flagged. When the relations differ and nothing is flagged, every element of a block that has no equal block on the other side MUST be flagged.
- **Issues.** One `netlist.assignment-differs` error per flagged element and pair, with the element as `where` and a message naming both sources and both nets (net names for `model` and `board`, the exported label for `export` and `schematic`). One `netlist.uncovered` info per pair, side and reason, with the count and the first five elements in sorted order. A reason is the source's own `Uncovered` reason, or `below-min-pins`, or `not-in-<source>` for an element that the other source does not name at all. No export, or a timeout, MUST give `check.oracle-failed` (error, `retryable: true` on a timeout).
- **Summary.** `summary` MUST hold `pairs` (one `{a, b, common, only_a, only_b, differences}` per pair), `min_pins` and `unnumbered`.
- **Evidence.** The stage evidence MUST be `Evidence.combine` of `validation.read.evidence`, `NetlistOutcome.evidence` and, on built input, `INFERRED` for Fenolite's model rules; `UNVERIFIED` when the export failed.

#### Scenario: Names do not matter
- **GIVEN** a `board` list with `R1-1` on `VIN` and `R1-2` and `D1-2` on `LED_A`, and an `export` list with `R1-1` on `N1` and `R1-2` and `D1-2` on `N2`
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k names` calls `compare`
- **THEN** it returns no difference and `common == 3`

#### Scenario: Reassigned pad located
- **GIVEN** a `model` list with `R1-2` and `D1-2` on `LED_A` and `D1-1` and `U1-9` on `GND`, and a `board` list equal except that `R1-2` is on `GND`
- **WHEN** `compare(model, board)` runs
- **THEN** it returns exactly one difference, naming `R1-2`

#### Scenario: Swapped pairs flagged
- **GIVEN** an `a` list with blocks `{P1-1, P2-1}` and `{P3-1, P4-1}`, and a `b` list with blocks `{P1-1, P3-1}` and `{P2-1, P4-1}`
- **WHEN** `compare(a, b)` runs
- **THEN** it returns four differences, one per element

#### Scenario: Uncovered elements are coverage
- **GIVEN** a `board` list holding `MH1-1` on no net and an `export` list without it, both otherwise equal
- **WHEN** the stage runs with a fake netlist oracle
- **THEN** it reports no `netlist.assignment-differs`, one `netlist.uncovered` info naming `MH1-1`, and status `ok`

#### Scenario: Single-pin nets
- **GIVEN** a net with one element on both sides of a pair
- **WHEN** `compare` runs with `min_pins=1` and then with `min_pins=2`
- **THEN** the element is common in the first run, and counted as uncovered with reason `below-min-pins` in the second

#### Scenario: Native input compares board and export only
- **GIVEN** the native `two_layer` project and a fake netlist oracle that returns the board's own partition under other labels
- **WHEN** the stage runs
- **THEN** `summary.pairs` holds one pair, (`board`, `export`), with 0 differences, and the status is `ok`

#### Scenario: Unconnected pins named on one side
- **GIVEN** a `model` list with `U1-2` and `U1-3` on no net, and a `board` list with `U1-2` on `unconnected-(U1-PA1-Pad2)` and `U1-3` on `unconnected-(U1-PA2-Pad3)`, both otherwise equal
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k unconnected` calls `compare`
- **THEN** it returns no difference

#### Scenario: Mapped pins are named by their pads
- **GIVEN** a model whose component `R1` has `pin_pad_map == (("1", "2"), ("2", "1"))` and whose net `VIN` lists pin `1`
- **WHEN** `model_netlist` runs
- **THEN** the element on `VIN` is `R1-2`, and `R1-1` is on no net

#### Scenario: Two unconnected pads joined on one side
- **GIVEN** a `model` list with `U1-2` and `U1-3` on no net, and a `board` list with both on one net `X`
- **WHEN** `compare(model, board)` runs
- **THEN** it returns at least one difference, naming `U1-2` or `U1-3`

#### Scenario: Schematic agrees with the model
- **GIVEN** a `model` list and a `schematic` list that hold the same partition, the schematic naming each unconnected pin `unconnected-(…)`
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k schematic_pair` runs the stage on built input with a fake `SchematicNetlistOracle`
- **THEN** `summary.pairs` holds (`model`, `board`), (`model`, `schematic`) and (`board`, `export`), each with 0 differences

#### Scenario: Two nets joined on the sheet
- **GIVEN** a `model` list with `U3-6` on `GND` and `U4-6` on `OTHER`, and a `schematic` list with both on one net
- **WHEN** the stage runs on built input
- **THEN** it reports `netlist.assignment-differs` for the pair (`model`, `schematic`), naming `U3-6` or `U4-6`, and nothing for (`model`, `board`)

#### Scenario: Native input compares the schematic with the board
- **GIVEN** a native project with a schematic, a fake oracle whose schematic netlist has `R1-2` on another net than the board has
- **WHEN** the stage runs
- **THEN** `summary.pairs` holds (`schematic`, `board`) and (`board`, `export`), and one difference names `R1-2`

#### Scenario: Schematic export fails
- **GIVEN** a native project with a schematic and a fake oracle whose `schematic_netlist` returns no netlist
- **WHEN** the stage runs
- **THEN** it reports one `check.oracle-failed` error, and `summary.pairs` holds (`board`, `export`)

#### Scenario: No schematic, pairs as before
- **GIVEN** the native `two_layer` project, which has no schematic
- **WHEN** the stage runs
- **THEN** `summary.pairs` holds only (`board`, `export`), and the oracle's `schematic_netlist` is not called

### Requirement: RT2 stage
`fenolite.checks.rt2.rt2_stage(oracle, project) -> StageResult` SHALL report RT2 of the board: KiCad's DRC gives the same violations for the board and for Fenolite's re-dump of it, as the reports of `oracle.rt2(project)` show (`kicad-oracle`, "RT2 oracle").
- **Keys.** `violation_key(group, violation, *, source)` MUST be `(group, type, severity, excluded, items)`, where `group` is `violations` or `unconnected_items` and `items` is the sorted tuple of each item's description and position. Item uuids MUST be left out, because a re-save drops or replaces some (`H-K-UUID-KEEP-2`). The parent folder of `source` MUST be replaced by `<tmp>` in descriptions.
- **Stability.** `compare_runs(outcome) -> Rt2Verdict(holds, unstable, differences, judged)` MUST treat a key as unstable when its count differs between the runs of the original (`before`) or between the runs of the re-dump (`after` and `repeats`); such keys MUST be left out of both sides and counted. `holds` MUST be true when the remaining keys of the first run of the original and of the first run of the re-dump have equal counts.
- **Judged.** A tool may not repeat its own report (`H-K-RT2-STABLE-2`), so a difference stands only when both sides repeat: `judged` MUST be true when `holds` is true or no key is unstable, and false otherwise. When `judged` is false the stage neither passes nor fails on the difference: it reports no `check.rt2-failed`, its status is `ok`, and its evidence is `UNVERIFIED`.
- **Issues.** When `judged` is true, one `check.rt2-failed` error per differing key, with its type and both counts in the message and the `@<x>,<y>` of its first item as `where` (empty when it has none). One `check.rt2-unstable` info with the count of unstable keys, when it is not 0; when `judged` is false, its message MUST also give the count of the other differing keys and say that RT2 is not judged. Fewer than two reports of the original, or no report of the re-dump, MUST give `check.oracle-failed` (error, `retryable: true` on a timeout).
- **Summary.** `summary` MUST hold `holds`, `judged`, `normalised`, `runs` (`original` and `redump` counts), `before` and `after` (violations and unconnected items of the first original run and of the first re-dump run), `unstable` and `differences`.
- **Evidence.** The stage evidence MUST be `Rt2Outcome.evidence` when both sides were compared and `judged` is true, and `UNVERIFIED` otherwise.

#### Scenario: Equal runs hold
- **GIVEN** a fake `RoundTripOracle` whose two original reports and re-dump report are equal
- **WHEN** `uv run pytest tests/unit/checks/test_rt2_stage.py -k equal` runs the stage
- **THEN** the status is `ok`, `summary.holds` is true and `summary.unstable` is 0

#### Scenario: Unstable violation excluded
- **GIVEN** a first original report with one more `silk_overlap` warning than the second, and a re-dump report equal to the second
- **WHEN** the stage runs
- **THEN** `summary.holds` is true, and one `check.rt2-unstable` info reports the count 1

#### Scenario: Changed re-dump fails
- **GIVEN** equal original reports and a re-dump report with one more `clearance` error
- **WHEN** the stage runs
- **THEN** it reports one `check.rt2-failed` error naming `clearance` with the counts 0 and 1, and the status is `errors`

#### Scenario: Difference on an unstable board is not judged
- **GIVEN** two original reports that differ in one `silk_overlap` warning, and a re-dump report with one more `clearance` error than both
- **WHEN** the stage runs
- **THEN** it reports no `check.rt2-failed` and one `check.rt2-unstable` info saying that RT2 is not judged, `summary.judged` and `summary.holds` are false, the status is `ok` and the evidence level is `UNVERIFIED`

#### Scenario: Repeated difference fails
- **GIVEN** five equal original reports, and a re-dump report with one more `clearance` error that its three repeats also hold
- **WHEN** the stage runs
- **THEN** it reports one `check.rt2-failed` error, `summary.judged` is true and the status is `errors`

#### Scenario: Item uuids masked
- **GIVEN** a re-dump report equal to the original reports except for every item uuid
- **WHEN** the stage runs
- **THEN** `summary.holds` is true

#### Scenario: Real runs on both majors
- **GIVEN** the native `two_layer` project and the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_rt2_stage.py` runs `fenolite check <project> --stages roundtrip.rt2 --json` on 9.0.9 and on 10.0.6
- **THEN** `roundtrip.rt2` has status `ok`, `summary.holds` is true, `summary.normalised` is true on 10.0.6 and false on 9.0.9, and the project snapshot is unchanged

### Requirement: Findings stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities, and `docs/cli-contract.md` MUST document each of them, with `kicad` for `<oracle>` ("Check issue codes").

| code | severity | when |
|---|---|---|
| `<oracle>.drc.<type>` | error, warning, info | one per DRC violation or unconnected item, `<type>` from `type_code` |
| `netlist.assignment-differs` | error | an element whose net block differs between the two sources of a pair |
| `netlist.uncovered` | info | elements that one side of a pair does not cover, per reason |
| `check.rt2-failed` | error | a violation key whose counts differ between the original and the re-dump |
| `check.rt2-unstable` | info | violation keys that differ between runs of one side; its message says when RT2 is therefore not judged |

- `netlist.assignment_compare` and `roundtrip.rt2` MUST also report `check.oracle-failed` when the tool writes no export or report, or times out.
- Every generated finding code MUST match `ISSUE_CODE` and MUST differ from every rules-verdict code.

#### Scenario: New literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each new literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: New codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** `kicad.drc.<type>`, `netlist.assignment-differs`, `netlist.uncovered`, `check.rt2-failed` and `check.rt2-unstable` appear in `docs/cli-contract.md`

### Requirement: Negative tests and a positive control
`tests/kicad/check/test_negatives.py` (markers `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that `fenolite check` locates two seeded faults, and SHALL keep c0018's overlapping-rules fixture as a permanent positive control. `tests/kicad/check/_fixtures.py` MUST write each project into `tmp_path` from c0013's authored built project or from a bench of c0018's `tests/kicad/rules/_rulecases.py::order`:
- **Reassigned pad.** Pad 2 of `R1` moved from `LED_A` to `GND` on the board only (`read_board`, the pad's `net_id` replaced, `write_board` for the running major), with the `.fenolite/` model unchanged: a `netlist.assignment-differs` error with `where` `R1-2` for the pair (`model`, `board`).
- **Bridging track.** One `F.Cu` track of net `VIN` from pad 1 to pad 2 of `R1` added to the board: a `kicad.drc.shorting-items` error whose `where` names `R1-2`.
- **Positive control.** The `forward` and `reverse` benches of `order(direction)`: a `_rulebench.builder()` bench, which holds c0018's canary pair, with the pair `ord` on `ORD_A` and `ORD_B` 2 mm apart, and `tests/data/kicad/rules/overlap.kicad_dru` (its two rules reversed for `reverse`) behind c0018's canary rule. c0018's own report of each bench (`order(direction).report`) MUST pass `require_canary`, and `violations_between` MUST find the `ord` pair's `clearance` violation in the forward one only. `overlap_bench` MUST write the same `Bench.design` and rules text into `tmp_path` with a `{}` project. Because the bench carries the canary (living `kicad-oracle`, "Rules proofs carry a canary"), the check output MUST be judged by item, matching issue codes and the locations that `item_locations` gives for `Bench.uuids(label)`: the forward run MUST give exactly one `kicad.drc.clearance` error whose `where` names the two `ord` tracks, and the reverse run none naming an `ord` track; both runs MUST give one `kicad.drc.clearance` error whose `where` names the two canary tracks, and `summary.canary` `fired`. A run without that canary finding MUST fail the test with "rules file not loaded", as `require_canary` does.
- The unmodified authored built project MUST give neither `netlist.assignment-differs` nor `kicad.drc.shorting-items`.

#### Scenario: Reassigned pad caught with location
- **GIVEN** the reassigned-pad project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k reassigned` runs on 9.0.9 and on 10.0.6
- **THEN** `fenolite check <project> --json` exits 5 with a `netlist.assignment-differs` error whose `where` is `R1-2`

#### Scenario: Bridging track caught with location
- **GIVEN** the bridging-track project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k bridging` runs on 9.0.9 and on 10.0.6
- **THEN** `fenolite check <project> --json` exits 5 with a `kicad.drc.shorting-items` error whose `where` contains `R1-2`

#### Scenario: Overlapping rules
- **GIVEN** the `forward` and `reverse` benches of `_rulecases.order`, whose own reports pass `require_canary`, written by `overlap_bench`
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k overlap` runs `fenolite check <bench> --json` on 9.0.9 and on 10.0.6
- **THEN** the forward run reports exactly one `kicad.drc.clearance` error whose `where` names the two `ord` tracks and the reverse run none naming an `ord` track, both runs report one `kicad.drc.clearance` error whose `where` names the two canary tracks, and `summary.canary` is `fired` in both

#### Scenario: Clean control
- **GIVEN** the unmodified authored built project
- **WHEN** the same test runs it
- **THEN** no `netlist.assignment-differs` and no `kicad.drc.shorting-items` issue is reported

### Requirement: Built examples have no assignment differences
`tests/kicad/check/test_check_built.py` SHALL check c0011's `examples/blink_2layer`, built into `tmp_path` with `fenolite build examples/blink_2layer/design.py --out <tmp> --kicad-version <target> --confirm` for each target the running major loads (9 on 9.0.9; 9 and 10 on 10.0.6), and c0013's authored built project, with `fenolite check <dir> --json` (v0.1 acceptance item 1, part).
- `netlist.assignment_compare` MUST have status `ok` with 0 differences in both pairs, and no `netlist.uncovered` with reason `unmatched-record` or `net-label-ambiguous`.
- Every `kicad.drc.unconnected-items` finding MUST name `REF-PIN` pads in its `where`.
- The second example board of v0.1 is checked by the same test once it exists (c0025).

#### Scenario: Blink on both majors
- **GIVEN** the blink built for each target the running major loads
- **WHEN** `uv run pytest tests/kicad/check/test_check_built.py -k assignment` runs on 9.0.9 and on 10.0.6
- **THEN** `netlist.assignment_compare` is `ok` with 0 differences in the pairs (`model`, `board`) and (`board`, `export`)

#### Scenario: Authored built project
- **GIVEN** c0013's authored built project for the running major
- **WHEN** the same test runs it
- **THEN** `netlist.assignment_compare` is `ok` with 0 differences, and each `kicad.drc.unconnected-items` issue names `REF-PIN` pads

### Requirement: Render stage
`fenolite.checks.render.render_stage(plotter, project) -> StageResult` SHALL be the stage `render`, last in `STAGE_ORDER`, and SHALL say whether the board plots.
- The stage MUST be opt-in: it runs only when `--stages` names it, and the default stage set MUST NOT hold it.
- `run_checks` MUST take `plotter: Plotter | None = None` and MUST call `plotter.plot(project)` at most once.
- The stage MUST report `render.failed` (warning; `where` = the view name) for each view the plotter could not produce, and MUST NOT report an error. Its status MUST be `ok` whenever it ran.
- `summary` MUST hold `tool_version` and `views` (`name`, `bytes`, `sha256`; sorted by name).
- Stage evidence MUST be `PlotOutcome.evidence`.
- The stage MUST write nothing: `check` stays read-only.
- A refused board read MUST skip the stage with reason `read-refused`, and a missing tool MUST follow the pre-flight of `drc.kicad`.
- `checks.codes.ISSUE_CODES` MUST gain `render.failed` (warning).

#### Scenario: Opt-in
- **WHEN** `uv run pytest tests/unit/checks/test_render_stage.py -k default` runs `run_checks` without `stages`
- **THEN** the report holds no `render` stage and the fake plotter was not called

#### Scenario: Views in the summary
- **GIVEN** a fake `Plotter` that gives four views
- **WHEN** `run_checks` runs with `stages=("render",)`
- **THEN** the stage is `ok`, `summary.views` holds four entries sorted by name, and no file was written

#### Scenario: A failed view never fails the check
- **GIVEN** a fake `Plotter` that gives two views and names two failures
- **WHEN** `fenolite check <board> --stages render` runs
- **THEN** the exit code is 0, and the issues hold two `render.failed` warnings

#### Scenario: Stage order
- **WHEN** `STAGE_ORDER` is read
- **THEN** `render` is its last entry

### Requirement: Copper clearance stage
`fenolite.checks.copper.copper_stage(design, *, project, rules_source, frame, evidence) -> StageResult` SHALL run `check_copper` (`copper-check`) on the board model that `run_checks` read (`Validation.read.design`), for native and built input alike, because the board is the layout authority (`design-model`, "Layout authority"). `evidence` is `Validation.read.evidence`.
- **Rules.** When `rules_source` is given, `rules_source.design_rules(design, project)` (`backend-protocol`, "Design rules source") MUST give the design that is checked, `min_clearance`, `rules_over_classes` and `floor_over_rules`, which the stage passes to `check_copper`. Otherwise the design MUST be checked as read, and one `copper.rules-incomplete` warning MUST say that no rules source was given.
- **Incomplete rules.** `opaque_clearance_rules > 0` MUST give one `copper.rules-incomplete` warning with the count, and each `unread` entry one `copper.rules-incomplete` warning naming the file and its error.
- **Pads.** When `frame` is given, `pads` MUST be `frame.board_pads(<checked design>)` (c0028); otherwise `None`.
- **Skip.** The stage MUST be skipped with reason `read-refused` when the board read was refused.
- **No tool.** The stage MUST run no subprocess, so it needs no `kicad-cli`.
- **Status.** `ok` when no issue has severity `error`, `errors` otherwise.
- **Summary.** `CopperReport.summary`, plus `rules`: `{min_clearance, opaque_clearance_rules, unread}`.
- **Evidence.** `Evidence.combine` of `CopperReport.evidence`, `evidence` and `DesignRules.evidence` when a rules source was given; `UNVERIFIED` when the stage gave `copper.rules-incomplete` or `copper.item-unsupported`.
- The stage MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: Bridging track caught without KiCad
- **GIVEN** `tests/_coppercheck.py::bridged_project(tmp_path, major=10)`: c0013's authored built project with one `F.Cu` track of net `VIN` added from pad 1 to pad 2 of `R1`, written with `write_board`; no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/checks/test_copper_stage.py -k bridging` runs `fenolite check <project> --stages copper.clearance --json`
- **THEN** the exit code is 5, the issues hold one `copper.short` error whose `where` contains `R1-2` and one more between the added track and the `LED_A` track that leaves that pad, and no subprocess ran

#### Scenario: Clean authored project
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite check <project> --stages copper.clearance --json` runs
- **THEN** the stage has status `ok` and no `copper.short` or `copper.clearance` issue

#### Scenario: Refused read
- **GIVEN** a fake `Validator` that raises `FormatError`
- **WHEN** `run_checks` runs with `stages=("copper.clearance",)` on native input
- **THEN** the stage is skipped with reason `read-refused` and gives no issue

#### Scenario: Validator without a rules source
- **GIVEN** a fake `Validator` that satisfies neither `DesignRulesSource` nor `BoardFrame`, and whose board holds one footprint with two pads
- **WHEN** `uv run pytest tests/unit/checks/test_copper_stage.py -k no_source` runs the stage
- **THEN** it reports one `copper.rules-incomplete` warning naming the missing rules source and one `copper.item-unsupported` warning for the pads, and its level is `UNVERIFIED`

### Requirement: Copper stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. The build guard (`design-dsl`, "Copper guard before writing") emits the same codes into the `build` envelope, where they pass through unchanged as `design-dsl` "Build issue codes" allows for codes that later requirements add.

| code | severity | when |
|---|---|---|
| `copper.short` | error | copper of two nets touches or overlaps on a shared copper layer |
| `copper.clearance` | error, warning | a gap below the clearance in force; the governing rule sets the severity |
| `copper.zone-overlap` | warning | zones of different nets and equal priority overlap on a shared layer |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, per kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force |

#### Scenario: Copper literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `copper.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Copper codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the six `copper.*` codes appear in `docs/cli-contract.md`

### Requirement: Document check pipeline
`fenolite.checks.documents` SHALL define `DOCUMENT_STAGES = ("model.validate", "erc.lite", "netlist.assignment_compare", "roundtrip.rta0", "roundtrip.rta1", "roundtrip.rta2")` and `run_document_checks(*, documents: DocumentSet, stages: Sequence[str], model: Design | None, built: bool, validator: DocumentValidator, cache_error: str = "") -> CheckReport`, the check of an input that is a set of documents instead of one board. `STAGE_ORDER`, `run_checks` and the KiCad stages are unchanged.
- **Order and results.** The selected stages MUST run in `DOCUMENT_STAGES` order whatever order is given, unselected stages MUST be left out, and each stage MUST return the `StageResult` of "Check stages and statuses". `validator.read_documents` MUST be called at most once per run and only when a selected stage needs a reading, and `validator.container_roundtrip` at most once per document and level.
- **Input issues.** Each entry of `ProjectRead.errors`, and each document whose `container_roundtrip` raises `FormatError` and that `errors` does not name, MUST give one `check.read-refused` error built like `stages.read_refused`, with the document name as the file. Each name of `DocumentSet.missing` MUST give one `check.document-missing` warning. A non-empty `cache_error` MUST give `check.cache-unreadable`. `CheckReport.issues` MUST hold these first, sorted by code and `where`, then the issues of each stage in stage order. `CheckReport.read_error` MUST be the error of the only document when the set holds exactly one document and its reading was refused, and `None` otherwise.
- **`model.validate`.** On built input the stage MUST report the `model.*` findings of `model.validate()`; with a `cache_error` it MUST be skipped with reason `cache-unreadable`. On native input it MUST report the `model.*` findings of the schematic reading and of the PCB reading, each `where` prefixed with `schematic:` or `pcb:`, together with the readers' own issues; without any reading it MUST be skipped, with reason `read-refused` when a reading was refused and `not-judged` when the set holds no schematic and no PCB document (a library alone). It MUST NOT report `check.footprint-unresolved` or `check.symbol-unresolved`. `summary` MUST hold, under the key of each side that was judged (`model`, `schematic`, `pcb`), its `components` and `nets`.
- **`erc.lite`.** `erc_lite.erc_lite` MUST run on the built model, or on native input on the schematic reading. Without a schematic reading on native input the stage MUST be skipped with reason `no-schematic`, or `read-refused` when a schematic document exists and its reading was refused.
- **`netlist.assignment_compare`.** The sources MUST be `model` (`assignment_compare.model_netlist` of the built model), `schematic` (`model_netlist` of the schematic reading) and `pcb` (`assignment_compare.board_netlist` of the PCB reading), each `PadNetList` named after its source. The pairs MUST be (`model`, `schematic`) and (`model`, `pcb`) on built input and (`schematic`, `pcb`) on native input, each only when both sources exist, compared with `assignment_compare.compare`. The issues and `summary` (`pairs`, `min_pins`, `unnumbered`) MUST have the form of "Assignment compare stage". Without any pair the stage MUST be skipped with reason `single-source`, or `cache-unreadable` on built input with a `cache_error`. It MUST NOT need an oracle. The stage's evidence combines the readings compared with `validator.stage_evidence()` of the stage.
- **`roundtrip.rta0` and `roundtrip.rta1`.** `checks.containers.container_stage(name, level, verdicts)` MUST turn the `ContainerRoundTrip` of every document of the set into one stage; `verdicts` maps a document name to its verdict, or to `None` for a document whose reading raised `FormatError`. The stage's evidence is `Evidence.combine` of the evidence of the judged verdicts. A verdict that is judged and not passed MUST give one `check.rta0-failed` or `check.rta1-failed` error whose `where` is `<document>:<difference>`. A verdict that is not judged MUST be counted in `summary.unjudged` by reason and MUST give one `check.roundtrip-unjudged` info, except for the reasons `not-a-container` and `read-refused`, which are only counted. For `RT-A1`, a document with a stream whose records are equal and whose bytes differ MUST give one `check.rta1-normalised` info that counts those streams. `summary` MUST hold `level`, `documents` (judged), `streams`, `failed` and `unjudged`, and for `RT-A1` also `records`, `bytes_equal` and `opaque_count`. A document whose reading raises `FormatError` MUST be counted under `read-refused`. When no document is judged the stage MUST be skipped: with reason `read-refused` when every document was refused, else `not-judged`; the skipped stage keeps its summary and its `check.roundtrip-unjudged` infos.
- **`roundtrip.rta2`.** `checks.rta2.rta2_stage(model, read, scope)` MUST run on built input only and MUST be skipped with reason `native-input` otherwise, `cache-unreadable` with a `cache_error`, and `read-refused` without any reading. It MUST compare the built model with the schematic reading over the circuit kinds of `scope` (`rta2.CIRCUIT_KINDS`: `component`, `net`, `no_connect`) and with the PCB reading over its other kinds, through `checks.diff.diff_designs(model, reading, scope=…)` ("Model difference scope"). A board kind (`rta2.BOARD_KINDS`) of which the built model holds no entity MUST NOT be compared: the build wrote that content from inputs outside the model, and the count of the reading's entities goes to `summary.not_in_model`. Each change MUST give one `check.rta2-failed` error whose `where` is the change's path prefixed with `schematic:` or `pcb:`, at most 50 per side; `summary` MUST hold `level` (`RT-A2`), `holds`, `differences` (the full count), `compared` (per side, the entity kinds compared) and `not_in_model` (per side, the count per board kind that was not compared). Without a schematic and without a PCB reading the stage is skipped with `read-refused` when a reading was refused, else `not-judged`.
- **Evidence.** A skipped stage carries `UNVERIFIED`. The envelope evidence MUST follow "Evidence per check stage": the stages that ran, and those skipped with `read-refused` or `cache-unreadable`, are combined; a stage skipped with `native-input`, `no-schematic`, `single-source` or `not-judged` MUST NOT count.
- **Layering.** `checks.documents`, `checks.containers` and `checks.rta2` MUST import only `core`, `model`, `geometry` and `backends.base`.

#### Scenario: Fixed order with a fake validator
- **GIVEN** a fake `DocumentValidator` in `tests/unit/checks/fakes.py` with one schematic and one PCB reading whose pad nets agree, and passing verdicts
- **WHEN** `uv run pytest tests/unit/checks/test_documents.py -k order` calls `run_document_checks` with `stages=("roundtrip.rta1", "model.validate", "netlist.assignment_compare")` and `built=False`
- **THEN** `CheckReport.stages` names `model.validate`, `netlist.assignment_compare` and `roundtrip.rta1` in this order, every status is `ok`, `read_documents` was called once, and the pair is (`schematic`, `pcb`) with 0 differences

#### Scenario: Pad on another net in the PCB document
- **GIVEN** the same fake whose PCB reading puts pad `R1-2` on the net of `R1-1`
- **WHEN** `netlist.assignment_compare` runs
- **THEN** the stage has status `errors` and at least one `netlist.assignment-differs` error, the `where` of one of them being `R1-2`

#### Scenario: Schematic alone
- **GIVEN** a fake whose set holds one schematic document and no PCB document
- **WHEN** every stage is selected on native input
- **THEN** `netlist.assignment_compare` is skipped with reason `single-source`, `roundtrip.rta2` with `native-input`, `erc.lite` ran, and neither skip counts in the envelope evidence

#### Scenario: One refused document among others
- **GIVEN** a fake whose PCB document raises `FormatError` and whose schematic reads
- **WHEN** every stage is selected on native input
- **THEN** the issues start with one `check.read-refused` error naming the PCB document, `model.validate` ran on the schematic, `summary.unjudged` of both container stages holds `read-refused: 1`, and `CheckReport.read_error` is `None`

#### Scenario: Failed and unjudged verdicts
- **GIVEN** verdicts for three documents: `RT-A0` failed with `difference` `Nets6/Data`, `RT-A0` unjudged with reason `too-large`, and `RT-A0` unjudged with reason `not-a-container`
- **WHEN** `uv run pytest tests/unit/checks/test_containers.py` runs `container_stage`
- **THEN** it reports one `check.rta0-failed` error whose `where` ends in `:Nets6/Data` and one `check.roundtrip-unjudged` info naming `too-large`, `summary.unjudged` is `{"not-a-container": 1, "too-large": 1}`, and the status is `errors`

#### Scenario: RT-A2 difference located
- **GIVEN** a built model whose component `R1` has the value `10k`, and a schematic reading in which it is `1k`
- **WHEN** `uv run pytest tests/unit/checks/test_rta2.py` runs `rta2_stage` with a scope that holds `component: ("value",)`
- **THEN** it reports one `check.rta2-failed` error whose `where` is `schematic:/component/R1/value`, and `summary.holds` is `false`

#### Scenario: Document checks stay backend-free
- **GIVEN** a module `src/fenolite/checks/documents.py` that imports `fenolite.backends.altium`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `checks → backends.altium`

### Requirement: Document check issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. No FEN code is added.

| code | severity | when |
|---|---|---|
| `check.document-missing` | warning | the project file lists a document that does not exist |
| `check.rta0-failed` | error | a container copy lost or changed a storage or a stream; `where` is `<document>:<stream path>` |
| `check.rta1-failed` | error | a stream's records differ after decode and encode; `where` is `<document>:<stream>#<record>` |
| `check.rta1-normalised` | info | streams whose records are equal and whose re-encoded bytes differ |
| `check.rta2-failed` | error | the built model and a reading of the written documents differ inside the written scope |
| `check.roundtrip-unjudged` | info | a document whose level was not judged; the message names the reason |

#### Scenario: New literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each of the six codes is a key of `ISSUE_CODES` with the severity of this table

#### Scenario: New codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the six codes appear in `docs/cli-contract.md`

### Requirement: Model difference scope
`fenolite.checks.diff.diff_designs` SHALL take the keyword-only argument `scope: ModelScope | None = None` (`backend-protocol`, "Document sets and container round trips"), as "Model difference report" (change c0066) allows a later change to add. Without a scope the report is the one of "Model difference report", unchanged; `diff_libraries` takes no scope.
- **Scope.** With a `scope`, only the kinds that are keys of `scope.fields` and only the fields listed for each MUST be compared; the kind `design` is compared only when it is a key. A keyed kind with an empty field list (`no_connect`) compares the presence of its keys.
- **Tolerance.** Two lengths (a value of a field typed `Nm`, `Point` or `Size`, or of a sequence of them) are equal when they differ by at most `scope.length_tolerance`. Every other value MUST be equal exactly.
- **Content kinds.** Content kinds are then matched in the canonical order of `a`, each entity taking the first unmatched entity of `b`, in canonical order, that is equal under the tolerance. Unmatched entities are `removed` or `added` as without a scope, and their `a` and `b` hold only the scoped fields.
- **Order and result.** `changes`, `summary`, `equal` and `to_json` are those of "Model difference report".
- The module MUST still import only `core`, `model`, `geometry` and `backends.base`.

#### Scenario: Tolerance on lengths
- **GIVEN** design `b` equal to `a` except that one track end is moved by 2 nm and one footprint by 3 nm
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py -k tolerance` runs `diff_designs(a, b, scope=ModelScope({"track": ("start", "end", "width", "layer"), "footprint": ("position",)}, length_tolerance=2))`
- **THEN** the only change is `/footprint/<ref>/position`

#### Scenario: Scope hides other kinds
- **GIVEN** two designs that differ only in one text
- **WHEN** `diff_designs` runs with a scope whose `fields` hold only `component`
- **THEN** `equal` is true

#### Scenario: Scope hides other fields
- **GIVEN** two designs whose component `R1` differs in `value` and in `properties`
- **WHEN** `diff_designs` runs with `ModelScope({"component": ("value",)})`
- **THEN** the only change is `/component/R1/value`

#### Scenario: Without a scope nothing changes
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py` runs the cases of "Model difference report" (change c0066)
- **THEN** they pass unchanged

### Requirement: ERC stage
`fenolite.checks.erc.erc_stage(oracle, project) -> StageResult` SHALL report KiCad's electrical rules check of the project's schematic as the stage `erc.kicad`, second in `STAGE_ORDER`, a default stage and a member of `ORACLE_STAGES`.
- **Input.** The stage MUST run on built and on native input alike, through `oracle.erc(project)` (`backend-protocol`, "ERC oracle protocol"), and MUST need no board model: a refused board read does not skip it, and `run_checks` MUST NOT read the board for this stage alone.
- **Skips.** It MUST be skipped with reason `no-schematic` when `project.files` holds no `<board stem>.kicad_sch`, and with reason `unsupported-oracle` when `isinstance(oracle, ErcOracle)` is false. Neither skip counts in the envelope evidence.
- **Issues.** With a report, the issues MUST be those of `checks.erc_json.finding_issues(report, oracle=oracle.name)` ("ERC findings as issues"). Without a report, or on a timeout, the stage MUST report `check.oracle-failed` (error) with `ErcOutcome.message`, and `retryable: true` on a timeout.
- **Summary.** `summary` MUST hold `tool_version`, `sheets` (the number of sheets in the report), `violations` (total), `by_type`, `by_severity`, `excluded`, `ignored_checks`, `types` (each emitted code mapped to the tool's raw type) and `tool_writes`.
- **Evidence.** The stage evidence MUST be `ErcOutcome.evidence` when a report exists and `UNVERIFIED` otherwise ("Evidence per check stage").
- The stage MUST keep "Check is read-only" and "Check output is deterministic": the tool runs on the copy set, and the output holds no report date and no temporary path.

#### Scenario: Clean built project
- **GIVEN** the blink built with a schematic for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_erc_oracle.py -k clean` runs `fenolite check <dir> --stages erc.kicad --json` on 9.0.9 and on 10.0.6
- **THEN** the exit code is 0, the stage has status `ok`, `summary.violations` is 0, and the stage's oracle is `kicad-cli <running version>`

#### Scenario: Unconnected pin reported
- **GIVEN** the same project with the label of pin 1 of `R1` removed from the schematic by token edit
- **WHEN** `fenolite check <dir> --stages erc.kicad --json` runs
- **THEN** the exit code is 5, and the issues hold one `kicad.erc.pin-not-connected` error whose `where` is `R1-1`

#### Scenario: No schematic
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages erc.kicad --json` runs with a fake `kicad-cli`
- **THEN** the stage has status `skipped` and reason `no-schematic`, the fake saw no `sch erc` run, and the exit code is 0

#### Scenario: Schematic the tool cannot load
- **GIVEN** a fake `ErcOracle` that returns no report and the message `Failed to load schematic`
- **WHEN** `uv run pytest tests/unit/checks/test_erc_stage.py -k no_report` runs the stage
- **THEN** it reports one `check.oracle-failed` error holding that message, and the stage evidence is `UNVERIFIED`

#### Scenario: Native project
- **GIVEN** the authored hierarchy `tests/data/kicad/schematic/hier/` copied into `tmp_path` with a board and a project file of the stem `top`
- **WHEN** `fenolite check <dir> --stages erc.kicad --json` runs on both majors
- **THEN** the stage runs with `summary.sheets` 2, and the folder snapshot is equal before and after

### Requirement: ERC findings as issues
`fenolite.checks.erc_json.finding_issues(report, *, oracle) -> tuple[Issue, ...]` SHALL map every violation of an `ErcReport` to exactly one issue.
- **Code.** The code MUST be `erc_json.type_code(oracle, type)`, that is `f"{oracle}.erc.{suffix}"`, the suffix being `checks.codes.type_suffix(type)`: the rule that `drc_json.type_code` applies to DRC types (lower case, `_` and every other character outside `[a-z0-9-]` replaced by `-`, runs collapsed, `unknown` when nothing remains). `drc_json.type_code` MUST use the same helper. A suffix in `erc_json.RESERVED_SUFFIXES = ("position-unscaled",)`, the code a reader of ERC reports uses for itself, MUST become `type-<suffix>`. The raw type MUST be kept in `summary.types`.
- **Severity.** `info` when `excluded` is true, otherwise `error` for `error`, `warning` for `warning`, and `error` for any other value.
- **Where.** The locations of the items, in report order, joined with `, `: an item's `where` when the oracle filled it (`REF-PIN` for a pin, `REF` for a symbol, the text for a label), and otherwise `<sheet>@<x>,<y>`, the sheet path and the item position in millimetres as an exact decimal without trailing zeros.
- **Message.** `<type>: <description>`, with the parent folder of `report.source` replaced by `<tmp>` and the home directory by `~`.
- The function MUST NOT emit a code literal; every code matches the `ISSUE_CODES` key `<oracle>.erc.<type>` ("ERC stage issue codes").

#### Scenario: Pin located as REF-PIN
- **GIVEN** an `ErcReport` whose one `pin_not_connected` violation of severity `error` has one item with `where == "U1-2"`
- **WHEN** `uv run pytest tests/unit/checks/test_erc_json.py -k ref_pin` calls `finding_issues(report, oracle="kicad")`
- **THEN** it returns one `kicad.erc.pin-not-connected` error whose `where` is `U1-2`

#### Scenario: Item without a location
- **GIVEN** a violation on sheet `/` whose only item has `where == ""` and position (139.7 mm, 59.69 mm)
- **WHEN** it is mapped
- **THEN** the issue's `where` is `/@139.7,59.69`

#### Scenario: Excluded violation
- **GIVEN** a violation with `excluded` true and severity `error`
- **WHEN** it is mapped
- **THEN** the issue has severity `info`

### Requirement: ERC stage issue codes
`checks.codes.ISSUE_CODES` SHALL gain the keys of this table, as "Check issue codes" allows, and `docs/cli-contract.md` MUST document them with `kicad` for `<oracle>`.

| code | severity | when |
|---|---|---|
| `<oracle>.erc.<type>` | error, warning or info | an ERC violation of that type; `info` when excluded |
| `<oracle>.drc.parity-unchecked` | warning | parity was asked for and the tool did not judge it |

`cli/data/explain.toml` MUST explain `kicad.erc.*`, `kicad.drc.parity-unchecked` and the reader's own `kicad.erc.position-unscaled` (`cli-contract`, "Explain command").

`checks.codes.table_key` MUST map an oracle's `.erc.` code to the key `<oracle>.erc.<type>`. The codes `erc.lite.*` MUST stay keys of `ISSUE_CODES` ("ERC lite stage").

#### Scenario: Closed set still enforced
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each is a key of `ISSUE_CODES`, `kicad.erc.pin-not-connected` matches the key `<oracle>.erc.<type>`, and every key appears in `docs/cli-contract.md`

### Requirement: Parity findings
When the DRC run tested schematic parity (`kicad-oracle`, "Parity in the DRC run"), the `drc.kicad` stage SHALL report each parity entry as an issue and SHALL say in its summary whether parity was judged.
- `summary.parity` MUST be the number of parity entries of the counted report, and `summary.parity_judged` MUST be true exactly when the run passed the parity flag and the tool judged it.
- Each entry MUST be mapped by `drc_json.finding_issues` as a violation is ("DRC findings as issues").
- When the flag was passed and the tool did not judge parity, the stage MUST report one `<oracle>.drc.parity-unchecked` warning with the tool's sanitised line, `summary.parity_judged` MUST be false, and the stage evidence MUST NOT be lowered: the copper verdict stands.
- A project without a schematic MUST give `parity_judged` false and no parity issue.

#### Scenario: Built project in agreement
- **GIVEN** the blink built with a schematic for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_parity.py -k built` runs `fenolite check <dir> --stages drc.kicad --json` on both majors
- **THEN** `summary.parity_judged` is `true`, `summary.parity` is 0, and no issue code is a parity type

#### Scenario: Pad on another net
- **GIVEN** the same board with pad 2 of `R1` moved to the net `GND` by token edit
- **WHEN** the same command runs
- **THEN** the issues hold `kicad.drc.net-conflict` with `where` `R1-2`, and `summary.parity` is at least 1

#### Scenario: Project without a schematic
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages drc.kicad --json` runs with a fake `kicad-cli`
- **THEN** the fake saw no `--schematic-parity`, and `summary.parity_judged` is `false`

### Requirement: Model difference report
`fenolite.checks.diff` SHALL define `Change(path: str, change: Literal["added", "removed", "changed"], a: str, b: str)`, `DiffReport(equal: bool, changes: tuple[Change, ...], summary: Mapping[str, Mapping[str, int]])`, `diff_designs(a: Design, b: Design, *, ext: bool = False) -> DiffReport`, `diff_libraries(a: Library, b: Library, *, ext: bool = False) -> DiffReport` and `diff_sheets(a: SchematicSheet, b: SchematicSheet, *, ext: bool = False) -> DiffReport`. The report lists every difference between two models exactly; it gives no verdict by level and removes no frame.
- **Never compared.** `id`, `native_ids` and `provenance` MUST be left out. `ext` MUST be left out unless `ext=True`, and is then compared as the SHA-256 of its canonical JSON. A reference by id (`net_id`, `component_id`, `netclass_id`, a member's component) MUST be replaced by the key of the entity it names before values are compared.
- **Keyed kinds.** `component` is matched by `ref`; `net` by `name`, and a net with an empty name by its sorted members as `REF-PIN`; `netclass` and `layer` by `name`; `no_connect` by `REF-PIN`; `footprint` by the `ref` of its component; `pad` by `<ref>-<number>`, with `#<k>` for the k-th further pad of one number or of no number; `interface` by `name` and `module` by `path`; in a library, `footprint_def` and `symbol_def` by `<library>:<name>` (the bare name for a definition without a library); in a sheet, `symbol` by `<ref>#<unit>`, `sheet_ref` by `name` and `lib_symbol` by its embedded name. An entity on one side only is `removed` (only in `a`) or `added` (only in `b`), with path `/<kind>/<key>`. A field that differs is `changed`, with path `/<kind>/<key>/<field>` and `a` and `b` holding the compact canonical JSON of each value. A key is one path segment: `~` is written `~0` and `/` is written `~1`, as in a JSON pointer, so a net called `/SDA` has the path `/net/~1SDA`. A key used twice in one kind takes `#<k>` as pads do. The values a design holds once (the board `outline`, the stack-up `finish`, `sheet` and `title_block`, and the board's `ext` with `ext=True`) are the fields of the kind `design`, which has no key: their paths are `/design/<field>`. In a sheet, `paper`, `title_block` and `pages` (and the sheet's `ext` with `ext=True`) are the fields of the keyless kind `sheet`, and the sheet's `name` MUST NOT be compared. The design's `name`, its manufacturing manifest and its findings MUST NOT be compared: the name identifies the design as an id does, and the other two describe outputs.
- **Content kinds.** `track`, `arc`, `via`, `zone`, `keepout`, `text`, `graphic`, `hole`, `rule` and `stack_layer`, and in a sheet `label` and `no_connect_flag`, have no key: two entities match when every compared field is equal, and each entity matches at most one. Unmatched entities are `removed` or `added`, with path `/<kind>/<n>`, `n` being the index among the unmatched entities of that side in canonical order (the order of the entities' compact canonical JSON, which no id takes part in), and the entity's compact canonical JSON as `a` or `b`.
- **Order.** `changes` MUST be sorted by path, then by change. `summary` MUST map each kind that has a change to its counts `added`, `removed` and `changed`. `equal` MUST be true exactly when `changes` is empty.
- `DiffReport.to_json(limit: int | None)` MUST return `equal`, `summary`, `differences` (the first `limit` changes, or all), `total` and `truncated`.
- The module MUST import only `core`, `model`, `geometry` and `backends.base`.
- A later change MAY add keyword-only arguments with defaults to the three functions (a comparison scope, a length tolerance); each such requirement names this one.

#### Scenario: Equal designs with different ids
- **GIVEN** two designs built from the same data with different seeds, so every `id` differs
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py -k ids` runs `diff_designs`
- **THEN** `equal` is true and `changes` is empty

#### Scenario: One change per kind
- **GIVEN** design `b` equal to `a` except: `R1` has another value, net `VIN` has one member more, one track is removed and one via is added
- **WHEN** `diff_designs(a, b)` runs
- **THEN** `changes` holds exactly `/component/R1/value` (`changed`), `/net/VIN/members` (`changed`), `/track/0` (`removed`) and `/via/0` (`added`), sorted by path

#### Scenario: Moved footprint is one change
- **GIVEN** design `b` equal to `a` except that the footprint of `R1` is moved by 1 mm in X
- **WHEN** `diff_designs(a, b)` runs
- **THEN** `changes` holds exactly one entry, `/footprint/R1/position` (`changed`), and no entry for the pads of `R1`, whose positions are stored relative to their footprint

#### Scenario: Renamed net
- **GIVEN** design `b` equal to `a` except that the net `VIN` is called `VBUS`
- **WHEN** `diff_designs(a, b)` runs
- **THEN** it reports `/net/VBUS` as `added` and `/net/VIN` as `removed`, and each pad of that net as `changed` in its `net_id` field

#### Scenario: Libraries
- **GIVEN** two libraries that hold the same footprint, the second with one pad 0.1 mm wider
- **WHEN** `diff_libraries(a, b)` runs
- **THEN** the only change is `changed` at `/pad/<library>:<name>-<number>/size`

#### Scenario: Sheets
- **GIVEN** two sheets read from `tests/data/kicad/schematic/flat.kicad_sch`, the second with `R1` moved and one global label removed
- **WHEN** `diff_sheets(a, b)` runs
- **THEN** `changes` holds `/symbol/R1#1/position` (`changed`) and one `/label/0` (`removed`)

#### Scenario: Opaque content only with ext
- **GIVEN** two sheets that differ in one opaque `wire`
- **WHEN** `diff_sheets(a, b)` runs, and again with `ext=True`
- **THEN** the first reports `equal` true, and the second one change whose path ends in `/ext`

#### Scenario: Diff stays backend-free
- **GIVEN** a version of `src/fenolite/checks/diff.py` that imports `fenolite.backends.kicad`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `checks → backends.kicad`

