## ADDED Requirements

### Requirement: Native acceptance inventory
The acceptance report SHALL identify every remaining native request from the
existing evidence pages and SHALL distinguish passed, failed, blocked and pending
steps. A newer dated report SHALL take precedence over a historic pending summary.

#### Scenario: Historic summary predates a result
- **GIVEN** a release summary lists Part G as pending and a later native report records G1-G7 as expected
- **WHEN** the inventory is prepared
- **THEN** Part G is recorded as previously completed and only unmeasured follow-ups remain pending

### Requirement: Measured acceptance and focused repairs
Each executed step SHALL record the source case, date, exact tool version,
expected outcome, observed outcome and evidence scope. A blocked or unexecuted
step SHALL NOT be marked passed. Any product repair SHALL have an explicit
OpenSpec task and focused proof before being included in a commit.

#### Scenario: Native pad inspection passes for one case
- **GIVEN** a four-layer authored padstack is inspected successfully in Altium
- **WHEN** its result is recorded
- **THEN** only that padstack and placement case are approved and connector masks remain unconfirmed

#### Scenario: Converted intentional open pin
- **GIVEN** a KiCad schematic netlist explicitly marks an isolated pin with `+no_connect`
- **WHEN** its schematic is converted to Altium through the own or prepared netlist path
- **THEN** the generated schematic retains the no-connect directive at that pin and emits no net wire for its isolated pseudo-net
- **AND** a marked pin that belongs to an actual multi-pin net remains a validation conflict

#### Scenario: Converted pad copper offset
- **GIVEN** a KiCad pad has a nonzero drill offset that moves its copper from its hole centre
- **WHEN** its board and derived footprint library are converted to Altium
- **THEN** both retain the copper offset in the appropriate rotated frame without changing the source slots or weakening clearance rules

### Requirement: Completion gate
Archival SHALL require the archived change's outstanding tasks and proof commands
to be completed. Commits SHALL contain sanitized results and source changes only;
native runtime files and private project data SHALL remain outside version control.

#### Scenario: Gate fails before archival
- **GIVEN** the full verification suite has unresolved failures
- **WHEN** the acceptance work is reviewed for completion
- **THEN** the failed gate is recorded, the completion task stays open and archival waits for resolution
