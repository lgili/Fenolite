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

