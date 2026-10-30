## ADDED Requirements

### Requirement: Copy mode in build
Without `--copper-check`, `fenolite build SCRIPT` SHALL run its copper guard in `warn` when the `PROVENANCE.json` beside `SCRIPT` marks a copy (`board-to-code`, "Import record marks a copy"), and in `refuse` otherwise; `result.copper_check.mode_source` MUST be `option`, `copy` or `default`.

#### Scenario: Imported folder builds
- **GIVEN** a copy of an authored example whose built board holds a short the guard refuses, and an import record beside its script
- **WHEN** `uv run pytest tests/unit/cli/test_build_copy_mode.py` runs `fenolite build` without `--copper-check`
- **THEN** the build plans its files, `result.copper_check.mode` is `warn`, `mode_source` is `copy`, and the short is a warning; with `"copy": false` it is refused
