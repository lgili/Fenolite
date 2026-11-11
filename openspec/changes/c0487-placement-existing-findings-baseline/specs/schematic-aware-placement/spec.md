## ADDED Requirements

### Requirement: Pre-existing findings are a baseline
The optimizer SHALL check the board before any move with the same checks and rules as its candidates, and
a candidate's hard finding that the board before has, and that the candidate does not make worse, SHALL NOT
reject the candidate (change c0487).
- A courtyard overlap or a `gap` finding between two parts MUST be worse only when the area of the
  intersection of their courtyards on that face grows, or, when they do not intersect, when their distance
  shrinks.
- A copper clearance finding MUST be worse only when its measured gap shrinks.
- Any other pre-existing finding MUST be worse when it names a moved part.
- A finding whose measure cannot be computed MUST be judged as new.
- Each candidate MUST list its baseline findings with their codes, locations and details, apart from its
  hard findings.

#### Scenario: An overlap far from the scope
- **GIVEN** an authored board whose fixed parts D1 and R2 overlap, and a free capacitor C1 elsewhere
- **WHEN** the optimizer is asked to place C1
- **THEN** it returns at least one candidate, and each lists the D1–R2 overlap as a baseline finding

#### Scenario: A move that deepens an old overlap
- **GIVEN** an authored board whose parts R1 and R2 overlap by 0.2 mm, with R1 in the scope
- **WHEN** a candidate pose of R1 overlaps R2 by 0.5 mm
- **THEN** that candidate is rejected with the overlap as a hard finding

#### Scenario: A move that reduces an old overlap
- **GIVEN** the same board
- **WHEN** a candidate pose of R1 overlaps R2 by 0.1 mm
- **THEN** the overlap is a baseline finding of that candidate and does not reject it
