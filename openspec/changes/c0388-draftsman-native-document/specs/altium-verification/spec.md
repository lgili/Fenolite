## ADDED Requirements

### Requirement: Draftsman scope round trip
RT-D1 SHALL compare the written scope of a built Draftsman document with its read-back, and RT-D2 SHALL compare it with a document that Altium saved after Import Changes: the same sheets, views, tables and notes. A difference MUST be a finding naming the sheet and the object.

#### Scenario: Altium's re-save
- **GIVEN** the document saved by the maintainer in case F8
- **WHEN** `FENOLITE_ALTIUM_F8=<file> uv run pytest tests/unit/backends/altium/test_part_f.py -k f8` runs
- **THEN** it passes when every written sheet, view, table and note is found, and names each one that is missing
