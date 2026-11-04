## ADDED Requirements

### Requirement: Checked native project worksheet resources
A digest-bound declared project SHALL preserve supported portable worksheet resources
as exact transitive inputs and output bytes. Both native page-layout scopes SHALL
remain independent. Every input SHALL be tracked in source provenance and reviewed
plan dependencies. Unsafe, ambiguous, missing or unsupported resources SHALL refuse
without output changes; ambient resource discovery SHALL NOT occur.

#### Scenario: PCB-only worksheet survives import
- **GIVEN** an authored project whose PCB frame names a worksheet and whose schematic frame is empty
- **WHEN** its complete checked inputs are imported and rebuilt
- **THEN** the worksheet bytes and PCB reference survive while the schematic reference stays empty

#### Scenario: A reviewed resource changes
- **WHEN** a worksheet changes after a dry-run plan
- **THEN** confirmation refuses as stale and writes nothing

#### Scenario: An explicit managed frame replaces native resources
- **WHEN** design.sheet explicitly supplies the frame
- **THEN** existing typed precedence remains authoritative without loading obsolete native references
