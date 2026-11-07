## ADDED Requirements

### Requirement: Protected geometry
Negotiation SHALL reroute only its own provisional routes. Manual or locked copper, accepted decisions and role corridors MUST remain immutable. Unsupported coupled subjects SHALL be refused as units.

#### Scenario: Protected geometry contract
- **GIVEN** an existing locked route blocks a corridor
- **WHEN** negotiation retries selected connections
- **THEN** the locked route is unchanged even if no solution exists

### Requirement: Atomic alternatives
Coupled reroutes SHALL be emitted and accepted as a jointly validated bundle. Accept, reject, replay and forget SHALL be atomic; an individual coupled member MUST NOT be accepted alone.

#### Scenario: Atomic alternatives contract
- **GIVEN** a bundle changes two mutually dependent paths
- **WHEN** one member alone is accepted
- **THEN** the request is refused and no project or decision bytes change

### Requirement: Bounded negotiation
Negotiation SHALL bound rounds and expanded states under the shared job budget. Provisional overlaps MUST NOT escape as candidates; exhaustion SHALL report unresolved subjects and keep prior copper unchanged.

#### Scenario: Bounded negotiation contract
- **GIVEN** all rounds end with provisional overlap
- **WHEN** the round budget expires
- **THEN** no invalid candidate is emitted and unresolved subjects are reported

