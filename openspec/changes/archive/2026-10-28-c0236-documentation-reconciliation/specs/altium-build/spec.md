## ADDED Requirements

### Requirement: Model write helper exposes the existing pour mode

`fenolite.lens.altium.write_model` SHALL accept the same optional `pour` mode as the backend write it delegates to. Omitting the option SHALL retain the backend's current default and missing-extra behavior. Explicit `outline` SHALL let callers reproduce historical unpoured measurements without changing the product default or weakening their comparisons.

#### Scenario: Historical model measurement selects outline
- **WHEN** a caller writes the authored routed sample with `write_model(..., pour="outline")`
- **THEN** the written PCB document has no polygon pour regions and the historical triangle's strict piece comparisons remain in force

#### Scenario: The model helper retains computed behavior
- **WHEN** the geo extra is installed and the same sample is written with omitted `pour` or explicit `computed`
- **THEN** both polygon pours are present and the result identifies computed mode
