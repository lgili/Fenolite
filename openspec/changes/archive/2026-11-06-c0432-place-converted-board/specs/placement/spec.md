## ADDED Requirements

### Requirement: Findings the move did not make
`fenolite place` SHALL judge the layout of the board before the moves with the same legality check. A
finding of the layout after the moves that the board before has with the same code, `where` and message,
and whose `where` names no moved part, MUST be reported as `place.existing` (warning) and MUST NOT refuse
the write; every other finding is reported with its own code and severity.

#### Scenario: An overlap left where it was
- **GIVEN** a board whose parts D1 and R1 overlap, and a legal move of another part
- **WHEN** `fenolite place --move` moves that part
- **THEN** the overlap of D1 and R1 is `place.existing`, the command exits 0, and the board is planned

#### Scenario: A finding the move makes
- **GIVEN** the same board
- **WHEN** the part is moved onto a third part
- **THEN** that overlap is `place.courtyard-overlap` (error) and nothing is planned without `--force`

### Requirement: Locked parts of a converted board
`place.locked` SHALL hint that a board converted or imported keeps each part's lock and that `--force`
moves the part.

#### Scenario: A locked part
- **GIVEN** a locked part
- **WHEN** it is moved without `--force`
- **THEN** `place.locked` names it, and its hint names `--force` and the kept lock
