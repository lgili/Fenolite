## ADDED Requirements

### Requirement: Conversions in capabilities
`fenolite capabilities` SHALL list under `result.conversions` one object per registered direction of `fenolite.convert.DIRECTIONS`, sorted by `from` and then `to`, with `from` and `to` (backend names), `targets` (the KiCad majors a KiCad target is written for, else an empty list), `experimental` and `evidence` (`{level, oracle, hypotheses}`). The brief view of `capabilities` MUST name the command `convert` and no direction.

#### Scenario: Directions listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs after this change
- **THEN** `result.conversions` holds `{"from": "kicad", "to": "altium", "experimental": true, ...}` and `{"from": "kicad", "to": "kicad", "targets": [9, 10], "experimental": false, ...}`
