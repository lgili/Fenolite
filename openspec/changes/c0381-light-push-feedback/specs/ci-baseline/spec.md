## ADDED Requirements

### Requirement: Light working-push feedback
Recognized working pushes MAY exclude measured whole-file long_flow tests from fast and use Linux/Python 3.13. Full validation SHALL retain every test and environment, and SHALL remain required on every PR and integration ref. Test/classification changes MUST force full. The target is 5–10 minutes and MUST be measured.

#### Scenario: Long board flow
- **WHEN** a test file is classified long_flow
- **THEN** fast excludes the entire file and full still collects every original case

#### Scenario: Classification changed
- **WHEN** tests or marker configuration change
- **THEN** the working push selects full

### Requirement: Audited parallel light execution
CI SHALL run the light selection in three whole-file partitions and SHALL require an exact-commit, complete, disjoint receipt audit before ci-fast succeeds.

#### Scenario: Missing light partition
- **WHEN** any light partition is missing or unsuccessful
- **THEN** the light audit and ci-fast SHALL fail
