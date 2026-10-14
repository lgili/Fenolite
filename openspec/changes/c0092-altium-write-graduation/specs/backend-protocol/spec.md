## ADDED Requirements

### Requirement: Graduation of a write kind
`fenolite.backends.base.graduated(row, register, runs)` SHALL say whether the write of a matrix row may leave `experimental`, and what is missing when it may not. The write graduates when all of these hold:
- the kind names an own-readback test in its claims and that test is part of the suite;
- for a kind that carries a model (a PCB document, a schematic document, a project file), the row of the round-trip level RT-A3 for it is release-verified;
- every hypothesis id of the write cell is release-verified (`verification-evidence`, "Release-verified levels");
- at least one hypothesis id of the cell is `ALTIUM-VERIFIED(kit)` from a committed run that is not stale.

A write cell that graduates MUST NOT be listed in the row's `experimental`, and a write cell that does not MUST be listed. This holds for every backend; for the KiCad rows the fourth condition is replaced by a `KICAD-VERIFIED` hypothesis.
- The evidence matrix page MUST show, for each write cell that is experimental, the conditions that are missing.

#### Scenario: Evidence short by one row
- **GIVEN** a matrix row whose write cell names three hypotheses, one of them `INFERRED`
- **WHEN** `graduated` runs
- **THEN** it returns false and names that hypothesis

#### Scenario: Both directions are enforced
- **WHEN** `uv run pytest tests/unit/backends/test_graduation.py -k matrix` checks every row of every backend
- **THEN** each write cell is experimental exactly when `graduated` is false

#### Scenario: A stale run undoes graduation
- **GIVEN** a graduated kind whose only kit row is returned by `stale_rows`
- **WHEN** `graduated` runs
- **THEN** it returns false and names the stale run

## MODIFIED Requirements

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
- The `altium` rows MUST include one row for every write kind of the experimental features (`cli-contract`, "Experimental features in capabilities"), each with `write` set; its membership in `experimental` follows "Graduation of a write kind". Since change c0043 `altium` is a registered backend, so every kind of its `read_kinds` also has `detect` and `read` set: `read` combines the reader's constant with `import_evidence.EVIDENCE`, and `detect` is `import_evidence.EVIDENCE`, the evidence of the backend's report. The `specctra` rows MUST include `specctra_dsn` with `write` set and `specctra_ses` with `read` set.
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
