# kicad-project Specification

## Purpose
TBD - created by archiving change c0344-kicad-project-sheet-identity. Update Purpose after archive.
## Requirements
### Requirement: Emitted schematic identities own project caches
A build that emits a schematic SHALL bind project root filename/name/UUID and
sheet-identity caches to the actual emitted root and child bytes. It SHALL
preserve all unrelated project keys. A build that skips or omits schematics
SHALL leave those identity caches untouched. No template root UUID or filename
may override the actual generated hierarchy.

#### Scenario: Populated repeat survives project save
- **WHEN** a generated project contains two populated instances of one child
- **THEN** project and root UUID agree and child paths use that UUID with distinct references
- **AND** target9/10 rebuild preserves those identities
- **AND** real native10 GUI save retains the expected electrical partition

#### Scenario: Preserve unrelated and no-schematic state
- **WHEN** a build updates an existing project
- **THEN** unrelated JSON stays unchanged
- **AND** schematic skip/no-emission leaves its sheet identity caches untouched

### Requirement: Proved effective project curve error
KiCad project extraction/writing SHALL preserve explicit supported curve approximation settings. Effective default normalization SHALL require real native missing/default controls on the supported versions. Unsupported target lowering SHALL retain the existing explicit loss policy.

#### Scenario: Nondefault source approximation
- **WHEN** a source project configures0.01mm curve approximation
- **THEN** import and a fresh standalone build retain10000nm, and level6 detects any changed setting

