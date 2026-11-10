# Delta for altium-schematic-writer

## ADDED Requirements

### Requirement: Clean-room regression fixture
The harness stream regression fixture SHALL use data authored for Fenolite and SHALL NOT contain
private-project identifiers, data or examples.

#### Scenario: Harness stream owner regression
- **GIVEN** independently authored harness connector, entry, type and line records
- **WHEN** a drawn sheet is built to Altium and read back
- **THEN** the records and their owner indexes satisfy the existing harness-stream requirement.
