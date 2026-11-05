## ADDED Requirements

### Requirement: Explicit local adapters
External candidates SHALL require --propose-with and a locally available supported router. The command MUST NOT download tools, upload designs or silently accept returned copper.

#### Scenario: Explicit local adapters contract
- **GIVEN** a requested router is absent
- **WHEN** proposals request that router
- **THEN** the existing external-tool-missing contract is returned without changing files

### Requirement: Verified scoped delta
External output SHALL preserve existing geometry, rules and unselected nets. Only validated new scoped copper may become candidates; unsupported pairs/groups MUST be refused atomically.

#### Scenario: Verified scoped delta contract
- **GIVEN** external output moves an existing pad or routes an unselected net
- **WHEN** the delta is inspected
- **THEN** the output is rejected rather than partially imported

### Requirement: One subprocess budget
All external candidate processes SHALL share the job timeout and cancellation. Killed, incomplete or malformed output MUST NOT become candidates or project writes.

#### Scenario: One subprocess budget contract
- **GIVEN** an adapter has written a partial result
- **WHEN** the shared budget expires
- **THEN** the process tree is stopped and the partial result is discarded

