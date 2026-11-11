## ADDED Requirements

### Requirement: Opt-in placement optimization and candidate review
`place --strategy optimize` SHALL read a versioned optimization request and report alternatives,
changed poses, fixed and unplaced components, rule findings, evidence, budgets and fingerprints.
Exploration SHALL have no confirmable plan without an explicit complete candidate. Candidate
review SHALL validate the saved result and current input identities, recheck the exact selected
poses and applicable requirements, and stage that move set only. Unknown or unsupported
mandatory checks and unsafe poses MUST block a confirmable plan. Existing placement strategies
MUST retain their contracts.

#### Scenario: Select a placement to apply
- **GIVEN** an optimization run returned two applicable placements and its result was saved
- **WHEN** the user reviews one candidate by its ID using the saved result
- **THEN** a dry-run plan stages only that exact set of moves, with no board write or new candidate search

#### Scenario: Unknown check or edited result
- **GIVEN** a saved result has poses inconsistent with its ID, or claims mandatory probe success for a blocked pose
- **WHEN** candidate review checks it against the actual inputs and required evidence
- **THEN** the altered identity or failed mandatory check prevents a confirmable plan

### Requirement: Reviewed placement transaction and layout preservation
Confirming an optimization plan SHALL consume only its reviewed staged bytes. A changed board,
rules, request or other consumed dependency MUST invalidate the plan. The write SHALL use
the existing atomic receipt and rollback contract. Applied poses SHALL follow the existing
layout precedence on rebuild.

#### Scenario: Stale placement confirmation
- **GIVEN** a board edit after a candidate was reviewed
- **WHEN** the old plan is confirmed
- **THEN** the write is refused and the later board edit is preserved

#### Scenario: Build after optimization
- **GIVEN** a candidate was explicitly reviewed and applied to a generated project
- **WHEN** it is rebuilt with the same source and effective layout rules
- **THEN** the accepted positions persist and script locks still have their original precedence

### Requirement: Altium exploration and converted application
The placement CLI SHALL support read-only proposals on a `.PcbDoc` or a `.PrjPcb` with one
readable PCB. The reviewed application workflow for Altium SHALL use a separate KiCad
working copy and a new Altium output. Native source write gates SHALL remain in effect.

#### Scenario: Review placement for an Altium board
- **GIVEN** an Altium board and an applicable placement request
- **WHEN** a proposal is made on the original or placement is reviewed on a separately converted copy
- **THEN** the original Altium inputs retain their bytes and the separately exported board can be read back
