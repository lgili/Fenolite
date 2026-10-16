## ADDED Requirements

### Requirement: Edge clearance explanation
Each `copper.edge-clearance` finding SHALL carry an immutable `EdgeClearanceExplanation`: the copper item's subject, the ring's name, the candidate rows (each matching `edge_clearance` rule with id, priority, selector, layers, value and severity, then the board minimum), the backend switch and the governing limit, built from the resolver's candidates without a second matcher. Metadata MUST NOT change limits, severity, count, order or messages.

#### Scenario: Rule over the board minimum
- **GIVEN** the finding of "A rule for one net"
- **WHEN** its explanation is read
- **THEN** it lists the `HV` rule as governing and the board minimum of 0.5 mm as a candidate, and resolving the explained inputs gives 1 mm
