# altium-draftsman Specification

## Purpose
TBD - created by archiving change c0172-altium-draftsman. Update Purpose after archive.
## Requirements
### Requirement: Draftsman facts come first
Every element, member and value that the Draftsman reader or writer relies on SHALL be a row of `docs/formats/altium/draftsman.md` with a registered source and an evidence label before the code that uses it. No fact MAY come from decompiled Altium code, its installed assemblies or a third-party parser, and no file that Altium saved MAY be committed.

#### Scenario: Rows carry sources and labels
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py -q` runs
- **THEN** every row of `docs/formats/altium/draftsman.md` names a registered source and a label, and the family `H-A-DWF-*` is accepted on that page

### Requirement: Draftsman document read
`read_draftsman(data) -> DraftsmanFile` SHALL split a `.PCBDwf` into its chunks and its decoded XML tree, and `summary(file)` SHALL list its sheets, views, tables, notes and parameters. Data that is not such a document MUST raise `DraftsmanError` naming the offset where reading stopped.

#### Scenario: Public samples decode
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py` runs with the corpus cached
- **THEN** the four rows `altium-third-party-pcbdwf-01` to `-04` decode into well-formed XML of the namespace `http://schemas.datacontract.org/2004/07/Altium.Designer.PcbDrawing.DataSerialization.V1`, and each summary has at least one sheet

#### Scenario: Not a document
- **WHEN** `read_draftsman` reads the bytes of a `.PcbDoc`
- **THEN** it raises `DraftsmanError`

### Requirement: Draftsman document written
`write_draftsman(spec) -> bytes` SHALL write a `DraftsmanSpec` in the container form that the reader decodes, with only the members that fact rows name, in data-contract order, and no date or random value. `written_scope` of the read-back MUST equal the spec's scope.

#### Scenario: Written document reads back
- **WHEN** `uv run pytest tests/unit/backends/altium/test_draftsman_write.py -k readback` writes the spec of the routed blink twice
- **THEN** both writes have equal bytes, and `written_scope` of the read document equals the spec's sheets, views, tables, notes and parameter texts

### Requirement: Draftsman write gate
`draftsman.NATIVE_WRITE` SHALL be `False` until the maintainer's probes FP1 to FP4 of Part F are recorded as passed in `docs/evidence/altium-draftsman.md`. While it is false, no build MUST plan a `.PCBDwf`. Gate G2 failed on 2026-11-04 (Altium Designer 24.5.2.23 refused the minimal document FP3 and the shell FP4, S-1575 and S-1581), so this change ships with the gate shut; opening it is change c0388's work.

#### Scenario: Gate follows the report
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** it passes only when `NATIVE_WRITE` is false or Part F records FP1 to FP4 as passed

#### Scenario: Gate G2 failed
- **GIVEN** Part F records FP3 and FP4 as refused by Altium Designer 24.5.2.23 on 2026-11-04
- **WHEN** the routed blink is built with `--target altium --altium-draftsman on --drawing-spec FILE --dry-run --json`
- **THEN** `draftsman.NATIVE_WRITE` is `False`, no `.PCBDwf` is planned, and `issues` holds `altium.draftsman-not-written` naming the gate

