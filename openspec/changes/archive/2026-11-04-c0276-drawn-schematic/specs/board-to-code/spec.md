## ADDED Requirements

### Requirement: Active schematic symbols beside native board-only metadata
An import with a unique physical reference and an active matching source schematic symbol MUST retain that symbol as a normal code part while preserving the native PCB `board_only` attribute. The attribute alone MUST NOT erase the drawing. Unmatched, duplicate or invalid physical references MUST retain existing board-only/keyed behavior and strict electrical checks.

#### Scenario: Native flag and actual source symbol
- **WHEN** an authored project has a netted schematic symbol and its PCB footprint carries `board_only`
- **THEN** strict import/build compares all nine levels equal, the symbol survives, the native attribute remains and duplicate/unmatched cases retain their guards

### Requirement: Embedded source aliases
An unqualified embedded `lib_name` alias SHALL be vendored under the namespace of its instance's original library id, using `_Source` only when that id is also unqualified. Its native body and poses MUST survive. Extraction and lowering MUST use the same canonical identity; conflicting bodies under that identity MUST still refuse before staging.

#### Scenario: Local embedded copies
- **WHEN** authored ordinary and power symbols use bare embedded aliases and are strictly imported and built
- **THEN** the project libraries are valid, all nine fidelity levels compare equal, and every original input byte remains unchanged

### Requirement: Source drawings in KiCad project imports
A KiCad project import SHALL emit `schematic.toml` and `load_schematic`, preserving source drawing items, embedded symbol slots, power definitions and instance references. It MUST self-check the written drawing before staging. Conflicting definitions, missing symbols or unsupported poses MUST refuse explicitly. Board-only inputs MUST keep their bytes; source files MUST remain unchanged.

#### Scenario: Drawn project survives import
- **WHEN** an authored project with junctions, buses or repeated sheets is imported, confirmed and built
- **THEN** the source drawing and symbol geometry survive, the drawn connectivity guard runs, and every input byte remains unchanged

#### Scenario: Written connectivity defect
- **GIVEN** the drawn writer is patched to move a connected wire
- **WHEN** an import self-check builds the emitted project
- **THEN** the import reports failure and plans no output writes

#### Scenario: Source symbol conflict
- **GIVEN** two source sheets embed different bodies under one library id
- **WHEN** the project is imported
- **THEN** the import refuses with the conflicting id and source sheet named, before any file is staged
