## ADDED Requirements

### Requirement: Opt-in search
The router SHALL preserve pattern routing by default. The search family SHALL propose ordinary connections only. Opt-in search modes MUST NOT propose independent pair legs; other unsupported search subjects SHALL retain supported atomic pattern candidates or an explicit refusal.

#### Scenario: Opt-in search contract
- **GIVEN** an ordinary connection blocked from all fixed patterns
- **WHEN** bounded search is explicitly enabled
- **THEN** a legal detour is proposed and the board bytes remain unchanged

#### Scenario: A half-selected pair stays atomic
- **GIVEN** a named or declared differential pair with only one net selected
- **WHEN** proposals use search=fallback or search=only
- **THEN** no independent-leg candidate is emitted, search-unsupported is reported, and project bytes stay unchanged

### Requirement: Physical legality
Search SHALL check swept geometry, cutouts, exact endpoint attachments and through-via clearance on every traversed copper layer. Missing necessary geometry or rules MUST prevent a candidate.

#### Scenario: Physical legality contract
- **GIVEN** a via whose endpoints are clear but whose barrel intersects inner-layer copper
- **WHEN** search considers that transition
- **THEN** the transition is rejected

### Requirement: Deterministic bounds
Search SHALL use stable integer state ordering, explicit state/via bounds and the job wall-clock budget. Fixed state-limited runs SHALL be byte deterministic; clock-limited runs SHALL report truncation without claiming identical exploration.

#### Scenario: Deterministic bounds contract
- **GIVEN** the same board, options, seed and state bound without clock exhaustion
- **WHEN** search runs twice
- **THEN** candidate bytes and termination facts match

