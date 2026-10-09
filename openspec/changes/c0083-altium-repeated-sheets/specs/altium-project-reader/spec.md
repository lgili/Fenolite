## ADDED Requirements

### Requirement: Annotation file read
`fenolite.backends.altium.read.annotation.read_annotation(data, *, file)` SHALL read a project's `.Annotation` file into its entries, each a unique-id path with the designator it assigns, and SHALL keep the text so that it can be written back byte for byte ("Text forms are kept byte for byte").
- The facts of the file's form MUST be recorded in `docs/formats/altium/project.md` with their sources and labels before the reader is written. Where no public source states the form, the page MUST say so (`UNKNOWN`) and state the form the reader assumes as Fenolite's choice: an entry is a `<key>=<value>` line, in any section, whose key is a unique-id path and whose value is the designator (`H-A-IMP-RPT-ANNOT`, settled by Part R, step R4).
- A file that does not have that form MUST raise the located `FormatError` of the text readers; an entry that names no unique-id path MUST be kept and reported with `altium.text.unknown-key`.
- `load_project` MUST return the annotation file of a project that lists one.

#### Scenario: Authored annotation file
- **GIVEN** `tests/data/altium/channels/two/two.Annotation`, authored from the recorded facts
- **WHEN** `read_annotation` runs
- **THEN** it returns the two entries of the file, and writing the read value gives the same bytes

#### Scenario: Annotation file listed by the project
- **GIVEN** a project file that lists `p.Annotation`, a file holding one entry
- **WHEN** `load_project` runs
- **THEN** `annotations` holds one `(1, AnnotationFile)` pair and `annotation_designators()` gives that entry

## MODIFIED Requirements

### Requirement: Project loading
`fenolite.backends.altium.read.project.load_project(path)` SHALL read the project file at `path` and the text companions it lists, and SHALL return an `AltiumProject(root, name, project, documents, outjobs, rule_files, stackups, rules, issues, annotations)`. It is the entry point for the import change (c0043).
- `root` is the folder of `path`. `documents` MUST hold one `LoadedDocument(document, file, present)` per `ProjectFile.documents` entry, where `file` is `root / document.posix` and `present` says whether it is a file.
- A document whose path is absolute, starts with a drive letter or `\\`, or leaves `root` through `..` MUST NOT be opened: `file` is `None`, and the warning `altium.project.document-outside` names the document index, not the path.
- A listed document that is not a file MUST add the warning `altium.project.document-missing`. Paths MUST be resolved as written; when no file of that spelling exists and exactly one file of `root` matches without case, that file is used.
- Present documents of the kinds `output-job`, `rules`, `stackup` and `annotation` MUST be read with `read_outjob`, `read_rule_file`, `read_stackup` and `read_annotation` and stored in `outjobs`, `rule_files`, `stackups` and `annotations` as `(document index, result)` pairs; `annotation_designators()` MUST give the unique-id path → designator of every annotation file read, the first entry of a path winning. A `FormatError` of a companion MUST NOT fail the load: it adds the warning `altium.project.companion-unreadable` naming the document index and the error.
- `rules` MUST hold one `(document index, RuleMapping)` per rule file, from `map_rules(file.records, origin=<document posix path>, summary=file.kind == "summary")`.
- Documents of every other kind MUST be listed and not opened. `generated` documents MUST NOT be opened.
- `issues` MUST hold the issues of the project file, then those of each companion in document order.
- A project file that cannot be read MUST raise `FormatError`; a missing `path` MUST raise `FileNotFoundError`.
- `load_project` MUST NOT write anything and MUST NOT import `fenolite.backends.altium.read.cfb` or any reader of compound files.

#### Scenario: Project with companions
- **GIVEN** a folder with the authored fixtures: a project file that lists `Top.SchDoc` (absent), `jobs.OutJob`, `rules_export.RUL` and `two_layer.stackup`
- **WHEN** `load_project(folder / "project_companions.PrjPcb")` is called
- **THEN** `outjobs`, `rule_files`, `stackups` and `rules` each hold one entry with the right document index, `documents[0].present is False`, and the issues hold one `altium.project.document-missing` followed by the companions' issues

#### Scenario: Path outside the project folder
- **GIVEN** a project file whose `Document2` is `..\..\shared\Fab.OutJob`
- **WHEN** it is loaded
- **THEN** that document has `file is None`, nothing outside the folder is opened, and the issues hold one `altium.project.document-outside` naming document 2

#### Scenario: Unreadable companion
- **GIVEN** a project file that lists `bad.RUL`, a file holding `hello`
- **WHEN** it is loaded
- **THEN** the load succeeds, `rule_files == ()`, and the issues hold one `altium.project.companion-unreadable` naming the document index

#### Scenario: No compound reader
- **GIVEN** the modules of `fenolite.backends.altium.read` named `textfile`, `ini`, `proptext`, `project`, `outjob`, `rul`, `rules`, `scope`, `stackup` and `annotation`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_imports.py` runs
- **THEN** none of them imports `fenolite.backends.altium.read.cfb` or `fenolite.backends.altium.cfb`, and each imports only the standard library, `fenolite.core`, `fenolite.model` and its sibling text modules

### Requirement: Text reader issue codes
`fenolite.backends.altium.read.textfile.TEXT_READ_CODES` SHALL be this closed mapping, and every issue of the modules of this capability MUST use one of its codes with the severity given:

| code | severity | when |
|---|---|---|
| `altium.text.encoding-assumed` | warning | no byte-order mark and the bytes are not UTF-8; read as Latin-1 |
| `altium.text.mixed-line-ends` | info | more than one kind of line end |
| `altium.text.duplicate-key` | info | a key repeated in one section |
| `altium.text.stray-line` | info | a line that is neither a section, a key nor empty |
| `altium.text.unknown-key` | info | a key line of an annotation file that names no unique-id path with a designator |
| `altium.project.no-design-section` | warning | a project file without `[Design]` |
| `altium.project.hierarchy-mode-unknown` | warning | a `HierarchyMode` outside `HIERARCHY_MODES` |
| `altium.project.document-kind-unknown` | info | a document extension outside `DOCUMENT_KINDS` |
| `altium.project.document-missing` | warning | a listed document is not a file |
| `altium.project.document-outside` | warning | a document path leaves the project folder |
| `altium.project.companion-unreadable` | warning | a listed companion raised `FormatError` |
| `altium.outjob.output-incomplete` | warning | an output without its type |
| `altium.rule.record-malformed` | warning | a line of an export file without a rule kind |
| `altium.rule.summary-form` | info | a summary-form file: its rules are not mapped |
| `altium.rule.unmapped` | info | one rule that is not mapped, with its reason |
| `altium.stackup.unknown-form` | warning | more than one generation of layer keys |
| `altium.stackup.length-unreadable` | warning | a thickness that is not a length |

No issue of this capability MUST have the severity `error`: malformed input raises `FormatError`, which the CLI maps to `FEN-3004`. An issue message MUST NOT hold a path outside the project folder.

#### Scenario: Closed set
- **GIVEN** the issues produced by the unit cases of this capability and the `altium.text.`, `altium.project.`, `altium.outjob.`, `altium.rule.` and `altium.stackup.` literals in `src/fenolite/backends/altium/read/*.py`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_codes.py` runs
- **THEN** every produced code is a key of `TEXT_READ_CODES` with the table's severity, and the set of literals of the ten text modules equals the keys of `TEXT_READ_CODES`
