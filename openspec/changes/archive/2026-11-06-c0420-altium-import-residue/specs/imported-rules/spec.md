## ADDED Requirements

### Requirement: Rules scoped to items in no net
The Altium scope reader SHALL read `InAnyNet` as the selector of any net (`net *`), so that `Not InAnyNet` is `model.rules.NO_NET` and a scope such as `IsPad And (Not InAnyNet)` maps without a `scope` refusal (change c0420, B7; S-1680). The Altium rule writer SHALL lower `net *` to `InAnyNet`, so a rule scoped to `NO_NET` is written as `Not InAnyNet`.

#### Scenario: A netless pad scope
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_rule.py -k any_net -q` maps a Clearance rule scoped `IsPad And (Not InAnyNet)`
- **THEN** the rule maps with no unmapped record and its first selector is `and(item_kind pad, NO_NET)`

#### Scenario: A netless pad scope written to Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k without_a_net -q` lowers a rule on pads in no net
- **THEN** its scope is written as `IsPad And (Not InAnyNet)` and reads back as the same selector
