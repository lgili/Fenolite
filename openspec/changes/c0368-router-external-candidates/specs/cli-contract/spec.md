## ADDED Requirements

### Requirement: External candidate review
The route command SHALL accept repeatable --propose-with for octilinear proposals and for regenerating their accept/reject decisions. Confirmation MUST consume reviewed staged bytes without running a tool again. Changed declared tool inputs MUST invalidate the plan.

#### Scenario: Review external proposal bytes
- **GIVEN** a supported local adapter generates a scoped candidate
- **WHEN** its acceptance is reviewed and subsequently confirmed
- **THEN** the staged copper is written without rerunning the external process

### Requirement: Candidate adapter discovery
Capabilities router entries SHALL add external_candidates metadata, null for unsupported adapters, describing supported local scope and availability. Availability SHALL be null when tools were not queried.

#### Scenario: Discover without running tools
- **GIVEN** capabilities is requested with --no-tools
- **WHEN** candidate adapters are described
- **THEN** no process starts and their availability remains unknown

### Requirement: External candidate provenance
External candidate rows and their acceptance rows SHALL report tool router/version, tool-input and job fingerprints and an honest determinism declaration.

#### Scenario: Tool identity remains reviewable
- **GIVEN** an external candidate is proposed
- **WHEN** its facts are read
- **THEN** tool-byte and job fingerprints are visible and no deterministic-tool guarantee is invented

#### Scenario: Regenerate the explicit candidate limit
- **GIVEN** external proposals used an explicit --candidates limit for internal shapes
- **WHEN** their generated acceptance command is run
- **THEN** that limit is permitted and repeated, while external adapters add their own alternatives separately
