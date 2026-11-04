## ADDED Requirements

### Requirement: Bounded variant signature work
Board library derivation SHALL serialize each instance's normalized comparison signature at most once. It MUST preserve footprint variants, names, ordering, native text, issues, nickname filtering and preparation callbacks. This changes no public argument, format or evidence level.

#### Scenario: Many variants and one repeated instance
- **GIVEN** an authored board with twelve differing instances of one footprint and one repeated instance
- **WHEN** library derivation runs for each supported target
- **THEN** it retains the same twelve variants and reference memberships, with no more signature serializations than source instances

#### Scenario: Existing native outputs remain unchanged
- **WHEN** existing derivation and importer vendor regressions run
- **THEN** their native bytes, diagnostics and nickname mappings remain equal to their existing expectations
