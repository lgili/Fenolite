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

#### Scenario: KiCad capability report
- **WHEN** `KicadBackend().capabilities().to_json()` is called
- **THEN** it has exactly the eight keys, `name` is `kicad`, `read_kinds` contains `kicad_pcb`, `kicad_mod` and `kicad_sym`, `operations` contains `detect` and `read`, and the evidence level is `INFERRED`

#### Scenario: Unavailable operations are visible
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks its report
- **THEN** every listed operation is a method of the backend, and a backend with an empty `write_kinds` lists no `write`, has empty `targets` and has `default_target` `None`, so an agent knows it cannot write

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

