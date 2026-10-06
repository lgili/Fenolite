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
- The built-in backends, KiCad (`kicad`) and Altium (`altium`, `fenolite.backends.altium.backend.AltiumBackend`, change c0043), MUST be registered on the first call to any of them. Their modules MUST be imported inside a function, not at module import. Registering the Altium backend MUST NOT import a reader, the adapter or a writer: `backends/altium/backend.py` imports them inside `read`.
- `register` MUST raise `ValueError` for a name already registered.
- `get` MUST raise `KeyError` naming the known backends for an unknown name.
- `all_backends()` MUST return the backends sorted by name.
- `for_path` MUST return the first backend, in that order, whose `detect` returns `True`, or `None`. No path MUST be detected by two built-in backends.

#### Scenario: Built-in backends listed
- **WHEN** `registry.all_backends()` is called in a fresh interpreter
- **THEN** it returns two backends whose names are `altium` and `kicad`, in that order

#### Scenario: Registration stays cheap
- **WHEN** a fresh interpreter calls `registry.all_backends()` and then lists `sys.modules`
- **THEN** no module under `fenolite.backends.altium.read` or `fenolite.backends.altium.adapter` is loaded

#### Scenario: Duplicate registration
- **WHEN** a second backend named `kicad` is registered
- **THEN** `ValueError` is raised naming `kicad`

#### Scenario: Unknown backend
- **WHEN** `registry.get("nope")` is called
- **THEN** `KeyError` is raised and its message names `altium` and `kicad`

#### Scenario: Backend for a path
- **WHEN** `registry.for_path(Path("a.kicad_pcb"))`, `registry.for_path(Path("a.PcbDoc"))` and `registry.for_path(Path("a.txt"))` are called
- **THEN** the first returns the KiCad backend, the second the Altium backend and the third `None`

#### Scenario: Detection is disjoint
- **GIVEN** one path per suffix that a built-in backend detects
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k disjoint` asks every built-in backend
- **THEN** exactly one backend detects each path

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
- `DrcOutcome(report: DrcReport | None, tool_version: str, canary: CanaryState, canary_reason: str = "", canary_removed: int = 0, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence(), parity_judged: bool = False)`. `report` MUST be `None` when the tool wrote no report, and MUST otherwise hold no violation or unconnected item that names a canary uuid. `message` MUST be the first sanitised line of the tool's stderr; when the run asked for the comparison with the schematic and the tool did not make it, it MUST be the line the tool gave for that. `parity_judged` MUST be true exactly when the run asked the tool to compare the board with its schematic and the tool did so.
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

#### Scenario: Parity flag defaults to false
- **WHEN** `DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")` is constructed
- **THEN** its `parity_judged` is `False`

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

### Requirement: Evidence matrix rows
`fenolite.backends.base` SHALL provide `MATRIX_OPERATIONS == ("detect", "read", "write", "roundtrip_exact", "roundtrip_modified")` and the frozen dataclass `MatrixRow(backend: str, kind: str, detect: Evidence | None = None, read: Evidence | None = None, write: Evidence | None = None, roundtrip_exact: Evidence | None = None, roundtrip_modified: Evidence | None = None, experimental: tuple[str, ...] = ())`. A row states what one backend package does with one file kind and how well each operation is verified. A cell that is `None` means that the package does not implement that operation for that kind.
- The cells mean:
  - `detect`: the package names the kind of a file from its name or its content;
  - `read`: a reader of the package builds a model object from a file of the kind;
  - `write`: a writer of the package produces a file of the kind from a model object that Fenolite created;
  - `roundtrip_exact`: a file of the kind that is read and written back for the same version, with no change in between, keeps its whole content, modelled or not;
  - `roundtrip_modified`: a file of the kind that is read, changed through the model and written keeps everything the change did not touch, or the write is refused.
