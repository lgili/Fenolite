# backend-protocol Specification

## Purpose
Define what every file-format backend offers, independent of any one backend: the `Backend` protocol (detect, read, capabilities), read results that hold a `Design` or a `Library`, capability reports that list only implemented operations, and the registry through which the CLI, checks and placement reach backends. Module: `fenolite.backends.base` and `fenolite.backends.registry`.
## Requirements
### Requirement: Backend protocol
`fenolite.backends.base` SHALL define `Backend` as a `typing.Protocol` with the attribute `name: str` and the methods `detect(path) -> bool`, `read(path, *, issues=None) -> ReadResult` and `capabilities() -> CapabilityReport`.
- `backends.base` MUST import only `core` and `model`.
- `detect` MUST decide from the path alone, without reading the file.
- `read` MUST append warnings and infos to `issues` when a list is given, and MUST raise errors as exceptions that carry a registered `cli_code` or are `FormatError`s.
- The KiCad backend, `fenolite.backends.kicad.backend.KicadBackend`, MUST satisfy the protocol with `name == "kicad"`.

#### Scenario: KiCad backend satisfies the protocol
- **GIVEN** a function annotated to take a `Backend`
- **WHEN** `uv run pyright src` checks a call that passes `KicadBackend()`
- **THEN** it reports no error

#### Scenario: Detection by name
- **WHEN** `KicadBackend().detect` is called on `Path("a.kicad_pcb")`, `Path("a.kicad_mod")`, `Path("a.kicad_sym")`, an existing folder `Lib.kicad_symdir` and `Path("a.txt")`
- **THEN** it returns `True`, `True`, `True`, `True` and `False`, and no file is opened

