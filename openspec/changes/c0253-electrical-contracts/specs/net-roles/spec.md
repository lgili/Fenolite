## ADDED Requirements

### Requirement: Role rows in the requirement table
The judge of `fenolite.roles` SHALL give one `RequirementRow` (`fenolite.core.requirement_table`) per role measure that it judges against a limit, in the `summary.requirements` of `roles.rules` and in `result.requirements` of `fenolite roles --check`. The role findings, their messages (`key=value (origin)`), their severities and the role profile MUST NOT change.

#### Scenario: The bad buck's rows
- **GIVEN** the `bad` variant of `examples/roles/buck_shunt` with its roles confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_table.py` runs `fenolite roles <board> --check --json`
- **THEN** `result.requirements` holds a row whose `id` starts with `roles.loop-area:` and names the hot loop, with status `fail`, and the issues equal those of the same command before this change

### Requirement: Sources of role rows
In a role row:
- a limit of origin `profile` SHALL have source `policy`, with a basis naming its key and its `S-` or `H-G-ROLE-` id;
- a limit of origin `override` SHALL have source `user`, with basis `role_limits`;
- a limit of origin `requirements` SHALL have source `user`, with the row's `source` text or `requirements.toml` as basis;
- a role's `milliamps` or `working_mv` used as a value SHALL have source `role`.

#### Scenario: Profile and override sources
- **GIVEN** the `bad` variant of `examples/roles/buck_shunt` with its roles confirmed, once as is and once with `design.role_limits(loop_max="60mm2")`
- **WHEN** `uv run pytest tests/unit/roles/test_table.py -k sources` runs the check on both
- **THEN** the hot loop's row has limit source `policy` with a basis naming `loop_ratio_max` and `H-G-ROLE-LOOP-RATIO` in the first, and in the second the hot loop's row for `loop_max` has limit source `user` with basis `role_limits`
