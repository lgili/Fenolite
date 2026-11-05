## ADDED Requirements

### Requirement: Explicit project curve approximation setting
Board SHALL append optional max_curve_error as positive exact integer nanometres, rejecting booleans and nonintegers. None SHALL preserve legacy defaults and canonical bytes. The setting SHALL describe target-project configuration, not a universal algorithmic guarantee.

#### Scenario: Exact setting survives
- **WHEN** code requests max_curve_error10000nm
- **THEN** canonical/schema/DSL and supported target project read/write preserve that exact setting

#### Scenario: No requested setting
- **WHEN** an authored board omits max_curve_error
- **THEN** existing authored outputs remain byte-identical
