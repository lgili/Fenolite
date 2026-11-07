## ADDED Requirements

### Requirement: Structured proposal regeneration controls
Octilinear proposal replies SHALL expose structured original generation controls. Decision regeneration SHALL permit the original net, kind, group and candidate-limit selectors. The served viewer MUST validate controls against a closed argument allowlist and root-contained requirements files; it MUST NOT execute proposal command strings.

#### Scenario: Review with original selection
- **GIVEN** a proposal generated with explicit selection and candidate limits
- **WHEN** the served viewer reviews its decision
- **THEN** the validated original selection is regenerated before staging and explicit confirmation consumes staged bytes only

### Requirement: Whole-unit viewer decisions
The viewer SHALL permit complete bundle IDs only when all members, subjects and regeneration metadata are valid. Member candidates and their parent proposal IDs MUST NOT bypass atomic review.

#### Scenario: Reject partial atomic selection
- **GIVEN** a displayed atomic alternative
- **WHEN** a client submits one member or its parent proposal ID
- **THEN** the server refuses without writing files
