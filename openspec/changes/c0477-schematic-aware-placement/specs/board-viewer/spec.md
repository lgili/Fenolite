## ADDED Requirements

### Requirement: Inspect and refine placement alternatives
The viewer SHALL show the current and proposed poses, locks, constraint and scope explanations,
and clearly marked estimates and probe outcomes by candidate. It SHALL support component and
pad cross-probe. Static exports MUST allow inspection only. A served refinement SHALL use the
explicitly selected region or components and the current board snapshot.

#### Scenario: Inspect an electrical placement rule
- **GIVEN** two candidates with different decoupler poses and return-path evidence
- **WHEN** the engineer selects the rule and switches candidates
- **THEN** the affected exact pads, pose changes and scoped route evidence update without changing the board

### Requirement: Explicit viewer placement decisions
The served viewer SHALL use the existing reviewed-plan protocol and allowlisted structured
parameters. Candidate inspection MUST NOT stage or confirm a write. Confirming a stale candidate
or plan SHALL be refused without altering the board.

#### Scenario: Lock a manual adjustment and refine a region
- **GIVEN** an engineer moved and fixed an IC after reviewing an earlier placement result
- **WHEN** they request a new refinement for neighboring passives
- **THEN** the new proposal uses the updated fixed pose, and the old result cannot write over it
