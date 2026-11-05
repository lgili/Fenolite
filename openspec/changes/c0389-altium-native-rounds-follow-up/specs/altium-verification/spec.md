## ADDED Requirements

### Requirement: Altium native rounds follow-up keeps unmet criteria open
The Altium native rounds follow-up SHALL keep a moved task open until a recorded Altium run meets that task's
proof criteria as written. An agent run counts only under the maintainer's delegation of 2026-11-04 and only
when its criteria pass. A failed case SHALL stay recorded as a result, and no level SHALL rise from a failed or
unrun step.

#### Scenario: A moved task whose run failed a criterion
- **GIVEN** a moved task whose recorded run failed one of its criteria
- **WHEN** the task is reviewed
- **THEN** its box stays open, its blocker names the failed criterion, and no level changes

#### Scenario: A moved task whose run meets its proof
- **GIVEN** a moved task whose recorded run meets every criterion of its proof as written
- **WHEN** the task is reviewed
- **THEN** its box is ticked, and the tick names who ran it and on whose delegation