#### Scenario: Base module stays neutral
- **GIVEN** `src/fenolite/backends/base.py` imports `fenolite.backends.kicad`, which `package-layering` alone would allow
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k base_imports` runs
- **THEN** the test fails naming `fenolite.backends.kicad` and stating that `base` imports only `core` and `model`

### Requirement: Read results
`read` SHALL return `ReadResult(content, issues, evidence)`.
- `content` MUST be a `Design` for a board file, and a `Library` for a footprint file or a symbol library (file or `.kicad_symdir` folder).
- The property `design` MUST return `content` when it is a `Design`, and MUST raise `TypeError` otherwise.
- For a board, `issues` MUST be the reader's issues followed by the issues of `design.validate()`.
- `evidence` MUST be the reader module's `EVIDENCE`.

#### Scenario: Board read through the backend
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `KicadBackend().read(path)` is called
- **THEN** `result.design.board.footprints` has two entries, no issue has severity `error`, and `result.evidence.level` is `INFERRED`

#### Scenario: Footprint read through the backend
- **GIVEN** `tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod`
- **WHEN** `KicadBackend().read(path)` is called
- **THEN** `result.content` is a `Library` holding one `FootprintDef` named `Mini_R_0603`, and reading `result.design` raises `TypeError`

### Requirement: Capability reports
`capabilities()` SHALL return `CapabilityReport(name, read_kinds, write_kinds, targets, default_target, downgrade, operations, evidence)`, and `CapabilityReport.to_json()` SHALL return a JSON-compatible mapping with exactly these keys, `evidence` written as `{level, oracle, hypotheses}`. Each field MUST describe what the backend implements when the report is made, so that the report stays true as later changes add writers:
- `operations` MUST list exactly the operations the backend implements, from `detect`, `read`, `write`, `lower` and `validate`. `detect` and `read` MUST always be listed.
- `read_kinds` MUST list exactly the file kinds that `read` accepts. The KiCad report MUST contain `kicad_pcb`, `kicad_mod` and `kicad_sym`.
- `write_kinds` MUST list exactly the file kinds the backend can write. While it is empty, `write` MUST NOT be in `operations`, `targets` MUST be empty and `default_target` MUST be `None`.
- `downgrade` MUST be `"unsupported"` unless the backend can write a file read at a newer version for an older target.
- `evidence` MUST be what the backend's operations return for an arbitrary file, not the level of the best-tested case. The KiCad report's evidence MUST be `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`, computed and not written as a literal.
- For every registered backend, each hypothesis the report names MUST be a row of `docs/hypotheses.md` that is not refuted, and the report's level MUST NOT be stronger than the level of any of those rows. The level MAY be weaker than every row: a row states what its test covered, and the report states what holds for any file. `tests/unit/test_capability_evidence.py` SHALL check both rules with `report_problems(evidence, rows)`, which returns one message per problem.

#### Scenario: KiCad capability report
- **WHEN** `KicadBackend().capabilities().to_json()` is called
- **THEN** it has exactly the eight keys, `name` is `kicad`, `read_kinds` contains `kicad_pcb`, `kicad_mod` and `kicad_sym`, `operations` contains `detect` and `read`, and the evidence level is `INFERRED`

#### Scenario: Unavailable operations are visible
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks its report
- **THEN** every listed operation is a method of the backend, and a backend with an empty `write_kinds` lists no `write`, has empty `targets` and has `default_target` `None`, so an agent knows it cannot write

#### Scenario: Report follows its operations
- **WHEN** `uv run pytest tests/unit/test_capability_evidence.py -k operations` compares `KicadBackend().capabilities().evidence` with `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`
- **THEN** they are equal, and the source of `backends/kicad/backend.py` holds no `Level.` literal

#### Scenario: Report stronger than the register
- **GIVEN** an evidence of level `KICAD-VERIFIED` that names `H-K-PCB-READ`, and a register in which that row is `CORPUS-VERIFIED`
- **WHEN** `report_problems(evidence, rows)` is called
- **THEN** it returns one problem naming `H-K-PCB-READ`, `KICAD-VERIFIED` and `CORPUS-VERIFIED`

#### Scenario: Unregistered or refuted hypothesis
- **GIVEN** an evidence that names an id with no row, and one that names a row whose result starts with `refuted`
- **WHEN** `report_problems(evidence, rows)` is called for each
- **THEN** each call returns one problem naming the id

#### Scenario: Live reports agree with the register
- **WHEN** `uv run pytest tests/unit/test_capability_evidence.py -k live` checks every backend of `registry.all_backends()` against `docs/hypotheses.md`
- **THEN** it finds no problem

### Requirement: Backend registry
`fenolite.backends.registry` SHALL provide `register(backend)`, `get(name)`, `all_backends()` and `for_path(path)`.
- The built-in KiCad backend MUST be registered on the first call to any of them. Its module MUST be imported inside a function, not at module import.
- `register` MUST raise `ValueError` for a name already registered.
- `get` MUST raise `KeyError` naming the known backends for an unknown name.
- `all_backends()` MUST return the backends sorted by name.
- `for_path` MUST return the first backend, in that order, whose `detect` returns `True`, or `None`.

#### Scenario: Built-in backend listed
- **WHEN** `registry.all_backends()` is called in a fresh interpreter
- **THEN** it returns one backend whose `name` is `kicad`

#### Scenario: Duplicate registration
- **WHEN** a second backend named `kicad` is registered
- **THEN** `ValueError` is raised naming `kicad`

#### Scenario: Unknown backend
- **WHEN** `registry.get("nope")` is called
- **THEN** `KeyError` is raised and its message names `kicad`

#### Scenario: Backend for a path
- **WHEN** `registry.for_path(Path("a.kicad_pcb"))` and `registry.for_path(Path("a.txt"))` are called
- **THEN** the first returns the KiCad backend and the second returns `None`

### Requirement: Backend modules in the layering test
`tests/unit/test_import_graph.py` SHALL check `backends/base.py` and `backends/registry.py` against the `backends` row of `package-layering` ("`backends` (its top-level modules such as `base` and `registry`) → `model`, `geometry`, any `backends.<x>`"). It MUST NOT report them as absent from the layering table. Every other `backends.<x>` MUST still be checked against the `backends.<x>` row.

#### Scenario: Registry may import the KiCad backend
- **GIVEN** `backends/registry.py` imports `fenolite.backends.kicad.backend` inside a function, and `backends/base.py` imports `fenolite.model`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes

#### Scenario: A backend may not import another backend
- **GIVEN** a module under `backends/kicad/` imports `fenolite.backends.other`
- **WHEN** the test runs
- **THEN** it fails naming `backends.kicad → backends.other`

### Requirement: Write capability fields
`fenolite.backends.base` SHALL provide the frozen dataclass `WriteResult(text: str, issues: tuple[Issue, ...] = ())`, the neutral result of a backend writer. A backend whose `CapabilityReport.write_kinds` is not empty MUST also report:
- `targets`: the tool versions it writes for, oldest first;
- `default_target`: the target used when the caller names none, which MUST be one of `targets`;
- `downgrade`: `"unsupported"` when a file read at a newer version cannot be written for an older target, or `"supported"`.

A backend that lists `"write"` in `operations` MUST have a non-empty `write_kinds` and MUST provide `write(design, *, target=None, allow_lossy=False) -> WriteResult`, which writes the design's board for `target` (`default_target` when `None`) and never writes a file. A backend with a non-empty `write_kinds` MUST list `"write"` in `operations`. A backend that lists `"lower"` in `operations` MUST provide `lower(design, *, name, target=None, allow_lossy=False, issues=None) -> dict[str, str]`, which returns the coherent set of files for `design` (file name → text) for `target` (`default_target` when `None`), appends its warnings and infos to `issues` when a list is given, and never writes a file; a backend MAY accept further keyword arguments.

The KiCad backend MUST include `"kicad_pcb"` in `write_kinds`, MUST report `targets == (9, 10)`, `default_target == 10` and `downgrade == "unsupported"`, MUST list `"detect"`, `"read"`, `"write"` and `"lower"` in `operations`, MUST list `"validate"` exactly when it satisfies `Validator` ("Validation operation"), as "Capability reports" requires, and MUST list no other operation it does not implement. The order of the tuple is not pinned. `KicadBackend.write` MUST return what `fenolite.backends.kicad.pcb.write_board` returns for the same arguments. Later writers add their kinds to the same tuple. These values replace the pre-writer values of c0009 (`write_kinds == ()`, `targets == ()`, `default_target is None`, `operations == ("detect", "read")`) and the exact tuple `("detect", "read", "write")` of c0017. `KicadBackend.lower` MUST return what `fenolite.backends.kicad.triad.write_triad` returns for the same arguments (c0010, "Generated projects are coherent"). `fenolite capabilities` MUST show them for the `kicad` entry of `result.backends`.

#### Scenario: KiCad write fields in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `kicad` entry of `result.backends` has `"kicad_pcb"` in `write_kinds`, `targets == [9, 10]`, `default_target == 10`, `downgrade == "unsupported"`, and its `operations` contain `"detect"`, `"read"`, `"write"`, `"lower"` and `"validate"`

#### Scenario: Write operation advertised and implemented
- **GIVEN** `KicadBackend()` and the created test board `tests/_boards.py::created_board()`
- **WHEN** an agent finds `"write"` in `capabilities().operations` and calls `backend.write(design)`
- **THEN** it returns a `WriteResult` equal to `write_board(design, target=10)`, `"lower"` is listed and `backend.lower` is callable, and every other entry of `operations` names a callable method of the backend

#### Scenario: Later operations by membership
- **GIVEN** `KicadBackend()` once `KicadBackend.validate` exists
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k capability_write_advertised` reads `capabilities().operations`
- **THEN** it contains `lower` and `validate`, and `backend.lower` and `backend.validate` are callable

