## ADDED Requirements

### Requirement: A lossy refusal lists what is lost
`FEN-7001` from a conversion SHALL say, per kind it would lose, the count, the count per reason, and up to
three examples with their layer. Each `convert.lossy` issue SHALL hold `count`, `reasons` and `examples` in
its detail. The numbers MUST be those that the report of the same conversion with `--allow-lossy` gives
(change c0495).

#### Scenario: Drawings on layers KiCad lacks
- **GIVEN** an authored PCB document with lines on a mechanical layer that has no KiCad layer and one
  dimension
- **WHEN** `fenolite convert <doc> --to kicad` runs without `--allow-lossy`
- **THEN** it exits 7, and the message names the kind, its count and each reason with its count
- **AND** the run with `--allow-lossy` reports the same counts in `result.report`
