## ADDED Requirements

### Requirement: Mechanical intent metadata
The model SHALL expose MechanicalIntent with stable key, board frame, integer tolerance, source,
input status (`measured`, `estimated` or `proposed`) and evidence. FootprintInstance.anchor, Hole.intent and Keepout.intent SHALL default
to None, preserving legacy canonical output. Intent MUST NOT change pad nets or create geometry.

#### Scenario: Legacy canonical output
- **GIVEN** a board contains no declared mechanical intent
- **WHEN** its canonical JSON is produced
- **THEN** the new default fields are omitted and existing geometry is unchanged
