## ADDED Requirements

### Requirement: Zone, hole and pad-type selectors written
The KiCad rules writer SHALL write the selector leaves `zone`, `hole` and `pad_type` as the expressions of KiCad's public custom-rule documentation (S-2213). A leaf that has no such expression MUST make that rule a reported loss, never a broader rule.

#### Scenario: A hole-scoped rule round trip
- **GIVEN** a design with a `hole_size` rule scoped `hole 1000001..`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rulemap_leaves_c0462.py -q -n 0` writes its rules file and reads it back
- **THEN** the rule comes back with the same selector
