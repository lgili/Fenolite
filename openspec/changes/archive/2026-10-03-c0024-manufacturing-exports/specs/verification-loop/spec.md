## ADDED Requirements

### Requirement: Render stage
`fenolite.checks.render.render_stage(plotter, project) -> StageResult` SHALL be the stage `render`, last in `STAGE_ORDER`, and SHALL say whether the board plots.
- The stage MUST be opt-in: it runs only when `--stages` names it, and the default stage set MUST NOT hold it.
- `run_checks` MUST take `plotter: Plotter | None = None` and MUST call `plotter.plot(project)` at most once.
- The stage MUST report `render.failed` (warning; `where` = the view name) for each view the plotter could not produce, and MUST NOT report an error. Its status MUST be `ok` whenever it ran.
- `summary` MUST hold `tool_version` and `views` (`name`, `bytes`, `sha256`; sorted by name).
- Stage evidence MUST be `PlotOutcome.evidence`.
- The stage MUST write nothing: `check` stays read-only.
- A refused board read MUST skip the stage with reason `read-refused`, and a missing tool MUST follow the pre-flight of `drc.kicad`.
- `checks.codes.ISSUE_CODES` MUST gain `render.failed` (warning).

#### Scenario: Opt-in
- **WHEN** `uv run pytest tests/unit/checks/test_render_stage.py -k default` runs `run_checks` without `stages`
- **THEN** the report holds no `render` stage and the fake plotter was not called

#### Scenario: Views in the summary
- **GIVEN** a fake `Plotter` that gives four views
- **WHEN** `run_checks` runs with `stages=("render",)`
- **THEN** the stage is `ok`, `summary.views` holds four entries sorted by name, and no file was written

#### Scenario: A failed view never fails the check
- **GIVEN** a fake `Plotter` that gives two views and names two failures
- **WHEN** `fenolite check <board> --stages render` runs
- **THEN** the exit code is 0, and the issues hold two `render.failed` warnings

#### Scenario: Stage order
- **WHEN** `STAGE_ORDER` is read
- **THEN** `render` is its last entry