- Construction MUST raise `ValueError` when `roundtrip_exact` is set without `read`, when `roundtrip_modified` is set without both `read` and `write`, and when `experimental` names anything but an operation whose cell is set, or names one twice.
- `verified_by() -> tuple[str, ...]` MUST return the hypothesis ids of the cells that are set, each once, sorted.
- `to_json()` MUST return a mapping with exactly the keys `backend`, `kind`, the five operations, `verified_by` and `experimental`. Each operation is `Evidence.label()` of its cell, or `None`. `experimental` lists its operations in the order of `MATRIX_OPERATIONS`.
- Every package `fenolite.backends.<name>` MUST provide the module `claims` with `MATRIX: tuple[MatrixRow, ...]`, whose rows all have `backend == <name>` and distinct kinds. Every cell MUST be an evidence constant of a module of that package, or `Evidence.combine` of such constants: `claims.py` MUST NOT name `Level` and MUST call `Evidence` only as `Evidence.combine`. A level therefore changes in one place, the module that owns the claim. A `claims` module imports `fenolite.backends.base`, `fenolite.core.evidence` and modules of its own package; the rule that the Altium writer modules import only `fenolite.core` and `fenolite.model` (`altium-schematic-writer`) does not apply to `altium/claims.py`, as it does not apply to `altium/backend.py`.
- `fenolite.backends.matrix.packages() -> tuple[str, ...]` MUST return the dotted names of the sub-packages of `fenolite.backends` (`fenolite.backends.kicad`), sorted, and `fenolite.backends.matrix.rows() -> tuple[MatrixRow, ...]` MUST return the rows of every package, sorted by `(backend, kind)`. `rows()` MUST run no external tool and read no file but the modules it imports. Importing `fenolite.backends.matrix` MUST NOT import a backend package; `rows()` imports them. `backends/matrix.py` is a top-level module of `backends`, like `base` and `registry`, and `tests/unit/test_import_graph.py` MUST check it against the `backends` row of `package-layering` ("Backend modules in the layering test").
- For every backend of `registry.all_backends()`, every kind of its report's `read_kinds` MUST have a row with `detect` and `read` set, and the kinds whose `write` is set and not experimental MUST be exactly the report's `write_kinds` ("Capability reports"). A kind MAY have `read` set without being in `read_kinds`: the package then has a reader that `Backend.read` does not dispatch.
- The `kicad_pcb` row MUST have `read` equal to `pcb.EVIDENCE`, `write` equal to `pcb.WRITE_EVIDENCE`, `roundtrip_exact` equal to `pcb.EVIDENCE` (RT1; `kicad-file-backend`, "Round-trip verdict") and `roundtrip_modified` equal to `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`, which is the evidence of the KiCad capability report.
- The `kicad` rows MUST include `kicad_lib_table` (the files `fp-lib-table` and `sym-lib-table`) with `read` equal to `libs.EVIDENCE` and `write` equal to `libs.WRITE_EVIDENCE`, and the KiCad report's `write_kinds` MUST contain `kicad_lib_table` ("Write capability fields": later writers add their kinds). The `kicad_sym` row MUST have `write` equal to `sym.WRITE_EVIDENCE` and listed in `experimental` while no register row covers `sym.write_symbol_library`.
- The `altium` rows MUST include one row for every write kind of the experimental features (`cli-contract`, "Experimental features in capabilities"), each with `write` set and listed in `experimental`. Since change c0043 `altium` is a registered backend, so every kind of its `read_kinds` also has `detect` and `read` set: `read` combines the reader's constant with `import_evidence.EVIDENCE`, and `detect` is `import_evidence.EVIDENCE`, the evidence of the backend's report. The `specctra` rows MUST include `specctra_dsn` with `write` set and `specctra_ses` with `read` set.
- A cell whose level is `INFERRED` MUST name at least one hypothesis, and a cell whose level is `UNVERIFIED` MUST be listed in its row's `experimental`.

#### Scenario: Row as JSON
- **GIVEN** `MatrixRow("kicad", "kicad_wks", read=Evidence(Level.INFERRED, hypotheses=("H-K-WKS-CORNER",)), write=Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-WKS-CORNER", "H-K-PCB-WRITE")), experimental=("write",))`
- **WHEN** `uv run pytest tests/unit/backends/test_matrix_row.py -k json` calls `to_json()`
- **THEN** the mapping has exactly the nine keys, `detect`, `roundtrip_exact` and `roundtrip_modified` are `None`, `read` is `INFERRED`, `write` is `KICAD-VERIFIED`, `verified_by` is `["H-K-PCB-WRITE", "H-K-WKS-CORNER"]`, and `experimental` is `["write"]`

