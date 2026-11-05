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
`draftsman.NATIVE_WRITE` SHALL be `False` until the maintainer's probes FP1 to FP4 of Part F are recorded as passed in `docs/evidence/altium-draftsman.md`. While it is false, no build MUST plan a `.PCBDwf`. Gate G2 failed on 2026-11-04 (Altium Designer 24.5.2.23 refused the minimal document FP3 and the shell FP4, S-1575 and S-1581). It failed again after the correction round of change c0388 (round FPC, S-1606): the shell's view stays empty after Import Changes. So the gate stays shut, and route P ships.

#### Scenario: Gate follows the report
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** it passes only when `NATIVE_WRITE` is false or Part F records FP1 to FP4 as passed

#### Scenario: Gate G2 failed
- **GIVEN** Part F records FP3 and FP4 as refused by Altium Designer 24.5.2.23 on 2026-11-04, and round FPC records the shell's view as empty after Import Changes
- **WHEN** the routed blink is built with `--target altium --altium-draftsman on --drawing-spec FILE --dry-run --json`
- **THEN** `draftsman.NATIVE_WRITE` is `False`, no `.PCBDwf` is planned, and `issues` holds `altium.draftsman-not-written` naming route P

### Requirement: Draftsman native document correction round
One correction round SHALL be run on the native document: FP3 and FP4 corrected from the members that every saved document of round F0 holds and the candidates lack, and FP5 tried through a document template registered in Altium's Preferences. Gate G2 SHALL be decided again from that round's report only; without a passing probe the native document stays unshipped and route P is decided.

Amended on 2026-11-05 by the coordinator: the writer's views, tables and dimensions MAY be written before that report, under three conditions. While `draftsman.NATIVE_WRITE` is `False`, no output of them SHALL reach a user: no command, build or export writes a `.PCBDwf` or `.DwfDot` from them, and only unit tests and kits built for a maintainer's run read them. They SHALL be judged only by unit tests against the member rows of round F0 (`docs/formats/altium/draftsman.md`, S-1421), which judge member names and order, never Altium's acceptance. The correction round still decides the probes, and its result MAY force this code to be reworked or removed. Task 6.3, which sets `NATIVE_WRITE` to `True`, still needs FP1 to FP4 to pass.

#### Scenario: Writer content behind the closed gate
- **GIVEN** gate G2 failed on 2026-11-04 (c0172, S-1575 and S-1581) and the correction round has not reported
- **WHEN** the writer holds views, tables and dimensions
- **THEN** `draftsman.NATIVE_WRITE` is `False`, no command writes a Draftsman document, and each written item holds the members of its round F0 row in that row's order

#### Scenario: The correction round still decides
- **GIVEN** the correction round's report is recorded
- **WHEN** no probe of it opens, or an opening probe needs other members or values
- **THEN** route P is decided, or the writer's items are reworked to the probe that opened, before task 6.3 may set the gate

#### Scenario: Gate stays shut without a report
- **GIVEN** no report of the correction round is recorded in `docs/evidence/altium-draftsman.md`
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** it passes only while `draftsman.NATIVE_WRITE` is `False`

### Requirement: Fabrication sheet of a Draftsman document
The first sheet SHALL hold a Drill Drawing View (top, Top–Bottom pair), a Drill Table, a Layer Stack Legend when the board has a stack-up, a Table of c0117's board rows, a Note of `[fab].notes` when it has any, and the title-block Texts, placed by c0117's `place` at 1:1 on the paper `choose_paper` gives.

#### Scenario: Fabrication sheet of the routed blink
- **GIVEN** the routed blink and a drawing specification with two `[fab]` notes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_draftsman.py -k fab` builds its spec
- **THEN** sheet 1 has the title `Fabrication drawing`, one drill drawing view, one drill table, one layer stack legend, one table, one note of two entries, and no two objects overlap by the estimated sizes

### Requirement: Assembly sheets of a Draftsman document
The document SHALL hold one assembly sheet per side of `[assembly].sides` that has parts, each with a Board Assembly View of that side with designator captions, a Bill Of Materials table filtered to that view, the title-block Texts, and on the top sheet a Note of `[assembly].notes`. A do-not-populate part MUST give one `altium.not-lowered` info naming it.

#### Scenario: No part on the bottom
- **GIVEN** the routed blink with `D1` placed on the top, so that every part is on the top
- **WHEN** its Draftsman spec is built with the default drawing specification
- **THEN** the document has two sheets, the second holds a top assembly view and a BOM table, and no bottom sheet exists

### Requirement: Draftsman route P
Gate G2 failed after the correction round (round FPC, S-1606: the minimal document opens, but Import Changes leaves a written view empty and the written template gives no board view), so route P of c0172's Decision 9 SHALL ship. While `draftsman.NATIVE_WRITE` is `False`, a build with `--target altium --altium-draftsman on` SHALL write the non-empty title-block fields as `[Parameter<n>]` sections into a project file that it writes, in the order of `title_parameters`. It MUST plan no `.PCBDwf`, MUST list no document and add no `PCBDrawing` output, and MUST leave every other design file with the bytes of a build without the option. `result.draftsman` SHALL be null, and the info `altium.draftsman-not-written` SHALL name route P and say what the project file holds. `docs/altium.md` SHALL give the procedure for a document made from an Altium template.

#### Scenario: Title-block parameters without a document
- **GIVEN** the blink with a title block holding `Title` `Blink` and `Revision` `B`
- **WHEN** it is built for Altium with an output job and `--altium-draftsman on`
- **THEN** `blink.PrjPcb` holds `[Parameter1]` with `Name=Title` and `Value=Blink`, lists the same documents as a build without the option, and is the only design file whose bytes differ; no `.PCBDwf` is planned

#### Scenario: No title-block field
- **GIVEN** a design whose board has no title-block field
- **WHEN** it is built for Altium with `--altium-draftsman on`
- **THEN** every design file holds the bytes of a build without the option, and the info says that there is no field to write

#### Scenario: Kept project file
- **GIVEN** a project file that the build keeps
- **WHEN** the design is built with `--altium-draftsman on`
- **THEN** the project file is not written, and the info says that it is not rewritten

