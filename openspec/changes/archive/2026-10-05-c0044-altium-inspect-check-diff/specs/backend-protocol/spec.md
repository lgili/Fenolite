## ADDED Requirements

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
