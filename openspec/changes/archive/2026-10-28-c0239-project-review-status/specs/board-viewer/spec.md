## ADDED Requirements

### Requirement: Project review status and finding workflow

The viewer SHALL display explicit not-run, passed, failed and limited states for its available validation categories. It SHALL preserve stage evidence, limits and scope, SHALL NOT interpret absent or skipped checks as passes, and SHALL NOT declare fabrication readiness from artifact generation. A report without a matching input hash for the current document SHALL NOT establish a current passed state.

#### Scenario: No check was supplied
- **WHEN** a user opens an ordinary document
- **THEN** reading is reported for the current scene and validation categories say not run
- **AND** the panel explains how to supply check results without running checks on opening

#### Scenario: Limited and failed checks
- **WHEN** stages include skipped results, warnings, capped counts, unknown statuses, incomplete category coverage or insufficient scope
- **THEN** the affected card is limited and exposes the reason and original evidence
- **AND** reported errors remain failed, while every missing category stays not run

#### Scenario: Review a finding
- **WHEN** a user filters findings and moves through matching results
- **THEN** each result retains its original message, code, severity, stage, evidence, location and hint
- **AND** Locate uses the existing geometry marker or states that no location exists
- **AND** reviewing an item never records that the underlying error was corrected

#### Scenario: Document changed after a check
- **WHEN** a saved report is attached to a different current input hash, including after a live save
- **THEN** previously passing report cards are limited and the revision mismatch is visible
- **AND** old findings remain identifiable as historical report data

#### Scenario: Review on keyboard and narrow screens
- **WHEN** review is opened with native controls by keyboard or on a narrow viewport
- **THEN** the panel can be navigated, filtered and closed, and Locate makes the drawing available
- **AND** ordinary document selection remains consistent with asynchronous navigation guards
