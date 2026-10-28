## ADDED Requirements

### Requirement: Roles stage
`fenolite check` SHALL gain the default stage `roles.rules` in both pipelines: after `placement.rules` and before `zone.fill` in `STAGE_ORDER`, and after `placement.rules` in `DOCUMENT_STAGES`. It MUST run no tool and MUST NOT be in `ORACLE_STAGES`. It MUST judge the stored, declared and inferred roles as `net-roles` says, and MUST be `skipped` with the reason `no-roles` when the board has no stored or declared role.

#### Scenario: A board without roles is unchanged
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages roles.rules --json` runs
- **THEN** the stage is `skipped` with the reason `no-roles`, and the exit code is 0

#### Scenario: Confirmed roles are judged
- **GIVEN** the `bad` variant of `buck_shunt` built in `tmp_path`, with its roles confirmed
- **WHEN** `uv run pytest tests/unit/checks/test_roles_stage.py` runs `fenolite check <dir> --json`
- **THEN** `result.stages` names `roles.rules` after `placement.rules`, the issues hold `roles.kelvin-outer` as an error, and the exit code is 5
