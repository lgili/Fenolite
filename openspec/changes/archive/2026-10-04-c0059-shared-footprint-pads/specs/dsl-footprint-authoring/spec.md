## ADDED Requirements

### Requirement: Author repeated physical pads for one terminal

`Footprint.pad(number, ..., shared=False)` SHALL keep pad numbers unique by default. A caller MAY declare a subsequent physical pad with a number already present only by passing `shared=True`. Passing `shared=True` without an earlier pad of that number MUST raise `DslError`. All physical pads with the same number SHALL remain separate pads and receive the electrical net of that footprint pad number during build resolution. Their generated entity IDs MUST be unique and deterministic; existing IDs of footprints with unique pad numbers MUST remain unchanged.

#### Scenario: Two physical lands share a symbol terminal

- **GIVEN** a footprint with pad `2` and a second pad `2` declared with `shared=True`
- **WHEN** the footprint is built for a part whose symbol pin `2` is on net `GND`
- **THEN** both physical pads numbered `2` carry net `GND` and have distinct stable IDs

#### Scenario: Accidental duplicate remains an error

- **GIVEN** a footprint that declares pad `2` twice without `shared=True`
- **WHEN** the second pad is declared
- **THEN** `DslError` reports the duplicate pad number

#### Scenario: Shared flag requires a prior pad

- **GIVEN** a footprint with no pad `2`
- **WHEN** pad `2` is declared with `shared=True`
- **THEN** `DslError` reports that there is no earlier pad to share
