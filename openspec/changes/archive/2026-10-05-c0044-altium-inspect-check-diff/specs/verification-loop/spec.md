## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Check command input
`fenolite check PATH` SHALL be registered by `src/fenolite/cli/cmd_check.py` with `mutates=False`, and SHALL check the KiCad project that `PATH` names, or the documents of another backend that `PATH` names (**Document input**), without writing any file. Every bullet below but **Document input** describes the KiCad path.
- **Board.** The board MUST be found with `fenolite.backends.kicad.projectset.resolve_board(PATH)` (`kicad-oracle`, "Check project copy set"). An ambiguous folder MUST exit 2 with `FEN-2001` and a hint listing the candidates. A missing path or board MUST exit 3 with `FEN-3001`.
- **Document input.** Before the board is looked for, the command MUST take `PATH` as document input when it is a file for which `registry.for_path(PATH)` gives a backend that satisfies `DocumentValidator` (`backend-protocol`, "Document sets and container round trips"), or a folder that holds exactly one file such a backend detects as a project file (its `documents(folder)` gives a set) and no `.kicad_pro` and no `.kicad_pcb` file. A folder that holds a KiCad project or board and files of such a backend without exactly one project file stays KiCad input. A folder that holds both a KiCad project or board and such a project file MUST exit 2 with `FEN-2001` and a hint that names both. Document input MUST be checked by `fenolite.checks.documents.run_document_checks` ("Document check pipeline"), `--stages` MUST then select a subset of `DOCUMENT_STAGES`, no oracle MUST be built and no subprocess MUST run, and `--kicad-cli` and `--timeout` MUST be accepted and ignored. Its result and exit codes are those of `altium-verification`, "Check on Altium inputs".
- **Flags.** `--stages a,b` MUST select a subset of `STAGE_ORDER`; an unknown or empty stage name MUST exit 2 with `FEN-2001`. `--kicad-cli PATH` MUST be passed to `find_kicad_cli` as the explicit path. `--timeout SECONDS` MUST default to 300 and MUST be passed to `KicadCli`.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the board's folder, and native otherwise. Built input MUST load its model with `model.canonical.load_dir(<root>/.fenolite)`. The board's `generator` atom MUST NOT decide it.
- **Injection.** The command MUST narrow `registry.for_path(board)` with `isinstance(backend, Validator)` (`Validator` is `@runtime_checkable`), exit 2 with `FEN-2001` when no backend validates the board, and pass the narrowed backend as the `Validator` and `KicadOracle(KicadCli(path, timeout=…))` as the `Oracle` to `fenolite.checks.stages.run_checks`. It MUST build the oracle only when a stage of `ORACLE_STAGES` is selected ("Stages added for findings and round trips").
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

### Requirement: ERC lite stage
`checks.erc_lite` SHALL define `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`, `erc_lite(design) -> tuple[Issue, ...]`, `erc_stage(design) -> StageResult`, `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`) and `REMOVE_IN = (0, 2)`. In `run_checks` the stage MUST run on built input only; on native input it MUST be skipped with reason `native-input`. In `run_document_checks` the same rules run on the built model, or on the reading of the schematic documents ("Document check pipeline").
- `erc.lite.output-conflict`: a net with two or more member pins whose `etype` is `output` or `power_out`.
- `erc.lite.power-undriven`: a net with a `power_in` member pin and no `power_out` member pin, whose id is not a value of the `members` of any `Interface` with `kind == "power"` (c0011's `Power(hv, lv)`, which acts as a power flag).
- `erc.lite.floating-pin`: a pin whose `etype` is not `no_connect`, that no net lists and that `Circuit.no_connects` does not list (`design-model`, "No-connect marks in the circuit model"), reported once per pin. A mark is matched by `PinRef(<component id>, <pin number>)`, the form the builds store.
- The three rules MUST NOT report a marked pin that a net also lists: that is `model.no-connect-on-net`, a finding of `Design.validate()` and of the `model.validate` stage.
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

#### Scenario: Marked pin is not floating
- **GIVEN** a model whose component `U1` has the `input` pins `11`, `12` and `13` on no net, and whose `Circuit.no_connects` holds `PinRef(<U1 id>, "11")` and `PinRef(<U1 id>, "12")`
- **WHEN** `uv run pytest tests/unit/checks -k "erc_lite and no_connect"` runs `erc_lite`
- **THEN** it reports exactly one `erc.lite.floating-pin`, whose `where` is `U1-13`

#### Scenario: Marked pins of a built project
- **GIVEN** a blink variant with `U1` of `Mini:Mini_QFP32_IC` whose supply pins are connected and whose remaining pins are all marked with `no_connect`, built with `--confirm` into `B`
- **WHEN** `fenolite check B --stages erc.lite --json` runs
- **THEN** the exit code is 0 and no `erc.lite.floating-pin` issue names `U1`

#### Scenario: Rules run on a schematic reading
- **GIVEN** a fake `DocumentValidator` whose schematic reading holds a component `U1` with the `input` pins `1` and `2`, pin `1` on a net with a `power_out` pin and pin `2` on no net
- **WHEN** `uv run pytest tests/unit/checks/test_documents.py -k erc_native` calls `run_document_checks` with `stages=("erc.lite",)` and `built=False`
- **THEN** `erc.lite` has status `ok` and exactly one `erc.lite.floating-pin` warning, whose `where` is `U1-2`