#### Scenario: Default target among the targets
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k capability` checks their reports
- **THEN** each backend with a non-empty `write_kinds` has `default_target in targets`

#### Scenario: Write result is immutable
- **GIVEN** `WriteResult(text="(kicad_pcb)\n")`
- **WHEN** code assigns `result.text = ""`
- **THEN** a `FrozenInstanceError` is raised

### Requirement: Neutral DRC report
`fenolite.backends.base` SHALL provide the frozen dataclasses `DrcItem(uuid, description, position)`, `DrcViolation(type, description, severity, items, excluded, comment)` and `DrcReport(source, date, kicad_version, coordinate_units, violations, unconnected_items, schematic_parity, ignored_checks, included_severities)`.
- `position` MUST be a `Point` in integer nanometres, and `DrcItem` MUST raise `TypeError` for a coordinate that is not an `int`.
- `type` and `severity` MUST be the tool's own strings, and violations MUST keep the order of the report.
- `DrcReport.of_type(type)` MUST return the violations, unconnected items and parity items whose `type` equals the argument, in report order.
- `fenolite.backends.base` MUST NOT import any `fenolite.backends.<x>` module, so `checks` can receive reports by injection without importing a backend.

#### Scenario: Violations by type
- **GIVEN** a `DrcReport` with two `clearance` violations and one `lib_footprint_mismatch` violation
- **WHEN** `report.of_type("lib_footprint_mismatch")` is called
- **THEN** it returns the one violation

#### Scenario: Integer positions only
- **WHEN** `DrcItem(uuid="u", description="d", position=Point(1.5, 0))` is constructed
- **THEN** a `TypeError` is raised

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

### Requirement: Validation operation
`fenolite.backends.base` SHALL define the neutral validation types, so that `checks` can validate a file without importing a backend:
- `RoundTrip(level: Literal["RT1"], passed: bool, tree_equal: bool, model_equal: bool, opaque_equal: bool, opaque_count: int, difference: str = "")`, a frozen dataclass. `passed` MUST equal `tree_equal and model_equal and opaque_equal`, and construction MUST raise `ValueError` otherwise.
- `Validation(read: ReadResult, roundtrip: RoundTrip)`, a frozen dataclass.
- `Validator`, a `@runtime_checkable` `typing.Protocol` with `name: str` and `validate(path, *, issues=None) -> Validation`. `validate` MUST raise the reader's `FormatError` (its subclasses included, such as `UnsupportedFormatError`, `FEN-3003`) for a file it cannot read, and `ValueError` naming the kind for a file kind it cannot validate. A caller holding a `Backend` MUST narrow it with `isinstance(backend, Validator)` before calling `validate`.

A backend that lists `"validate"` in `operations` MUST satisfy `Validator`. `src/fenolite/backends/kicad/backend.py` MUST hold the typed statement `_VALIDATOR: Validator = KicadBackend()`, which `pyright` checks. The KiCad backend MUST list `"validate"` in its `operations`, beside the operations that earlier changes added (as "Write capability fields" states). The pinned capability tests (`tests/unit/backends/test_registry.py`, `tests/unit/backends/test_base_types.py`, `tests/unit/cli/test_capabilities_backends.py`) MUST be updated in the same commit.

#### Scenario: KiCad backend is a validator
- **GIVEN** the statement `_VALIDATOR: Validator = KicadBackend()` in `backends/kicad/backend.py`, and the `isinstance(backend, Validator)` narrowing in `cli/cmd_check.py`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Validate advertised
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the `operations` of the `kicad` entry of `result.backends` contain `validate`

#### Scenario: Advertised operation implemented
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks its report
- **THEN** every backend that lists `validate` has a callable `validate` method

#### Scenario: Inconsistent round trip refused
- **WHEN** `RoundTrip(level="RT1", passed=True, tree_equal=False, model_equal=True, opaque_equal=True, opaque_count=0)` is constructed
- **THEN** a `ValueError` is raised

### Requirement: Oracle protocol
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for a DRC verdict:
- `SkippedFile(name: str, reason: Literal["outside-root", "variable", "relative", "missing", "nested-table", "too-large", "reserved-name"])`.
- `ProjectSet(root: Path, board: str, files: Mapping[str, Path], skipped: tuple[SkippedFile, ...] = (), has_project: bool = False, has_rules: bool = False)`. `files` MUST map POSIX names relative to `root` to source paths, and `board` MUST be a key of `files`; construction MUST raise `ValueError` otherwise.
- `CanaryState = Literal["fired", "absent", "inconclusive", "not-applicable"]`.
- `DrcOutcome(report: DrcReport | None, tool_version: str, canary: CanaryState, canary_reason: str = "", canary_removed: int = 0, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `report` MUST be `None` when the tool wrote no report, and MUST otherwise hold no violation or unconnected item that names a canary uuid. `message` MUST be the first sanitised line of the tool's stderr.
- `Oracle`, a `typing.Protocol` with `name: str`, `version() -> str` and `drc(project: ProjectSet) -> DrcOutcome`. `drc` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out.

These types MUST be frozen dataclasses. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `Oracle` with `name == "kicad"`.

#### Scenario: KiCad oracle satisfies the protocol
- **GIVEN** the call of `run_checks` in `cli/cmd_check.py`, whose `oracle` parameter is typed `Oracle | None`, passing `KicadOracle(KicadCli(path, timeout=…))`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Board outside the files
- **WHEN** `ProjectSet(root=Path("p"), board="a.kicad_pcb", files={})` is constructed
- **THEN** a `ValueError` naming `a.kicad_pcb` is raised

#### Scenario: Fake oracle without a backend
- **GIVEN** a fake `Oracle` defined in `tests/unit/checks/`, which imports only `fenolite.backends.base`
- **WHEN** `uv run pytest tests/unit/checks tests/unit/test_import_graph.py` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

#### Scenario: Outcome is immutable
- **GIVEN** `DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")`
- **WHEN** code assigns `outcome.canary = "fired"`
- **THEN** a `FrozenInstanceError` is raised

### Requirement: Netlist and round-trip oracles
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for its netlist export and for the reports of an RT2 run, without importing a backend:
- `PadAssignment(element: str, net: str)`: `element` is `REF-PIN` (a component reference, `-`, a pad or pin number); `net` is the source's own label for the element's net, `""` for no net.
- `Uncovered(element: str, reason: str)`: an element that a source names but does not assign, with the reason.
- `PadNetList(source: str, assignments: tuple[PadAssignment, ...], uncovered: tuple[Uncovered, ...] = ())`. Construction MUST raise `ValueError` when an element is both assigned and uncovered.
- `NetlistOutcome(netlist: PadNetList | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `netlist` MUST be `None` when the tool wrote no export, and `message` MUST then be the first sanitised line of the tool's stderr or of the parse error.
- `Rt2Outcome(before: tuple[DrcReport, ...], after: DrcReport | None, normalised: bool, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence(), repeats: tuple[DrcReport, ...] = ())`. `before` MUST hold the reports of the runs on the original in run order: two, more when the oracle repeated them, and fewer when a run wrote no report. `after` is the report of the first run on the re-dump, and `repeats` the reports of the further runs on the re-dump.
- `DrcReport.entries()` MUST return the violations and unconnected items as a sorted tuple of `(group, type, severity, excluded, items)`, with `group` `violations` or `unconnected_items` and each item as `(description, x, y)`. Item uuids and the report order MUST be left out, so that two runs of a tool on one file can be compared.
- `NetlistOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `netlist(project: ProjectSet, *, board: Design) -> NetlistOutcome`.
- `RoundTripOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `rt2(project: ProjectSet) -> Rt2Outcome`.

The types MUST be frozen dataclasses. `netlist` and `rt2` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out. c0013's `Oracle` protocol is unchanged: a caller narrows an `Oracle` with `isinstance(oracle, NetlistOracle)` or `isinstance(oracle, RoundTripOracle)` before calling the new methods. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `Oracle`, `NetlistOracle` and `RoundTripOracle`, and `oracle.py` MUST hold a typed function that returns a `KicadOracle` as each of the three, which `pyright` checks.

#### Scenario: KiCad oracle satisfies the three protocols
- **GIVEN** the typed function in `src/fenolite/backends/kicad/oracle.py` that returns a `KicadOracle` as `Oracle`, `NetlistOracle` and `RoundTripOracle`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Element assigned and uncovered
- **WHEN** `PadNetList(source="export", assignments=(PadAssignment("R1-1", "VIN"),), uncovered=(Uncovered("R1-1", "not-exported"),))` is constructed
- **THEN** a `ValueError` naming `R1-1` is raised

#### Scenario: Narrowing a drc-only oracle
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements only `name`, `version` and `drc`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k oracle_protocols` checks it
- **THEN** `isinstance(fake, NetlistOracle)` and `isinstance(fake, RoundTripOracle)` are false, and both are true for a fake that also implements `netlist` and `rt2`

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/checks` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

#### Scenario: Outcomes are immutable
- **GIVEN** `Rt2Outcome(before=(), after=None, normalised=False, tool_version="9.0.9")`
- **WHEN** code assigns `outcome.normalised = True`
- **THEN** a `FrozenInstanceError` is raised

#### Scenario: Entries leave out uuids and order
- **GIVEN** two reports holding the same two violations in another order and with other item uuids
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k entries` compares `entries()`
- **THEN** they are equal, and a report with one violation fewer gives other entries

### Requirement: Board-frame protocol
`fenolite.backends.base` SHALL define the plain-data records through which `checks`, `placement` and `lens` read the board-frame geometry of a design without importing a backend, and the protocol `BoardFrame` that computes them:
- `PadCopper(layer: str, core: tuple[Point, ...], width: Nm, filled: bool = False, exact: bool = True)`: the copper of a pad on one copper layer, the set of points within `width / 2` of the core, boundary included. The core MUST be one point (a disc of diameter `width`), two or more points with `filled` false (an open polyline of closed segments; a closed outline repeats its first point at its end), or three or more points with `filled` true (the region that a ring accepted by `Polygon` encloses under the non-zero rule, the ring in the normal form of `geometry-kernel`, "Polygons with holes and a normal form"). `exact` is false when the entry is a conservative superset of the pad's copper.
- `BoardPad(footprint_id: str, ref: str, path: str, pad_id: str, number: str, kind: PadKind, position: Point, rotation: Udeg, side: Side, layers: tuple[str, ...], net_id: str | None, net: str | None, copper: tuple[PadCopper, ...] = (), hole: tuple[Point, ...] = (), drill: Nm | None = None)`.
- `PlacedExtent(footprint_id: str, side: Side, front: tuple[tuple[Point, ...], ...] = (), back: tuple[tuple[Point, ...], ...] = (), source: Literal["courtyard", "definition", "pads", "none"] = "none", exact: bool = True)`, whose property `own` MUST return `front` on the `top` side and `back` on the `bottom` side. Each ring is a ring that `Polygon` accepts, in the normal form.
- `BoardFrame`, a `@runtime_checkable` `typing.Protocol` with `board_pads(design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]` and `placed_extents(design: Design, *, issues: list[Issue] | None = None) -> tuple[PlacedExtent, ...]`.

The records MUST be frozen dataclasses with slots whose field types are builtins, `typing` constructs, `fenolite.core` types and `fenolite.model` types only. `PadCopper` MUST raise `ValueError` for an empty core, a negative width, a core of one point with width 0, and a filled core of fewer than three points: the cores that c0029's `Thick` refuses and that `backends.base` can check without `geometry`. `backends.base` MUST still import only `core` and `model`.

`KicadBackend` MUST satisfy `BoardFrame` through `board-frame` ("Board-frame module"), and `backends/kicad/backend.py` MUST hold the statement `_FRAME: BoardFrame = KicadBackend()`, which pyright checks. `board_pads` and `placed_extents` are not operations: `CapabilityReport.operations` stays the closed list of "Capability reports", and the pinned capability tests pass unchanged.

#### Scenario: KiCad backend is a board frame
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k board_frame` checks `isinstance(KicadBackend(), BoardFrame)` and `KicadBackend().capabilities().operations`
- **THEN** the first is true, and the operations name neither `board_pads` nor `placed_extents`

#### Scenario: Base module stays neutral
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k base_imports` runs
- **THEN** it passes, `backends/base.py` importing only `core` and `model`

#### Scenario: Records are plain data
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k frame_records` reads `typing.get_type_hints` of `PadCopper`, `BoardPad` and `PlacedExtent`, and builds `PadCopper("F.Cu", (), 0)`, `PadCopper("F.Cu", (Point(0, 0),), -1)`, `PadCopper("F.Cu", (Point(0, 0),), 0)` and `PadCopper("F.Cu", (Point(0, 0), Point(1, 0)), 0, filled=True)`
- **THEN** every annotation names only builtins, `typing` constructs, `fenolite.core` or `fenolite.model` types, and the four constructions raise `ValueError`

#### Scenario: Own face by side
- **GIVEN** `PlacedExtent("fp_x", "bottom", front=(), back=((Point(0, 0), Point(10, 0), Point(10, 10)),))`
- **WHEN** `own` is read
- **THEN** it equals `back`

### Requirement: Design rules source
`fenolite.backends.base` SHALL define the frozen dataclass `DesignRules(design: Design, min_clearance: Nm | None = None, rules_over_classes: bool = True, floor_over_rules: bool = False, opaque_clearance_rules: int = 0, unread: tuple[tuple[str, str], ...] = (), evidence: Evidence = Evidence())` and the `@runtime_checkable` protocol `DesignRulesSource` with the method `design_rules(design: Design, project: ProjectSet, *, issues: list[Issue] | None = None) -> DesignRules`. Through it, `checks` reaches the clearance rules that a project's own files hold, without importing a backend.
- `DesignRules.design` MUST be `design` with the net classes, the class of each net and the design rules that the project's files give; what a missing or unread file would give MUST keep `design`'s own value.
- `min_clearance` MUST be the project's board minimum clearance in nm, or `None`. `rules_over_classes` and `floor_over_rules` MUST say, for the tool version the board is judged against, whether a governing custom clearance rule replaces the class clearances and whether the board minimum also raises rule values (`copper-check`, "Clearance in force"). `opaque_clearance_rules` MUST count the project's clearance rules that could not be lifted into the model. `unread` MUST name each project file that failed to read, with the error's message, in file-name order.
- `design_rules` MUST NOT raise for a file that fails to read, and MUST append the readers' warnings and infos to `issues` when a list is given.
- `design_rules` is not an operation: `CapabilityReport.operations` stays the closed list of "Capability reports".
- `KicadBackend` MUST satisfy `DesignRulesSource` (`kicad-file-backend`, "Design rules for the copper check"), and `backends/kicad/backend.py` MUST hold the statement `_RULES_SOURCE: DesignRulesSource = KicadBackend()`, which pyright checks.
- `backends.base` MUST still import only `core` and `model`.

#### Scenario: KiCad backend is a rules source
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k rules_source` checks `isinstance(KicadBackend(), DesignRulesSource)` and `KicadBackend().capabilities().operations`
- **THEN** the first is true, and the operations do not name `design_rules`

#### Scenario: Unread file reported, not raised
- **GIVEN** a project set whose `<stem>.kicad_pro` holds the text `{`
- **WHEN** `KicadBackend().design_rules(design, project)` is called
- **THEN** no exception is raised, `unread` holds one entry naming `<stem>.kicad_pro`, and `DesignRules.design.circuit.netclasses` equals `design.circuit.netclasses`

#### Scenario: Base module stays neutral
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k base_imports` runs
- **THEN** it passes, `backends/base.py` importing only `core` and `model`

