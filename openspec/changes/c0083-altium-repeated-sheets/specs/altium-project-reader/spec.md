## ADDED Requirements

### Requirement: Annotation file read
`fenolite.backends.altium.read.annotation.read_annotation(data, *, file)` SHALL read a project's `.Annotation` file into its entries, each a unique-id path with the designator it assigns, and SHALL keep the text so that it can be written back byte for byte ("Text forms are kept byte for byte").
- The facts of the file's form MUST be recorded in `docs/formats/altium/project.md` with their sources and labels before the reader is written.
- A file that does not have that form MUST raise the located `FormatError` of the text readers; an entry that names no unique-id path MUST be kept and reported with `altium.text.unknown-key`.
- `load_project` MUST return the annotation file of a project that lists one.

#### Scenario: Authored annotation file
- **GIVEN** `tests/data/altium/channels/two/two.Annotation`, authored from the recorded facts
- **WHEN** `read_annotation` runs
- **THEN** it returns the two entries of the file, and writing the read value gives the same bytes
