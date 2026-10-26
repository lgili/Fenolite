## MODIFIED Requirements

### Requirement: Altium backend
`fenolite.backends.altium.backend.AltiumBackend` SHALL satisfy the `Backend` protocol with `name == "altium"`, and SHALL be a built-in of the registry ("Backend registry" of `backend-protocol`).
- `detect(path)` MUST return `True` exactly for the suffixes `.PrjPcb`, `.SchDoc`, `.SchLib`, `.PcbDoc` and `.PcbLib`, compared without letter case, and MUST NOT open the file.
- `read(path, *, issues=None)` MUST return a `ReadResult` whose `content` is: for a PCB document, the design of `import_board`; for a schematic document in the binary or the ASCII form, a design whose circuit is `import_circuit` of that one sheet, with `board is None`; for a project file, the design of `import_project` over `read.project.load_project(path)`; for a PCB library and a schematic library, a `Library`.
- For a design, `issues` MUST be the readers' issues, then the adapter's, then those of `design.validate()`; `evidence` MUST be `adapter.EVIDENCE`. In a project read, the project reader's `altium.project.document-outside` and `altium.project.document-missing` issues about a sheet or a PCB document are replaced by `altium.import.document-skipped`, so that one document gives one issue.
- A project document outside the project folder, a missing document and a document that a reader refuses MUST NOT stop the import: each gives `altium.import.document-skipped` (warning) with the reason, and the design is built from the rest. A project file that names no readable sheet and no readable PCB document MUST raise `FormatError`.
- Reader errors of the file that `read` was called on MUST be raised unchanged. The backend MUST call the readers in their lenient mode.
- `capabilities()` MUST return `CAPABILITIES`: `read_kinds == ("altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib")`, `write_kinds == ()`, `targets == ()`, `default_target is None`, `downgrade == "unsupported"`, `operations == ("detect", "read")` and `evidence == adapter.EVIDENCE`. The backend MUST NOT offer `lower` or `validate`. It offers `write(design, …)` for a model (`backend-protocol`, "Altium write of a model"; change c0090), which is experimental like the writers of `build`: the report names no write kind and lists no `write` operation until the writers leave that state.
- Registering the backend MUST NOT change what `fenolite inspect` and `fenolite check` accept: `cli-contract` "Inspect command" and `verification-loop` "Check command input" decide that, and this change edits neither command.

#### Scenario: Detection by suffix
- **WHEN** `AltiumBackend().detect` is called on `Path("a.PcbDoc")`, `Path("a.pcbdoc")`, `Path("a.SCHLIB")`, `Path("a.PrjPcb")`, `Path("a.SchDot")` and `Path("a.kicad_pcb")`
- **THEN** it returns `True`, `True`, `True`, `True`, `False` and `False`, and no file is opened

#### Scenario: Backend for a path
- **WHEN** `registry.for_path(Path("board.PcbDoc"))` and `registry.for_path(Path("board.kicad_pcb"))` are called
- **THEN** the first returns the Altium backend and the second the KiCad backend

#### Scenario: Schematic alone
- **GIVEN** `tests/data/altium/sample/altium_sample.SchDoc` (ASCII) and `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **WHEN** `AltiumBackend().read` reads each
- **THEN** both designs have `board is None` and equal circuits, apart from provenance

#### Scenario: Capability invariants
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks every registered backend
- **THEN** the Altium report lists only `detect` and `read`, both callable, with an empty `write_kinds`, empty `targets` and `default_target` `None`, and the backend has a callable `write` that the report does not list

#### Scenario: Skipped document
- **GIVEN** a copy of the blink project under `tmp_path` whose project file also lists `..\outside\x.SchDoc` and `missing.SchDoc`
- **WHEN** the project is read
- **THEN** the circuit, the board and every other issue equal those read without those two lines, apart from two `altium.import.document-skipped` warnings that give the reasons `outside-root` and `missing`
