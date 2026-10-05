## ADDED Requirements

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
- Every package `fenolite.backends.<name>` MUST provide the module `claims` with `MATRIX: tuple[MatrixRow, ...]`, whose rows all have `backend == <name>` and distinct kinds. Every cell MUST be an evidence constant of a module of that package, or `Evidence.combine` of such constants: `claims.py` MUST NOT name `Level` and MUST call `Evidence` only as `Evidence.combine`. A level therefore changes in one place, the module that owns the claim.
- `fenolite.backends.matrix.packages() -> tuple[str, ...]` MUST return the names of the sub-packages of `fenolite.backends`, sorted, and `fenolite.backends.matrix.rows() -> tuple[MatrixRow, ...]` MUST return the rows of every package, sorted by `(backend, kind)`. `rows()` MUST run no external tool and read no file but the modules it imports. Importing `fenolite.backends.matrix` MUST NOT import a backend package; `rows()` imports them.
- For every backend of `registry.all_backends()`, every kind of its report's `read_kinds` MUST have a row with `detect` and `read` set, and the kinds whose `write` is set and not experimental MUST be exactly the report's `write_kinds` ("Capability reports"). A kind MAY have `read` set without being in `read_kinds`: the package then has a reader that `Backend.read` does not dispatch.
- The `kicad_pcb` row MUST have `read` equal to `pcb.EVIDENCE`, `write` equal to `pcb.WRITE_EVIDENCE`, `roundtrip_exact` equal to `pcb.EVIDENCE` (RT1; `kicad-file-backend`, "Round-trip verdict") and `roundtrip_modified` equal to `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`, which is the evidence of the KiCad capability report.
- The `altium` rows MUST include one row for every write kind of the experimental features (`cli-contract`, "Experimental features in capabilities"), each with `write` set and listed in `experimental`. The `specctra` rows MUST include `specctra_dsn` with `write` set and `specctra_ses` with `read` set.
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
- **GIVEN** a version of `src/fenolite/backends/kicad/claims.py` in which one cell is `Evidence(Level.KICAD_VERIFIED)`
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
Every module of a backend package, that is every `.py` file under `src/fenolite/backends/<name>/` at any depth except `__init__.py` and `claims.py`, SHALL declare its evidence in exactly one of three forms:
- **constants**: one or more module-level names `EVIDENCE` or `<NAME>_EVIDENCE`, assigned in that module to an `Evidence`;
- **`# evidence: see <module>[, <module>…]`**: the module makes no claim of its own, because its code runs only inside the operations of the named modules of the same package. Each named module MUST exist and MUST declare constants;
- **`# evidence: none, <reason>`**: the module states nothing about a file format or a tool. The reason MUST NOT be empty.

A marker is a comment that starts in column 0. The same text inside a string or a docstring is not a marker. A module with constants MUST NOT carry a marker, and no module may carry two markers. A constant whose level is `INFERRED` MUST name at least one hypothesis.
- `fenolite.backends.matrix.module_claims(package) -> tuple[ModuleClaim, ...]` MUST return, for the package with that dotted name, one frozen `ModuleClaim(package, module, constants, see, none)` per module, sorted by `module`: `constants` is a tuple of `(name, Evidence)` sorted by name, `see` a tuple of module names, `none` the reason or `""`. The constants are read by importing the module; the markers by tokenising its source.
- `fenolite.backends.matrix.problems(packages=None) -> tuple[str, ...]` MUST return one message per broken rule of this requirement and of "Evidence matrix rows", sorted, each naming the module or the row. With `packages` `None` it checks every package of `packages()`. It MUST return an empty tuple when every rule holds.
- `tests/unit/backends/test_evidence_declared.py` MUST fail while `problems()` is not empty, and its failure message MUST list the problems. It runs in the `unit` job, so a backend module without a declaration fails CI.
- The declarations MUST change no level: a constant that exists keeps its name and its value.

#### Scenario: Every live module declares
- **WHEN** `uv run pytest tests/unit/backends/test_evidence_declared.py -k live` calls `problems()`
- **THEN** the tuple is empty, and `module_claims` returns at least one module with constants for each of `fenolite.backends.altium`, `fenolite.backends.kicad` and `fenolite.backends.specctra`

#### Scenario: The four broken forms are named
- **GIVEN** a temporary package on `sys.path` with the modules `good` (an `EVIDENCE` constant that names `H-K-PCB-READ`), `helper` (`# evidence: see good`), `plain` (no declaration), `both` (a constant and a marker), `lost` (`# evidence: see missing`), `quiet` (`# evidence: none,` with no reason) and a `claims` module whose `MATRIX` is empty
- **WHEN** `problems([package])` is called
- **THEN** it returns four messages, naming `plain`, `both`, `lost` and `quiet`, and none names `good` or `helper`

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
