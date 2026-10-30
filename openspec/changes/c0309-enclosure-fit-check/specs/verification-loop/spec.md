## ADDED Requirements

### Requirement: Enclosure fit stage
`fenolite check` SHALL gain the default stage `enclosure.fit` after `placement.rules` and before `roles.rules` in `STAGE_ORDER` and `DOCUMENT_STAGES`, running no tool, reading `.fenolite/enclosure.json` or the record of `--enclosure FILE`. It MUST be skipped with `no-enclosure` without a record and `not-judged` without a judge; `checks` MUST receive the judge injected.

#### Scenario: No record
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages enclosure.fit --json` runs
- **THEN** the stage is `skipped` with reason `no-enclosure`, and the exit code is 0

#### Scenario: A bad fit fails
- **GIVEN** `examples/enclosure/fit_box.py` built in `tmp_path` and then a part moved over boss `B1` on the bottom side
- **WHEN** `uv run pytest tests/unit/checks/test_enclosure_stage.py -k collision` runs `fenolite check <dir> --json`
- **THEN** `result.stages` names `enclosure.fit` after `placement.rules`, the issues hold `enclosure.boss-collision` naming the part and `B1`, and the exit code is 5

#### Scenario: A fake judge
- **GIVEN** a fake `EnclosureJudge` in `tests/unit/checks/fakes.py` returning one `enclosure.web-thin` warning
- **WHEN** `run_checks` runs with it and `stages=("enclosure.fit",)` on a board with a record
- **THEN** the stage has status `ok` and that one issue, and without the judge it is skipped with `not-judged`

### Requirement: Enclosure fit issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL hold `check.enclosure-unreadable` and the fifteen `enclosure.*` codes of the stage with the severities of c0309's `design.md`, "Codes"; `explain.toml` MUST hold a table for each and `docs/cli-contract.md` MUST document each under `check`.

#### Scenario: Codes are keys and explained
- **WHEN** `uv run pytest tests/unit/checks -k codes` and `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py` run, and then `uv run fenolite explain enclosure.too-tall --json`
- **THEN** every `enclosure.*` literal under `src/fenolite/checks/` and `src/fenolite/enclosure/` is a key with its severities, and the command exits 0 with a non-empty `result.fix`
