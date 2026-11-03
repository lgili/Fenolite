## ADDED Requirements

### Requirement: Block versions in the circuit model
The model `Module` SHALL gain `block_version: str = ""`, the version of the recorded block that made the instance, which MUST be `MAJOR.MINOR.PATCH` when not empty and MUST be empty when `block` is empty. The field MUST be omitted from `circuit.json` when empty, so a circuit file without it loads, validates and is written back with the same bytes.

#### Scenario: Older circuit file
- **GIVEN** a `circuit.json` written by c0251 with a block module and no `block_version`
- **WHEN** it is loaded and written again
- **THEN** the bytes are equal

#### Scenario: Version without a block
- **WHEN** a `Module` with `block == ""` and `block_version == "1.0.0"` is built
- **THEN** `ValueError` is raised naming `block_version`