#### Scenario: Impossible rows are refused
- **WHEN** a row is built with `roundtrip_exact` set and `read` unset, with `roundtrip_modified` set and `write` unset, with `experimental=("write",)` and `write` unset, and with `experimental=("read", "read")`
- **THEN** each construction raises `ValueError`

#### Scenario: Board row follows its constants
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k board_row` looks up the `kicad_pcb` row of `rows()`
- **THEN** `read` is `pcb.EVIDENCE`, `write` is `pcb.WRITE_EVIDENCE`, `roundtrip_exact` is `pcb.EVIDENCE`, and `roundtrip_modified` equals `KicadBackend().capabilities().evidence`

#### Scenario: Claims hold no literal level
- **GIVEN** a `claims` module of a package named `kicad` in which one cell is `Evidence(Level.KICAD_VERIFIED)`
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k literal` runs
- **THEN** it fails naming `kicad.claims`

#### Scenario: Report kinds agree with the matrix
- **GIVEN** every backend of `registry.all_backends()`
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k report_kinds` compares its report with its rows
- **THEN** each kind of `read_kinds` has `detect` and `read` set, and the kinds with a `write` that is not experimental are exactly `write_kinds`

#### Scenario: Rows are sorted and need no tool
- **GIVEN** `subprocess.run` replaced by a function that raises
- **WHEN** `rows()` is called twice
- **THEN** both calls return the same tuple, sorted by `(backend, kind)`, with at least one row for each of `altium`, `kicad` and `specctra`

#### Scenario: Importing the collector stays light
- **WHEN** `uv run python -c "import sys, fenolite.backends.matrix; print(sorted(m for m in sys.modules if m.startswith(('fenolite.backends.altium', 'fenolite.backends.kicad', 'fenolite.backends.specctra'))))"` runs
- **THEN** it prints `[]` and exits 0

### Requirement: Backend modules declare their evidence
Every module of a backend package, that is every `.py` file under `src/fenolite/backends/<name>/` at any depth except `__init__.py` and the package's `claims.py`, SHALL declare its evidence in exactly one of three forms:
- **constants**: one or more module-level names assigned in that module to an `Evidence` (`EVIDENCE`, `WRITE_EVIDENCE`, `EVIDENCE_V3`, …). A name that the module only imports is not assigned there and is no declaration;
- **`# evidence: see <module>[, <module>…]`**: the module makes no claim of its own, because its code runs only inside the operations of the named modules of the same package. A module is named by its dotted path below the package (`pcb`, `read.pcb`). Each named module MUST exist and MUST declare constants;
- **`# evidence: none, <reason>`**: the module states nothing about a file format or a tool. The reason MUST NOT be empty.

A marker is a comment that starts in column 0. The same text inside a string or a docstring is not a marker. An `__init__.py` need not declare; one that assigns constants (`altium/read/sch/__init__.py`) is listed as the module named by its package (`read.sch`), may be named by a `see` marker, and follows the same rules. A module with constants MUST NOT carry a marker, and no module may carry two markers. A constant whose level is `INFERRED` MUST name at least one hypothesis.
- `fenolite.backends.matrix.module_claims(package) -> tuple[ModuleClaim, ...]` MUST return, for the package with that dotted name, one frozen `ModuleClaim(package, module, constants=(), see=(), none="")` per module, sorted by `module`: `constants` is a tuple of `(name, Evidence)` sorted by name, `see` a tuple of module names, `none` the reason or `""`. The constants are read by importing the module; the markers by tokenising its source.
- `fenolite.backends.matrix.problems(packages=None) -> tuple[str, ...]` MUST return one message per broken rule of this requirement and of "Evidence matrix rows", sorted, each naming the module or the row. With `packages` `None` it checks every package of `packages()`. It MUST return an empty tuple when every rule holds.
- `tests/unit/backends/test_evidence_declared.py` MUST fail while `problems()` is not empty, and its failure message MUST be `fenolite.backends.matrix.failure_text(problems)`: the problems, then `fenolite.backends.matrix.HELP`. It runs in the `unit` job, so a backend module without a declaration fails CI.
- The message for a module that declares nothing MUST name the module and the three forms, and `HELP` MUST say when each form applies, give one example of each, name `docs/hypotheses.md` and the rule that the lowest level wins, and name the command that regenerates `docs/evidence/matrix.md`. A contributor who never read this requirement can fix the failure from the text alone.
- The declarations MUST change no level: a constant that exists keeps its name and its level. One constant changes its ids: `read.sch.EVIDENCE` stops naming `H-A-RD-SCH-TEXT`, which is refuted (`altium-schematic-reader`, "Schematic reader entry points").

