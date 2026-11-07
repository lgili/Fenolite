## ADDED Requirements

### Requirement: Explicit board workflow
Documentation SHALL distinguish development phase order from board execution order: roles, critical routes, power copper, proposal review, optional tidy, fill, checks and export. Ordinary routes MUST remain explicitly accepted.

#### Scenario: Explicit board workflow contract
- **GIVEN** an engineer follows the completion recipe
- **WHEN** critical routes and power copper are prepared
- **THEN** remaining routes are proposed for review rather than silently committed

### Requirement: Truthful completion
Completion SHALL require post-fill connectivity and declared checks, exposing opens, rejections, unattempted subjects and unknown checks separately. Oracle limitations MUST remain visible and MUST NOT be counted as successful checks.

#### Scenario: Truthful completion contract
- **GIVEN** all candidates were rejected but physical opens remain
- **WHEN** the completion report is generated
- **THEN** the board is reported incomplete with those opens

### Requirement: Preserved output and scale evidence
Acceptance tests SHALL prove preserved locks/manual edits, scoped tidy, repeatability, interruption safety and KiCad-to-Altium readback on authored fixtures. Performance claims MUST identify inputs, bounds, versions and measured evidence.

#### Scenario: Preserved output and scale evidence contract
- **GIVEN** a reviewed route is followed by scoped tidy and a second routing pass
- **WHEN** both stages finish or cancel
- **THEN** protected copper is preserved and incomplete stages are reported honestly

