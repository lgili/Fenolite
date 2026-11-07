## ADDED Requirements

### Requirement: Drawn style default omission
New optional drawn style fields SHALL be omitted when absent. Old canonical JSON and drawn TOML without them MUST retain exact bytes, ids and ordering. Explicit false and zero MUST remain distinguishable from absence. All existing example build maps MUST pass without rebaselining.

#### Scenario: Legacy drawing
- **GIVEN** a canonical drawing without optional fonts or new sheet-property poses
- **WHEN** it is read, serialized and built
- **THEN** its canonical bytes and existing planned-file digests are unchanged

#### Scenario: Explicit false
- **WHEN** a drawing with explicit false bold is read and written twice
- **THEN** false remains present and both canonical texts are identical
