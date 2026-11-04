## ADDED Requirements

### Requirement: Authored block payload collection boundary
Repository pytest discovery SHALL exclude only the authored self-test payload `tests/data/blocks/lib/tests/test_divider.py`. The actual block runner MUST still execute its functions. Ordinary and neighboring tests MUST remain collectable with bytecode enabled. The data-manifest validator MUST continue rejecting undeclared cache files; no global bytecode suppression may substitute for this proof.

#### Scenario: Normal collection leaves the payload clean
- **GIVEN** the actual repository pytest policy and authored block fixture in an isolated copy
- **WHEN** pytest collects with bytecode enabled
- **THEN** public controls collect and create normal bytecode, while the fixture does neither

#### Scenario: Explicit execution and strict manifest
- **WHEN** the block runner executes the fixture and a failing function is planted
- **THEN** it reports the actual pass/failure, restores bytecode state and creates no fixture cache
- **AND** the unchanged manifest validator rejects a separately injected undeclared bytecode file