#### Scenario: Every live module declares
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k live` calls `problems()`
- **THEN** the tuple is empty, and `module_claims` returns at least one module with constants for each of `fenolite.backends.altium`, `fenolite.backends.kicad` and `fenolite.backends.specctra`

#### Scenario: The four broken forms are named
- **GIVEN** a temporary package on `sys.path` with the modules `good` (an `EVIDENCE` constant that names `H-K-PCB-READ`), `helper` (`# evidence: see good`), `plain` (no declaration), `both` (a constant and a marker), `lost` (`# evidence: see missing`), `quiet` (`# evidence: none,` with no reason) and a `claims` module whose `MATRIX` is empty
- **WHEN** `problems([package])` is called
- **THEN** it returns four messages, naming `plain`, `both`, `lost` and `quiet`, and none names `good` or `helper`

#### Scenario: The message says what to add
- **GIVEN** a temporary package with one module `schwrite` that declares nothing
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k says_what_to_add` reads `problems([package])` and `failure_text` of it
- **THEN** the one message starts with the module's dotted name and holds `EVIDENCE = Evidence(`, `# evidence: see <module>` and `# evidence: none, <reason>`, and the text also holds `docs/hypotheses.md`, `lowest wins` and `uv run python tools/gen_evidence_matrix.py`

#### Scenario: Marker text in a docstring does not count
- **GIVEN** a module of that temporary package whose docstring holds the line `# evidence: none, only text` and that has no constant and no comment marker
- **WHEN** `problems([package])` is called
- **THEN** one message names that module as declaring nothing

#### Scenario: Inferred level without a hypothesis
- **GIVEN** a module of that temporary package with `EVIDENCE = Evidence(Level.INFERRED)`
- **WHEN** `problems([package])` is called
- **THEN** one message names the module, `EVIDENCE` and `INFERRED`

#### Scenario: Unverified cell outside experimental
- **GIVEN** a `claims` module of that temporary package with a row whose `write` cell is a constant of level `UNVERIFIED` and whose `experimental` is empty
- **WHEN** `problems([package])` is called
- **THEN** one message names the row's kind and `write`; with `experimental=("write",)` there is none

### Requirement: Document sets and container round trips
`fenolite.backends.base` SHALL define the neutral types through which `checks` and the CLI ask a backend for the documents of a project, for their readings and for the round trip of one container file, without importing a backend. Every dataclass MUST be frozen.
- `DocumentRole = Literal["project", "schematic", "pcb", "symbol-library", "footprint-library", "other"]`.
- `Document(name: str, kind: str, role: DocumentRole)`: `name` is a POSIX name relative to the set's root, and `kind` is a read kind of the backend's capability report.
- `DocumentSet(root: Path, project: str | None, board: str | None, documents: tuple[Document, ...], missing: tuple[str, ...] = ())`: `documents` is sorted by name, `project` and `board` are names of `documents` or `None`, and `missing` holds, sorted, the names that the project file lists and that do not exist. Construction MUST raise `ValueError` for a name that is absolute, holds `..` or `\`, or is repeated, for `documents` or `missing` that are not sorted, and when `project` or `board` is not a name of `documents`. `named(name)` returns the document of that name and `of_role(role)` the documents of one role.
- `ProjectRead(schematic: ReadResult | None, pcb: ReadResult | None, errors: Mapping[str, FormatError])`, with `errors` empty by default: `schematic` is the reading of every schematic document of the set as one design, `pcb` the reading of the document `board`, and `errors` maps a document name to the error that refused it. A side without a document, or whose reading was refused, MUST be `None`.
- `ContainerLevel = Literal["RT-A0", "RT-A1"]` and `ContainerRoundTrip(level: ContainerLevel, judged: bool, passed: bool, streams: int = 0, different: tuple[str, ...] = (), records: int = 0, bytes_equal: int = 0, opaque_count: int = 0, difference: str = "", reason: str = "", evidence: Evidence = Evidence())`. `evidence` is the backend's evidence for the verdict (the level of the reader of the file's kind and the hypotheses the level rests on), so that `checks` names no hypothesis of a backend. Construction MUST raise `ValueError` unless `passed == (judged and not different)`, unless `reason` is non-empty exactly when `judged` is false, and unless `difference` is empty exactly when `different` is empty.
- `ModelScope(fields: Mapping[str, tuple[str, ...]], length_tolerance: int = 0)`: the model fields, per entity kind, that a comparison covers, and the tolerance in nanometres for lengths. `length_tolerance` MUST be an `int` that is not negative.
- `DocumentValidator`, a `@runtime_checkable` `typing.Protocol` with `name: str` and the methods `documents(path: Path) -> DocumentSet`, `read_documents(documents: DocumentSet) -> ProjectRead`, `container_roundtrip(path: Path, level: ContainerLevel) -> ContainerRoundTrip`, `written_scope() -> ModelScope` and `stage_evidence() -> Mapping[str, Evidence]`. `stage_evidence` maps the name of a check stage to the evidence that the backend adds to it (the hypotheses its readings rest on for that stage).
- `ChangeKind`, `Change` and `DiffReport`, the result types of a comparison (`verification-loop`, "Model difference report", change c0066), are defined here and re-exported by `fenolite.checks.diff`: a backend returns them for the records of two files and MUST NOT import `checks`.

`documents` MUST decide from the path, from the project file and from at most the first eight bytes of each document, which tell a compound file from a text file: a document path gives a set holding that document, and a project file or a folder gives the project's documents. No method MAY write a file. `container_roundtrip` MUST raise the reader's `FormatError` for a file it cannot read, and MUST return `judged=False` with a reason instead of raising when the level cannot be judged. `Validator`, `Validation` and `RoundTrip` are unchanged.

#### Scenario: Verdict consistency enforced
- **WHEN** `ContainerRoundTrip(level="RT-A0", judged=True, passed=True, streams=3, different=("Nets6/Data",), difference="Nets6/Data")` is constructed
- **THEN** a `ValueError` is raised; with `passed=False` it is constructed

#### Scenario: Unjudged verdict needs a reason
- **WHEN** `ContainerRoundTrip(level="RT-A0", judged=False, passed=False)` is constructed
- **THEN** a `ValueError` naming `reason` is raised; with `reason="too-large"` it is constructed

#### Scenario: Document names are relative
- **WHEN** `DocumentSet(root=Path("."), project=None, board=None, documents=(Document("../x.PcbDoc", "altium_pcbdoc", "pcb"),))` is constructed
- **THEN** a `ValueError` naming `../x.PcbDoc` is raised

#### Scenario: Narrowing a backend
- **GIVEN** a fake backend in `tests/unit/checks/fakes.py` that implements only `detect`, `read` and `capabilities`, and a second fake that also implements the five methods of `DocumentValidator`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k document_validator` checks them
- **THEN** `isinstance(fake, DocumentValidator)` is false for the first and true for the second, and `KicadBackend()` is not a `DocumentValidator`

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and `src/fenolite/backends/base.py` imports only `core` and `model`

### Requirement: Neutral ERC report
`fenolite.backends.base` SHALL provide the frozen dataclasses `ErcItem(uuid, description, position, where="")`, `ErcViolation(type, description, severity, items, excluded=False, sheet="", sheet_id="")` and `ErcReport(source, date, kicad_version, coordinate_units, violations, ignored_checks=(), included_severities=(), sheets=())`.
- `position` MUST be a `Point` in integer nanometres on the sheet, and `ErcItem` MUST raise `TypeError` for a coordinate that is not an `int`. `where` is the location a backend found for the item (`REF-PIN`, `REF` or a label text), or `""`.
- `type` and `severity` MUST be the tool's own strings. `sheet` MUST be the tool's readable path of the sheet the violation is listed under, and `sheet_id` the tool's own identifier of that sheet (for KiCad its path of uuids), by which a backend finds the reference a symbol has there. Violations MUST keep report order, sheet by sheet. `ErcReport.sheets` MUST hold the readable path of every sheet the report lists, with or without violations, in report order.
- `ErcReport.of_type(type)` MUST return the violations of that type, in report order.
- `ErcReport.entries()` MUST return the violations as a sorted tuple of `(sheet, type, severity, excluded, items)`, each item as `(description, x, y)`, leaving out uuids, `where`, `sheet_id` and the report order, so that one report can be compared with itself or with a copy of it.
- `ErcReport.kinds()` MUST return the violations as a sorted tuple of `(sheet, type, severity, excluded)`, one entry per violation and no item, so that two runs of a tool on one project can be compared: a tool may name another item of one violation in each run.
- `fenolite.backends.base` MUST NOT import any `fenolite.backends.<x>` module.

#### Scenario: Violations by type
- **GIVEN** an `ErcReport` with two `pin_not_connected` violations and one `lib_symbol_issues` violation
- **WHEN** `report.of_type("lib_symbol_issues")` is called
- **THEN** it returns the one violation

#### Scenario: Entries leave out uuids and order
- **GIVEN** two reports holding the same two violations in another order and with other item uuids
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k erc_entries` compares `entries()`
- **THEN** they are equal, and a report with one violation fewer gives other entries

#### Scenario: Kinds leave out the items and keep the counts
- **GIVEN** two reports holding the same two violations with other items and positions, and a third holding one of them twice
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k erc_kinds` compares `kinds()`
- **THEN** the first two are equal although their `entries()` differ, and the third differs from both

#### Scenario: Integer positions only
- **WHEN** `ErcItem(uuid="u", description="d", position=Point(1.5, 0))` is constructed
- **THEN** a `TypeError` is raised

### Requirement: ERC oracle protocol
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for an ERC verdict, without importing a backend:
- `ErcOutcome(report: ErcReport | None, tool_version: str, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `report` MUST be `None` when the tool wrote no report, and `message` MUST then be the first sanitised line of the tool's output.
- `ErcRt2Outcome(before: tuple[ErcReport, ...], after: ErcReport | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence(), redumped: int = 0, kept: int = 0)`: the reports of the runs on the project as it is, the report of the run on the re-dump, and the numbers of sheet files re-dumped and left as they are.
- `ErcOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `erc(project: ProjectSet) -> ErcOutcome`.

The types MUST be frozen dataclasses. `erc` MUST NOT write under `project.root` and MUST return `outcome == "timeout"` instead of raising when the tool times out. c0013's `Oracle` protocol is unchanged: a caller narrows an `Oracle` with `isinstance(oracle, ErcOracle)`. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `ErcOracle`, and the typed function of `oracle.py` that returns a `KicadOracle` as each protocol (`_protocols`, now a tuple of four) MUST cover it.

#### Scenario: KiCad oracle satisfies the protocol
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error for the typed function that returns a `KicadOracle` as `ErcOracle`

#### Scenario: Narrowing a drc-only oracle
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements only `name`, `version` and `drc`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k erc_protocol` checks it
- **THEN** `isinstance(fake, ErcOracle)` is false, and it is true for a fake that also implements `erc`

#### Scenario: Outcome is immutable
- **GIVEN** `ErcOutcome(report=None, tool_version="10.0.6")`
- **WHEN** code assigns `outcome.message = "x"`
- **THEN** a `FrozenInstanceError` is raised

### Requirement: Schematic netlist oracle
`fenolite.backends.base` SHALL define `SchematicNetlistOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `schematic_netlist(project: ProjectSet) -> NetlistOutcome`, through which `checks` asks an external tool for the netlist of a project's schematic without importing a backend.
- The `NetlistOutcome` is the type of "Netlist and round-trip oracles". Its `PadNetList` MUST have the source `schematic` and one `PadAssignment(f"{ref}-{pin}", <net name>)` per pin the tool lists; a pin the tool does not list is not an element.
- `netlist` MUST be `None` when the tool wrote no export, and `message` MUST then be the first sanitised line of the tool's output or of the parse error.
- `schematic_netlist` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out.
- c0013's `Oracle` protocol is unchanged: a caller narrows with `isinstance(oracle, SchematicNetlistOracle)`. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy the protocol, and a typed function of `oracle.py` MUST return a `KicadOracle` as `SchematicNetlistOracle`, so `pyright` checks the assignment.

#### Scenario: KiCad oracle satisfies the protocol
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error for the typed function that returns a `KicadOracle` as `SchematicNetlistOracle`

#### Scenario: Narrowing
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements `name`, `version`, `drc` and `netlist`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k schematic_netlist` checks it
- **THEN** `isinstance(fake, SchematicNetlistOracle)` is false, and it is true for a fake that also implements `schematic_netlist`

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/checks` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

