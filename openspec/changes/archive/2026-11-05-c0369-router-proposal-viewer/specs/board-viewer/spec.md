## ADDED Requirements

### Requirement: Inspectable alternatives
The viewer SHALL draw candidate tracks, vias, endpoints, layers and facts distinctly from committed copper. It SHALL keep unresolved subjects visible and MUST NOT rank, recommend or preselect acceptance.

#### Scenario: Inspectable alternatives contract
- **GIVEN** a subject has two alternatives and one missing measurement
- **WHEN** the proposal panel opens
- **THEN** both geometries are inspectable and the missing fact reads unknown

### Requirement: Reviewed viewer writes
Served acceptance SHALL preview and confirm the existing reviewed plan, reject stale inputs and apply coupled bundles atomically. Static exports MUST provide no project-writing action.

#### Scenario: Reviewed viewer writes contract
- **GIVEN** a board changes after an acceptance preview
- **WHEN** the user confirms that plan
- **THEN** the write is refused and the prior project is preserved

### Requirement: Safe accessible rendering
Proposal controls SHALL support keyboard inspection and escaped untrusted text. Unknown candidate families SHALL degrade to generic inspection without arbitrary action dispatch.

#### Scenario: Safe accessible rendering contract
- **GIVEN** a tool reason contains HTML and the source family is unfamiliar
- **WHEN** the scene is opened
- **THEN** text is displayed safely and geometry remains inspectable

