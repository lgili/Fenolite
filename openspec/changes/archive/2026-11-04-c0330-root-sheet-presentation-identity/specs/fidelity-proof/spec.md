## ADDED Requirements

### Requirement: Explicit project-root presentation identity
Presentation comparison SHALL pair explicitly resolved project-root sheets despite a safe filename change. It MUST retain every primitive and child identity, refuse ambiguous collisions and preserve existing tolerances. It SHALL NOT infer root identity from filename sorting or suppress missing panels.

#### Scenario: A safely renamed root
- **GIVEN** equivalent original and rebuilt root sheets with different safe filenames
- **WHEN** the complete fidelity proof compares presentation
- **THEN** the two explicit roots are compared as one panel without accepting differences
- **AND** a planted visible loss still fails presentation

#### Scenario: A child collides with a root spelling
- **WHEN** pairing a renamed root would overwrite a distinct child panel
- **THEN** the comparison refuses explicitly rather than dropping either panel
