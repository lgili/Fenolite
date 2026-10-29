## ADDED Requirements

### Requirement: Roles stage
`fenolite check` SHALL gain the default stage `roles.rules`: after `placement.rules` and before `zone.fill` in `STAGE_ORDER`, after `placement.rules` and before `parity` in `DOCUMENT_STAGES`. It MUST run no tool, MUST NOT be in `ORACLE_STAGES`, and MUST be skipped with `no-roles` when the board has no stored or declared role, and with `not-judged` when no judge is passed.

#### Scenario: A board without roles is unchanged
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages roles.rules --json` runs
- **THEN** the stage is `skipped` with the reason `no-roles`, and the exit code is 0

#### Scenario: Confirmed roles are judged
- **GIVEN** the `bad` variant of `buck_shunt` built in `tmp_path`, with its roles confirmed
- **WHEN** `uv run pytest tests/unit/checks/test_roles_stage.py` runs `fenolite check <dir> --json`
- **THEN** `result.stages` names `roles.rules` after `placement.rules`, the issues hold `roles.kelvin-outer` as an error, and the exit code is 5

### Requirement: Roles judge injected into the stage
`checks.roles.roles_stage` SHALL take a `RolesJudge`, a protocol of `checks.roles` that maps the board model, the `.fenolite/` model, the project and the board-frame pads to the judged issues, summary and evidence. `cmd_check` MUST pass `fenolite.roles.judge` to `run_checks` and `run_document_checks`, as it passes the plotter and the fill oracle; `checks` MUST NOT import `roles` or `analysis`.

#### Scenario: A fake judge
- **GIVEN** a fake `RolesJudge` in `tests/unit/checks/fakes.py` that returns one `roles.loop-area` warning
- **WHEN** `uv run pytest tests/unit/checks/test_roles_stage.py -k fake` calls `run_checks` with it and `stages=("roles.rules",)` on a board with a stored role
- **THEN** the stage has status `ok` and that one issue, and without the judge it is skipped with `not-judged`
