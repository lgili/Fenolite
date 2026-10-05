## ADDED Requirements

### Requirement: ERC stage
`fenolite.checks.erc.erc_stage(oracle, project) -> StageResult` SHALL report KiCad's electrical rules check of the project's schematic as the stage `erc.kicad`, second in `STAGE_ORDER`, a default stage and a member of `ORACLE_STAGES`.
- **Input.** The stage MUST run on built and on native input alike, through `oracle.erc(project)` (`backend-protocol`, "ERC oracle protocol"), and MUST need no board model: a refused board read does not skip it.
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
- **Code.** The code MUST be `f"{oracle}.erc.{suffix}"`, the suffix being `checks.codes.type_suffix(type)`: the rule that `drc_json.type_code` applies to DRC types (lower case, `_` and every other character outside `[a-z0-9-]` replaced by `-`, runs collapsed, `unknown` when nothing remains). `drc_json.type_code` MUST use the same helper. The raw type MUST be kept in `summary.types`.
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

## MODIFIED Requirements

### Requirement: Check command input
`fenolite check PATH` SHALL be registered by `src/fenolite/cli/cmd_check.py` with `mutates=False`, and SHALL check the KiCad project that `PATH` names without writing any file.
- **Board.** The board MUST be found with `fenolite.backends.kicad.projectset.resolve_board(PATH)` (`kicad-oracle`, "Check project copy set"). An ambiguous folder MUST exit 2 with `FEN-2001` and a hint listing the candidates. A missing path or board MUST exit 3 with `FEN-3001`.
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
`checks.erc_lite` SHALL define `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`, `erc_lite(design) -> tuple[Issue, ...]`, `erc_stage(design) -> StageResult` and `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`). The three rules are a function for pipelines of inputs that have no ERC oracle; the KiCad pipeline does not run them: `STAGE_ORDER` holds `erc.kicad` instead ("ERC stage"), and `run_checks` MUST NOT call `erc_stage`.
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
