## ADDED Requirements
### Requirement: Preserve approved licence registry entries across repositories
The shipped registry SHALL retain all previously approved text digests and
match the library registry after incorporating documented maintainer approvals.

#### Scenario: Synchronize the reviewed registry union
- **WHEN** both old registries and new text approvals are reconciled
- **THEN** every old approved digest remains allowed
- **AND** the shipped registry equals the library registry without relaxing any other licence rule
