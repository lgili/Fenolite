## ADDED Requirements

### Requirement: Draftsman facts come first
Every element, member and value that the Draftsman reader or writer relies on SHALL be a row of `docs/formats/altium/draftsman.md` with a registered source and an evidence label before the code that uses it. No fact MAY come from decompiled Altium code, its installed assemblies or a third-party parser, and no file that Altium saved MAY be committed.

#### Scenario: Rows carry sources and labels
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py -q` runs
- **THEN** every row of `docs/formats/altium/draftsman.md` names a registered source and a label, and the family `H-A-DWF-*` is accepted on that page

### Requirement: Draftsman document read
`read_draftsman(data) -> DraftsmanFile` SHALL split a `.PCBDwf` into its header and its decoded XML tree, and `summary(file)` SHALL list its sheets, views, tables, notes and parameters. Data that is not such a document MUST raise `DraftsmanError` naming the offset where reading stopped.

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
`draftsman.NATIVE_WRITE` SHALL be `False` until the maintainer's probes FP1 to FP4 of Part F are recorded as passed in `docs/evidence/altium-draftsman.md`. While it is false, no build MUST plan a `.PCBDwf`.

#### Scenario: Gate follows the report
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** it passes only when `NATIVE_WRITE` is false or Part F records FP1 to FP4 as passed

### Requirement: Fabrication sheet of a Draftsman document
The first sheet SHALL hold a Drill Drawing View (top, Top–Bottom pair), a Drill Table, a Layer Stack Legend when the board has a stack-up, a Table of c0117's board rows, a Note of `[fab].notes` when it has any, and the title-block Texts, placed by c0117's `place` at 1:1 on the paper `choose_paper` gives.

#### Scenario: Fabrication sheet of the routed blink
- **GIVEN** the routed blink and a drawing specification with two `[fab]` notes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_draftsman.py -k fab` builds its spec
- **THEN** sheet 1 has the title `Fabrication drawing`, one drill drawing view, one drill table, one layer stack legend, one table, one note of two entries, and no two objects overlap by the estimated sizes

### Requirement: Assembly sheets of a Draftsman document
The document SHALL hold one assembly sheet per side of `[assembly].sides` that has parts, each with a Board Assembly View of that side with designator captions, a Bill Of Materials table filtered to that view, the title-block Texts, and on the top sheet a Note of `[assembly].notes`. A do-not-populate part MUST give one `altium.not-lowered` info naming it.

#### Scenario: No part on the bottom
- **GIVEN** the routed blink, whose parts are all on the top
- **WHEN** its Draftsman spec is built with the default drawing specification
- **THEN** the document has two sheets, the second holds a top assembly view and a BOM table, and no bottom sheet exists
