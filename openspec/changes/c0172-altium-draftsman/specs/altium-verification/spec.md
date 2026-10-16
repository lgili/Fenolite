## ADDED Requirements

### Requirement: Kit cases for Draftsman documents
`docs/evidence/altium-draftsman.md` SHALL hold Part F: the observation files F0.1 to F0.14, the probes FP1 to FP5 and the cases F1 to F8 of change c0172's design, each with its expected outcome, and the maintainer's reports in the form of the native acceptance inventory. No Draftsman row MUST be `ALTIUM-VERIFIED` before its report is recorded.

#### Scenario: Every case has an outcome to check
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** F0.1 to F0.14, FP1 to FP5 and F1 to F8 each appear with an expected outcome, and no `H-A-DWF-*` row is `ALTIUM-VERIFIED` without a recorded report

### Requirement: Draftsman scope round trip
RT-D1 SHALL compare the written scope of a built Draftsman document with its read-back, and RT-D2 SHALL compare it with a document that Altium saved after Import Changes: the same sheets, views, tables and notes. A difference MUST be a finding naming the sheet and the object.

#### Scenario: Altium's re-save
- **GIVEN** the document saved by the maintainer in case F8
- **WHEN** `FENOLITE_ALTIUM_F8=<file> uv run pytest tests/unit/backends/altium/test_part_f.py -k f8` runs
- **THEN** it passes when every written sheet, view, table and note is found, and names each one that is missing
