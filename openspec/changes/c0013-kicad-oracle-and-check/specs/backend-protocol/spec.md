## ADDED Requirements

### Requirement: Validation operation
`fenolite.backends.base` SHALL define the neutral validation types, so that `checks` can validate a file without importing a backend:
- `RoundTrip(level: Literal["RT1"], passed: bool, tree_equal: bool, model_equal: bool, opaque_equal: bool, opaque_count: int, difference: str = "")`, a frozen dataclass. `passed` MUST equal `tree_equal and model_equal and opaque_equal`, and construction MUST raise `ValueError` otherwise.
- `Validation(read: ReadResult, roundtrip: RoundTrip)`, a frozen dataclass.
- `Validator`, a `@runtime_checkable` `typing.Protocol` with `name: str` and `validate(path, *, issues=None) -> Validation`. `validate` MUST raise the reader's `FormatError` (its subclasses included, such as `UnsupportedFormatError`, `FEN-3003`) for a file it cannot read, and `ValueError` naming the kind for a file kind it cannot validate. A caller holding a `Backend` MUST narrow it with `isinstance(backend, Validator)` before calling `validate`.

A backend that lists `"validate"` in `operations` MUST satisfy `Validator`. `src/fenolite/backends/kicad/backend.py` MUST hold the typed statement `_VALIDATOR: Validator = KicadBackend()`, which `pyright` checks. The KiCad backend MUST list `"validate"` in its `operations`, beside the operations that earlier changes added ("Write capability fields", as modified below). The pinned capability tests (`tests/unit/backends/test_registry.py`, `tests/unit/backends/test_base_types.py`, `tests/unit/cli/test_capabilities_backends.py`) MUST be updated in the same commit.

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

## MODIFIED Requirements

### Requirement: Write capability fields
`fenolite.backends.base` SHALL provide the frozen dataclass `WriteResult(text: str, issues: tuple[Issue, ...] = ())`, the neutral result of a backend writer. A backend whose `CapabilityReport.write_kinds` is not empty MUST also report:
- `targets`: the tool versions it writes for, oldest first;
- `default_target`: the target used when the caller names none, which MUST be one of `targets`;
- `downgrade`: `"unsupported"` when a file read at a newer version cannot be written for an older target, or `"supported"`.

A backend that lists `"write"` in `operations` MUST have a non-empty `write_kinds` and MUST provide `write(design, *, target=None, allow_lossy=False) -> WriteResult`, which writes the design's board for `target` (`default_target` when `None`) and never writes a file. A backend with a non-empty `write_kinds` MUST list `"write"` in `operations`.

The KiCad backend MUST include `"kicad_pcb"` in `write_kinds`, MUST report `targets == (9, 10)`, `default_target == 10` and `downgrade == "unsupported"`, and MUST list `"detect"`, `"read"` and `"write"` in `operations`. It MUST list `"lower"` exactly when it provides a callable `lower` method, and `"validate"` exactly when it satisfies `Validator` ("Validation operation"), as "Capability reports" requires; the changes that implement them add them to the same tuple. `KicadBackend.write` MUST return what `fenolite.backends.kicad.pcb.write_board` returns for the same arguments. Later writers add their kinds to the same tuple. These values replace the pre-writer values of c0009 (`write_kinds == ()`, `targets == ()`, `default_target is None`, `operations == ("detect", "read")`). `fenolite capabilities` MUST show them for the `kicad` entry of `result.backends`.

#### Scenario: KiCad write fields in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `kicad` entry of `result.backends` has `"kicad_pcb"` in `write_kinds`, `targets == [9, 10]`, `default_target == 10` and `downgrade == "unsupported"`, and its `operations` contain `detect`, `read` and `write`

#### Scenario: Write operation advertised and implemented
- **GIVEN** `KicadBackend()` and the created test board `tests/_boards.py::created_board()`
- **WHEN** an agent finds `"write"` in `capabilities().operations` and calls `backend.write(design)`
- **THEN** it returns a `WriteResult` equal to `write_board(design, target=10)`, and every other entry of `operations` names a callable method of the backend

#### Scenario: Later operations by membership
- **GIVEN** `KicadBackend()` once `KicadBackend.validate` exists
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k capability_write_advertised` reads `capabilities().operations`
- **THEN** it contains `validate`, and it contains `lower` exactly when `KicadBackend` has a callable `lower` method

#### Scenario: Default target among the targets
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k capability` checks their reports
- **THEN** each backend with a non-empty `write_kinds` has `default_target in targets`

#### Scenario: Write result is immutable
- **GIVEN** `WriteResult(text="(kicad_pcb)\n")`
- **WHEN** code assigns `result.text = ""`
- **THEN** a `FrozenInstanceError` is raised
