## ADDED Requirements

### Requirement: Recorded operation reports in view

`fenolite view PATH --report FILE` SHALL accept a recorded convert or export reply, MAY be repeated for different commands, and SHALL expose the reports' scope and limitations in JSON, live viewing and offline HTML. Duplicate command reports or malformed envelopes SHALL be refused before an output write. Loading a report SHALL NOT run the recorded command. Existing dry-run and confirmed staged replay SHALL govern HTML output.

#### Scenario: Recorded conversion and export
- **WHEN** view receives one valid convert report and one valid export report
- **THEN** both are available in project review with original evidence, revision binding and limitations
- **AND** absent verification or receipt information cannot create a passed card

#### Scenario: Invalid or duplicate report
- **WHEN** a report file is missing, malformed, unsupported or duplicates another report's command
- **THEN** view returns an existing input/usage error and plans no output
