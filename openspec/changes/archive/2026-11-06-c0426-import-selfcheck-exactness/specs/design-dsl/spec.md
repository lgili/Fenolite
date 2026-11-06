## ADDED Requirements

### Requirement: Via without a ring in a copper table
`Design.via_table` SHALL accept a `drill` equal to its `diameter` (change c0426): a via without a ring, which a
source document can hold and which `fenolite import --to python` writes as it reads it. A `drill` larger than the
`diameter` MUST raise `DslError` at the call, naming the table key and both sizes in nanometres.

#### Scenario: Equal and larger drills
- **GIVEN** a design with a net `GND`
- **WHEN** `d.via_table("V/0", net=gnd, diameter=mm("0.3"), drill=mm("0.3"), rows_nm=((0, 0),))` is called, then `d.via_table("V/1", net=gnd, diameter=mm("0.3"), drill=mm("0.4"), rows_nm=((0, 0),))`
- **THEN** the first records one via table, and the second raises `DslError` with "the drill 400000 nm is larger than the diameter 300000 nm"
