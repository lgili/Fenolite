## ADDED Requirements

### Requirement: Net roles in the model
`fenolite.model.rules` SHALL define the frozen value objects `NetRole`, `HotLoop`, `KelvinPair`, `GateLoop`, `RoleLimit` and `RoleSet`, and `RuleSet` SHALL gain `roles: RoleSet | None`, stored in `rules.json` under `roles` only when not empty. Each value MUST be an integer (nm, nm², mA, mV, per-mille) or text. A `rules.json` without the key MUST load with `None` and be written back to the same bytes. No backend lowers roles.

#### Scenario: Roles round trip
- **GIVEN** a design whose `RuleSet.roles` holds a `NetRole("SW", "switch_node", "declared")` and a `HotLoop` of six pads
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded roles equal the originals, and `rules.json` holds them under `roles`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written before this change
- **WHEN** it is loaded, validated against the regenerated schema and written again
- **THEN** `RuleSet.roles` is `None` and the written bytes equal the input

#### Scenario: Refused values
- **WHEN** a `NetRole` with the kind `motor`, a `HotLoop` of two pads and a `RoleSet` with two loops named `buck` are built
- **THEN** each raises `ValueError`
