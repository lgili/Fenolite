## ADDED Requirements

### Requirement: Portable private block cleanup
The block-test runner MUST restore the caller's working directory before removing
its private temporary tree, on both successful and exceptional exits. It SHALL
retain import, argument, bytecode and random-state isolation and preserve an
authored failure rather than replacing it with a cleanup error.

#### Scenario: Windows-style directory lock
- **GIVEN** a cleanup implementation that rejects deleting the active working directory
- **WHEN** an authored block usage or test finishes
- **THEN** cleanup runs outside that directory and the public runner reports the authored result

#### Scenario: Authored failure
- **WHEN** authored code raises while inside the private working directory
- **THEN** the caller's directory is restored before deletion and the original exception is retained
