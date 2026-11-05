## ADDED Requirements

### Requirement: Draftsman drawing preparation imports
`lens.altium_draftsman` MAY import only `exports.drawing_spec`, `drawing_layout` and `drawing_tables` for pure preparation; `lens.altium` MAY import `drawing_spec` for its value/default. The general lens import row MUST stay unchanged. Altium backends MUST NOT import exports, and no lens exception MAY admit plotting or export runners.

#### Scenario: Preparation stays pure and bounded
- **WHEN** the import guard and candidate packing tests run
- **THEN** only those exact module edges are accepted, `exports.drawings` remains forbidden, and packing starts no subprocess
