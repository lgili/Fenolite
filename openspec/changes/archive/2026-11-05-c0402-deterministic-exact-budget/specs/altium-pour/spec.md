## ADDED Requirements

### Requirement: Deterministic work budget of an exact cut
Every bound that decides the outcome of an exact neck cut SHALL count work or storage. The cut SHALL charge
counted work units to one per-operation total and one per-stage total and SHALL refuse with the existing
`GeometryError` when either is used up. The same input SHALL give the same polygons or the same refusal on
every machine and under any load. Wall time SHALL only be a safety net above the caps' measured time; it SHALL
raise `ExactDeadline` (`FEN-1005`, retryable), which is not a `GeometryError`, so the command writes nothing and
no caller turns it into a different result.

#### Scenario: A slowed clock does not change the result
- **GIVEN** a cut whose polygons are known
- **WHEN** it runs again with a clock that advances so that the readings span four times the former 240 s
  deadline, within the safety net
- **THEN** it gives the same polygons and charges the same work

#### Scenario: A work refusal does not depend on the clock
- **GIVEN** a work cap one unit below what a cut needs
- **WHEN** the cut runs with a fast clock and with a slowed clock
- **THEN** both refuse with the same "work budget exceeded" message

#### Scenario: The safety net is retryable
- **WHEN** the clock passes the safety net before the work cap is used up
- **THEN** the cut raises `ExactDeadline`, the command ends in `FEN-1005` with `retryable` true, and nothing is
  written

## MODIFIED Requirements

### Requirement: Existing debris order and certified refusal
The cut SHALL test piece net area before removing small holes. Every removed whole face SHALL have exact/integer eligibility and unique parent/child ownership; a collapsed loop SHALL have zero signed line currents. Uncertified topology, precision or counted resource limits SHALL refuse through existing GeometryError without an approximate fallback. The wall-time safety net SHALL NOT refuse through GeometryError.

#### Scenario: Thin piece owns its hole
- **GIVEN** a simple area-9 outer square and an area-1 hole, with tolerance 3
- **WHEN** debris removal runs
- **THEN** the net area-8 piece disappears with its hole and cannot become a solid area-9 square

#### Scenario: Zero shoelace area is insufficient
- **WHEN** a projected bow tie has zero shoelace area and nonzero signed line currents
- **THEN** it is refused as an uncertified collapse
