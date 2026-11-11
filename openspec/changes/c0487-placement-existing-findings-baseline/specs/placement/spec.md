## MODIFIED Requirements

### Requirement: Findings the move did not make
`fenolite place` SHALL judge the layout of the board before the moves with the same legality check. A
finding of the layout after the moves that the board before has with the same code, `where` and message
MUST be reported as `place.existing` (warning) and MUST NOT refuse the write when its `where` names no moved
part, or when it is a `place.courtyard-overlap` whose area of intersection of the two courtyards is not
larger after the moves than before (change c0487). Every other finding is reported with its own code and
severity. A finding whose overlap area cannot be computed is judged as new.

#### Scenario: An overlap left where it was
- **GIVEN** a board whose parts D1 and R1 overlap, and a legal move of another part
- **WHEN** `fenolite place --move` moves that part
- **THEN** the overlap of D1 and R1 is `place.existing`, the command exits 0, and the board is planned

#### Scenario: A finding the move makes
- **GIVEN** the same board
- **WHEN** the part is moved onto a third part
- **THEN** that overlap is `place.courtyard-overlap` (error) and nothing is planned without `--force`

#### Scenario: A moved part leaves an old overlap smaller
- **GIVEN** the same board
- **WHEN** R1 is moved 0.1 mm away from D1 and they still overlap
- **THEN** the overlap of D1 and R1 is `place.existing`, and the board is planned

#### Scenario: A moved part deepens an old overlap
- **GIVEN** the same board
- **WHEN** R1 is moved 0.1 mm toward D1
- **THEN** the overlap is `place.courtyard-overlap` (error) and nothing is planned without `--force`
