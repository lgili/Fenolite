## ADDED Requirements

### Requirement: Hard role limits
Search SHALL treat declared electrical exclusions as hard constraints. It MUST NOT exchange a violated user limit for a shorter route or invent a missing high-voltage distance.

#### Scenario: Hard role limits contract
- **GIVEN** a shorter path violates a declared switching clearance
- **WHEN** role-aware search compares it with a legal detour
- **THEN** only the legal detour can become a candidate

### Requirement: Honest ground reference
Reference coverage SHALL be measured from valid current fill geometry. Missing or stale fill SHALL be reported as unknown; it MUST NOT count as proven reference coverage.

#### Scenario: Honest ground reference contract
- **GIVEN** a ground-zone outline whose fill is stale
- **WHEN** candidate facts are measured
- **THEN** coverage is unknown and no ground-reference assurance is emitted

### Requirement: Role provenance
Role fields SHALL use nonnegative integer penalties with provenance, retain final role/copper judgment, and invalidate results on changed inputs. Unconfirmed roles MUST NOT become confirmed through routing.

#### Scenario: Role provenance contract
- **GIVEN** a proposal calculated from a confirmed role profile
- **WHEN** the profile changes before acceptance
- **THEN** the old reviewed write is refused

